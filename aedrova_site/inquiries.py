"""Export pending enterprise requests privately; this does not send any messages."""

import argparse
import json
import os
import time
from pathlib import Path

from sqlalchemy import text

from aedrova_site.config import Config
from aedrova_site.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = Config.load()
    store = Store(config.database, config.encryption_key)
    try:
        with store.tx() as db:
            rows = db.execute(
                text("SELECT payload,expires FROM sessions WHERE expires>:now"),
                {"now": int(time.time())},
            ).all()
        inquiries = []
        for payload, expires in rows:
            value = json.loads(store.cipher.decrypt(payload.encode()))
            if value.get("kind") == "enterprise_inquiry":
                inquiries.append({**value, "expires": expires})
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(inquiries, stream, indent=2)
            stream.write("\n")
        print(f"Exported {len(inquiries)} enterprise requests into a private local file.")
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
