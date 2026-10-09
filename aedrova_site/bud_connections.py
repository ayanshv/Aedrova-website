"""Multiple private, revocable resource grants for a shared Bud identity."""

import hashlib
import json
import time
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import inspect, text

from aedrova_site.bud_providers import CATALOG, ReadProvider, descriptor, validate_resource
from aedrova_site.store import Denied

SCHEMA = """CREATE TABLE IF NOT EXISTS bud_connections (
 id TEXT PRIMARY KEY, dot TEXT NOT NULL, workspace TEXT NOT NULL, user_id TEXT NOT NULL,
 provider TEXT NOT NULL, resource TEXT NOT NULL, dot_version INTEGER NOT NULL,
 secret TEXT NOT NULL, expires BIGINT NOT NULL, synced BIGINT NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'Connected',
 UNIQUE(dot,user_id,provider,resource))"""


class BudConnections:
    def __init__(self, dots, *, transport=None):
        self.dots, self.store = dots, dots.store
        self.providers = {
            key: ReadProvider(key, transport=transport) for key in CATALOG if key != "github"
        }
        # Reuse the existing bounded GitHub reader; token-based access does not invoke OAuth.
        self.providers["github"] = dots.providers["github"]
        with self.store.tx() as db:
            if self.store.engine.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73114012)"))
            db.execute(text(SCHEMA))
            if "status" not in {
                column["name"] for column in inspect(db).get_columns("bud_connections")
            }:
                db.execute(
                    text(
                        "ALTER TABLE bud_connections ADD COLUMN status "
                        "TEXT NOT NULL DEFAULT 'Connected'"
                    )
                )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS bud_connections_scope "
                    "ON bud_connections(workspace,dot,user_id)"
                )
            )

    def close(self):
        if hasattr(self, "oauth"):
            self.oauth.close()
        for key, provider in self.providers.items():
            if key != "github":
                provider.close()

    def rows(self, dot, user):
        with self.store.tx() as db:
            db.execute(
                text("DELETE FROM bud_connections WHERE expires<:t"), {"t": int(time.time())}
            )
            rows = (
                db.execute(
                    text(
                        "SELECT * FROM bud_connections WHERE dot=:d AND workspace=:w AND user_id=:u"
                    ),
                    {"d": dot["id"], "w": dot["workspace_id"], "u": user},
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]

    def listing(self, dot, user):
        return [
            {
                "id": r["id"],
                "provider": r["provider"],
                "resource": r["resource"],
                "expires": r["expires"],
                "last_sync": r["synced"],
                "status": r["status"]
                if r["dot_version"] == dot["version"]
                else "Needs authorization",
                "tools": CATALOG[r["provider"]][4],
                "version": r["id"],
            }
            for r in self.rows(dot, user)
        ]

    def connect(
        self,
        session,
        workspace,
        dot_id,
        provider,
        resource,
        credential,
        hours,
        *,
        oauth=None,
        expected_version=None,
    ):
        dot, user = self.dots.dot(session, workspace, dot_id)
        dot = dict(dot)
        if expected_version is not None and dot["version"] != expected_version:
            raise Denied("Bud settings changed during authorization. Try again.")
        resource = validate_resource(provider, resource)
        if not 8 <= len(credential) <= 4096 or any(c.isspace() for c in credential):
            raise Denied("Enter a valid access token without spaces.")
        if not 1 <= hours <= 2160:
            raise Denied("Choose an access lifetime from 1 hour to 90 days.")
        # A successful real API read is mandatory; no optimistic 'Connected' state.
        for tool in CATALOG[provider][4]:
            self.read(provider, credential, resource, tool, oauth=bool(oauth))
        fresh, fresh_user = self.dots.dot(session, workspace, dot_id)
        if fresh["version"] != dot["version"] or fresh_user != user:
            raise Denied("Bud settings changed during authorization. Try again.")
        connection_id = str(uuid4())
        with self.store.tx() as db:
            if self.store.engine.dialect.name == "postgresql":
                lock = int(hashlib.sha256((dot_id + user).encode()).hexdigest()[:15], 16)
                db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock})
            count = db.execute(
                text("SELECT count(*) FROM bud_connections WHERE dot=:d AND user_id=:u"),
                {"d": dot_id, "u": user},
            ).scalar()
            existing = db.execute(
                text(
                    "SELECT id FROM bud_connections WHERE dot=:d AND user_id=:u "
                    "AND provider=:p AND resource=:r"
                ),
                {"d": dot_id, "u": user, "p": provider, "r": resource},
            ).scalar()
            if count >= 12 and not existing:
                raise Denied("Each Bud supports up to 12 connected resources per account.")
            db.execute(
                text(
                    "INSERT INTO bud_connections(id,dot,workspace,user_id,provider,resource,"
                    "dot_version,secret,expires) VALUES(:id,:d,:w,:u,:p,:r,:v,:s,:e) "
                    "ON CONFLICT(dot,user_id,provider,resource) DO UPDATE SET "
                    "id=:id,dot_version=:v,secret=:s,expires=:e,synced=0,status='Connected'"
                ),
                {
                    "id": connection_id,
                    "d": dot_id,
                    "w": workspace,
                    "u": user,
                    "p": provider,
                    "r": resource,
                    "v": dot["version"],
                    "s": self.store.cipher.encrypt(
                        (json.dumps(oauth) if oauth else credential).encode()
                    ).decode(),
                    "e": int(time.time()) + hours * 3600,
                },
            )
        self.dots.audit(dot, user, "connector_authorized:" + provider)
        return {"connected": True, "id": connection_id}

    def read(self, provider, access, resource, tool, *, oauth=False):
        if provider == "github" or not oauth:
            return self.providers[provider].execute(access, resource, tool)
        return self.providers[provider].execute(access, resource, tool, oauth=True)

    def access(self, grant, *, force=False):
        """Serialize token rotation without ever recreating a disconnected grant."""
        secret = self.store.cipher.decrypt(grant["secret"].encode()).decode()
        if not secret.startswith("{"):
            return grant, secret, False
        envelope = json.loads(secret)
        if not force and envelope["token_expires"] > int(time.time()) + 60:
            return grant, envelope["access"], True
        # Row locks serialize refresh across server workers; SQLite uses BEGIN IMMEDIATE.
        with self.store.tx() as db:
            suffix = " FOR UPDATE" if self.store.engine.dialect.name == "postgresql" else ""
            current = (
                db.execute(
                    text("SELECT * FROM bud_connections WHERE id=:i" + suffix), {"i": grant["id"]}
                )
                .mappings()
                .first()
            )
            if (
                not current
                or current["secret"] != grant["secret"]
                or current["expires"] <= int(time.time())
            ):
                if current and current["expires"] > int(time.time()):
                    latest = json.loads(self.store.cipher.decrypt(current["secret"].encode()))
                    return dict(current), latest["access"], True
                raise Denied("Needs authorization")
            if not envelope["refresh"]:
                raise Denied("Needs authorization")
            refreshed = self.oauth.token(grant["provider"], refresh=envelope["refresh"])
            encoded = self.store.cipher.encrypt(json.dumps(refreshed).encode()).decode()
            result = db.execute(
                text("UPDATE bud_connections SET secret=:s WHERE id=:i AND secret=:old"),
                {"s": encoded, "i": grant["id"], "old": grant["secret"]},
            )
            if result.rowcount != 1:
                raise Denied("Needs authorization")
            grant = {**grant, "secret": encoded}
        return grant, refreshed["access"], True

    def disconnect(self, session, workspace, dot_id, connection_id):
        dot, user = self.dots.dot(session, workspace, dot_id)
        with self.store.tx() as db:
            result = db.execute(
                text(
                    "DELETE FROM bud_connections WHERE id=:id AND dot=:d "
                    "AND workspace=:w AND user_id=:u"
                ),
                {"id": str(UUID(connection_id)), "d": dot_id, "w": workspace, "u": user},
            )
        if result.rowcount != 1:
            raise Denied("This connection is no longer available to your account.")
        self.dots.audit(dot, user, "connector_disconnected")
        # API tokens cannot generally be revoked by the consumer. Be explicit about that.
        return {"disconnected": True, "provider_revoked": False}

    def execute(self, session, workspace, dot_id, composite):
        dot, user = self.dots.dot(session, workspace, dot_id)
        connection_id, _, tool = composite.partition(".")
        try:
            connection_id = str(UUID(connection_id))
        except ValueError:
            raise Denied("Invalid connector selection.") from None
        grant = next((r for r in self.rows(dot, user) if r["id"] == connection_id), None)
        if (
            not grant
            or grant["dot_version"] != dot["version"]
            or grant["status"] not in {"Connected", "Error"}
        ):
            raise Denied("Needs authorization")
        try:
            grant, secret, oauth = self.access(grant)
            try:
                evidence = self.read(
                    grant["provider"], secret, grant["resource"], tool, oauth=oauth
                )
            except Denied as error:
                if not oauth or str(error) != "Needs authorization":
                    raise
                grant, secret, oauth = self.access(grant, force=True)
                evidence = self.read(
                    grant["provider"], secret, grant["resource"], tool, oauth=oauth
                )
        except Denied as exc:
            state = str(exc) if str(exc) in {"Needs authorization", "Permission issue"} else "Error"
            with self.store.tx() as db:
                db.execute(
                    text(
                        "UPDATE bud_connections SET status=:s WHERE id=:id AND user_id=:u "
                        "AND secret=:secret"
                    ),
                    {"s": state, "id": connection_id, "u": user, "secret": grant["secret"]},
                )
            self.dots.audit(dot, user, "connector_failed:" + grant["provider"] + ":" + tool)
            raise
        if oauth:
            envelope = json.loads(self.store.cipher.decrypt(grant["secret"].encode()))
            serialized = json.dumps(evidence)
            if any(envelope.get(k) and envelope[k] in serialized for k in ("access", "refresh")):
                raise Denied("Provider data contains sensitive credentials and was withheld.")
        fresh, fresh_user = self.dots.dot(session, workspace, dot_id)
        current = next((r for r in self.rows(fresh, fresh_user) if r["id"] == connection_id), None)
        if (
            not current
            or fresh["version"] != dot["version"]
            or current["secret"] != grant["secret"]
        ):
            raise Denied("The connector was disconnected while working. Retry your request.")
        now = int(time.time())
        with self.store.tx() as db:
            db.execute(
                text(
                    "UPDATE bud_connections SET synced=:t,status='Connected' "
                    "WHERE id=:id AND user_id=:u"
                ),
                {"t": now, "id": connection_id, "u": user},
            )
        self.dots.audit(dot, user, "connector_read:" + grant["provider"] + ":" + tool)
        return {
            **evidence,
            "dot": dot_id,
            "name": dot["name"],
            "dot_version": dot["version"],
            "connection_id": connection_id,
            "connection_version": connection_id,
            "provider": grant["provider"],
            "resource": grant["resource"],
            "tool": tool,
            "fetched_at": now,
            "citation": "bud:" + dot_id + ":" + connection_id + ":" + tool,
        }


class ConnectionBody(BaseModel):
    model_config = {"extra": "forbid"}
    workspace: UUID
    dot: UUID
    provider: str = Field(min_length=1, max_length=40)
    resource: str = Field(min_length=1, max_length=200)
    credential: SecretStr
    hours: int = Field(default=24, ge=1, le=2160, strict=True)


class DisconnectBody(BaseModel):
    model_config = {"extra": "forbid"}
    workspace: UUID
    dot: UUID
    connection: UUID


def install(app, dots, auth):
    service = BudConnections(dots)
    dots.connections = service
    from aedrova_site.bud_oauth import PROVIDERS
    from aedrova_site.bud_oauth import install as install_oauth

    install_oauth(app, service, auth)

    @app.get("/api/buds/connectors")
    def catalog(request: Request):
        dots.identity.user(auth(request))
        return {
            "providers": [
                {
                    **descriptor(key),
                    "available": dots.config.dots_enabled,
                    "oauth_available": service.oauth.available(key),
                    "oauth_supported": key in PROVIDERS,
                    "oauth_setup_hint": service.oauth.setup_hint(key),
                }
                for key in CATALOG
            ]
        }

    @app.get("/api/buds/connections")
    def connections(request: Request, workspace: UUID, dot: UUID):
        row, user = dots.dot(auth(request), str(workspace), str(dot))
        return {"items": service.listing(row, user)}

    @app.post("/api/buds/connections")
    def connect(request: Request, body: ConnectionBody):
        token = auth(request, change=True)
        dots.store.rate_limit("bud-connect:" + hashlib.sha256(token.encode()).hexdigest(), limit=10)
        return service.connect(
            token,
            str(body.workspace),
            str(body.dot),
            body.provider,
            body.resource,
            body.credential.get_secret_value(),
            body.hours,
        )

    @app.post("/api/buds/connections/disconnect")
    def disconnect(request: Request, body: DisconnectBody):
        return service.disconnect(
            auth(request, change=True), str(body.workspace), str(body.dot), str(body.connection)
        )
