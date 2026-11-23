"""Shared-password gate for the invited beta download.

The password lives only in the AEDROVA_BETA_PASSWORD environment value. A correct entry sets a
signed, expiring, HttpOnly cookie; changing the password signs every tester out.
"""

import hashlib
import hmac
import time

COOKIE = "aedrova_beta"
LIFETIME = 7 * 86400


def _key(password):
    return hashlib.sha256(b"aedrova-beta-gate:" + password.encode()).digest()


def matches(password, attempt):
    """Constant-time comparison that does not reveal the password's length."""
    if not password or not attempt:
        return False
    return hmac.compare_digest(
        hashlib.sha256(password.encode()).digest(), hashlib.sha256(attempt.encode()).digest()
    )


def issue(password, now=None):
    expires = int((time.time() if now is None else now) + LIFETIME)
    signature = hmac.new(_key(password), str(expires).encode(), "sha256").hexdigest()
    return f"{expires}.{signature}"


def valid(password, token, now=None):
    if not password or not token:
        return False
    expires, _, signature = token.partition(".")
    if not expires.isdigit() or int(expires) < (time.time() if now is None else now):
        return False
    expected = hmac.new(_key(password), expires.encode(), "sha256").hexdigest()
    return hmac.compare_digest(expected, signature)
