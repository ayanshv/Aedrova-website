"""Scoped drafts and approvals; only an explicit dispatch route can publish."""

import hashlib
import ipaddress
import json
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from aedrova_site.social.providers import BufferAdapter, Uncertain
from aedrova_site.store import Denied

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS social_channels (
      connection TEXT NOT NULL, channel TEXT NOT NULL, permission TEXT NOT NULL,
      metadata TEXT NOT NULL, PRIMARY KEY(connection,channel))""",
    """CREATE TABLE IF NOT EXISTS social_posts (
      id TEXT PRIMARY KEY, workspace TEXT NOT NULL, dot TEXT NOT NULL, user_id TEXT NOT NULL,
      connection TEXT NOT NULL, channel TEXT NOT NULL, revision INTEGER NOT NULL,
      body TEXT NOT NULL, state TEXT NOT NULL, approval TEXT NOT NULL DEFAULT '',
      provider_id TEXT NOT NULL DEFAULT '', provider_status TEXT NOT NULL DEFAULT '',
      error TEXT NOT NULL DEFAULT '', created BIGINT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS social_posts_scope ON social_posts(workspace,dot,user_id,created)",
]


def media_url(value):
    try:
        if any(ord(c) < 33 for c in value):
            raise ValueError("Control character")
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname or ""
    except ValueError:
        raise Denied("Use a valid public HTTPS media URL.") from None
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.fragment
        or parsed.query
        or host.lower() == "localhost"
        or "." not in host
        or host.lower().endswith((".local", ".internal"))
    ):
        raise Denied(
            "Media needs a stable public HTTPS URL without credentials or expiry parameters."
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise Denied("Use a public media host.")
    return value


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: UUID
    dot: UUID


class ChannelSelection(Scope):
    connection: UUID
    channels: list[str] = Field(max_length=50)


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(image|video)$")
    url: str = Field(min_length=8, max_length=2000)


class Draft(Scope):
    id: UUID
    connection: UUID
    channel: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(default=0, ge=0)
    text: str = Field(min_length=1, max_length=10000)
    action: str = Field(pattern="^(publish|schedule)$")
    due_at: datetime | None = None
    assets: list[Asset] = Field(default_factory=list, max_length=4)


class PostAction(Scope):
    id: UUID
    revision: int = Field(ge=1)


class SocialService:
    def __init__(self, connections, *, adapter=None):
        self.connections, self.dots, self.store = connections, connections.dots, connections.store
        self.adapters = {"buffer": adapter or BufferAdapter()}
        with self.store.tx() as db:
            if self.store.engine.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73114013)"))
            for statement in SCHEMA:
                db.execute(text(statement))

    def close(self):
        for adapter in self.adapters.values():
            adapter.close()

    def scope(self, session, workspace, bud):
        if not self.dots.config.social_publishing_enabled:
            raise Denied("Social publishing is not enabled on this service yet.")
        return self.dots.dot(session, str(workspace), str(bud))

    def grant(self, dot, user, connection):
        grant = next(
            (r for r in self.connections.rows(dot, user) if r["id"] == str(connection)), None
        )
        if (
            not grant
            or grant["provider"] not in self.adapters
            or grant["dot_version"] != dot["version"]
            or grant["status"] != "Connected"
        ):
            raise Denied("Reconnect the publishing provider for this account and Bud.")
        grant, token, _ = self.connections.access(grant)
        return grant, token, self.adapters[grant["provider"]]

    def permission(self, db, connection, channel):
        row = (
            db.execute(
                text("SELECT * FROM social_channels WHERE connection=:c AND channel=:h"),
                {"c": str(connection), "h": channel},
            )
            .mappings()
            .first()
        )
        if not row:
            raise Denied("Select this social channel before preparing a post.")
        return dict(row)

    def channels(self, session, workspace, bud):
        dot, user = self.scope(session, workspace, bud)
        items = []
        for row in self.connections.rows(dot, user):
            if row["provider"] not in self.adapters:
                continue
            grant, token, adapter = self.grant(dot, user, row["id"])
            with self.store.tx() as db:
                selected = set(
                    db.execute(
                        text("SELECT channel FROM social_channels WHERE connection=:c"),
                        {"c": row["id"]},
                    ).scalars()
                )
            items.extend(
                {**channel, "connection": grant["id"], "selected": channel["id"] in selected}
                for channel in adapter.get_connected_accounts(token, grant["resource"])
            )
        return {
            "channels": items,
            "analytics_available": False,
            "notice": (
                "Metrics are unavailable for Buffer OAuth apps. "
                "Scheduled posts remain in Buffer after disconnect."
            ),
        }

    def select(self, session, body):
        dot, user = self.scope(session, body.workspace, body.dot)
        grant, token, adapter = self.grant(dot, user, body.connection)
        available = {r["id"]: r for r in adapter.get_connected_accounts(token, grant["resource"])}
        if any(c not in available or not available[c]["can_publish"] for c in body.channels):
            raise Denied("Choose available channels with publishing permission.")
        # Recheck the grant in the write transaction; a concurrent disconnect must win.
        with self.store.tx() as db:
            self.lock_grant(db, grant)
            db.execute(text("DELETE FROM social_channels WHERE connection=:c"), {"c": grant["id"]})
            for channel in set(body.channels):
                db.execute(
                    text("INSERT INTO social_channels VALUES(:c,:h,:p,:m)"),
                    {
                        "c": grant["id"],
                        "h": channel,
                        "p": str(uuid4()),
                        "m": json.dumps(available[channel]),
                    },
                )
            db.execute(
                text(
                    "UPDATE social_posts SET state='draft',approval='' "
                    "WHERE connection=:c AND state='approved'"
                ),
                {"c": grant["id"]},
            )
        return {"selected": len(set(body.channels))}

    def lock_grant(self, db, grant):
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
            or current["status"] != "Connected"
            or current["expires"] <= time.time()
        ):
            raise Denied("The connection changed. Reconnect and review the post again.")

    def post(self, db, dot, user, identifier):
        suffix = " FOR UPDATE" if self.store.engine.dialect.name == "postgresql" else ""
        row = (
            db.execute(
                text(
                    "SELECT * FROM social_posts WHERE id=:i AND workspace=:w "
                    "AND dot=:d AND user_id=:u" + suffix
                ),
                {"i": str(identifier), "w": dot["workspace_id"], "d": dot["id"], "u": user},
            )
            .mappings()
            .first()
        )
        if not row:
            raise Denied("Post not found in your account and workspace.")
        return dict(row)

    def encode(self, body):
        return self.store.cipher.encrypt(json.dumps(body, sort_keys=True).encode()).decode()

    def decode(self, row):
        return json.loads(self.store.cipher.decrypt(row["body"].encode()))

    def fingerprint(self, row):
        return hashlib.sha256(
            json.dumps(
                {"body": self.decode(row), "revision": row["revision"]}, sort_keys=True
            ).encode()
        ).hexdigest()

    def public(self, row):
        if row["state"] == "sending":
            row = {
                **row,
                "state": "unknown",
                "error": "Submission is unconfirmed. Check Buffer before creating another post.",
            }
        return {
            k: row[k]
            for k in (
                "id",
                "connection",
                "channel",
                "revision",
                "state",
                "provider_id",
                "provider_status",
                "error",
            )
        } | {"content": self.decode(row)}

    def save(self, session, body):
        dot, user = self.scope(session, body.workspace, body.dot)
        grant, _, _ = self.grant(dot, user, body.connection)
        if not body.text.strip() or any(ord(c) < 32 and c not in "\n\t" for c in body.text):
            raise Denied("Enter valid post text.")
        from aedrova_site.credential_patterns import credential_rules

        if credential_rules(body.text.encode()):
            raise Denied("Remove credentials from post text.")
        due = body.due_at
        if body.action == "schedule" and (
            not due
            or due.tzinfo is None
            or not time.time() + 60 <= due.timestamp() <= time.time() + 366 * 86400
        ):
            raise Denied("Choose a timezone-aware future time within one year.")
        if body.action == "publish" and due is not None:
            raise Denied("Immediate publishing cannot include a scheduled time.")
        with self.store.tx() as db:
            self.lock_grant(db, grant)
            permission = self.permission(db, grant["id"], body.channel)
            channel = json.loads(permission["metadata"])
            # Validate platform requirements using explicit basic formats; provider
            # validation remains authoritative for plan and channel-specific limits.
            if (
                channel["platform"] in {"instagram", "tiktok", "youtube", "pinterest"}
                and not body.assets
            ):
                raise Denied("This platform needs an image or video asset.")
            if channel["platform"] in {"tiktok", "youtube"} and (
                len(body.assets) != 1 or body.assets[0].kind != "video"
            ):
                raise Denied("Choose one public video for this platform.")
            content = dict(
                text=body.text.strip(),
                action=body.action,
                due_at=due.astimezone(UTC).isoformat() if due else None,
                assets=[dict(kind=a.kind, url=media_url(a.url)) for a in body.assets],
                permission=permission["permission"],
                platform=channel["platform"],
                channel_name=channel["name"],
                dot_version=dot["version"],
            )
            existing = db.execute(
                text("SELECT id FROM social_posts WHERE id=:i"), {"i": str(body.id)}
            ).first()
            if existing:
                previous = self.post(db, dot, user, body.id)
                if (
                    previous["connection"] == grant["id"]
                    and previous["channel"] == body.channel
                    and self.decode(previous) == content
                    and previous["revision"] == body.revision + 1
                ):
                    return self.public(previous)  # Lost save response; no second draft.
                if previous["revision"] != body.revision or previous["state"] not in {
                    "draft",
                    "approved",
                    "rejected",
                }:
                    raise Denied("Post changed or was already dispatched. Refresh before editing.")
                db.execute(
                    text(
                        "UPDATE social_posts SET body=:b,connection=:c,channel=:h,"
                        "revision=revision+1,"
                        "state='draft',approval='',error='' WHERE id=:i"
                    ),
                    {
                        "b": self.encode(content),
                        "c": grant["id"],
                        "h": body.channel,
                        "i": str(body.id),
                    },
                )
            else:
                if body.revision:
                    raise Denied("Draft revision is invalid.")
                db.execute(
                    text(
                        "INSERT INTO social_posts(id,workspace,dot,user_id,connection,"
                        "channel,revision,"
                        "body,state,created) VALUES(:i,:w,:d,:u,:c,:h,1,:b,'draft',:t)"
                    ),
                    {
                        "i": str(body.id),
                        "w": dot["workspace_id"],
                        "d": dot["id"],
                        "u": user,
                        "c": grant["id"],
                        "h": body.channel,
                        "b": self.encode(content),
                        "t": int(time.time()),
                    },
                )
            return self.public(self.post(db, dot, user, body.id))

    def decide(self, session, body, *, approve):
        dot, user = self.scope(session, body.workspace, body.dot)
        with self.store.tx() as db:
            row = self.post(db, dot, user, body.id)
            if row["revision"] != body.revision or row["state"] not in {
                "draft",
                "approved",
                "rejected",
            }:
                raise Denied("Refresh and review the current draft before approval.")
            state = "approved" if approve else "rejected"
            db.execute(
                text("UPDATE social_posts SET state=:s,approval=:a WHERE id=:i"),
                {"s": state, "a": self.fingerprint(row) if approve else "", "i": row["id"]},
            )
        self.dots.audit(dot, user, "social_" + state)
        return {"state": state}

    def dispatch(self, session, body):
        dot, user = self.scope(session, body.workspace, body.dot)
        with self.store.tx() as db:
            row = self.post(db, dot, user, body.id)
        if row["revision"] != body.revision:
            raise Denied("Review the latest draft first.")
        if row["state"] in {"sending", "submitted", "unknown"}:
            return self.public(row)  # An ambiguous request is never sent again.
        grant, token, adapter = self.grant(dot, user, row["connection"])
        channels = adapter.get_connected_accounts(token, grant["resource"])
        if not any(
            c["id"] == row["channel"] and c["can_publish"] and not c["paused"] for c in channels
        ):
            raise Denied(
                "The selected channel is disconnected, locked, paused or no longer writable."
            )
        with self.store.tx() as db:
            self.lock_grant(db, grant)
            row = self.post(db, dot, user, body.id)
            content = self.decode(row)
            permission = self.permission(db, row["connection"], row["channel"])
            if (
                row["state"] != "approved"
                or row["revision"] != body.revision
                or row["approval"] != self.fingerprint(row)
                or content["dot_version"] != dot["version"]
                or content["permission"] != permission["permission"]
            ):
                raise Denied("Approve the exact content, channel and time before publishing.")
            if (
                content["due_at"]
                and datetime.fromisoformat(content["due_at"]).timestamp() <= time.time()
            ):
                raise Denied("The scheduled time passed. Edit and approve a new time.")
            db.execute(
                text("UPDATE social_posts SET state='sending' WHERE id=:i"), {"i": row["id"]}
            )
        # Durable claim precedes any external write. Crash/timeout cannot replay it.
        state, result, error = "unknown", {}, "Check Buffer before resubmitting this post."
        try:
            fresh, fresh_user = self.scope(session, body.workspace, body.dot)
            if fresh_user != user or fresh["version"] != dot["version"]:
                raise Denied("Bud settings changed. No post was submitted.")
            with self.store.tx() as db:
                self.lock_grant(db, grant)
                # Disconnect and channel deselection serialize with this request.
                current_permission = self.permission(db, row["connection"], row["channel"])
                if current_permission["permission"] != content["permission"]:
                    raise Denied("Channel selection changed. No post was submitted.")
                request = dict(
                    channel=row["channel"],
                    text=content["text"],
                    assets=content["assets"],
                )
                if content["action"] == "schedule":
                    result = adapter.schedule_post(token, {**request, "due_at": content["due_at"]})
                else:
                    result = adapter.publish_post(token, request)
            state, error = "submitted", ""
        except Uncertain as exc:
            error = str(exc)
        except Denied as exc:
            state, error = "rejected", str(exc)
        finally:
            with self.store.tx() as db:
                db.execute(
                    text(
                        "UPDATE social_posts SET state=:s,provider_id=:p,"
                        "provider_status=:ps,error=:e "
                        "WHERE id=:i AND state='sending'"
                    ),
                    {
                        "s": state,
                        "p": result.get("id", ""),
                        "ps": result.get("status", ""),
                        "e": error,
                        "i": row["id"],
                    },
                )
        self.dots.audit(dot, user, "social_dispatch_" + state)
        return self.list_posts(session, body.workspace, body.dot, identifier=row["id"])["posts"][0]

    def list_posts(self, session, workspace, bud, *, identifier=None):
        dot, user = self.scope(session, workspace, bud)
        with self.store.tx() as db:
            rows = (
                db.execute(
                    text(
                        "SELECT * FROM social_posts WHERE workspace=:w AND dot=:d "
                        "AND user_id=:u ORDER BY created DESC,id DESC LIMIT 100"
                    ),
                    {"w": dot["workspace_id"], "d": dot["id"], "u": user},
                )
                .mappings()
                .all()
            )
        return {
            "posts": [
                self.public(dict(r)) for r in rows if identifier is None or r["id"] == identifier
            ]
        }

    def status(self, session, body):
        dot, user = self.scope(session, body.workspace, body.dot)
        with self.store.tx() as db:
            row = self.post(db, dot, user, body.id)
        if not row["provider_id"]:
            return self.public(row)
        grant, token, adapter = self.grant(dot, user, row["connection"])
        result = adapter.get_post_status(token, row["provider_id"])
        if result["channel_id"] != row["channel"]:
            raise Denied("The provider returned a different destination.")
        with self.store.tx() as db:
            db.execute(
                text("UPDATE social_posts SET provider_status=:s WHERE id=:i"),
                {"s": result["status"], "i": row["id"]},
            )
        return {**self.public(row), "provider_status": result["status"]}


def install(app, connections, auth):
    service = SocialService(connections)
    connections.social = service

    def session(request, *, change=False):
        value = auth(request, change=change)
        connections.store.rate_limit(
            "social:" + hashlib.sha256(value.encode()).hexdigest(), limit=30
        )
        return value

    @app.get("/api/buds/social/capabilities")
    def capabilities(request: Request, workspace: UUID, dot: UUID):
        connections.dots.dot(session(request), str(workspace), str(dot))
        return {
            "available": connections.oauth.available("buffer"),
            "analytics_available": False,
            "setup_hint": connections.oauth.setup_hint("buffer"),
        }

    @app.get("/api/buds/social/channels")
    def channels(request: Request, workspace: UUID, dot: UUID):
        return service.channels(session(request), workspace, dot)

    @app.post("/api/buds/social/channels")
    def select(request: Request, body: ChannelSelection):
        return service.select(session(request, change=True), body)

    @app.get("/api/buds/social/posts")
    def posts(request: Request, workspace: UUID, dot: UUID):
        return service.list_posts(session(request), workspace, dot)

    @app.post("/api/buds/social/drafts")
    def save(request: Request, body: Draft):
        return service.save(session(request, change=True), body)

    @app.post("/api/buds/social/approve")
    def approve(request: Request, body: PostAction):
        return service.decide(session(request, change=True), body, approve=True)

    @app.post("/api/buds/social/reject")
    def reject(request: Request, body: PostAction):
        return service.decide(session(request, change=True), body, approve=False)

    @app.post("/api/buds/social/dispatch")
    def dispatch(request: Request, body: PostAction):
        return service.dispatch(session(request, change=True), body)

    @app.post("/api/buds/social/status")
    def status(request: Request, body: PostAction):
        return service.status(session(request, change=True), body)
