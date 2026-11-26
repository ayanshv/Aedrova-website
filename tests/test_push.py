"""Push notifications reveal who and where, never message text, and clean up dead devices."""

import asyncio
import base64
import json

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.push import FcmSender, PushSender, alert_for, provider_token, service_account

KEY = ec.generate_private_key(ec.SECP256R1())
PEM = KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
NOTE = {
    "id": 7,
    "user_id": "u1",
    "kind": "mention",
    "channel": "c1",
    "message": "m1",
    "parent": None,
    "workspace": "w1",
    "channel_name": "launch",
    "channel_kind": "channel",
    "sender": "Maya",
}


class FakeData:
    def __init__(self, devices):
        self._devices, self.forgotten = devices, []

    def delivery(self, identifier):
        if identifier != 7:
            return None
        return {**NOTE, "devices": list(self._devices), "unseen": 3}

    def forget(self, token):
        self.forgotten.append(token)


def sender(handler, devices):
    data = FakeData(devices)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return PushSender(
        data=data,
        key=PEM,
        key_id="KEY1234567",
        team_id="TEAM123456",
        topic="com.aedrova.desktop",
        client=client,
        clock=lambda: 1_000.0,
    ), data


def b64decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_provider_token_is_a_valid_es256_jwt():
    token = provider_token(PEM, "KEY1234567", "TEAM123456", 1_000)
    header, claims, signature = token.split(".")
    assert json.loads(b64decode(header)) == {"alg": "ES256", "kid": "KEY1234567"}
    assert json.loads(b64decode(claims)) == {"iss": "TEAM123456", "iat": 1000}
    raw = b64decode(signature)
    assert len(raw) == 64
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    KEY.public_key().verify(der, f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


def test_alerts_name_the_person_and_place_but_not_the_message():
    assert alert_for("mention", "Maya", "launch", False) == ("Maya", "Mentioned you in #launch")
    assert alert_for("dm", "Maya", "x", True) == ("Maya", "Sent you a message")
    assert alert_for("channel", "Maya", "launch", False) == ("#launch", "Maya posted a message")
    title, body = alert_for("mention", "A\nB" + "x" * 200, "launch", False)
    assert "\n" not in title and len(title) <= 60 and "#launch" in body


def test_delivery_sends_a_private_alert_to_each_device_with_the_right_host():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)

    push, _ = sender(
        handler,
        [
            {"token": "ab" * 32, "environment": "development"},
            {"token": "cd" * 32, "environment": "production"},
        ],
    )
    assert asyncio.run(push.deliver(7)) == 2
    assert {r.url.host for r in seen} == {"api.sandbox.push.apple.com", "api.push.apple.com"}
    first = seen[0]
    assert first.headers["apns-topic"] == "com.aedrova.desktop"
    assert first.headers["apns-push-type"] == "alert"
    assert first.headers["authorization"].startswith("bearer ")
    body = json.loads(first.content)
    assert body["aps"]["alert"] == {"title": "Maya", "body": "Mentioned you in #launch"}
    assert body["aps"]["badge"] == 3 and body["channel"] == "c1" and body["message"] == "m1"
    assert "text" not in json.dumps(body).lower().replace("context", "")


def test_unregistered_devices_are_forgotten_and_others_still_receive():
    def handler(request):
        if request.url.path.endswith("ab" * 32):
            return httpx.Response(410, json={"reason": "Unregistered"})
        return httpx.Response(200)

    push, data = sender(
        handler,
        [
            {"token": "ab" * 32, "environment": "production"},
            {"token": "cd" * 32, "environment": "production"},
        ],
    )
    assert asyncio.run(push.deliver(7)) == 1
    assert data.forgotten == ["ab" * 32]


def test_an_expired_provider_token_is_renewed_once():
    calls = []

    def handler(request):
        calls.append(request.headers["authorization"])
        if len(calls) == 1:
            return httpx.Response(403, json={"reason": "ExpiredProviderToken"})
        return httpx.Response(200)

    push, _ = sender(handler, [{"token": "ab" * 32, "environment": "production"}])
    assert asyncio.run(push.deliver(7)) == 1 and len(calls) == 2


def test_unknown_notifications_and_missing_configuration_send_nothing():
    push, _ = sender(
        lambda request: httpx.Response(200), [{"token": "ab" * 32, "environment": "production"}]
    )
    assert asyncio.run(push.deliver(99)) == 0
    push.key = ""
    assert not push.configured and asyncio.run(push.deliver(7)) == 0


def app_with_push(tmp_path, **settings):
    config = Config(database=f"sqlite:///{tmp_path}/push.sqlite", **settings)
    return create_app(config)


def test_webhook_is_hidden_until_configured_and_requires_the_shared_secret(tmp_path, monkeypatch):
    delivered = []

    async def deliver(self, identifier):
        delivered.append(identifier)

    monkeypatch.setattr(PushSender, "deliver", deliver)
    with TestClient(app_with_push(tmp_path)) as client:
        assert client.post("/internal/push", json={"notification_id": 7}).status_code == 404
    on = app_with_push(
        tmp_path,
        push_webhook_secret="s" * 40,
        apns_key=PEM,
        apns_key_id="KEY1234567",
        apns_team_id="TEAM123456",
    )
    good = {"Authorization": "Bearer " + "s" * 40}
    with TestClient(on) as client:
        assert client.post("/internal/push", json={"notification_id": 7}).status_code == 403
        wrong = {"Authorization": "Bearer " + "x" * 40}
        assert (
            client.post("/internal/push", json={"notification_id": 7}, headers=wrong).status_code
            == 403
        )
        assert (
            client.post("/internal/push", json={"notification_id": 0}, headers=good).status_code
            == 422
        )
        assert delivered == []
        accepted = client.post("/internal/push", json={"notification_id": 7}, headers=good)
        assert accepted.status_code == 200 and accepted.json() == {"accepted": True}
    assert delivered == [7]


def test_provider_token_accepts_keys_with_lost_line_breaks():
    text = PEM if isinstance(PEM, str) else PEM.decode()
    one_line = text.replace("\n", " ")
    escaped = text.replace("\n", "\\n")
    bare = "".join(line for line in text.splitlines() if not line.startswith("-----"))
    for variant in (text, one_line, escaped, bare):
        token = provider_token(variant, "KEY1234567", "TEAM123456", 1000)
        assert token.count(".") == 2


# -- Android, through Firebase Cloud Messaging --------------------------------------------------

RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PEM = RSA.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
ACCOUNT = {
    "client_email": "push@aedrova-test.iam.gserviceaccount.com",
    "private_key": RSA_PEM,
    "project_id": "aedrova-test",
    "token_uri": "https://oauth2.googleapis.com/token",
}
PHONE = {
    "token": "fcm-token:APA91b_example-0123456789",
    "environment": "production",
    "platform": "android",
}
IPHONE = {"token": "ab" * 32, "environment": "production", "platform": "ios"}


def both(handler, devices, *, fcm=True, apple=True):
    data = FakeData(devices)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return PushSender(
        data=data,
        key=PEM if apple else "",
        key_id="KEY1234567" if apple else "",
        team_id="TEAM123456" if apple else "",
        topic="com.aedrova.desktop",
        client=client,
        clock=lambda: 1_000.0,
        fcm=FcmSender(ACCOUNT, clock=lambda: 1_000.0) if fcm else None,
    ), data


def google(requests, *, status=200, body=None):
    def handler(request):
        requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.token", "expires_in": 3600})
        if request.url.host == "fcm.googleapis.com":
            return httpx.Response(status, json=body or {"name": "projects/x/messages/1"})
        return httpx.Response(200)

    return handler


def test_service_accounts_load_from_json_base64_or_escaped_lines():
    raw = json.dumps(ACCOUNT)
    assert service_account(raw)["project_id"] == "aedrova-test"
    assert service_account(base64.b64encode(raw.encode()).decode())["project_id"] == "aedrova-test"
    escaped = json.dumps({**ACCOUNT, "private_key": RSA_PEM.replace("\n", "\\n")})
    assert "\n" in service_account(escaped)["private_key"]
    for junk in ("", "not json", "{}", json.dumps({"client_email": "x"}), None):
        assert service_account(junk) is None


def test_the_signed_request_to_google_verifies():
    sender_, _ = both(google([]), [PHONE])
    jwt = sender_.fcm.assertion(1_000.0)
    head, claims, signature = jwt.split(".")
    pad = "=" * (-len(claims) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(claims + pad))
    assert decoded["iss"] == ACCOUNT["client_email"]
    assert decoded["scope"].endswith("firebase.messaging")
    assert decoded["exp"] - decoded["iat"] == 3600
    RSA.public_key().verify(
        base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
        f"{head}.{claims}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_an_android_phone_gets_the_name_and_place_but_never_the_message():
    requests = []
    sender_, _ = both(google(requests), [PHONE], apple=False)
    assert asyncio.run(sender_.deliver(7)) == 1
    send = next(r for r in requests if r.url.host == "fcm.googleapis.com")
    assert send.url.path == "/v1/projects/aedrova-test/messages:send"
    assert send.headers["authorization"] == "Bearer ya29.token"
    message = json.loads(send.content)["message"]
    assert message["token"] == PHONE["token"]
    assert message["notification"] == {"title": "Maya", "body": "Mentioned you in #launch"}
    assert message["android"]["notification"]["channel_id"] == "messages"
    assert message["android"]["notification"]["notification_count"] == 3
    assert message["data"] == {"workspace": "w1", "channel": "c1", "message": "m1", "parent": ""}


def test_each_phone_goes_to_its_own_service():
    requests = []
    sender_, _ = both(google(requests), [IPHONE, PHONE])
    assert asyncio.run(sender_.deliver(7)) == 2
    hosts = sorted(r.url.host for r in requests)
    assert "api.push.apple.com" in hosts and "fcm.googleapis.com" in hosts


def test_a_phone_is_skipped_when_its_service_is_not_set_up():
    requests = []
    only_android, _ = both(google(requests), [IPHONE, PHONE], apple=False)
    assert only_android.configured
    assert asyncio.run(only_android.deliver(7)) == 1
    requests.clear()
    only_apple, _ = both(google(requests), [IPHONE, PHONE], fcm=False)
    assert asyncio.run(only_apple.deliver(7)) == 1
    assert all(r.url.host != "fcm.googleapis.com" for r in requests)
    neither, _ = both(google([]), [PHONE], apple=False, fcm=False)
    assert not neither.configured
    assert asyncio.run(neither.deliver(7)) == 0


def test_an_unregistered_android_device_is_forgotten():
    requests = []
    handler = google(
        requests,
        status=404,
        body={
            "error": {
                "code": 404,
                "status": "NOT_FOUND",
                "details": [{"errorCode": "UNREGISTERED"}],
            }
        },
    )
    sender_, data = both(handler, [PHONE], apple=False)
    assert asyncio.run(sender_.deliver(7)) == 0
    assert data.forgotten == [PHONE["token"]]


def test_an_expired_google_token_is_renewed_once():
    calls = {"send": 0}

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            token = f"t{calls['send']}"
            return httpx.Response(200, json={"access_token": token, "expires_in": 3600})
        calls["send"] += 1
        return httpx.Response(401 if calls["send"] == 1 else 200, json={})

    sender_, data = both(handler, [PHONE], apple=False)
    assert asyncio.run(sender_.deliver(7)) == 1
    assert calls["send"] == 2 and data.forgotten == []


def test_a_google_outage_does_not_raise():
    def handler(request):
        raise httpx.ConnectError("down")

    sender_, _ = both(handler, [PHONE], apple=False)
    assert asyncio.run(sender_.deliver(7)) == 0
