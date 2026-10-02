"""Hourly private-content expiry and conservative abandoned-request reconciliation."""

from aedrova_site.config import Config
from aedrova_site.store import Store


def main():
    config = Config.load()
    store = Store(config.database, config.encryption_key)
    try:
        store.maintain()
        print("Expired sessions/content removed; abandoned reservations reconciled.")
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
