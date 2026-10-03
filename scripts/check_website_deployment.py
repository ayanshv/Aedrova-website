"""Read-only first-domain-deployment preflight; no purchases, OAuth or mutations.

Run inside the host environment. Optional --probe checks public HTTPS readiness without
sending database credentials, session tokens or API keys to the public endpoint.
"""

import argparse
import json

import httpx

from aedrova_site.config import Config


def check(config, *, probe=False, client=None):
    config.validate()
    if not config.production:
        raise ValueError("Use the production website environment.")
    if any(
        (
            config.checkout_enabled,
            config.gateway_enabled,
            config.meetings_enabled,
            config.release_ready,
            config.stripe_test_mode,
        )
    ):
        raise ValueError("The first website deployment must keep product release gates closed.")
    if probe:
        owned = client is None
        client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        try:
            for path, expected in (("/health", "ok"), ("/health/ready", "ready")):
                with client.stream("GET", config.origin.rstrip("/") + path) as response:
                    if response.status_code != 200:
                        raise ValueError("HTTPS readiness failed or redirected.")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 16384:
                            raise ValueError("Unexpected readiness response.")
                    result = json.loads(body)
                    if not isinstance(result, dict) or result.get("status") != expected:
                        raise ValueError("The website or database is unavailable.")
                    if path == "/health" and (
                        result.get("checkout_enabled") is not False
                        or result.get("managed_ai_enabled") is not False
                    ):
                        raise ValueError("Unexpected public product gates.")
            for path in ("/", "/onboarding", "/plans", "/welcome", "/download"):
                with client.stream("GET", config.origin.rstrip("/") + path) as response:
                    if response.status_code != 200:
                        raise ValueError("A public page is unavailable or redirected.")
                    if "text/html" not in response.headers.get("content-type", ""):
                        raise ValueError("Unexpected public page response.")
                    if response.headers.get("x-content-type-options") != "nosniff":
                        raise ValueError("Missing security response headers.")
        finally:
            if owned:
                client.close()
    return {
        "configuration": "passed",
        "https_pages_and_database": "passed" if probe else "not tested",
        "google_sign_in": "manual acceptance required",
        "paid_checkout_ai_and_download": "disabled",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    try:
        report = check(Config.load(), probe=args.probe)
    except Exception:
        raise SystemExit(
            "Website preflight failed. Check private host configuration, TLS, database and "
            "release gates. Credentials were not printed."
        ) from None
    print(json.dumps(report))


if __name__ == "__main__":
    main()
