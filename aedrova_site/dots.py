"""Workspace-scoped capability sources. Provider secrets never leave the server."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from aedrova_site.store import Denied

STATES = {
    "Connected",
    "Connecting",
    "Needs authorization",
    "Permission issue",
    "Syncing",
    "Error",
    "Disconnected",
}
REGISTRY = {
    "github": {
        "name": "GitHub",
        "tools": {
            "repository": "Repository metadata",
            "changes": "Recent commits",
            "issues": "Open issues and pull requests",
            "deployments": "Recent deployments",
        },
        "auth": "GitHub App OAuth",
        "permissions": (
            "Read-only repository contents, metadata, issues, pull requests and deployments"
        ),
    },
    "stripe": {
        "name": "Stripe",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Revenue and subscriptions (planned)",
    },
    "supabase": {
        "name": "Supabase",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Approved aggregate database metrics (planned)",
    },
    "vercel": {
        "name": "Vercel",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Deployments and project health (planned)",
    },
    "posthog": {
        "name": "PostHog",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Product analytics (planned)",
    },
    "figma": {
        "name": "Figma",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Design context (migration pending)",
    },
    "notion": {
        "name": "Notion",
        "tools": {},
        "auth": "Not available yet",
        "permissions": "Document context (migration pending)",
    },
}
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS dot_grants (
        dot TEXT NOT NULL, user_id TEXT NOT NULL, workspace TEXT NOT NULL,
        version INTEGER NOT NULL, resource TEXT NOT NULL, secret TEXT NOT NULL,
        expires BIGINT NOT NULL, status TEXT NOT NULL, synced BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY(dot,user_id))""",
    """CREATE TABLE IF NOT EXISTS dot_oauth (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires BIGINT NOT NULL,
        started INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS dot_audit (
        id TEXT PRIMARY KEY, dot TEXT NOT NULL, workspace TEXT NOT NULL,
        user_id TEXT NOT NULL, action TEXT NOT NULL, created BIGINT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS dot_grants_workspace ON dot_grants(workspace)",
    "CREATE INDEX IF NOT EXISTS dot_audit_workspace ON dot_audit(workspace,created)",
    """CREATE TABLE IF NOT EXISTS dot_evidence_cache (
        dot TEXT NOT NULL, user_id TEXT NOT NULL, workspace TEXT NOT NULL,
        tool TEXT NOT NULL, version INTEGER NOT NULL, grant_hash TEXT NOT NULL,
        payload TEXT NOT NULL, created BIGINT NOT NULL, expires BIGINT NOT NULL,
        PRIMARY KEY(dot,user_id,tool))""",
]


def identifier(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise Denied("Invalid Bud or workspace.") from None


def resource(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", value) or ".." in value:
        raise Denied("Use a GitHub repository in owner/repository format.")
    return value


class DotProvider(Protocol):
    """Adapter contract: typed tools, explicit authentication and revocation."""

    def execute(self, token: str, repository: str, tool: str) -> dict: ...
    def exchange(self, code: str, verifier: str) -> tuple[str, int]: ...
    def revoke(self, token: str) -> bool: ...
    def close(self) -> None: ...


class GitHubProvider:
    """Fixed-host, bounded, read-only tools; model input cannot supply URLs."""

    def __init__(self, config, *, transport=None):
        self.config = config
        self.client = httpx.Client(
            timeout=httpx.Timeout(12, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def get(self, token, path):
        try:
            with self.client.stream(
                "GET",
                "https://api.github.com" + path,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            ) as response:
                if response.status_code == 401:
                    raise Denied("Needs authorization")
                if response.status_code in {403, 404}:
                    raise Denied("Permission issue")
                response.raise_for_status()
                data = bytearray()
                for block in response.iter_bytes():
                    data.extend(block)
                    if len(data) > 512 * 1024:
                        raise Denied("The provider response is too large. Narrow the request.")
                return json.loads(data)
        except Denied:
            raise
        except (httpx.HTTPError, ValueError):
            raise Denied("GitHub is temporarily unavailable. Try again shortly.") from None

    def execute(self, token, repository, tool):
        repository = resource(repository)
        path = "/repos/" + repository

        def record(path, *, many=False):
            data = self.get(token, path)
            if (
                many and (not isinstance(data, list) or any(not isinstance(r, dict) for r in data))
            ) or (not many and not isinstance(data, dict)):
                raise Denied("GitHub returned an unsupported response. Retry shortly.")
            return data

        if tool == "repository":
            row = record(path)
            result = {
                "kind": "Repository",
                "name": row.get("full_name"),
                "description": str(row.get("description") or "")[:1000],
                "language": row.get("language"),
                "default_branch": row.get("default_branch"),
                "updated_at": row.get("updated_at"),
                "private": bool(row.get("private")),
            }
        elif tool == "changes":
            rows = record(path + "/commits?per_page=10", many=True)
            result = [
                {
                    "kind": "CodeChange",
                    "id": str(r.get("sha", ""))[:40],
                    "summary": str(r.get("commit", {}).get("message", ""))[:1200],
                    "date": r.get("commit", {}).get("committer", {}).get("date"),
                }
                for r in rows[:10]
            ]
        elif tool == "issues":
            rows = record(path + "/issues?state=open&per_page=10", many=True)
            result = [
                {
                    "kind": "PullRequest" if r.get("pull_request") else "Issue",
                    "number": r.get("number"),
                    "title": str(r.get("title", ""))[:500],
                    "summary": str(r.get("body") or "")[:1200],
                    "updated_at": r.get("updated_at"),
                }
                for r in rows[:10]
            ]
        elif tool == "deployments":
            rows = record(path + "/deployments?per_page=10", many=True)
            result = [
                {
                    "kind": "Deployment",
                    "id": r.get("id"),
                    "environment": str(r.get("environment", ""))[:100],
                    "ref": str(r.get("ref", ""))[:200],
                    "created_at": r.get("created_at"),
                }
                for r in rows[:10]
            ]
        else:
            raise Denied("This tool is not available.")
        serialized = json.dumps(result, ensure_ascii=False)
        # External text is evidence, never instructions. Refuse recognizable credentials.
        if token in serialized or re.search(
            r"(?:gh[pousr]_[A-Za-z0-9]{20,}|sk_(?:live|test)_[A-Za-z0-9]+|"
            r"AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY)",
            serialized,
        ):
            raise Denied("Provider data contains sensitive credentials and was withheld.")
        return {
            "records": result,
            "source": "https://github.com/" + repository,
            "coverage": "Most recent 10 records; no complete-history claim",
            "untrusted": True,
        }

    def exchange(self, code, verifier):
        try:
            response = self.client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": self.config.github_dot_client_id,
                    "client_secret": self.config.github_dot_client_secret,
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": self.config.origin + "/dots/github/callback",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("access_token") or payload.get("token_type", "").lower() != "bearer":
                raise Denied("GitHub authorization did not complete. Try connecting again.")
            return payload["access_token"], int(payload.get("expires_in", 28800))
        except Denied:
            raise
        except (httpx.HTTPError, ValueError):
            raise Denied("GitHub authorization did not complete. Try connecting again.") from None

    def revoke(self, token):
        try:
            response = self.client.request(
                "DELETE",
                "https://api.github.com/applications/"
                + self.config.github_dot_client_id
                + "/token",
                json={"access_token": token},
                auth=(self.config.github_dot_client_id, self.config.github_dot_client_secret),
            )
            return response.status_code in {204, 404, 401}
        except httpx.HTTPError:
            return False


class DotService:
    def __init__(self, config, store, identity, *, transport=None):
        self.config, self.store, self.identity = config, store, identity
        self.providers: dict[str, DotProvider] = {
            "github": GitHubProvider(config, transport=transport)
        }
        with store.tx() as db:
            if store.engine.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73114011)"))
            for statement in SCHEMA:
                db.execute(text(statement))

    def enabled(self):
        if not self.config.dots_enabled:
            raise Denied("Buds need the shared service to be configured. Your chats still work.")

    def audit(self, dot, user, action):
        with self.store.tx() as db:
            db.execute(
                text("INSERT INTO dot_audit VALUES(:id,:d,:w,:u,:a,:t)"),
                {
                    "id": secrets.token_hex(16),
                    "d": dot["id"],
                    "w": dot["workspace_id"],
                    "u": user,
                    "a": action,
                    "t": int(time.time()),
                },
            )

    def dot(self, token, workspace, dot_id):
        self.enabled()
        workspace, dot_id = identifier(workspace), identifier(dot_id)
        user = self.identity.require(token, workspace)
        with self.store.tx() as db:
            db.execute(text("DELETE FROM dot_grants WHERE expires<:t"), {"t": int(time.time())})
            db.execute(
                text("DELETE FROM dot_evidence_cache WHERE expires<:t"), {"t": int(time.time())}
            )
            db.execute(
                text("DELETE FROM dot_audit WHERE created<:t"), {"t": int(time.time()) - 90 * 86400}
            )
        rows = self.identity.request(
            "/rest/v1/workspace_dots?"
            + urlencode(
                {
                    "id": "eq." + dot_id,
                    "workspace_id": "eq." + workspace,
                    "deleted_at": "is.null",
                    "select": "*",
                }
            ),
            token,
        )
        if not rows or rows[0].get("id") != dot_id or rows[0].get("workspace_id") != workspace:
            raise Denied("This Bud is no longer available in this workspace.")
        return rows[0], user["id"]

    def grant(self, dot, user, *, allow_stale=False):
        with self.store.tx(write=False) as db:
            row = (
                db.execute(
                    text("SELECT * FROM dot_grants WHERE dot=:d AND user_id=:u AND workspace=:w"),
                    {"d": dot["id"], "u": user, "w": dot["workspace_id"]},
                )
                .mappings()
                .first()
            )
        return dict(row) if row and (allow_stale or row["version"] == dot["version"]) else None

    def list(self, token, workspace):
        self.enabled()
        workspace = identifier(workspace)
        user = self.identity.require(token, workspace)["id"]
        rows = self.identity.request(
            "/rest/v1/workspace_dots?"
            + urlencode(
                {
                    "workspace_id": "eq." + workspace,
                    "deleted_at": "is.null",
                    "select": "*",
                    "order": "created_at.asc",
                }
            ),
            token,
        )
        for row in rows:
            grant = self.grant(row, user)
            status = "Needs authorization"
            if grant:
                status = (
                    grant["status"] if grant["expires"] > time.time() else "Needs authorization"
                )
            provider = REGISTRY.get(row["provider"], {})
            row.update(
                status=status,
                last_sync=grant["synced"] if grant else 0,
                tools=provider.get("tools", {}),
                permissions=provider.get("permissions", ""),
            )
            if hasattr(self, "connections"):
                connections = self.connections.listing(row, user)
                row["connections"] = connections
                if connections and status != "Connected":
                    row["tools"] = {}
                for connection in connections:
                    if connection["status"] in {"Connected", "Error"}:
                        if connection["status"] == "Connected":
                            row["status"] = "Connected"
                        elif row["status"] != "Connected":
                            row["status"] = "Error"
                        row["last_sync"] = max(row["last_sync"], connection["last_sync"])
                        row["tools"] = {
                            **row["tools"],
                            **{
                                connection["id"] + "." + key: connection["provider"] + " · " + value
                                for key, value in connection["tools"].items()
                            },
                        }
        return rows

    def cached(self, dot, user, grant, tool, *, stale=False):
        if (
            not grant
            or grant["expires"] <= time.time()
            or grant["status"] not in {"Connected", "Syncing", "Error"}
        ):
            return None
        with self.store.tx(write=False) as db:
            row = (
                db.execute(
                    text(
                        "SELECT * FROM dot_evidence_cache WHERE dot=:d AND user_id=:u "
                        "AND workspace=:w AND tool=:t"
                    ),
                    {"d": dot["id"], "u": user, "w": dot["workspace_id"], "t": tool},
                )
                .mappings()
                .first()
            )
        if not row or row["version"] != dot["version"] or row["expires"] <= time.time():
            return None
        if row["grant_hash"] != hashlib.sha256(grant["secret"].encode()).hexdigest():
            return None
        if not stale and (not grant["synced"] or time.time() - row["created"] >= 300):
            return None
        evidence = json.loads(self.store.cipher.decrypt(row["payload"].encode()))
        return None if not stale and evidence.get("read_failed_at") else evidence

    def cache(self, dot, user, grant, tool, evidence):
        with self.store.tx() as db:
            current = db.execute(
                text(
                    "SELECT secret FROM dot_grants WHERE dot=:d AND user_id=:u "
                    "AND workspace=:w AND version=:v AND expires>:t"
                ),
                {
                    "d": dot["id"],
                    "u": user,
                    "w": dot["workspace_id"],
                    "v": dot["version"],
                    "t": int(time.time()),
                },
            ).scalar()
            if current != grant["secret"]:
                raise Denied("The Bud was disconnected while working. Retry your request.")
            db.execute(
                text("""INSERT INTO dot_evidence_cache
                VALUES(:d,:u,:w,:t,:v,:g,:p,:c,:e)
                ON CONFLICT(dot,user_id,tool) DO UPDATE SET
                workspace=excluded.workspace,version=excluded.version,grant_hash=excluded.grant_hash,
                payload=excluded.payload,created=excluded.created,expires=excluded.expires"""),
                {
                    "d": dot["id"],
                    "u": user,
                    "w": dot["workspace_id"],
                    "t": tool,
                    "v": dot["version"],
                    "g": hashlib.sha256(grant["secret"].encode()).hexdigest(),
                    "p": self.store.cipher.encrypt(json.dumps(evidence).encode()).decode(),
                    "c": evidence["fetched_at"],
                    "e": min(grant["expires"], evidence["fetched_at"] + 86400),
                },
            )

    def start(self, token, workspace, dot_id):
        dot, user = self.dot(token, workspace, dot_id)
        if dot["provider"] != "github" or not self.config.github_dot_client_secret:
            raise Denied("This provider is not configured yet.")
        state, proof, verifier = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(48),
        )
        payload = {"dot": dot, "user": user, "session": token, "proof": proof, "verifier": verifier}
        with self.store.tx() as db:
            db.execute(text("DELETE FROM dot_oauth WHERE expires<:t"), {"t": int(time.time())})
            db.execute(
                text("INSERT INTO dot_oauth(id,payload,expires) VALUES(:s,:p,:e)"),
                {
                    "s": hashlib.sha256(state.encode()).hexdigest(),
                    "p": self.store.cipher.encrypt(json.dumps(payload).encode()).decode(),
                    "e": int(time.time()) + 600,
                },
            )
        self.audit(dot, user, "authorization_started")
        return self.config.origin + "/dots/authorize/" + state

    def state(self, state, *, consume=False, peek=False):
        key = hashlib.sha256(state.encode()).hexdigest()
        with self.store.tx() as db:
            row = (
                db.execute(
                    text("SELECT * FROM dot_oauth WHERE id=:s AND expires>:t"),
                    {"s": key, "t": int(time.time())},
                )
                .mappings()
                .first()
            )
            if not row:
                raise Denied("Authorization expired. Connect this Bud again.")
            if consume:
                deleted = db.execute(text("DELETE FROM dot_oauth WHERE id=:s"), {"s": key})
                if deleted.rowcount != 1:
                    raise Denied("Authorization already completed.")
            elif peek:
                pass
            elif row["started"]:
                raise Denied("Authorization already opened. Connect this Bud again.")
            else:
                updated = db.execute(
                    text("UPDATE dot_oauth SET started=1 WHERE id=:s AND started=0"), {"s": key}
                )
                if updated.rowcount != 1:
                    raise Denied("Authorization already opened.")
        return json.loads(self.store.cipher.decrypt(row["payload"].encode()))

    def callback(self, state, proof, code):
        payload = self.state(state, consume=True)
        if not hmac.compare_digest(payload["proof"], proof):
            raise Denied("Authorization browser changed. Connect this Bud again.")
        previous = payload["dot"]
        dot, user = self.dot(payload["session"], previous["workspace_id"], previous["id"])
        if dot["version"] != previous["version"] or user != payload["user"]:
            raise Denied("Dot settings changed. Connect it again.")
        token, expires = self.providers["github"].exchange(code, payload["verifier"])
        prior = self.grant(dot, user, allow_stale=True)
        try:
            self.providers["github"].execute(token, dot["resource"], "repository")
            fresh, _ = self.dot(payload["session"], dot["workspace_id"], dot["id"])
            if fresh["version"] != dot["version"]:
                raise Denied("Dot settings changed. Connect it again.")
            with self.store.tx() as db:
                db.execute(
                    text(
                        "INSERT INTO dot_grants(dot,user_id,workspace,version,resource,"
                        "secret,expires,status) "
                        "VALUES(:d,:u,:w,:v,:r,:s,:e,'Connected') "
                        "ON CONFLICT(dot,user_id) DO UPDATE SET "
                        "version=:v,resource=:r,secret=:s,expires=:e,status='Connected',synced=0"
                    ),
                    {
                        "d": dot["id"],
                        "u": user,
                        "w": dot["workspace_id"],
                        "v": dot["version"],
                        "r": dot["resource"],
                        "s": self.store.cipher.encrypt(token.encode()).decode(),
                        "e": int(time.time()) + min(28800, max(1, expires)),
                    },
                )
            self.audit(dot, user, "authorized")
            if prior:
                previous = self.store.cipher.decrypt(prior["secret"].encode()).decode()
                if previous != token and not self.providers["github"].revoke(previous):
                    self.audit(dot, user, "superseded_revoke_pending")
        except Exception:
            self.providers["github"].revoke(token)
            raise

    def execute(self, token, workspace, calls, *, refresh=False):
        if len(calls) > 3 or not calls:
            raise Denied("Select between one and three tools.")
        results = []
        for call in calls:
            if "." in call["tool"] and hasattr(self, "connections"):
                results.append(
                    self.connections.execute(token, workspace, call["dot"], call["tool"])
                )
                continue
            dot, user = self.dot(token, workspace, call["dot"])
            if call["tool"] not in REGISTRY.get(dot["provider"], {}).get("tools", {}):
                raise Denied("This Bud cannot use the selected tool.")
            grant = self.grant(dot, user)
            if (
                not grant
                or grant["status"] not in {"Connected", "Syncing", "Error"}
                or grant["expires"] <= time.time()
            ):
                raise Denied("Needs authorization")
            secret = self.store.cipher.decrypt(grant["secret"].encode()).decode()
            cached = None if refresh else self.cached(dot, user, grant, call["tool"])
            try:
                result = cached or self.providers[dot["provider"]].execute(
                    secret, dot["resource"], call["tool"]
                )
            except Denied as exc:
                status = str(exc) if str(exc) in STATES else "Error"
                self.status(dot, user, status)
                if status == "Error":
                    prior = self.cached(dot, user, grant, call["tool"], stale=True)
                    if prior:
                        prior["read_failed_at"] = int(time.time())
                        self.cache(dot, user, grant, call["tool"], prior)
                self.audit(dot, user, "tool_failed:" + call["tool"])
                raise
            fresh, _ = self.dot(token, workspace, dot["id"])
            current = self.grant(fresh, user)
            if (
                fresh["version"] != dot["version"]
                or not current
                or current["secret"] != grant["secret"]
            ):
                raise Denied("The Bud was disconnected while working. Retry your request.")
            self.status(dot, user, "Connected", synced=result.get("fetched_at", int(time.time())))
            self.audit(dot, user, "read:" + call["tool"])
            evidence = {
                "dot": dot["id"],
                "name": dot["name"],
                "dot_version": dot["version"],
                "provider": dot["provider"],
                "tool": call["tool"],
                "citation": "dot:" + dot["id"] + ":" + call["tool"],
                **result,
                "fetched_at": result.get("fetched_at", int(time.time())),
            }
            if not cached:
                self.cache(dot, user, grant, call["tool"], evidence)
            results.append(evidence)
        return results

    def status(self, dot, user, value, synced=0):
        with self.store.tx() as db:
            db.execute(
                text(
                    "UPDATE dot_grants SET status=:s,synced=CASE WHEN :t>0 THEN :t ELSE synced END "
                    "WHERE dot=:d AND user_id=:u AND version=:v"
                ),
                {"s": value, "t": synced, "d": dot["id"], "u": user, "v": dot["version"]},
            )

    def remove(self, token, workspace, dot_id, version):
        dot, user = self.dot(token, workspace, dot_id)
        self.identity.require(token, workspace, billing=True)
        if dot["version"] != version:
            raise Denied("Dot changed. Refresh before removing.")
        self.identity.request(
            "/rest/v1/rpc/remove_workspace_dot",
            token,
            method="POST",
            data={"p_id": dot_id, "p_workspace": workspace, "p_version": version},
        )
        with self.store.tx() as db:
            grants = (
                db.execute(
                    text("SELECT secret FROM dot_grants WHERE dot=:d AND workspace=:w"),
                    {"d": dot_id, "w": workspace},
                )
                .scalars()
                .all()
            )
            db.execute(
                text("DELETE FROM dot_grants WHERE dot=:d AND workspace=:w"),
                {"d": dot_id, "w": workspace},
            )
            db.execute(
                text("DELETE FROM dot_evidence_cache WHERE dot=:d AND workspace=:w"),
                {"d": dot_id, "w": workspace},
            )
        token_connections = False
        if hasattr(self, "connections"):
            with self.store.tx() as db:
                token_connections = bool(
                    db.execute(
                        text("SELECT count(*) FROM bud_connections WHERE dot=:d AND workspace=:w"),
                        {"d": dot_id, "w": workspace},
                    ).scalar()
                )
                db.execute(
                    text("DELETE FROM bud_connections WHERE dot=:d AND workspace=:w"),
                    {"d": dot_id, "w": workspace},
                )
        revoked = all(
            [
                self.providers[dot["provider"]].revoke(
                    self.store.cipher.decrypt(secret.encode()).decode()
                )
                for secret in grants
            ]
        )
        revoked = revoked and not token_connections
        self.audit(dot, user, "removed" if revoked else "removed_revoke_pending")
        return {"removed": True, "provider_revoked": revoked}

    def disconnect(self, token, workspace, dot_id):
        dot, user = self.dot(token, workspace, dot_id)
        grant = self.grant(dot, user, allow_stale=True)
        with self.store.tx() as db:
            db.execute(
                text("DELETE FROM dot_grants WHERE dot=:d AND user_id=:u"),
                {"d": dot["id"], "u": user},
            )
            db.execute(
                text("DELETE FROM dot_evidence_cache WHERE dot=:d AND user_id=:u"),
                {"d": dot["id"], "u": user},
            )
        revoked = True
        if grant:
            revoked = self.providers[dot["provider"]].revoke(
                self.store.cipher.decrypt(grant["secret"].encode()).decode()
            )
        self.audit(dot, user, "disconnected" if revoked else "disconnected_revoke_pending")
        return {"status": "Disconnected", "provider_revoked": revoked}


class DotBody(BaseModel):
    model_config = {"extra": "forbid"}
    workspace: UUID
    dot: UUID


class RemoveBody(DotBody):
    version: int = Field(ge=1, strict=True)


class ToolCall(BaseModel):
    model_config = {"extra": "forbid"}
    dot: UUID
    tool: str = Field(min_length=1, max_length=96)


class ToolsBody(BaseModel):
    model_config = {"extra": "forbid"}
    workspace: UUID
    calls: list[ToolCall] = Field(min_length=1, max_length=3)


def install(app, config, store, identity, auth):
    service = DotService(config, store, identity)
    app.state.dots = service
    from aedrova_site.bud_connections import install as install_connections

    install_connections(app, service, auth)

    from aedrova_site.bud_providers import CATALOG, descriptor

    @app.get("/api/dots/providers")
    def providers(request: Request):
        identity.user(auth(request))
        return {
            "providers": [
                {
                    "id": key,
                    **value,
                    "configurable": key == "github",
                    "available": bool(
                        config.dots_enabled and key == "github" and config.github_dot_client_secret
                    ),
                }
                for key, value in REGISTRY.items()
                if key == "github" or key not in CATALOG
            ]
            + [
                {**descriptor(key), "available": config.dots_enabled}
                for key in CATALOG
                if key != "github"
            ]
        }

    @app.get("/api/dots")
    def dots(request: Request, workspace: UUID):
        return {"items": service.list(auth(request), str(workspace))}

    @app.post("/api/dots/connect")
    def connect(request: Request, body: DotBody):
        return {
            "url": service.start(auth(request, change=True), str(body.workspace), str(body.dot))
        }

    @app.post("/api/dots/disconnect")
    def disconnect(request: Request, body: DotBody):
        return service.disconnect(auth(request, change=True), str(body.workspace), str(body.dot))

    @app.post("/api/dots/remove")
    def remove(request: Request, body: RemoveBody):
        return service.remove(
            auth(request, change=True), str(body.workspace), str(body.dot), body.version
        )

    @app.post("/api/dots/tools")
    def tools(request: Request, body: ToolsBody):
        store.rate_limit("dots:" + hashlib.sha256(auth(request).encode()).hexdigest(), limit=20)
        return {
            "results": service.execute(
                auth(request, change=True),
                str(body.workspace),
                [{"dot": str(c.dot), "tool": c.tool} for c in body.calls],
            )
        }

    @app.get("/dots/authorize/{state}")
    def authorize(request: Request, state: str):
        service.enabled()
        payload = service.state(state, peek=True)
        try:
            browser_user = identity.user(auth(request))["id"]
        except Denied:
            return RedirectResponse("/auth/google?" + urlencode({"dot": state}), status_code=303)
        if browser_user != payload["user"]:
            raise Denied(
                "Sign in to the Aedrova website with the same account as your desktop app."
            )
        payload = service.state(state)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(payload["verifier"].encode()).digest())
            .decode()
            .rstrip("=")
        )
        response = RedirectResponse(
            "https://github.com/login/oauth/authorize?"
            + urlencode(
                {
                    "client_id": config.github_dot_client_id,
                    "redirect_uri": config.origin + "/dots/github/callback",
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )
        response.set_cookie(
            "aedrova_dot_state",
            payload["proof"],
            httponly=True,
            secure=config.origin.startswith("https"),
            samesite="lax",
            max_age=600,
            path="/dots/github",
        )
        return response

    @app.get("/dots/github/callback")
    def callback(request: Request, state: str = "", code: str = ""):
        service.enabled()
        bud = service.state(state, peek=True)["dot"]
        service.callback(state, request.cookies.get("aedrova_dot_state", ""), code)
        from aedrova_site.connection_confirmation import confirmation

        response = confirmation(request, "github", bud)
        response.delete_cookie("aedrova_dot_state", path="/dots/github")
        return response

    @app.post("/dots/github/events")
    async def events(request: Request):
        service.enabled()
        body = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        if (
            not config.github_dot_webhook_secret
            or len(body) > 512 * 1024
            or not hmac.compare_digest(
                signature,
                "sha256="
                + hmac.new(
                    config.github_dot_webhook_secret.encode(), body, hashlib.sha256
                ).hexdigest(),
            )
        ):
            raise Denied("Invalid provider event.")
        delivery = request.headers.get("x-github-delivery", "")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", delivery):
            raise Denied("Invalid provider event.")
        try:
            repo = resource(json.loads(body).get("repository", {}).get("full_name", ""))
        except (ValueError, AttributeError):
            raise Denied("Invalid provider event.") from None
        with store.tx() as db:
            result = db.execute(
                text("INSERT INTO events(id,created) VALUES(:id,:t) ON CONFLICT(id) DO NOTHING"),
                {"id": "dot-github:" + delivery, "t": int(time.time())},
            )
            if result.rowcount:
                db.execute(text("UPDATE dot_grants SET synced=0 WHERE resource=:r"), {"r": repo})
        return {"accepted": True}
