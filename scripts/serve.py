"""Container HTTP entry point; TLS terminates at the trusted hosting proxy."""

import os

import uvicorn


def main(factory="aedrova_site.app:create_app"):
    port = int(os.environ.get("PORT", "8090"))
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535.")
    trusted = os.environ.get("AEDROVA_TRUSTED_PROXY_IPS", "").strip()
    if "*" in trusted:
        raise SystemExit("List only the actual proxy IPs or networks; wildcard trust is denied.")
    uvicorn.run(
        factory,
        factory=True,
        host="0.0.0.0",
        port=port,
        access_log=False,
        proxy_headers=bool(trusted),
        forwarded_allow_ips=trusted,
        limit_concurrency=128,
        backlog=256,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=270,
    )


if __name__ == "__main__":
    main()
