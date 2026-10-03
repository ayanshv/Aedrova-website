"""Run alongside the HTTP service under a separate restart supervisor in production.

Both processes require the same private database and persistent encryption key.
The guard survives an HTTP process failure and retries durable participant revocations.
"""

import asyncio

from aedrova_site.config import Config
from aedrova_site.meeting_leases import MeetingLeases
from aedrova_site.services import Identity
from aedrova_site.store import Store


def main():
    config = Config.load()
    if not config.meetings_enabled:
        raise SystemExit("Enable meeting configuration before running its access guard.")
    store = Store(config.database, config.encryption_key)
    identity = Identity(config)
    try:
        asyncio.run(MeetingLeases(store).run(config, identity, role="external"))
    finally:
        identity.close()
        store.engine.dispose()


if __name__ == "__main__":
    main()
