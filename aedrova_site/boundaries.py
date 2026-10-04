"""Bound request bodies even when a client omits Content-Length."""

import asyncio

from starlette.responses import JSONResponse


class BodyLimit:
    def __init__(self, app, maximum=8 * 1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        maximum = (
            self.maximum
            if scope["path"].startswith("/gateway/")
            else (512 * 1024 if scope["path"] == "/api/meetings/speech" else
                  (1024 * 1024 if scope["path"] == "/stripe/webhook" else 64 * 1024))
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
        supplied = False

        async def buffered():
            nonlocal supplied
            if not supplied:
                supplied = True
                body = b"".join(chunks)
                chunks.clear()
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, buffered, send)
