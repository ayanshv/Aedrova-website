"""Apple and Android push notifications for new chat activity.

The database tells this service that a notification exists, using ids only. The text
sent to a phone names the person and place but never contains the message itself.
"""

import asyncio
import base64
import json
import logging
import re
import time

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from sqlalchemy import text

log = logging.getLogger("aedrova.push")
HOSTS = {
    "production": "https://api.push.apple.com",
    "development": "https://api.sandbox.push.apple.com",
}
# Apple asks providers to reuse a token for 20 to 60 minutes.
TOKEN_LIFETIME = 40 * 60
GONE = {"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"}
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
FCM_TOKEN_URL = "https://oauth2.googleapis.com/token"
FCM_LIFETIME = 50 * 60


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def normalize_pem(value):
    """Rebuilds an Apple .p8 key whose line breaks a settings field lost or escaped."""
    body = re.sub(r"-----[A-Z ]+-----", "", (value or "").replace("\\n", "\n"))
    body = re.sub(r"\s+", "", body)
    lines = [body[i : i + 64] for i in range(0, len(body), 64)]
    fence = "-" * 5
    return "\n".join(
        [f"{fence}BEGIN PRIVATE KEY{fence}", *lines, f"{fence}END PRIVATE KEY{fence}", ""]
    )


def provider_token(key_pem, key_id, team_id, now):
    """Signs the ES256 token Apple requires for each provider connection."""
    header = b64(json.dumps({"alg": "ES256", "kid": key_id}, separators=(",", ":")).encode())
    claims = b64(json.dumps({"iss": team_id, "iat": int(now)}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}"
    key = serialization.load_pem_private_key(normalize_pem(key_pem).encode(), password=None)
    r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
    return f"{signing_input}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def service_account(value):
    """Reads a Google service account from raw JSON or the same JSON in base64, or None."""
    value = (value or "").strip()
    if not value:
        return None
    for text_value in (value, _unbase64(value)):
        try:
            account = json.loads(text_value or "")
        except ValueError:
            continue
        if isinstance(account, dict) and all(
            isinstance(account.get(k), str) and account[k]
            for k in ("client_email", "private_key", "project_id")
        ):
            account["private_key"] = account["private_key"].replace("\\n", "\n")
            account.setdefault("token_uri", FCM_TOKEN_URL)
            return account
    return None


def _unbase64(value):
    try:
        return base64.b64decode(value, validate=True).decode()
    except ValueError:
        return ""


def clean(value, fallback):
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value or "").strip()
    return (value or fallback)[:60]


def alert_for(kind, sender, channel, direct):
    """Returns the title and body for a notification, without any message text."""
    sender = clean(sender, "Someone")
    place = "#" + clean(channel, "channel")
    if direct:
        if kind == "reply":
            return sender, "Replied to you"
        return sender, "Sent you a message"
    if kind == "mention":
        return sender, f"Mentioned you in {place}"
    if kind == "reply":
        return sender, f"Replied to you in {place}"
    return place, f"{sender} posted a message"


class PostgresPushData:
    """Reads and prunes push data in the shared Supabase database."""

    def __init__(self, store):
        self.store = store

    def delivery(self, identifier):
        """One notification with its recipient's devices and unseen count, or None."""
        with self.store.tx(write=False) as db:
            row = db.execute(
                text("SELECT public.push_delivery(:id)"), {"id": identifier}
            ).scalar()
        return dict(row) if row else None

    def forget(self, token):
        with self.store.tx() as db:
            db.execute(text("SELECT public.push_forget_device(:token)"), {"token": token})


class FcmSender:
    """Sends the same name-and-place alerts to Android phones through Firebase Cloud Messaging."""

    def __init__(self, account, *, clock=time.time):
        self.account = account if isinstance(account, dict) else service_account(account)
        self.clock = clock
        self._token, self._issued = "", 0.0

    @property
    def configured(self):
        return bool(self.account)

    def assertion(self, now):
        """Signs the one-hour request Google exchanges for an access token."""
        header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        claims = b64(
            json.dumps(
                {
                    "iss": self.account["client_email"],
                    "scope": FCM_SCOPE,
                    "aud": self.account["token_uri"],
                    "iat": int(now),
                    "exp": int(now) + 3600,
                },
                separators=(",", ":"),
            ).encode()
        )
        signing_input = f"{header}.{claims}"
        key = serialization.load_pem_private_key(
            self.account["private_key"].encode(), password=None
        )
        signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{signing_input}.{b64(signature)}"

    async def access_token(self, client, *, refresh=False):
        now = self.clock()
        if refresh or not self._token or now - self._issued > FCM_LIFETIME:
            response = await client.post(
                self.account["token_uri"],
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": self.assertion(now),
                },
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
            self._issued = now
        return self._token

    def message(self, device, note, badge, identifier):
        title, body = alert_for(
            note["kind"],
            note["sender"],
            note["channel_name"],
            note["channel_kind"] in {"dm", "group_dm"},
        )
        return {
            "message": {
                "token": device["token"],
                "notification": {"title": title, "body": body},
                "android": {
                    "priority": "HIGH",
                    "collapse_key": f"n{identifier}",
                    "notification": {
                        "channel_id": "messages",
                        "default_sound": True,
                        "notification_count": badge,
                    },
                },
                "data": {
                    "workspace": note["workspace"] or "",
                    "channel": note["channel"] or "",
                    "message": note["message"] or "",
                    "parent": note["parent"] or "",
                },
            }
        }

    async def send(self, client, device, note, badge, identifier, *, retried=False):
        try:
            token = await self.access_token(client, refresh=retried)
            response = await client.post(
                FCM_SEND.format(project=self.account["project_id"]),
                json=self.message(device, note, badge, identifier),
                headers={"authorization": "Bearer " + token},
            )
        except (httpx.HTTPError, KeyError, ValueError):
            log.warning("push delivery failed to reach Google")
            return False
        if response.status_code == 200:
            return True
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        codes = {d.get("errorCode") for d in error.get("details", []) if isinstance(d, dict)}
        if response.status_code == 404 or "UNREGISTERED" in codes:
            await asyncio.to_thread(self.data_forget, device["token"])
        elif response.status_code == 401 and not retried:
            return await self.send(client, device, note, badge, identifier, retried=True)
        else:
            log.warning("push rejected by Google: status %s", response.status_code)
        return False

    # Set by PushSender so a dead device is forgotten through the same database function.
    data_forget = staticmethod(lambda token: None)


class PushSender:
    def __init__(
        self, *, data, key, key_id, team_id, topic, client=None, clock=time.time, fcm=None
    ):
        self.data, self.key, self.key_id = data, key, key_id
        self.team_id, self.topic, self.clock = team_id, topic, clock
        self.client = client
        self.fcm = fcm
        if fcm is not None:
            fcm.data_forget = data.forget
        self._token, self._issued = "", 0.0

    @property
    def apple_ready(self):
        return bool(self.key and self.key_id and self.team_id and self.topic)

    @property
    def configured(self):
        return self.apple_ready or bool(self.fcm and self.fcm.configured)

    def authorization(self, *, refresh=False):
        now = self.clock()
        if refresh or not self._token or now - self._issued > TOKEN_LIFETIME:
            self._token = provider_token(self.key, self.key_id, self.team_id, now)
            self._issued = now
        return "bearer " + self._token

    def payload(self, note, badge):
        title, body = alert_for(
            note["kind"],
            note["sender"],
            note["channel_name"],
            note["channel_kind"] in {"dm", "group_dm"},
        )
        return {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": badge,
                "thread-id": note["channel"],
            },
            "workspace": note["workspace"],
            "channel": note["channel"],
            "message": note["message"],
            "parent": note["parent"],
        }

    async def deliver(self, identifier):
        """Sends one notification to every device its recipient has registered."""
        if not self.configured:
            return 0
        note = await asyncio.to_thread(self.data.delivery, identifier)
        if not note:
            return 0
        devices = note["devices"]
        if not devices:
            return 0
        badge = note["unseen"]
        body = json.dumps(self.payload(note, badge), separators=(",", ":"))
        client = self.client or httpx.AsyncClient(http2=True, timeout=10)
        sent = 0
        try:
            for device in devices:
                if device.get("platform", "ios") == "android":
                    if not (self.fcm and self.fcm.configured):
                        continue
                    delivered = await self.fcm.send(client, device, note, badge, identifier)
                elif self.apple_ready:
                    delivered = await self.send(client, device, body, identifier)
                else:
                    continue
                if delivered:
                    sent += 1
        finally:
            if client is not self.client:
                await client.aclose()
        return sent

    async def send(self, client, device, body, identifier, *, retried=False):
        host = HOSTS.get(device["environment"], HOSTS["production"])
        try:
            response = await client.post(
                f"{host}/3/device/{device['token']}",
                content=body,
                headers={
                    "authorization": self.authorization(refresh=retried),
                    "apns-topic": self.topic,
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                    "apns-collapse-id": f"n{identifier}",
                },
            )
        except httpx.HTTPError:
            log.warning("push delivery failed to reach Apple")
            return False
        if response.status_code == 200:
            return True
        try:
            reason = response.json().get("reason", "")
        except ValueError:
            reason = ""
        if response.status_code == 410 or reason in GONE:
            await asyncio.to_thread(self.data.forget, device["token"])
        elif reason == "ExpiredProviderToken" and not retried:
            return await self.send(client, device, body, identifier, retried=True)
        else:
            log.warning("push rejected: status %s reason %s", response.status_code, reason)
        return False
