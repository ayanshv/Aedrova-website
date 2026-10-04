"""Service-only, bounded orphan cleanup. Never loaded by the public web application."""

import base64
import json
import os
import re
import time
from uuid import UUID

import httpx


def headers(key):
    result = {"apikey": key, "Accept-Encoding": "identity"}
    if key.startswith("sb_secret_") and len(key) >= 30:
        return result
    try:
        claims = json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "==="))
        if claims.get("role") != "service_role":
            raise ValueError()
    except (ValueError, IndexError, AttributeError):
        raise ValueError(
            "Cleanup requires a server-only Supabase secret/service-role key."
        ) from None
    result["Authorization"] = "Bearer " + key
    return result


class StorageCleanup:
    def __init__(self, origin, key, *, transport=None):
        if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", origin):
            raise ValueError("Use the exact HTTPS Supabase project URL.")
        self.client = httpx.Client(
            base_url=origin,
            headers=headers(key),
            transport=transport,
            timeout=httpx.Timeout(10, connect=5),
            trust_env=False,
            follow_redirects=False,
        )

    def close(self):
        self.client.close()

    def request(self, method, path, body):
        started = time.monotonic()
        with self.client.stream(method, path, json=body) as response:
            if response.status_code != 200:
                raise RuntimeError("Storage cleanup request failed; the lease will expire safely.")
            data = bytearray()
            for chunk in response.iter_bytes():
                if len(data) + len(chunk) > 65536 or time.monotonic() - started > 20:
                    raise RuntimeError("Storage cleanup response exceeded its bounds.")
                data.extend(chunk)
        try:
            return json.loads(data)
        except ValueError:
            raise RuntimeError("Storage cleanup returned an invalid response.") from None

    def run(self):
        rows = self.request("POST", "/rest/v1/rpc/claim_storage_cleanup", {"p_limit": 10})
        if not isinstance(rows, list) or len(rows) > 10:
            raise RuntimeError("Invalid cleanup batch.")
        seen = set()
        # Validate the ENTIRE batch before any external deletion.
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("object_path"), str):
                raise RuntimeError("Invalid cleanup object.")
            path = row["object_path"]
            parts = path.split("/")
            try:
                if len(parts) != 3 or any(str(UUID(part)) != part for part in parts):
                    raise ValueError()
                UUID(row["lease"])
                if path in seen:
                    raise ValueError()
                seen.add(path)
            except (ValueError, KeyError, TypeError):
                raise RuntimeError("Invalid cleanup object or lease.") from None
        count = 0
        for row in rows:
            removed = self.request(
                "DELETE", "/storage/v1/object/aedrova-files", {"prefixes": [row["object_path"]]}
            )
            if not isinstance(removed, list):
                raise RuntimeError("Invalid Storage deletion response.")
            # SQL independently verifies storage metadata is gone before releasing bytes.
            result = self.request(
                "POST",
                "/rest/v1/rpc/finish_storage_cleanup",
                {"p_path": row["object_path"], "p_lease": row["lease"]},
            )
            if result is not True:
                raise RuntimeError("Cleanup lease changed; reserved bytes remain accounted.")
            count += 1
        return count


def main():
    if os.environ.get("AEDROVA_STORAGE_CLEANUP_ENABLED", "false") != "true":
        print("Storage cleanup disabled.")
        return
    worker = None
    try:
        worker = StorageCleanup(
            os.environ.get("AEDROVA_STORAGE_CLEANUP_URL", ""),
            os.environ.get("AEDROVA_STORAGE_CLEANUP_KEY", ""),
        )
        count = worker.run()
        print(f"Storage cleanup completed: {count} objects.")
    except Exception:
        raise SystemExit(
            "Storage cleanup failed. Check private configuration and service health; "
            "no failed deletion was acknowledged."
        ) from None
    finally:
        if worker:
            worker.close()


if __name__ == "__main__":
    main()
