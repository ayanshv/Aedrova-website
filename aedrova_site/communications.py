"""Purpose-bound launch-email opt-out tokens; never accepts account/OAuth tokens."""

import hashlib
import json
from urllib.parse import urlencode

from cryptography.fernet import InvalidToken

from aedrova_site.store import Denied


def registration_key(email):
    return "waitlist:" + hashlib.sha256(email.strip().casefold().encode()).hexdigest()


def unsubscribe_url(store, email, origin):
    token = store.cipher.encrypt(
        json.dumps(
            {"purpose": "launch-unsubscribe-v1", "registration": registration_key(email)}
        ).encode()
    ).decode()
    return origin.rstrip("/") + "/unsubscribe?" + urlencode({"token": token})


def unsubscribe(store, token):
    try:
        value = json.loads(store.cipher.decrypt(token.encode()))
        key = value["registration"]
        if value.get("purpose") != "launch-unsubscribe-v1" or not (
            isinstance(key, str) and key.startswith("waitlist:") and len(key) == 73
        ):
            raise ValueError("purpose")
    except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError):
        raise Denied("This unsubscribe link is invalid. Contact contact@aedrova.com.") from None
    # Retain a minimal suppression instead of deleting account or waitlist data.
    store.session("suppressed:" + key, {"kind": "launch-suppression"}, lifetime=10 * 365 * 86400)


def suppressed(store, email):
    try:
        return (
            store.session("suppressed:" + registration_key(email)).get("kind")
            == "launch-suppression"
        )
    except Denied:
        return False
