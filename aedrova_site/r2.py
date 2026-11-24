"""Short-lived signed download links for the private beta installer in Cloudflare R2."""

import datetime
import hashlib
import hmac
from urllib.parse import quote, urlparse


def _sign(key, message):
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def presigned_get(
    endpoint, bucket, key, access_key, secret_key, *, filename, seconds=300, now=None
):
    """An S3 SigV4 query-signed GET link that expires quickly and downloads as `filename`."""
    host = urlparse(endpoint).netloc
    moment = now or datetime.datetime.now(datetime.UTC)
    stamp, day = moment.strftime("%Y%m%dT%H%M%SZ"), moment.strftime("%Y%m%d")
    scope = f"{day}/auto/s3/aws4_request"
    path = "/" + quote(bucket, safe="") + "/" + quote(key, safe="/")
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(seconds),
        "X-Amz-SignedHeaders": "host",
        "response-content-disposition": f'attachment; filename="{filename}"',
    }
    canonical_query = "&".join(
        f"{quote(name, safe='')}={quote(query[name], safe='')}" for name in sorted(query)
    )
    request = "\n".join(
        ["GET", path, canonical_query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"]
    )
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(request.encode()).hexdigest()]
    )
    secret = _sign(("AWS4" + secret_key).encode(), day)
    for part in ("auto", "s3", "aws4_request"):
        secret = _sign(secret, part)
    signature = hmac.new(secret, to_sign.encode(), hashlib.sha256).hexdigest()
    return f"{endpoint.rstrip('/')}{path}?{canonical_query}&X-Amz-Signature={signature}"
