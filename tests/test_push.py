"""Push notifications reveal who and where, never message text, and clean up dead devices."""

import asyncio
import base64
import json

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.push import PushSender, alert_for, provider_token

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

    def notification(self, identifier):
        return dict(NOTE) if identifier == 7 else None

    def devices(self, user):
        return list(self._devices)

    def unseen(self, user):
        return 3

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
