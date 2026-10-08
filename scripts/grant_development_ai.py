"""Grant capped loopback funding after verifying a freshly signed-in workspace owner."""

import argparse
import json
import time

from sqlalchemy import text

from aedrova_site.config import Config
from aedrova_site.services import Identity
from aedrova_site.store import Denied, Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="Exact Supabase workspace UUID")
    args = parser.parse_args()
    config = Config.load()
    if not config.development_ai:
        raise SystemExit("Explicit private development mode is required.")
    store = Store(config.database, config.encryption_key, development_ai=True)
    identity = Identity(config)
    try:
        with store.tx(write=False) as db:
            rows = db.execute(
                text("SELECT payload FROM sessions WHERE expires>:now ORDER BY expires DESC"),
                {"now": int(time.time())},
            ).all()
        for (encrypted,) in rows:
            try:
                payload = json.loads(store.cipher.decrypt(encrypted.encode()))
                user = identity.require(payload["access_token"], args.workspace, billing=True)
            except Exception:
                continue
            balance = store.grant_development(user["id"], args.workspace)
            print(
                json.dumps(
                    {
                        "workspace": args.workspace,
                        "status": balance["status"],
                        "available_micro_usd": balance["available"],
                        "expires": balance["period_end"],
                    }
                )
            )
            return
        raise Denied("Sign in to the local website as this workspace owner, then retry.")
    except Denied as error:
        raise SystemExit(str(error)) from None
    finally:
        identity.close()
        store.engine.dispose()


if __name__ == "__main__":
    main()
