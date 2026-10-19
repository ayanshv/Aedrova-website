"""Bound request bodies even when a client omits Content-Length."""

import asyncio
import json
import math

from starlette.responses import JSONResponse


def reject_constant(_value):
    raise ValueError("Non-finite JSON number")


class BodyLimit:
    def __init__(self, app, maximum=8 * 1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        maximum = (
            self.maximum
            if scope["path"].startswith("/gateway/")
            else (
                2 * 1024 * 1024
                if scope["path"] == "/api/meetings/transcript/confirm"
                else (
                    1281000
                    if scope["path"] == "/api/chat/speech"
                    else (
                        512 * 1024
                        if scope["path"] == "/api/meetings/speech"
                        else (1024 * 1024 if scope["path"] == "/stripe/webhook" else 64 * 1024)
                    )
                )
            )
        )
        chunks, length = [], 0
        try:
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    length += len(chunk)
                    if length > maximum:
                        await JSONResponse({"error": "Request too large."}, status_code=413)(
                            scope, receive, send
                        )
                        return
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse(
                {"error": "Request upload timed out. Retry when connected."}, status_code=408
            )(scope, receive, send)
            return
        body = b"".join(chunks)
        chunks.clear()
        headers = dict(scope.get("headers", []))
        if headers.get(b"content-type", b"").split(b";", 1)[0].strip() == b"application/json":
            try:
                value = json.loads(body, parse_constant=reject_constant)
                pending = [(value, 0)]
                count = 0
                while pending:
                    item, depth = pending.pop()
                    count += 1
                    if isinstance(item, float) and not math.isfinite(item):
                        raise ValueError("Non-finite JSON number")
                    if depth > 64 or count > 20000:
                        raise ValueError("structure")
                    if isinstance(item, str) and any(
                        ord(c) < 32 and c not in "\t\n\r" for c in item
                    ):
                        raise ValueError("control")
                    if isinstance(item, dict):
                        pending.extend((entry, depth + 1) for entry in item.keys())
                        pending.extend((entry, depth + 1) for entry in item.values())
                    elif isinstance(item, list):
                        pending.extend((entry, depth + 1) for entry in item)
            except (ValueError, RecursionError, UnicodeError):
                gateway = scope["path"].startswith("/gateway/")
                await JSONResponse(
                    {"error": "Malformed request or excessive nesting. Check your input."},
                    status_code=403 if gateway else 422,
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)
                return
        supplied = False

        async def buffered():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, buffered, send)
