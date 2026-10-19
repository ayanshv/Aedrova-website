"""Shared, database-backed admission limits; never trust arbitrary forwarded headers."""

import asyncio
import hashlib
import time

from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from aedrova_site.store import RateLimited


def policy(path, method):
    if path == "/auth/google" or path.endswith("/oauth/start"):
        return "login-start", 10, 300
    if path == "/auth/callback" or path.endswith("/callback"):
        return "oauth-callback", 30, 300
    if path.startswith("/health"):
        return "health", 120, 60
    if path.startswith("/static/"):
        return "assets", 1200, 60
    if path == "/stripe/webhook":
        return "webhook", 600, 60
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return "write", 180, 60
    return "read", 600, 60


class TrafficLimits:
    def __init__(self, app, store):
        self.app, self.store = app, store
        self.health_window, self.health_count = -1, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        headers = scope.get("headers", [])
        names = [key.lower() for key, _ in headers]
        if any(
            names.count(name) > 1
            for name in (
                b"content-type",
                b"content-length",
                b"authorization",
                b"host",
                b"x-csrf-token",
            )
        ):
            await JSONResponse(
                {"error": "Ambiguous request headers."},
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        if (
            len(path.encode()) > 4096
            or len(scope.get("query_string", b"")) > 8192
            or len(headers) > 100
            or sum(len(k) + len(v) for k, v in headers) > 32768
        ):
            await JSONResponse({"error": "Request metadata too large."}, status_code=431)(
                scope, receive, send
            )
            return
        category, maximum, seconds = policy(path, scope["method"])
        # scope.client is supplied by the ASGI server. Its proxy allowlist must be
        # configured at deployment; raw X-Forwarded-For must never be a bypass.
        client = scope.get("client")
        address = client[0] if client else "unknown"
        key = "ingress:" + category + ":" + hashlib.sha256(address.encode()).hexdigest()
        try:
            if path == "/health":
                # Liveness must survive a DB outage. One bounded process-wide
                # counter, no growing per-IP fallback and no product API bypass.
                window = int(time.monotonic()) // 60
                if window != self.health_window:
                    self.health_window, self.health_count = window, 0
                self.health_count += 1
                if self.health_count > 1200:
                    raise RateLimited(60 - int(time.monotonic()) % 60)
            else:
                await asyncio.to_thread(self.store.rate_limit, key, limit=maximum, seconds=seconds)
        except RateLimited as error:
            await JSONResponse(
                {"error": "Too many requests. Please wait and retry."},
                status_code=429,
                headers={"Retry-After": str(error.retry_after), "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        except SQLAlchemyError:
            await JSONResponse(
                {"error": "The service is temporarily unavailable. Retry shortly."},
                status_code=503,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        await self.app(scope, receive, send)
