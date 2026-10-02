"""Bound request bodies even when a client omits Content-Length."""

from starlette.responses import JSONResponse


class BodyLimit:
    def __init__(self, app, maximum=8 * 1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        chunks, length = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            length += len(chunk)
            if length > self.maximum:
                await JSONResponse({"error": "Request too large."}, status_code=413)(
                    scope, receive, send
                )
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        supplied = False

        async def buffered():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, buffered, send)
