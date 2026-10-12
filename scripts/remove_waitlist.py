"""Operator-only removal after verifying a privacy request; never removes account sessions."""

import json
from getpass import getpass

from sqlalchemy import text

from aedrova_site.config import Config
from aedrova_site.store import Store


def remove_registration(store, email):
    address = email.strip().casefold()
    if not address or "@" not in address:
        raise ValueError("Provide a verified registration address.")
    # Fail closed if decryption fails. Inspect only the waitlist kind; OAuth/account
    # records can have the same email and must never be removed by this operation.
    with store.tx() as db:
        matches = []
        for identifier, encrypted in db.execute(text("SELECT id,payload FROM sessions")):
            payload = json.loads(store.cipher.decrypt(encrypted.encode()))
            if (
                payload.get("kind") == "waitlist"
                and str(payload.get("email", "")).casefold() == address
            ):
                matches.append(identifier)
        for identifier in matches:
            db.execute(text("DELETE FROM sessions WHERE id=:id"), {"id": identifier})
    return len(matches)


def main():
    config = Config.load()
    if not config.encryption_key:
        raise SystemExit("Configure the persistent server encryption key first.")
    store = Store(config.database, config.encryption_key)
    try:
        email = getpass("Verified waitlist address (hidden): ")
        confirmation = input("Type REMOVE after verifying the requester: ")
        if confirmation != "REMOVE":
            print("Cancelled. No registrations removed.")
            return
        count = remove_registration(store, email)
        print(f"Removed {count} matching registrations. No email was sent.")
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
