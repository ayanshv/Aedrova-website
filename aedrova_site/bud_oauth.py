"""Confidential, resource-bound OAuth grants; tokens never leave the server."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from aedrova_site.bud_providers import validate_resource
from aedrova_site.connection_confirmation import confirmation
from aedrova_site.store import Denied

# All destinations are fixed. Scopes are configured by Aedrova, never model/client input.
PROVIDERS = {
    "github": (
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        "offline_access",
    ),
    "figma": (
        "https://www.figma.com/oauth",
        "https://api.figma.com/v1/oauth/token",
        "file_content:read",
    ),
    "notion": (
        "https://api.notion.com/v1/oauth/authorize",
        "https://api.notion.com/v1/oauth/token",
        "",
    ),
    "supabase": (
        "https://api.supabase.com/v1/oauth/authorize",
        "https://api.supabase.com/v1/oauth/token",
        "",
    ),
}
SCHEMA = """CREATE TABLE IF NOT EXISTS bud_oauth (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires BIGINT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', connection_id TEXT NOT NULL DEFAULT '')"""


def state_key(state):
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", state):
        raise Denied("Invalid authorization. Connect your tool again.")
    return hashlib.sha256(state.encode()).hexdigest()


class BudOAuth:
    def __init__(self, connections, *, transport=None):
        self.connections = connections
        self.dots, self.store = connections.dots, connections.store
        self.config = self.dots.config
        self.client = httpx.Client(
            timeout=httpx.Timeout(12, connect=5),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )
        with self.store.tx() as db:
            db.execute(text(SCHEMA))

    def close(self):
        self.client.close()

    def credentials(self, provider):
        if provider not in PROVIDERS:
            raise Denied("This connector uses a scoped access token.")
        prefix = "github_dot" if provider == "github" else provider + "_bud"
        return (
            getattr(self.config, prefix + "_client_id"),
            getattr(self.config, prefix + "_client_secret"),
        )

    def setup_hint(self, provider):
        if provider == "supabase" and not self.config.origin.startswith("https://"):
            return (
                "Supabase requires an HTTPS callback. Aedrova’s owner must configure "
                "the HTTPS connection service before account sign-in is available. "
                "A scoped access token can be used below."
            )
        if (
            provider not in PROVIDERS
            or not self.config.dots_enabled
            or not all(self.credentials(provider))
        ):
            return (
                "The Aedrova owner must configure this provider’s OAuth app first. "
                "You can use a scoped access token meanwhile."
            )
        return ""

    def available(self, provider):
        return not self.setup_hint(provider)

    def redirect(self, provider):
        return self.config.origin.rstrip("/") + "/buds/oauth/" + provider + "/callback"

    def start(self, session, workspace, bud, provider, resource, hours):
        dot, user = self.dots.dot(session, workspace, bud)
        hint = self.setup_hint(provider)
        if hint:
            raise Denied(hint)
        resource = validate_resource(provider, resource)
        if not 1 <= hours <= 2160:
            raise Denied("Choose an access lifetime from 1 hour to 90 days.")
        state = secrets.token_urlsafe(32)
        payload = dict(
            dot=dot,
            user=user,
            session=session,
            provider=provider,
            resource=resource,
            hours=hours,
            verifier=secrets.token_urlsafe(48),
            proof=secrets.token_urlsafe(32),
        )
        with self.store.tx() as db:
            db.execute(text("DELETE FROM bud_oauth WHERE expires<:t"), {"t": int(time.time())})
            db.execute(
                text("INSERT INTO bud_oauth(id,payload,expires) VALUES(:i,:p,:e)"),
                dict(
                    i=state_key(state),
                    p=self.store.cipher.encrypt(json.dumps(payload).encode()).decode(),
                    e=int(time.time()) + 600,
                ),
            )
        self.dots.audit(dot, user, "connector_oauth_started:" + provider)
        return {"url": self.config.origin + "/buds/authorize/" + state, "state": state}

    def state(self, state, *, transition=None):
        key = state_key(state)
        with self.store.tx() as db:
            row = (
                db.execute(
                    text("SELECT * FROM bud_oauth WHERE id=:i AND expires>:t"),
                    dict(i=key, t=int(time.time())),
                )
                .mappings()
                .first()
            )
            if not row:
                raise Denied("Authorization expired. Connect your tool again.")
            if transition:
                before, after = transition
                result = db.execute(
                    text("UPDATE bud_oauth SET status=:a WHERE id=:i AND status=:b"),
                    dict(a=after, i=key, b=before),
                )
                if result.rowcount != 1:
                    raise Denied("Authorization already used. Connect your tool again.")
        return dict(row), json.loads(self.store.cipher.decrypt(row["payload"].encode()))

    def fresh(self, payload):
        previous = payload["dot"]
        dot, user = self.dots.dot(payload["session"], previous["workspace_id"], previous["id"])
        if user != payload["user"] or dot["version"] != previous["version"]:
            raise Denied("Bud settings or membership changed. Connect your tool again.")
        return dot, user

    def authorize(self, state, browser_user):
        row, payload = self.state(state)
        if row["status"] != "pending":
            raise Denied("Authorization already opened. Connect your tool again.")
        if not hmac.compare_digest(browser_user, payload["user"]):
            raise Denied("Use the same Google account on the website and desktop app.")
        self.fresh(payload)
        if not self.available(payload["provider"]):
            raise Denied("Provider setup is no longer available.")
        self.state(state, transition=("pending", "opened"))
        provider = payload["provider"]
        target, _, scope = PROVIDERS[provider]
        params = dict(
            client_id=self.credentials(provider)[0],
            redirect_uri=self.redirect(provider),
            response_type="code",
            state=state,
        )
        if scope:
            params["scope"] = scope
        if provider != "notion":
            params.update(
                code_challenge=base64.urlsafe_b64encode(
                    hashlib.sha256(payload["verifier"].encode()).digest()
                )
                .decode()
                .rstrip("="),
                code_challenge_method="S256",
            )
        if provider == "notion":
            params["owner"] = "user"
        return target + "?" + urlencode(params), payload

    def token(self, provider, *, code=None, verifier=None, refresh=None):
        client_id, client_secret = self.credentials(provider)
        if not client_id or not client_secret:
            raise Denied("Needs authorization")
        body = {"grant_type": "refresh_token" if refresh else "authorization_code"}
        if refresh:
            body["refresh_token"] = refresh
        else:
            body.update(code=code, redirect_uri=self.redirect(provider))
            if provider != "notion":
                body["code_verifier"] = verifier
        headers = {"Accept": "application/json"}
        kwargs = {"auth": (client_id, client_secret)}
        if provider == "github":
            # GitHub App user authorization (repository access is selected at installation).
            body.update(client_id=client_id, client_secret=client_secret)
            kwargs = {}
        if provider == "notion":
            kwargs["json"] = body
        else:
            kwargs["data"] = body
        try:
            with self.client.stream(
                "POST", PROVIDERS[provider][1], headers=headers, **kwargs
            ) as response:
                if response.status_code in {400, 401, 403}:
                    raise Denied("Needs authorization")
                response.raise_for_status()
                raw = bytearray()
                for block in response.iter_bytes():
                    raw.extend(block)
                    if len(raw) > 32768:
                        raise Denied("Unsupported authorization response.")
                result = json.loads(raw)
            access = result.get("access_token", "")
            refresh_token = result.get("refresh_token", refresh or "")
            if (
                not isinstance(access, str)
                or not 8 <= len(access) <= 4096
                or any(c.isspace() for c in access)
                or str(result.get("token_type", "bearer")).lower() != "bearer"
                or not isinstance(refresh_token, str)
                or len(refresh_token) > 4096
                or any(c.isspace() for c in refresh_token)
            ):
                raise Denied("Unsupported authorization response.")
            # Reject unexpectedly broad grants where the provider returns OAuth scopes.
            scope = result.get("scope")
            if scope and provider in {"figma", "supabase"}:
                scopes = set(scope.replace(",", " ").split() if isinstance(scope, str) else scope)
                allowed = {
                    "figma": {"file_content:read"},
                    "supabase": {"projects:read"},
                }[provider]
                if not scopes <= allowed:
                    raise Denied(
                        "This OAuth app requests excessive permissions. Ask the owner "
                        "to configure read-only scopes."
                    )
            seconds = result.get("expires_in", 28800 if provider == "github" else 3600)
            if type(seconds) is not int or not 1 <= seconds <= 31536000:
                raise Denied("Unsupported authorization expiry.")
            return {
                "kind": "oauth",
                "access": access,
                "refresh": refresh_token,
                "token_expires": int(time.time()) + seconds,
            }
        except Denied:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise Denied("Authorization provider unavailable. Retry shortly.") from None

    def callback(self, provider, state, proof, code, *, denied=False):
        row, payload = self.state(state)
        if row["status"] != "opened":
            raise Denied("Authorization already used. Connect your tool again.")
        if payload["provider"] != provider or not hmac.compare_digest(payload["proof"], proof):
            raise Denied("Authorization browser changed. Connect your tool again.")
        self.state(state, transition=("opened", "processing"))
        connection_id, status = "", "failed"
        try:
            self.fresh(payload)
            if denied:
                raise Denied("Authorization was cancelled. Your account was not connected.")
            if not code or len(code) > 2000:
                raise Denied("Missing authorization code. Connect your tool again.")
            token = self.token(provider, code=code, verifier=payload["verifier"])
            result = self.connections.connect(
                payload["session"],
                payload["dot"]["workspace_id"],
                payload["dot"]["id"],
                provider,
                payload["resource"],
                token["access"],
                payload["hours"],
                oauth=token,
                expected_version=payload["dot"]["version"],
            )
            connection_id, status = result["id"], "connected"
            return result
        finally:
            # Remove desktop session, browser proof and verifier once callback is consumed.
            payload = {k: payload[k] for k in ("dot", "user", "provider", "resource")}
            with self.store.tx() as db:
                db.execute(
                    text("UPDATE bud_oauth SET status=:s,connection_id=:c,payload=:p WHERE id=:i"),
                    dict(
                        s=status,
                        c=connection_id,
                        i=state_key(state),
                        p=self.store.cipher.encrypt(json.dumps(payload).encode()).decode(),
                    ),
                )

    def status(self, session, state):
        row, payload = self.state(state)
        dot, user = self.dots.dot(session, payload["dot"]["workspace_id"], payload["dot"]["id"])
        if user != payload["user"] or dot["version"] != payload["dot"]["version"]:
            raise Denied("This authorization is no longer available to your account.")
        status = row["status"]
        if status == "connected" and not any(
            grant["id"] == row["connection_id"]
            and grant["dot_version"] == dot["version"]
            and grant["status"] == "Connected"
            for grant in self.connections.rows(dot, user)
        ):
            status = "failed"
        return {
            "status": status,
            "connection": row["connection_id"] if status == "connected" else "",
        }


class OAuthBody(BaseModel):
    model_config = {"extra": "forbid"}
    workspace: UUID
    dot: UUID
    provider: str = Field(max_length=40)
    resource: str = Field(min_length=1, max_length=200)
    hours: int = Field(default=24, ge=1, le=2160, strict=True)


def install(app, connections, auth):
    oauth = BudOAuth(connections)
    connections.oauth = oauth

    @app.post("/api/buds/oauth/start")
    def start(request: Request, body: OAuthBody):
        session = auth(request, change=True)
        oauth.store.rate_limit(
            "bud-oauth:" + hashlib.sha256(session.encode()).hexdigest(), limit=10
        )
        return oauth.start(
            session, str(body.workspace), str(body.dot), body.provider, body.resource, body.hours
        )

    @app.get("/api/buds/oauth/status")
    def status(request: Request, state: str):
        return oauth.status(auth(request), state)

    @app.get("/buds/authorize/{state}")
    def authorize(request: Request, state: str):
        oauth.dots.enabled()
        oauth.state(state)
        try:
            user = oauth.dots.identity.user(auth(request))["id"]
        except Denied:
            return RedirectResponse("/auth/google?" + urlencode({"bud": state}), status_code=303)
        target, payload = oauth.authorize(state, user)
        response = RedirectResponse(target, status_code=303)
        response.set_cookie(
            "aedrova_bud_" + state_key(state)[:16],
            payload["proof"],
            httponly=True,
            secure=oauth.config.origin.startswith("https://"),
            samesite="lax",
            max_age=600,
            path="/buds/oauth/" + payload["provider"],
        )
        return response

    @app.get("/buds/oauth/{provider}/callback")
    def callback(request: Request, provider: str, state: str = "", code: str = "", error: str = ""):
        oauth.dots.enabled()
        cookie = "aedrova_bud_" + state_key(state)[:16]
        oauth.callback(provider, state, request.cookies.get(cookie, ""), code, denied=bool(error))
        _, payload = oauth.state(state)
        response = confirmation(request, provider, payload["dot"])
        response.delete_cookie(cookie, path="/buds/oauth/" + provider)
        return response
