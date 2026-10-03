"""Python website, account/paywall API and managed runtime gateway."""

import asyncio
import base64
import hashlib
import json
import re
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import cast
from urllib.parse import urlencode
from uuid import UUID

import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from aedrova_site.boundaries import BodyLimit
from aedrova_site.config import Config
from aedrova_site.gateway import authorize_run, inference
from aedrova_site.meeting_leases import MeetingLeases
from aedrova_site.meetings import issue_meeting_access
from aedrova_site.observability import (
    Admission,
    RequestEvents,
    configure_events,
    database_events,
    emit,
)
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.services import Identity, Payments, random_token
from aedrova_site.store import Denied, RateLimited, Store

ROOT = Path(__file__).parent


class WorkspaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    nickname: str = Field(
        default="Aedrova", min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _-]*$"
    )


class CheckoutBody(BaseModel):
    workspace: str = Field(min_length=1, max_length=100)
    plan: str
    request_id: str = Field(min_length=16, max_length=100)


class RunBody(BaseModel):
    workspace: str = Field(min_length=1, max_length=100)
    provider: str
    request_id: str = Field(min_length=16, max_length=100)


class MeetingJoinBody(BaseModel):
    meeting: UUID


class InquiryBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    team: str = Field(default="", max_length=100)
    message: str = Field(min_length=1, max_length=2000)


def create_app(config=None):
    configure_events()
    config = config or Config.load()
    config.validate()
    store, identity = (
        Store(
            config.database,
            config.encryption_key,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_timeout=config.db_pool_timeout,
        ),
        Identity(config),
    )
    asset_version = hashlib.sha256(
        (ROOT / "static/site.css").read_bytes() + (ROOT / "static/site.js").read_bytes()
    ).hexdigest()[:12]
    database_events(store.engine)
    payments = Payments(config, store)
    templates = Jinja2Templates(directory=ROOT / "templates")
    leases = MeetingLeases(store, require_external=config.production)

    @asynccontextmanager
    async def lifespan(_app):
        guard = (
            asyncio.create_task(leases.run(config, identity))
            if config.meetings_enabled and not config.production
            else None
        )
        try:
            yield
        finally:
            if guard:
                guard.cancel()
                with suppress(asyncio.CancelledError):
                    await guard
            await asyncio.to_thread(identity.close)
            await asyncio.to_thread(store.engine.dispose)

    app = FastAPI(
        title="Aedrova", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.meeting_leases = leases
    app.state.config, app.state.store, app.state.identity, app.state.payments = (
        config,
        store,
        identity,
        payments,
    )
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.middleware("http")
    async def boundaries(request, call_next):
        if request.headers.get("origin") and request.headers["origin"] != config.origin:
            return JSONResponse({"error": "This origin is not allowed."}, status_code=403)
        try:
            if int(request.headers.get("content-length", "0")) > 8 * 1024 * 1024:
                return JSONResponse({"error": "Request too large."}, status_code=413)
        except ValueError:
            return JSONResponse({"error": "Invalid content length."}, status_code=400)
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self' data:; font-src 'self'; "
                    "media-src 'self'; "
                    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
                    "form-action 'self'"
                ),
            }
        )
        if not request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        if config.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    app.add_middleware(BodyLimit)
    app.add_middleware(Admission, maximum=config.gateway_max_concurrency)
    app.add_middleware(RequestEvents)

    @app.exception_handler(RateLimited)
    async def limited(_request, exc):
        return JSONResponse(
            {"error": str(exc)}, status_code=429, headers={"Retry-After": str(exc.retry_after)}
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(_request, _exc):
        emit("database_failure", category=type(_exc).__name__)
        return JSONResponse(
            {"error": "The service is temporarily unavailable. Retry shortly."},
            status_code=503,
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(Denied)
    async def denied(_request, exc):
        return JSONResponse({"error": str(exc)}, status_code=403)

    @app.exception_handler(stripe.StripeError)
    async def stripe_error(_request, _exc):
        return JSONResponse(
            {"error": "Billing could not complete this request. Please retry shortly."},
            status_code=503,
        )

    def auth(request, *, change=False):
        bearer = request.headers.get("authorization", "")
        if bearer.startswith("Bearer "):
            store.rate_limit(
                "account:" + hashlib.sha256(bearer[7:].encode()).hexdigest(), limit=120
            )
            return bearer[7:]
        session_token = request.cookies.get("aedrova_session", "")
        store.rate_limit("account:" + hashlib.sha256(session_token.encode()).hexdigest(), limit=120)
        session = store.session(session_token)
        if change and not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), session["csrf"]
        ):
            raise Denied("Refresh this page before making changes.")
        return session["access_token"]

    def page(request, name, title, **context):
        return templates.TemplateResponse(
            request=request,
            name=name + ".html",
            context={
                "title": title,
                "stripe_test_mode": config.stripe_test_mode,
                "checkout_enabled": config.checkout_enabled,
                "asset_version": asset_version,
                **context,
            },
        )

    @app.get("/")
    def home(request: Request):
        return page(request, "home", "Talk. Build. Together")

    @app.get("/onboarding")
    def onboarding(request: Request):
        return page(request, "onboarding", "Make room for your next idea")

    @app.get("/plans")
    def plans(request: Request):
        allowances = {
            name: (
                f"${cast(int, approved['allowance_microusd']) / 1_000_000:g} "
                "included AI usage per billing period"
            )
            for name, approved in PLAN_POLICY.items()
        }
        return page(request, "plans", "Find your rhythm", allowances=allowances)

    @app.get("/account")
    def account(request: Request):
        try:
            store.session(request.cookies.get("aedrova_session", ""))
            authenticated = True
        except Denied:
            authenticated = False
        plan = request.query_params.get("plan", "")
        return page(
            request,
            "account",
            "Your workspace",
            authenticated=authenticated,
            selected_plan=plan if plan in {"weekly", "monthly"} else "",
        )

    @app.get("/welcome")
    def welcome(request: Request):
        return page(request, "welcome", "Welcome to what’s next")

    @app.get("/download")
    def download(request: Request):
        return page(request, "download", "Aedrova for Mac", release_ready=config.release_ready)

    @app.get("/enterprise")
    def enterprise(request: Request):
        return page(request, "enterprise", "Let’s talk")

    @app.get("/privacy")
    def privacy(request: Request):
        return page(request, "legal", "Privacy", kind="privacy")

    @app.get("/terms")
    def terms(request: Request):
        return page(request, "legal", "Terms", kind="terms")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "checkout_enabled": config.checkout_enabled,
            "managed_ai_enabled": config.gateway_enabled,
        }

    @app.get("/health/ready")
    def database_readiness():
        try:
            with store.tx(write=False) as db:
                db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    @app.get("/health/meetings")
    def meeting_health():
        ready = config.meetings_enabled and leases.ready()
        return JSONResponse(
            {"status": "ready" if ready else "unavailable"}, status_code=200 if ready else 503
        )

    @app.get("/auth/google")
    def google(request: Request):
        store.rate_limit(
            "oauth:" + (request.client.host if request.client else "unknown"), limit=10
        )
        verifier, state = random_token(), random_token()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        plan = request.query_params.get("plan", "")
        store.session(
            state,
            {"verifier": verifier, "plan": plan if plan in {"weekly", "monthly"} else ""},
            lifetime=600,
        )
        target = (
            config.supabase_url
            + "/auth/v1/authorize?"
            + urlencode(
                {
                    "provider": "google",
                    "redirect_to": config.origin + "/auth/callback",
                    "code_challenge": challenge,
                    "code_challenge_method": "s256",
                }
            )
        )
        result = RedirectResponse(target, status_code=303)
        result.set_cookie(
            "aedrova_oauth",
            state,
            httponly=True,
            secure=config.production or config.origin.startswith("https://"),
            samesite="lax",
            max_age=600,
            path="/auth",
        )
        return result

    @app.get("/auth/callback")
    def callback(request: Request):
        code, state = request.query_params.get("code"), request.cookies.get("aedrova_oauth", "")
        if not code or len(code) > 2000:
            return RedirectResponse("/account?login_error=1", status_code=303)
        try:
            session = store.session(state)
        except Denied:
            return RedirectResponse("/account?login_error=1", status_code=303)
        store.delete_session(state)
        try:
            result = identity.request(
                "/auth/v1/token?grant_type=pkce",
                method="POST",
                data={"auth_code": code, "code_verifier": session["verifier"]},
            )
            user = identity.user(result["access_token"])
        except (Denied, KeyError):
            response = RedirectResponse("/account?login_error=1", status_code=303)
            response.delete_cookie("aedrova_oauth", path="/auth")
            return response
        token = random_token()
        store.session(
            token,
            {"access_token": result["access_token"], "user": user["id"], "csrf": random_token()},
        )
        return_path = "/account"
        if session.get("plan"):
            return_path += "?" + urlencode({"plan": session["plan"]})
        response = RedirectResponse(return_path, status_code=303)
        response.set_cookie(
            "aedrova_session",
            token,
            httponly=True,
            secure=config.production or config.origin.startswith("https://"),
            samesite="lax",
            max_age=3600,
        )
        response.delete_cookie("aedrova_oauth", path="/auth")
        return response

    @app.get("/api/session")
    def session_api(request: Request):
        session = store.session(request.cookies.get("aedrova_session", ""))
        return {
            "csrf": session["csrf"],
            "checkout_enabled": config.checkout_enabled,
            "topup_enabled": bool(config.checkout_enabled and config.topup_price_id),
            "stripe_test_mode": config.stripe_test_mode,
        }

    @app.post("/api/logout")
    def logout(request: Request):
        auth(request, change=True)
        store.delete_session(request.cookies.get("aedrova_session", ""))
        result = JSONResponse({"ok": True})
        result.delete_cookie("aedrova_session")
        return result

    @app.get("/api/workspaces")
    def workspaces(request: Request):
        return identity.workspaces(auth(request))

    @app.post("/api/workspaces")
    def create_workspace(request: Request, body: WorkspaceBody):
        token = auth(request, change=True)
        user = identity.user(token)
        store.rate_limit("create-workspace:" + user["id"], limit=5)
        workspace = identity.request(
            "/rest/v1/rpc/onboard_workspace",
            token,
            method="POST",
            data={
                "p_name": body.name.strip(),
                "p_nickname": body.nickname.strip(),
                "p_provider": "codex",
            },
        )
        return {"id": workspace}

    @app.get("/api/balance/{workspace}")
    def balance(request: Request, workspace: str):
        identity.require(auth(request), workspace)
        try:
            return store.balance(workspace)
        except Denied:
            return {
                "plan": "",
                "status": "no_plan",
                "available": 0,
                "allowance": 0,
                "spent": 0,
                "reserved": 0,
                "period_end": 0,
            }

    @app.post("/api/checkout")
    def checkout(request: Request, body: CheckoutBody):
        user = identity.require(auth(request, change=True), body.workspace, billing=True)
        store.rate_limit("checkout:" + user["id"], limit=10)
        return {"url": payments.checkout(body.workspace, body.plan, body.request_id)}

    @app.get("/api/checkout/status")
    def checkout_status(request: Request, session_id: str):
        token = auth(request)
        if not re.fullmatch(r"cs_[A-Za-z0-9_]{8,200}", session_id):
            raise HTTPException(400, "Invalid checkout reference.")
        if not config.stripe_key:
            raise Denied("Billing confirmation is not configured yet.")
        identity.user(token)
        current = stripe.checkout.Session.retrieve(session_id, api_key=config.stripe_key)
        workspace = current.get("metadata", {}).get("workspace", "")
        identity.require(token, workspace)
        with store.tx() as db:
            customer = db.execute(
                text("SELECT customer FROM billing WHERE workspace=:w"), {"w": workspace}
            ).scalar()
        if (
            not customer
            or current.get("customer") != customer
            or current.get("mode") != "subscription"
        ):
            raise Denied("Checkout does not belong to this workspace.")
        if current.get("livemode") is not (not config.stripe_test_mode):
            raise Denied("Checkout mode does not match this server.")
        # The browser return never grants entitlement. Only signed canonical webhooks do.
        return {
            "workspace": workspace,
            "payment_status": current.get("payment_status"),
            "checkout_status": current.get("status"),
            "billing_status": store.balance(workspace)["status"],
            "stripe_test_mode": config.stripe_test_mode,
        }

    @app.post("/api/topup")
    def topup(request: Request, body: CheckoutBody):
        user = identity.require(auth(request, change=True), body.workspace, billing=True)
        store.rate_limit("topup:" + user["id"], limit=5)
        return {"url": payments.topup(body.workspace, body.request_id)}

    @app.post("/api/portal/{workspace}")
    def portal(request: Request, workspace: str):
        identity.require(auth(request, change=True), workspace, billing=True)
        return {"url": payments.portal(workspace)}

    @app.post("/stripe/webhook")
    async def webhook(request: Request):
        payload = await request.body()
        if len(payload) > 1024 * 1024:
            raise HTTPException(413)
        try:
            await asyncio.to_thread(
                payments.webhook, payload, request.headers.get("stripe-signature", "")
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise HTTPException(400, "Invalid webhook signature.") from exc
        return {"ok": True}

    @app.post("/api/inquiries")
    def inquiry(request: Request, body: InquiryBody):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", body.email):
            raise HTTPException(422, "Enter a valid email address.")
        store.rate_limit(
            "inquiry:" + (request.client.host if request.client else "unknown"),
            limit=5,
            seconds=3600,
        )
        identifier = random_token()
        store.session(
            "inquiry:" + identifier,
            {"kind": "enterprise_inquiry", "reference": identifier, **body.model_dump()},
            lifetime=30 * 86400,
        )
        return {"ok": True, "reference": identifier}

    @app.get("/api/download")
    def release_download():
        path = Path(config.download_path)
        if not config.release_ready or not path.is_file() or path.suffix != ".dmg":
            raise HTTPException(503, "The verified installer is not available yet.")
        return FileResponse(
            path, filename="Aedrova.dmg", media_type="application/x-apple-diskimage"
        )

    @app.get("/api/release")
    def release_information():
        if not config.release_ready:
            raise HTTPException(503, "The verified public installer is not available yet.")
        path = Path(config.download_path)
        try:
            manifest = json.loads(path.with_suffix(".manifest.json").read_text())
            size = path.stat().st_size
        except (OSError, ValueError):
            raise HTTPException(
                503, "The verified public installer is not available yet."
            ) from None
        return {
            "version": manifest["version"],
            "architecture": manifest["architecture"],
            "minimum_macos": manifest["minimum_macos"],
            "size_bytes": size,
            "sha256": config.download_sha256,
            "public_release": True,
        }

    @app.post("/api/meetings/join")
    def meeting_join(request: Request, body: MeetingJoinBody):
        return issue_meeting_access(
            config, identity, store, auth(request, change=True), body.meeting, leases
        )

    def meeting_token(request):
        if not config.meetings_enabled:
            raise Denied("Meetings are being prepared.")
        return auth(request, change=True)

    @app.get("/api/meetings/channel/{channel}")
    def meeting_list(request: Request, channel: UUID):
        token = meeting_token(request)
        return identity.request(
            "/rest/v1/meetings?channel_id=eq."
            + str(channel)
            + "&ended_at=is.null&select=id,title,started_by&limit=1",
            token,
        )

    @app.post("/api/meetings/start/{channel}")
    def meeting_start(request: Request, channel: UUID):
        token = meeting_token(request)
        return {
            "meeting": identity.request(
                "/rest/v1/rpc/start_meeting",
                token,
                method="POST",
                data={"p_channel": str(channel), "p_title": "Team call"},
            )
        }

    @app.post("/api/meetings/pulse")
    def meeting_pulse(request: Request, body: MeetingJoinBody):
        token = meeting_token(request)
        user = identity.user(token)
        identity.request(
            "/rest/v1/rpc/meeting_presence",
            token,
            method="POST",
            data={"p_meeting": str(body.meeting)},
        )
        leases.pulse(body.meeting, user["id"], token)
        return identity.request(
            "/rest/v1/rpc/meeting_consent_snapshot",
            token,
            method="POST",
            data={"p_meeting": str(body.meeting)},
        )

    @app.post("/api/meetings/leave")
    async def meeting_leave(request: Request, body: MeetingJoinBody):
        token = await asyncio.to_thread(meeting_token, request)
        user = await asyncio.to_thread(identity.user, token)
        await asyncio.to_thread(leases.revoke, body.meeting, user["id"])
        await asyncio.to_thread(
            identity.request,
            "/rest/v1/rpc/leave_meeting",
            token,
            method="POST",
            data={"p_meeting": str(body.meeting)},
        )
        return {"ok": True}

    @app.post("/api/meetings/end")
    def meeting_end(request: Request, body: MeetingJoinBody):
        token = meeting_token(request)
        identity.request(
            "/rest/v1/rpc/end_meeting", token, method="POST", data={"p_meeting": str(body.meeting)}
        )
        leases.revoke(body.meeting)
        return {"ok": True}

    @app.post("/api/runs")
    def create_run(request: Request, body: RunBody):
        if not config.gateway_enabled or body.provider not in config.models:
            raise Denied("Included AI access is not configured yet.")
        token = auth(request, change=True)
        user = identity.require(token, body.workspace)
        store.rate_limit("runs:" + user["id"], limit=20)
        store.reconcile_expired()
        run = store.create_run(user["id"], body.workspace, body.provider, body.request_id)
        store.session(run["token"], {"access_token": token}, lifetime=7200)
        return {
            **run,
            "model": config.models[body.provider]["id"],
            "base_url": config.origin
            + "/gateway/"
            + body.provider
            + ("/v1" if body.provider == "codex" else ""),
        }

    @app.post("/api/runs/{run_id}/close")
    def close_run(request: Request, run_id: str):
        user = identity.user(auth(request, change=True))
        store.end_run(run_id, user["id"])
        return {"ok": True}

    @app.post("/gateway/codex/v1/responses")
    async def codex(request: Request):
        return await inference(request, "codex", config, store, identity)

    @app.post("/gateway/codex/v1/responses/compact")
    async def codex_compact(request: Request):
        return await inference(request, "codex", config, store, identity, compact=True)

    @app.post("/gateway/claude_code/v1/messages")
    async def claude(request: Request):
        return await inference(request, "claude_code", config, store, identity)

    @app.post("/gateway/claude_code/v1/messages/count_tokens")
    async def count_tokens(request: Request):
        # Count-only requests spend no provider credits but require the same live access.
        await authorize_run(request, "claude_code", config, store, identity)
        body = await request.body()
        try:
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError()
        except ValueError as exc:
            raise Denied("Invalid model request.") from exc
        return {"input_tokens": len(body) + 8192}

    return app
