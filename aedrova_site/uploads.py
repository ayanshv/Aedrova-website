"""Authenticated streaming validation before chat publication. No privileged Storage key."""

import hashlib
import re
import threading
import time
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import text

from aedrova_site.file_policy import MAX_BYTES, inspect_file
from aedrova_site.store import Denied


class UploadVerifier:
    def __init__(self, identity, store):
        self.identity, self.store = identity, store
        self.slots = threading.BoundedSemaphore(2)

    def verify(self, token, identifier, parent=None):
        user = self.identity.user(token)
        self.store.rate_limit("uploads:" + user["id"], limit=10)
        rows = self.identity.request(
            "/rest/v1/attachments?" + urlencode({"id": "eq." + str(identifier), "select": "*"}),
            token,
        )
        if len(rows) != 1 or rows[0]["uploader_id"] != user["id"]:
            raise Denied("This upload is not available to your account.")
        row = rows[0]
        if not 1 <= row["byte_size"] <= MAX_BYTES or not re.fullmatch(
            r"[a-f0-9-]{36}/[a-f0-9-]{36}/[a-f0-9-]{36}", row["object_path"]
        ):
            raise Denied("Invalid upload metadata.")
        if not self.slots.acquire(blocking=False):
            raise Denied("File checks are busy. Try again shortly.")
        try:
            started = time.monotonic()
            headers = {
                "apikey": self.identity.config.supabase_key,
                "Authorization": "Bearer " + token,
                "Accept-Encoding": "identity",
            }
            data = bytearray()
            with self.identity.client.stream(
                "GET",
                self.identity.config.supabase_url
                + "/storage/v1/object/authenticated/aedrova-files/"
                + row["object_path"],
                headers=headers,
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > 30 or len(data) + len(chunk) > row["byte_size"]:
                        raise ValueError("Upload exceeded its bounds.")
                    data.extend(chunk)
            digest = hashlib.sha256(data).hexdigest()
            if len(data) != row["byte_size"] or digest != row["sha256"]:
                raise ValueError("Upload integrity check failed.")
            kind = inspect_file(row["filename"], bytes(data))
            with self.store.engine.begin() as db:
                result = db.execute(
                    text("select public.finish_verified_attachment(:u,:i,:s,:t,:p)"),
                    {
                        "u": str(UUID(user["id"])),
                        "i": str(identifier),
                        "s": digest,
                        "t": kind,
                        "p": str(parent) if parent else None,
                    },
                ).scalar_one()
            return {"message": str(result), "verified_type": kind}
        except Exception as error:
            raise Denied(
                "File could not be verified. Check its type, size or channel access."
            ) from error
        finally:
            self.slots.release()
