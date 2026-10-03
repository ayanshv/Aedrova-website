"""Durable, encrypted call leases. JWT expiry alone never disconnects a live call."""

import asyncio
import time

from livekit import api
from sqlalchemy import text

from aedrova_site.store import Denied

LEASE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS meeting_leases (
        room TEXT NOT NULL, user_id TEXT NOT NULL, meeting TEXT NOT NULL,
        token TEXT NOT NULL, expires BIGINT NOT NULL, state TEXT NOT NULL,
        PRIMARY KEY(room,user_id))""",
    """CREATE TABLE IF NOT EXISTS meeting_guard_health (
        role TEXT PRIMARY KEY, checked BIGINT NOT NULL, healthy INTEGER NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS meeting_lease_lookup ON meeting_leases(meeting,user_id)",
    "CREATE INDEX IF NOT EXISTS meeting_active_scan ON meeting_leases(room,user_id) "
    "WHERE state!='revoked'",
]

RESERVE_LEASE = """INSERT INTO meeting_leases VALUES(:room,:user,:meeting,
    :token,:expires,'active') ON CONFLICT(room,user_id) DO UPDATE SET
    meeting=:meeting,token=:token,expires=:expires,state='active'
    WHERE meeting_leases.state='revoked' AND meeting_leases.expires<=:now
    RETURNING user_id"""


class MeetingLeases:
    def __init__(self, store, *, require_external=False):
        self.store = store
        self.require_external = require_external
        self.last_success = 0
        with store.tx() as db:
            for statement in LEASE_SCHEMA:
                db.execute(text(statement))

    def ready(self):
        if self.require_external:
            return self.external_ready()
        return time.monotonic() - self.last_success < 10

    def external_ready(self):
        # Shared evidence, not HTTP-process uptime. A stopped guard expires fail-closed.
        try:
            with self.store.tx() as db:
                row = db.execute(
                    text("SELECT checked,healthy FROM meeting_guard_health WHERE role='external'")
                ).first()
            return bool(row and row[1] == 1 and 0 <= time.time() - row[0] < 10)
        except Exception:
            return False

    def publish_health(self, role, healthy):
        with self.store.tx() as db:
            db.execute(
                text("""INSERT INTO meeting_guard_health VALUES(:role,:checked,:healthy)
                ON CONFLICT(role) DO UPDATE SET checked=:checked,healthy=:healthy"""),
                {"role": role, "checked": int(time.time()), "healthy": int(healthy)},
            )

    def put(self, scope, token):
        room, user = scope["room_name"], scope["user_id"]
        encrypted = self.store.cipher.encrypt(token.encode()).decode()
        with self.store.tx() as db:
            result = db.execute(
                text(RESERVE_LEASE),
                {
                    "room": room,
                    "user": user,
                    "meeting": scope["meeting_id"],
                    "token": encrypted,
                    "expires": int(time.time()) + 30,
                    "now": int(time.time()),
                },
            )
            if result.first() is None:
                raise Denied("You already have a call connection. Leave it before rejoining.")

    def rows(self, *, after=None, limit=100):
        with self.store.tx(write=False) as db:
            cursor = " AND (room,user_id)>(:room,:user)" if after else ""
            return [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT * FROM meeting_leases WHERE state!='revoked'"
                        + cursor
                        + " ORDER BY room,user_id LIMIT :limit"
                    ),
                    {
                        "room": after[0] if after else "",
                        "user": after[1] if after else "",
                        "limit": min(max(limit, 1), 100),
                    },
                ).mappings()
            ]

    def pulse(self, meeting, user, token):
        with self.store.tx() as db:
            result = db.execute(
                text("""UPDATE meeting_leases SET expires=:expires,token=:token
                WHERE meeting=:meeting AND user_id=:user AND state='active' AND expires>:now"""),
                {
                    "meeting": str(meeting),
                    "user": user,
                    "expires": int(time.time()) + 30,
                    "now": int(time.time()),
                    "token": self.store.cipher.encrypt(token.encode()).decode(),
                },
            )
            if result.rowcount != 1:
                raise Denied("Call access expired. Leave and rejoin the meeting.")

    def revoke(self, meeting, user=None):
        with self.store.tx() as db:
            db.execute(
                text(
                    "UPDATE meeting_leases SET state='revoking' WHERE meeting=:meeting"
                    + (" AND user_id=:user" if user else "")
                    + " AND state!='revoked'"
                ),
                {"meeting": str(meeting), "user": user},
            )

    async def sweep(self, identity, service):
        cursor, healthy = None, True
        self.last_success = 0
        concurrency = asyncio.Semaphore(10)

        async def bounded(row):
            async with concurrency:
                return await self.check(row, identity, service)

        while True:
            rows = await asyncio.to_thread(self.rows, after=cursor)
            if not rows:
                break
            results = await asyncio.gather(*(bounded(row) for row in rows))
            healthy = healthy and all(results)
            cursor = (rows[-1]["room"], rows[-1]["user_id"])
        self.last_success = time.monotonic() if healthy else 0

    async def check(self, row, identity, service):
        valid = row["state"] == "active" and row["expires"] > time.time()
        if valid:
            try:
                token = self.store.cipher.decrypt(row["token"].encode()).decode()
                snapshot = await asyncio.to_thread(
                    identity.request,
                    "/rest/v1/rpc/meeting_consent_snapshot",
                    token,
                    method="POST",
                    data={"p_meeting": row["meeting"]},
                )
                valid = not snapshot["ended"] and any(
                    p["user_id"] == row["user_id"] for p in snapshot["participants"]
                )
            except Exception:
                valid = False  # Includes membership loss, expired JWT and auth outage.
        if valid:
            return True
        if not await asyncio.to_thread(self.revoke_current, row):
            return False  # A heartbeat or another guard changed it; recheck next sweep.
        try:
            # Cloud explicit cutoff rejects freshly refreshed cached tokens too.
            await asyncio.wait_for(
                service.room.remove_participant(
                    api.RoomParticipantIdentity(
                        room=row["room"],
                        identity=row["user_id"],
                        revoke_token_ts=int(time.time()) + 1,
                    )
                ),
                timeout=5,
            )
        except Exception:
            return False  # Durable retry; never silently forget failed removal.
        await asyncio.to_thread(self.mark_revoked, row)
        return True

    def revoke_current(self, row):
        with self.store.tx() as db:
            result = db.execute(
                text(
                    "UPDATE meeting_leases SET state='revoking' "
                    "WHERE room=:room AND user_id=:user AND token=:token AND expires=:expires "
                    "AND state=:state"
                ),
                {
                    "room": row["room"],
                    "user": row["user_id"],
                    "token": row["token"],
                    "expires": row["expires"],
                    "state": row["state"],
                },
            )
            return result.rowcount == 1

    def mark_revoked(self, row):
        with self.store.tx() as db:
            db.execute(
                text(
                    "UPDATE meeting_leases SET state='revoked',token='',expires=:now "
                    "WHERE room=:room AND user_id=:user AND state='revoking'"
                ),
                {"room": row["room"], "user": row["user_id"], "now": int(time.time()) + 2},
            )

    async def run(self, config, identity, *, role="embedded"):
        service = api.LiveKitAPI(
            config.livekit_url, config.livekit_api_key, config.livekit_api_secret
        )
        try:
            while True:
                try:
                    await self.sweep(identity, service)
                    await asyncio.to_thread(self.publish_health, role, self.ready_local())
                except Exception:
                    self.last_success = 0
                    try:
                        await asyncio.to_thread(self.publish_health, role, False)
                    except Exception:
                        pass  # Prior heartbeat expires; never replace with a success.
                await asyncio.sleep(3)
        finally:
            try:
                await asyncio.to_thread(self.publish_health, role, False)
            finally:
                await service.aclose()

    def ready_local(self):
        return time.monotonic() - self.last_success < 10
