"""Provider protocol proxy with atomic reservations and conservative uncertain accounting."""

import asyncio
import hashlib
import json
import math
import time

import httpx
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response, StreamingResponse

from aedrova_site.observability import emit
from aedrova_site.store import Denied


def cost(usage, model):
    if not isinstance(usage, dict):
        return None
    inputs = usage.get("input_tokens")
    outputs = usage.get("output_tokens")
    if type(inputs) is not int or type(outputs) is not int or inputs < 0 or outputs < 0:
        return None
    # OpenAI includes cached tokens in input_tokens; Anthropic reports cache
    # reads/writes separately. Never charge cached OpenAI tokens twice.
    details = usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        return None
    cached = details.get("cached_tokens", 0)
    writes = usage.get("cache_creation_input_tokens", 0)
    reads = usage.get("cache_read_input_tokens", 0)
    if (
        any(type(value) is not int or value < 0 for value in (writes, reads, cached))
        or cached > inputs
    ):
        return None
    creation = usage.get("cache_creation") or {}
    if not isinstance(creation, dict):
        return None
    long_writes = creation.get("ephemeral_1h_input_tokens", 0)
    if type(long_writes) is not int or long_writes < 0 or long_writes > writes:
        return None
    return math.ceil(
        (
            (inputs - cached) * model["input_rate"]
            + outputs * model["output_rate"]
            + (cached + reads) * model.get("cache_read_rate", model["input_rate"])
            + (writes - long_writes) * model.get("cache_write_rate", model["input_rate"] * 2)
            + long_writes * model.get("cache_long_write_rate", model["input_rate"] * 2)
        )
        / 1_000_000
    )


def usage_from_events(data, provider):
    usage, completed = {}, False
    for line in data.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except ValueError:
            continue
        if not isinstance(event, dict):
            raise ValueError("Invalid provider event.")
        kind = event.get("type")
        if provider == "codex" and kind == "response.completed":
            response = event.get("response", {})
            if not isinstance(response, dict):
                raise ValueError("Invalid provider completion.")
            usage, completed = response.get("usage", {}), True
        elif provider == "claude_code":
            if kind == "message_start":
                message = event.get("message", {})
                update = message.get("usage", {}) if isinstance(message, dict) else None
                if not isinstance(update, dict):
                    raise ValueError("Invalid provider usage.")
                usage.update(update)
            elif kind == "message_delta":
                update = event.get("usage", {})
                if not isinstance(update, dict):
                    raise ValueError("Invalid provider usage.")
                usage.update(update)
            elif kind == "message_stop":
                completed = True
    return usage, completed


async def authorize_run(request: Request, provider, config, store, identity):
    if not config.gateway_enabled or provider not in config.models:
        raise Denied("Managed AI is not configured yet. No provider usage was started.")
    token = request.headers.get("authorization", "").removeprefix("Bearer ") or request.headers.get(
        "x-api-key", ""
    )
    run = await asyncio.to_thread(store.run, token)
    if run["provider"] != provider:
        raise Denied("This build token cannot access that provider.")
    session = await asyncio.to_thread(store.session, token)
    user = await asyncio.to_thread(identity.require, session["access_token"], run["workspace"])
    if user["id"] != run["user_id"]:
        raise Denied("Build account changed.")
    await asyncio.to_thread(store.rate_limit, "inference:" + run["id"], limit=120)
    return run


async def inference(request: Request, provider, config, store, identity, *, compact=False):
    run = await authorize_run(request, provider, config, store, identity)
    raw = await request.body()
    if len(raw) > 8 * 1024 * 1024:
        raise Denied("Model request exceeds the 8 MiB limit.")
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError()
    except (ValueError, RecursionError) as exc:
        raise Denied("Invalid model request.") from exc
    if not isinstance(body.get("tools", []), list) or any(
        not isinstance(tool, dict) for tool in body.get("tools", [])
    ):
        raise Denied("Invalid tool definitions.")

    # Remote image/file references can incur unbounded input costs. This beta accepts
    # text and locally supplied tool results; reject hosted multimedia references.
    def remote_content(value):
        stack = [(value, 0)]
        visited = 0
        while stack:
            value, depth = stack.pop()
            visited += 1
            if depth > 100 or visited > 100000:
                raise Denied("Model request exceeds its nesting or item limit.")
            if isinstance(value, dict):
                if value.get("type") in {"input_image", "input_file", "image", "document"}:
                    return True
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
        return False

    if remote_content(body):
        raise Denied("Multimedia model inputs are not enabled in this coding beta.")
    model = config.models[provider]
    if provider == "codex":
        key, output_key = config.openai_key, "max_output_tokens"
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        if any(tool.get("type") not in {"function", "custom"} for tool in body.get("tools", [])):
            raise Denied("Hosted tools are not included in this beta gateway.")
        body["store"] = False
        if body.get("previous_response_id") or body.get("background"):
            raise Denied("Managed builds require inline, stateless requests.")
        body.pop("previous_response_id", None)
        body["background"] = False
        body["service_tier"] = "default"
        if compact:
            url += "/compact"
            body = {
                key: value
                for key, value in body.items()
                if key in {"input", "instructions", "service_tier"}
            }
    else:
        key, output_key = config.anthropic_key, "max_tokens"
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        # Provider-hosted tools have separate costs. Local agent tools have no type or type=custom.
        if any(tool.get("type") not in {None, "custom"} for tool in body.get("tools", [])):
            raise Denied("Hosted tools are not included in this beta gateway.")
        beta = request.headers.get("anthropic-beta", "")
        approved_beta = set(model.get("beta_headers", []))
        if beta and not set(beta.split(",")) <= approved_beta:
            raise Denied("This Claude beta capability has not been approved for managed access.")
        if beta:
            headers["anthropic-beta"] = beta
        body["service_tier"] = "standard"
    if not key:
        raise Denied("This model's commercial billing is not configured yet.")
    try:
        output = min(16384, max(1, int(body.get(output_key, 4096))))
    except (ValueError, TypeError) as exc:
        raise Denied("Invalid output limit.") from exc
    body["model"] = model["id"]
    if compact:
        # The standalone API has no output-limit parameter. Reserve its model
        # ceiling before calling it; small balances fail without provider spend.
        output = 128000
    else:
        body[output_key] = output
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) + 8192 > model.get("max_input_tokens", 200_000):
        raise Denied(
            "This request exceeds the beta model context limit. "
            "Narrow the build or start a fresh run."
        )
    # One byte per token is a conservative input bound, plus protocol/tool overhead.
    reserve = math.ceil(
        (
            (len(encoded) + 8192) * model["input_rate"] * (2 if provider == "claude_code" else 1)
            + output * model["output_rate"]
        )
        / 1_000_000
    )
    fingerprint = (b"compact:" if compact else b"response:") + encoded
    identifier, cached = await asyncio.to_thread(
        store.reserve, run, hashlib.sha256(fingerprint).hexdigest(), reserve
    )
    streaming = body.get("stream", False)
    media = "text/event-stream" if streaming else "application/json"
    if cached is not None:
        return Response(cached, media_type=media)

    async def generate():
        result = bytearray()
        settled = False
        started = time.monotonic()
        try:
            async with (
                asyncio.timeout(config.provider_deadline_seconds),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(180, connect=15), follow_redirects=False
                ) as client,
            ):
                async with client.stream("POST", url, headers=headers, content=encoded) as upstream:
                    if upstream.status_code != 200:
                        # Explicit rejection: no completed inference; keep diagnostics private.
                        await asyncio.to_thread(store.settle, identifier, 0)
                        settled = True
                        failure = {
                            "error": {
                                "message": (
                                    "The model provider rejected this request. Check managed "
                                    "provider billing and model access."
                                ),
                                "type": "provider_error",
                            }
                        }
                        if streaming:
                            yield ("event: error\ndata: " + json.dumps(failure) + "\n\n").encode()
                        else:
                            yield json.dumps(failure).encode()
                        return
                    async for chunk in upstream.aiter_bytes():
                        result.extend(chunk)
                        if len(result) > 16 * 1024 * 1024:
                            raise Denied("Provider response exceeded the 16 MiB limit.")
                        if streaming:
                            yield chunk
                        if await request.is_disconnected():
                            raise Denied("The local agent disconnected.")
            if streaming:
                usage, complete = usage_from_events(bytes(result), provider)
            else:
                response = json.loads(result)
                if not isinstance(response, dict):
                    raise ValueError("Invalid provider response.")
                usage = response.get("usage", {})
                complete = not response.get("error") and (
                    provider != "codex"
                    or response.get("status") == "completed"
                    or (compact and response.get("object") == "response.compaction")
                )
            await asyncio.to_thread(
                store.settle,
                identifier,
                cost(usage, model) if complete else None,
                bytes(result) if complete else None,
                usage,
            )
            settled = True
            emit(
                "ai_settled",
                provider=provider,
                complete=complete,
                input_tokens=usage.get("input_tokens")
                if type(usage.get("input_tokens")) is int
                else None,
                output_tokens=usage.get("output_tokens")
                if type(usage.get("output_tokens")) is int
                else None,
                duration_ms=round((time.monotonic() - started) * 1000, 2),
            )
            if not streaming:
                yield bytes(result)
        except (httpx.HTTPError, ValueError, RecursionError, Denied, TimeoutError, SQLAlchemyError):
            emit("ai_interrupted", provider=provider)
            if streaming:
                yield (
                    b'event: error\ndata: {"error":{"message":"Managed model '
                    b"connection interrupted. Review partial work before "
                    b'retrying."}}\n\n'
                )
            else:
                yield b'{"error":{"message":"Managed model connection interrupted."}}'
        finally:
            if not settled:
                # Never refund an uncertain upstream request or replay it silently.
                try:
                    await asyncio.shield(asyncio.to_thread(store.settle, identifier, None))
                except SQLAlchemyError:
                    emit("ai_settlement_deferred", provider=provider)

    return StreamingResponse(
        generate(),
        media_type=media,
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
