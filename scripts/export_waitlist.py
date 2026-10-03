"""Operator-only export; requires the configured database and persistent encryption key."""

import argparse
import csv
import json
import os
import time
from pathlib import Path

from sqlalchemy import text

from aedrova_site.config import Config
from aedrova_site.store import Store


def export(store, destination):
    # Exclusive create prevents overwriting another list; output is owner-readable only.
    with store.tx(write=False) as db:
        rows = (
            db.execute(
                text("SELECT payload FROM sessions WHERE expires > :now"),
                {"now": int(time.time())},
            )
            .scalars()
            .all()
        )
    contacts = []
    for encrypted in rows:
        payload = json.loads(store.cipher.decrypt(encrypted.encode()))
        if payload.get("kind") == "waitlist":
            email = payload["email"]
            if email.startswith(("=", "+", "-", "@")):
                email = "'" + email  # Prevent spreadsheet formula execution on CSV open.
            contacts.append((email, payload["consent"]))
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("email", "consent"))
        writer.writerows(sorted(contacts))
    return len(contacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    config = Config.load()
    if not config.encryption_key:
        raise SystemExit("Configure the persistent server encryption key before exporting.")
    store = Store(config.database, config.encryption_key)
    try:
        count = export(store, args.destination)
        print(f"Exported {count} waitlist contacts. Keep the CSV private; no emails were sent.")
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
