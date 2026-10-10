"""Dedicated HTTPS Bud service; unrelated product routes remain inaccessible."""

import re

from fastapi.responses import JSONResponse

from aedrova_site.app import create_app
from aedrova_site.config import Config

GET_PATHS = {
    "/health",
    "/health/ready",
    "/auth/google",
    "/auth/callback",
    "/api/dots",
    "/api/dots/providers",
    "/api/buds/connectors",
    "/api/buds/connections",
    "/api/buds/oauth/status",
    "/dots/github/callback",
}
POST_PATHS = {
    "/api/dots/connect",
    "/api/dots/disconnect",
    "/api/dots/remove",
    "/api/dots/tools",
    "/api/buds/connections",
    "/api/buds/connections/disconnect",
    "/api/buds/oauth/start",
}


def allowed(method, path):
    if method in {"GET", "HEAD"}:
        return (
            path in GET_PATHS
            or path.startswith("/static/")
            or bool(
                re.fullmatch(
                    r"/(?:buds|dots)/authorize/[A-Za-z0-9_-]{40,100}|"
                    r"/buds/oauth/(?:github|supabase|figma|notion|tiktok)/callback",
                    path,
                )
            )
        )
    return method == "POST" and path in POST_PATHS


def validate(config):
    config.validate()
    if not config.production or not config.supabase_database or not config.dots_enabled:
        raise ValueError(
            "The connector service requires production HTTPS, restricted Supabase and Buds."
        )
    if any(
        (
            config.meetings_enabled,
            config.meeting_context_enabled,
            config.speech_enabled,
            config.gateway_enabled,
            config.development_ai,
            config.checkout_enabled,
            config.release_ready,
            config.legal_ready,
            config.stripe_test_mode,
        )
    ):
        raise ValueError("The connector service must keep all other release gates disabled.")
    if config.db_pool_size != 1 or config.db_max_overflow != 0:
        raise ValueError("The connector service uses one pooled connection and no overflow.")


def create_connector_app(config=None):
    config = config or Config.load()
    validate(config)
    app = create_app(config)

    @app.middleware("http")
    async def connector_boundary(request, call_next):
        if request.method in {"GET", "HEAD"} and request.url.path == "/":
            response = JSONResponse(
                {
                    "service": "Aedrova Bud connections",
                    "status": "ready",
                    "sign_in": "Start from your Bud in Aedrova.",
                }
            )
        elif not allowed(request.method, request.url.path):
            response = JSONResponse(
                {"error": "This route is unavailable on the connector service."}, status_code=404
            )
        else:
            return await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Strict-Transport-Security": "max-age=31536000",
            }
        )
        return response

    return app
