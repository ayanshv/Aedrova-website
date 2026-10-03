"""Content-free request and slow-query events; no private payloads or raw URLs."""

import json
import logging
import time
from threading import Lock
from uuid import uuid4

from sqlalchemy import event
from starlette.responses import JSONResponse

LOG = logging.getLogger("aedrova.events")


def configure_events():
    LOG.setLevel(logging.INFO)
    if not LOG.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        LOG.addHandler(handler)
    LOG.propagate = False


def emit(kind, **fields):
    LOG.info(json.dumps({"event": kind, **fields}, separators=(",", ":")))


class Admission:
    """Immediate per-worker admission: no unbounded waiting queue or provider retries."""

    def __init__(self, app, maximum=8):
        self.app, self.maximum = app, maximum
        self.active = 0
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/gateway/"):
            await self.app(scope, receive, send)
            return
        with self.lock:
            admitted = self.active < self.maximum
            if admitted:
                self.active += 1
        if not admitted:
            emit("ai_admission_rejected", limit=self.maximum)
            await JSONResponse(
                {"error": "AI service is busy. Retry shortly. No usage started."},
                status_code=503,
                headers={"Retry-After": "5"},
            )(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            with self.lock:
                self.active -= 1


class RequestEvents:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier, start, status = uuid4().hex, time.monotonic(), 500

        async def measured(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", identifier.encode())
                ]
            await send(message)

        try:
            await self.app(scope, receive, measured)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            emit(
                "http_request",
                request_id=identifier,
                method=scope["method"],
                route=route,
                status=status,
                duration_ms=round((time.monotonic() - start) * 1000, 2),
            )


def database_events(engine):
    @event.listens_for(engine, "before_cursor_execute")
    def before(_connection, _cursor, _statement, _parameters, context, _many):
        context.aedrova_started = time.monotonic()

    @event.listens_for(engine, "after_cursor_execute")
    def after(_connection, _cursor, _statement, _parameters, context, _many):
        elapsed = (time.monotonic() - context.aedrova_started) * 1000
        if elapsed >= 250:
            emit("database_slow", duration_ms=round(elapsed, 2), dialect=engine.dialect.name)
