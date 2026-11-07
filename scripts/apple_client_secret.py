"""Generate an Apple OAuth client secret into a new private file, never stdout."""

import argparse
import base64
import json
import os
import re
import stat
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def generate(key_data, team_id, key_id, services_id, *, now=None):
    if not all(re.fullmatch(r"[A-Z0-9]{10}", item) for item in (team_id, key_id)):
        raise ValueError("Use the Apple team ID and key ID, each 10 uppercase letters/digits.")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+){2,}", services_id):
        raise ValueError("Use the registered Apple Services ID.")
    key = serialization.load_pem_private_key(key_data, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Apple Sign in requires a P-256 signing key.")
    issued = int(time.time()) if now is None else now
    expires = issued + 179 * 86400
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    claims = {
        "iss": team_id,
        "iat": issued,
        "exp": expires,
        "aud": "https://appleid.apple.com",
        "sub": services_id,
    }
    unsigned = b".".join(
        encode(json.dumps(item, separators=(",", ":")).encode()) for item in (header, claims)
    )
    r, s = decode_dss_signature(key.sign(unsigned, ec.ECDSA(hashes.SHA256())))
    return unsigned + b"." + encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")), expires


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--services-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = args.key.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_size > 16384:
        parser.error("Use a regular private key file (chmod 600), at most 16 KiB.")
    token, expires = generate(args.key.read_bytes(), args.team_id, args.key_id, args.services_id)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(token + b"\n")
    print(
        json.dumps(
            {
                "saved": str(args.output),
                "expires_at_unix": expires,
                "rotate_before_unix": expires - 30 * 86400,
            }
        )
    )


if __name__ == "__main__":
    main()
