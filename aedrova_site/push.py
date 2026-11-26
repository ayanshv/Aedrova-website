"""Apple push notifications for new chat activity.

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
from cryptography.hazmat.primitives.asymmetric import ec
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


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def normalize_pem(value):
    """Rebuilds an Apple .p8 key whose line breaks a settings field lost or escaped."""
    body = re.sub(r"-----[A-Z ]+-----", "", (value or "").replace("\\n", "\n"))
    body = re.sub(r"\s+", "", body)
    lines = [body[i : i + 64] for i in range(0, len(body), 64)]
    return "\n".join(["-----BEGIN PRIVATE KEY-----", *lines, "-----END PRIVATE KEY-----", ""])


def provider_token(key_pem, key_id, team_id, now):
    """Signs the ES256 token Apple requires for each provider connection."""
    header = b64(json.dumps({"alg": "ES256", "kid": key_id}, separators=(",", ":")).encode())
    claims = b64(json.dumps({"iss": team_id, "iat": int(now)}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}"
    key = serialization.load_pem_private_key(normalize_pem(key_pem).encode(), password=None)
    r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
    return f"{signing_input}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


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

    def notification(self, identifier):
        with self.store.tx(write=False) as db:
            row = (
                db.execute(
                    text(
                        """SELECT n.id, n.user_id::text AS user_id, n.kind,
                        m.channel_id::text AS channel, m.id::text AS message,
                        m.parent_id::text AS parent, c.workspace_id::text AS workspace,
                        c.name AS channel_name, c.kind AS channel_kind,
                        COALESCE(u.raw_user_meta_data->>'full_name', 'Someone') AS sender
                        FROM public.chat_notifications n
                        JOIN public.messages m ON m.id = n.message_id
                        JOIN public.channels c ON c.id = m.channel_id
                        LEFT JOIN auth.users u ON u.id = m.sender_id
                        WHERE n.id = :id AND m.unsent_at IS NULL"""
                    ),
                    {"id": identifier},
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def devices(self, user):
        with self.store.tx(write=False) as db:
            rows = db.execute(
                text(
                    "SELECT token, environment FROM aedrova_private.push_devices "
                    "WHERE user_id = CAST(:user AS uuid)"
                ),
                {"user": user},
            ).all()
        return [{"token": r[0], "environment": r[1]} for r in rows]

    def unseen(self, user):
        with self.store.tx(write=False) as db:
            return int(
                db.execute(
                    text(
                        "SELECT count(*) FROM public.chat_notifications "
                        "WHERE user_id = CAST(:user AS uuid) AND seen_at IS NULL"
                    ),
                    {"user": user},
                ).scalar()
                or 0
            )

    def forget(self, token):
        with self.store.tx() as db:
            db.execute(
                text("DELETE FROM aedrova_private.push_devices WHERE token = :token"),
                {"token": token},
            )


class PushSender:
    def __init__(self, *, data, key, key_id, team_id, topic, client=None, clock=time.time):
        self.data, self.key, self.key_id = data, key, key_id
        self.team_id, self.topic, self.clock = team_id, topic, clock
        self.client = client
        self._token, self._issued = "", 0.0

    @property
    def configured(self):
        return bool(self.key and self.key_id and self.team_id and self.topic)

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
        note = await asyncio.to_thread(self.data.notification, identifier)
        if not note:
            return 0
        devices = await asyncio.to_thread(self.data.devices, note["user_id"])
        if not devices:
            return 0
        badge = await asyncio.to_thread(self.data.unseen, note["user_id"])
        body = json.dumps(self.payload(note, badge), separators=(",", ":"))
        client = self.client or httpx.AsyncClient(http2=True, timeout=10)
        sent = 0
        try:
            for device in devices:
                if await self.send(client, device, body, identifier):
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
