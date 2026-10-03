"""Run alongside the HTTP service under a separate restart supervisor in production.

Both processes require the same private database and persistent encryption key.
The guard survives an HTTP process failure and retries durable participant revocations.
"""

import asyncio

from aedrova_site.config import Config
from aedrova_site.meeting_leases import MeetingLeases
from aedrova_site.services import Identity
from aedrova_site.store import Store


def run():
    config = Config.load()
    if not config.meetings_enabled:
        raise SystemExit("Enable meeting configuration before running its access guard.")
    store = Store(
        config.database,
        config.encryption_key,
        pool_size=config.db_pool_size,
        max_overflow=config.db_max_overflow,
        pool_timeout=config.db_pool_timeout,
    )
    identity = None
    try:
        identity = Identity(config)
        asyncio.run(MeetingLeases(store).run(config, identity, role="external"))
    finally:
        try:
            if identity is not None:
                identity.close()
        finally:
            store.engine.dispose()


def main():
    try:
        run()
    except Exception:
        # Driver/provider exceptions can include credentials or connection strings.
        raise SystemExit(
            "Meeting guard stopped. Check its private configuration, database and LiveKit "
            "connectivity; credentials were not printed."
        ) from None


if __name__ == "__main__":
    main()
