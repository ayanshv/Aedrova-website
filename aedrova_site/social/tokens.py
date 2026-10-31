"""Durable single-use refresh claims: a crashed worker cannot replay a Buffer token."""

import json
import time

from sqlalchemy import text

from aedrova_site.store import Denied


def access(service, grant, *, force=False):
    store = service.store
    with store.tx() as db:
        suffix = " FOR UPDATE" if store.engine.dialect.name == "postgresql" else ""
        row = (
            db.execute(
                text("SELECT * FROM bud_connections WHERE id=:i" + suffix), {"i": grant["id"]}
            )
            .mappings()
            .first()
        )
        if not row or row["expires"] <= time.time() or row["status"] != "Connected":
            raise Denied("Needs authorization")
        grant = dict(row)
        envelope = json.loads(store.cipher.decrypt(row["secret"].encode()))
        if not force and envelope["token_expires"] > time.time() + 60:
            return grant, envelope["access"], True
        renewal = envelope.get("refresh")
        if not renewal:
            raise Denied("Needs authorization")
        # Commit removal before sending a single-use refresh token to Buffer.
        claimed = store.cipher.encrypt(json.dumps({**envelope, "refresh": ""}).encode()).decode()
        db.execute(
            text("UPDATE bud_connections SET secret=:s,status='Refreshing' WHERE id=:i"),
            {"s": claimed, "i": row["id"]},
        )
    try:
        refreshed = service.oauth.token("buffer", refresh=renewal)
    except Exception:
        with store.tx() as db:
            db.execute(
                text(
                    "UPDATE bud_connections SET status='Needs authorization' "
                    "WHERE id=:i AND secret=:s"
                ),
                {"i": grant["id"], "s": claimed},
            )
        raise Denied("Needs authorization") from None
    encoded = store.cipher.encrypt(json.dumps(refreshed).encode()).decode()
    with store.tx() as db:
        result = db.execute(
            text(
                "UPDATE bud_connections SET secret=:s,status='Connected' "
                "WHERE id=:i AND secret=:c AND expires>:t"
            ),
            {"s": encoded, "i": grant["id"], "c": claimed, "t": int(time.time())},
        )
        if result.rowcount != 1:
            raise Denied("Needs authorization")
    return {**grant, "secret": encoded}, refreshed["access"], True
