"""Inventory the actual FastAPI route graph without production credentials or traffic."""

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.routing import APIRoute

from aedrova_site.app import create_app
from aedrova_site.config import Config

PUBLIC = {
    "/",
    "/product",
    "/robots.txt",
    "/sitemap.xml",
    "/waitlist",
    "/onboarding",
    "/plans",
    "/api/early-access",  # Public fixed promotion clock; no workspace/account information.
    "/account",
    "/welcome",
    "/download",
    "/enterprise",
    "/support",
    "/privacy",
    "/terms",
    "/refunds",
    "/unsubscribe",
    "/data-controls",
    "/subprocessors",
    "/cookies",
    "/acceptable-use",
    "/security",
    "/health",
    "/health/ready",
    "/health/meetings",
    "/api/download",
    "/api/release",
}
SIGNED = {"/stripe/webhook", "/dots/github/events"}
OAUTH = {
    "/auth/google",
    "/auth/callback",
    "/buds/authorize/{state}",
    "/dots/authorize/{state}",
    "/buds/oauth/{provider}/callback",
    "/dots/github/callback",
}


def classification(path):
    if path in PUBLIC:
        return "public-read-or-release-gated"
    if path in SIGNED:
        return "signed-provider-webhook"
    if path in OAUTH:
        return "oauth-state-pkce-browser-proof"
    if path in {"/api/waitlist", "/api/inquiries", "/api/unsubscribe"}:
        return "public-bounded-submission"
    if path.startswith("/gateway/"):
        return "scoped-build-token-and-entitlement"
    if path.startswith("/api/"):
        return "user-session-or-bearer-and-resource-authorization"
    return "UNCLASSIFIED"


def inventory(app):
    root = Path(__file__).resolve().parents[1]
    rows = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        rows.append(
            {
                "path": route.path,
                "methods": sorted(route.methods),
                "boundary": classification(route.path),
                "source": str(Path(inspect.getsourcefile(route.endpoint)).relative_to(root)),
                "line": inspect.getsourcelines(route.endpoint)[1],
            }
        )
    return sorted(rows, key=lambda row: row["path"])


if __name__ == "__main__":
    with TemporaryDirectory(prefix="aedrova-audit-") as directory:
        app = create_app(Config(database="sqlite:///" + str(Path(directory) / "audit.sqlite")))
        print(json.dumps(inventory(app), indent=2))
        app.state.identity.close()
        app.state.store.engine.dispose()
