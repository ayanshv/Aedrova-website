"""Provider boundary: no model-controlled hosts, tokens, or GraphQL operations."""

import base64
import hashlib
import json
import re
import time
from typing import Protocol
from urllib.parse import urlencode

import httpx

from aedrova_site.store import Denied


class Uncertain(Denied):
    """A write may have reached the provider. Never automatically repeat it."""


class SocialProvider(Protocol):
    def connect_provider(self, client_id, redirect, state, verifier): ...
    def disconnect_provider(self): ...
    def get_connected_accounts(self, token: str, organization: str) -> list[dict]: ...
    def create_post(self, token: str, post: dict) -> dict: ...
    def schedule_post(self, token: str, post: dict) -> dict: ...
    def publish_post(self, token: str, post: dict) -> dict: ...
    def get_post_status(self, token: str, post_id: str) -> dict: ...
    def get_post_analytics(self, token: str, post_id: str) -> dict: ...


class BufferAdapter:
    AUTHORIZE = "https://auth.buffer.com/auth"
    TOKEN = "https://auth.buffer.com/token"
    API = "https://api.buffer.com"
    SCOPES = "posts:read posts:write account:read offline_access"

    def __init__(self, *, transport=None):
        self.client = httpx.Client(
            timeout=httpx.Timeout(12, connect=5),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    @classmethod
    def connect_provider(cls, client_id, redirect, state, verifier):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        return (
            cls.AUTHORIZE
            + "?"
            + urlencode(
                dict(
                    client_id=client_id,
                    redirect_uri=redirect,
                    response_type="code",
                    state=state,
                    scope=cls.SCOPES,
                    code_challenge=challenge.decode().rstrip("="),
                    code_challenge_method="S256",
                    prompt="consent",
                )
            )
        )

    @staticmethod
    def disconnect_provider():
        # No documented token-revocation endpoint. Local revocation is immediate;
        # provider-side removal is available in Buffer's Connected Apps settings.
        return "Remove Aedrova from Buffer's connected apps to revoke the provider grant."

    def token(self, client_id, client_secret, redirect, *, code=None, verifier=None, refresh=None):
        body = dict(
            client_id=client_id,
            client_secret=client_secret,
            grant_type="refresh_token" if refresh else "authorization_code",
        )
        if refresh:
            body["refresh_token"] = refresh
        else:
            body.update(code=code, code_verifier=verifier, redirect_uri=redirect)
        try:
            with self.client.stream("POST", self.TOKEN, data=body) as response:
                response.raise_for_status()
                result = self._json(response, 32768)
            access, renewal = result.get("access_token"), result.get("refresh_token")
            scopes = set(str(result.get("scope", "")).split())
            if not set(self.SCOPES.split()) <= scopes or not scopes <= set(self.SCOPES.split()):
                raise Denied("Authorize only Buffer account read and post read/write access.")
            if (
                any(
                    not isinstance(v, str) or not 8 <= len(v) <= 4096 or any(c.isspace() for c in v)
                    for v in (access, renewal)
                )
                or str(result.get("token_type", "")).lower() != "bearer"
                or type(result.get("expires_in")) is not int
                or not 1 <= result["expires_in"] <= 86400
                or renewal == refresh
            ):
                raise Denied("Needs authorization")
            return dict(
                kind="oauth",
                access=access,
                refresh=renewal,
                token_expires=int(time.time()) + result["expires_in"],
            )
        except Denied:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # A refresh is single-use; ambiguous exchange errors require reconnect.
            raise Denied("Needs authorization") from None

    @staticmethod
    def _json(response, maximum=1024 * 1024):
        raw = bytearray()
        for part in response.iter_bytes():
            raw.extend(part)
            if len(raw) > maximum:
                raise ValueError("Oversized response")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Malformed response")
        return result

    def query(self, token, query, variables=None, *, write=False):
        try:
            with self.client.stream(
                "POST",
                self.API,
                headers={"Authorization": "Bearer " + token},
                json={"query": query, "variables": variables or {}},
            ) as response:
                if response.status_code == 401:
                    raise Denied("Needs authorization")
                if response.status_code == 403:
                    raise Denied("Buffer denied this operation. Check channel permissions.")
                if response.status_code == 429:
                    raise Denied("Buffer rate limit reached. Wait before trying again.")
                response.raise_for_status()
                result = self._json(response)
            if result.get("errors"):
                if write:
                    raise Uncertain("Check Buffer before trying again; publication is unconfirmed.")
                raise Denied("Buffer could not complete this read. Check access and retry.")
            if not isinstance(result.get("data"), dict):
                raise ValueError("Missing data")
            return result["data"]
        except Denied:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            if write:
                raise Uncertain(
                    "Check Buffer before trying again; publication is unconfirmed."
                ) from None
            raise Denied("Buffer is temporarily unavailable. Try again later.") from None

    def organizations(self, token):
        data = self.query(token, "query { account { organizations { id name } } }")
        account = data.get("account")
        rows = account.get("organizations") if isinstance(account, dict) else None
        if not isinstance(rows, list) or len(rows) > 100:
            raise Denied("Buffer returned an unsupported organization list.")
        return [dict(id=self.identifier(r, "id"), name=self.name(r, token)) for r in rows]

    @staticmethod
    def identifier(row, key):
        value = row.get(key) if isinstance(row, dict) else None
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
            raise Denied("Buffer returned an unsupported identifier.")
        return value

    @staticmethod
    def name(row, token):
        value = row.get("name") if isinstance(row, dict) else None
        if not isinstance(value, str) or not value.strip() or token in value:
            raise Denied("Buffer returned unsupported account information.")
        return "".join(c for c in value[:160] if ord(c) >= 32)

    def get_connected_accounts(self, token, organization):
        data = self.query(
            token,
            """query Channels($input: ChannelsInput!) {
            channels(input: $input) { id name service organizationId allowedActions
              isDisconnected isLocked isQueuePaused } }""",
            {"input": {"organizationId": organization}},
        )
        rows = data.get("channels")
        if not isinstance(rows, list) or len(rows) > 200:
            raise Denied("Buffer returned too many channels. Select a smaller organization.")
        result = []
        for row in rows:
            if not isinstance(row, dict) or row.get("organizationId") != organization:
                raise Denied("Buffer returned a channel outside your selected organization.")
            result.append(
                dict(
                    id=self.identifier(row, "id"),
                    name=self.name(row, token),
                    platform=self.identifier(row, "service"),
                    paused=bool(row.get("isQueuePaused")),
                    can_publish=(
                        isinstance(row.get("allowedActions"), list)
                        and "scheduleUpdates" in row["allowedActions"]
                        and row.get("isDisconnected") is False
                        and row.get("isLocked") is False
                    ),
                )
            )
        return result

    @staticmethod
    def post_status(value):
        return (
            value
            if isinstance(value, str) and value in {"buffer", "sent", "error", "notSent", "draft"}
            else "unknown"
        )

    def create_post(self, token, post):
        # The service speaks a neutral draft vocabulary; Buffer's wire format lives here.
        payload = dict(
            channelId=post["channel"],
            text=post["text"],
            assets=[{a["kind"]: {"url": a["url"]}} for a in post["assets"]],
            schedulingType="automatic",
            needsApproval=False,
            source="Aedrova",
            mode="customScheduled" if post.get("due_at") else "shareNow",
        )
        if post.get("platform") == "instagram":
            # Instagram requires explicit format and feed policy, even for one image.
            payload["metadata"] = {
                "instagram": {
                    "type": "reel" if any(a["kind"] == "video" for a in post["assets"]) else "post",
                    "shouldShareToFeed": True,
                }
            }
        if post.get("due_at"):
            payload["dueAt"] = post["due_at"]
        operation = """mutation Publish($input: CreatePostInput!) { createPost(input: $input) {
            ... on PostActionSuccess { post { id channelId text status dueAt } }
            ... on MutationError { message } } }"""
        data = self.query(token, operation, {"input": payload}, write=True)
        result = data.get("createPost")
        if not isinstance(result, dict):
            raise Uncertain("Check Buffer before trying again; publication is unconfirmed.")
        if not isinstance(result.get("post"), dict):
            if result.get("message"):
                raise Denied(
                    "Buffer rejected the post. Check the channel, format and posting limits."
                )
            raise Uncertain("Check Buffer before trying again; publication is unconfirmed.")
        row = result["post"]
        if (
            not isinstance(row.get("id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", row["id"])
            or row.get("channelId") != post["channel"]
        ):
            raise Uncertain("Check Buffer before trying again; publication is unconfirmed.")
        return {
            "id": str(row["id"]),
            "status": self.post_status(row.get("status")),
            "due_at": row.get("dueAt"),
        }

    def schedule_post(self, token, post):
        return self.create_post(token, post)

    def publish_post(self, token, post):
        return self.create_post(token, {**post, "due_at": None})

    def get_post_status(self, token, post_id):
        row = self.query(
            token,
            """query Status($input: PostInput!) {
            post(input: $input) { id channelId status dueAt } }""",
            {"input": {"id": post_id}},
        ).get("post")
        if not isinstance(row, dict) or row.get("id") != post_id:
            raise Denied("Buffer did not return the requested post.")
        return {
            "id": row["id"],
            "channel_id": self.identifier(row, "channelId"),
            "status": self.post_status(row.get("status")),
            "due_at": row.get("dueAt"),
        }

    def get_post_analytics(self, token, post_id):
        raise Denied(
            "Buffer post metrics are not available to OAuth apps. No metrics were fetched."
        )
