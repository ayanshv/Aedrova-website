import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from scripts.apple_client_secret import generate


def test_apple_secret_signature_audience_and_bounded_expiry():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    token, expires = generate(
        pem, "ABCDEFGHIJ", "1234567890", "com.aedrova.login.staging", now=1000
    )
    header, body, signature = token.split(b".")
    claims = json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)))
    assert claims == {
        "iss": "ABCDEFGHIJ",
        "iat": 1000,
        "exp": expires,
        "aud": "https://appleid.apple.com",
        "sub": "com.aedrova.login.staging",
    }
    assert expires - 1000 == 179 * 86400
    raw = base64.urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))
    signature = encode_dss_signature(
        int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    )
    key.public_key().verify(signature, header + b"." + body, ec.ECDSA(hashes.SHA256()))
    with pytest.raises(ValueError):
        generate(pem, "invalid", "1234567890", "com.aedrova.login")
