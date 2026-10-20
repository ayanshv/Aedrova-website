"""Recognizable credentials only; findings never include matched secret values."""

import base64
import json
import re

PATTERNS = {
    "figma-token": rb"figd_[A-Za-z0-9_-]{20,}",
    "notion-token": rb"ntn_[A-Za-z0-9_-]{20,}",
    "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "supabase-secret": rb"sb_secret_[A-Za-z0-9_-]{20,}",
    "google-client-secret": rb"GOCSPX-[A-Za-z0-9_-]{20,}",
    "provider-secret": rb"sk-(?:proj-|ant-)[A-Za-z0-9_-]{20,}",
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "stripe-secret": rb"(?:[sr]k_(?:live|test)_[A-Za-z0-9]{20,}|whsec_[A-Za-z0-9]{20,})",
    "aws-access-key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
}


def credential_rules(data):
    rules = {name for name, pattern in PATTERNS.items() if re.search(pattern, data)}
    for payload in re.findall(rb"eyJ[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]+", data):
        try:
            claims = json.loads(base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)))
            if isinstance(claims, dict) and claims.get("role") == "service_role":
                rules.add("supabase-service-role-jwt")
        except (ValueError, UnicodeDecodeError):
            pass
    return sorted(rules)
