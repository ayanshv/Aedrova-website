"""Python website, account/paywall API and managed runtime gateway."""

import asyncio
import base64
import hashlib
import json
import re
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlencode
from uuid import UUID

import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from aedrova_site import discovery, promotion
from aedrova_site.boundaries import BodyLimit, ResponseHeaders
from aedrova_site.communications import unsubscribe
from aedrova_site.config import Config
from aedrova_site.error_pages import BrowserErrors
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
from aedrova_site.policy import PLAN_POLICY, PUBLIC_PLAN_PRICES
from aedrova_site.services import Identity, Payments, random_token
from aedrova_site.speech import DictationService, SpeechService
from aedrova_site.store import Denied, RateLimited, Store
from aedrova_site.team import TEAM_MEMBERS
from aedrova_site.traffic_limits import TrafficLimits

ROOT = Path(__file__).parent


class BaseModel(PydanticBaseModel):
    model_config = {"extra": "forbid", "str_max_length": 65536}


class WorkspaceBody(BaseModel):
    parent_id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=60)
    nickname: str = Field(
        default="Aedrova", min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _-]*$"
    )


class MoveSpaceBody(BaseModel):
    parent_id: str = Field(min_length=1, max_length=100)
    expected_parent: str = Field(min_length=1, max_length=100)
    confirmed: bool = False


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


class WaitlistBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    consent: bool = Field(default=False, strict=True)
    age_confirmed: bool = Field(default=False, strict=True)
    referral_source: Literal[
        "",
        "chatgpt",
        "claude",
        "gemini",
        "perplexity",
        "search",
        "social",
        "friend",
        "other",
        "prefer_not",
    ] = ""
    referral_detail: str = Field(default="", max_length=160)


class UnsubscribeBody(BaseModel):
    token: str = Field(min_length=40, max_length=2048)


class MeetingConsentBody(MeetingJoinBody):
    transcription: bool = Field(default=False, strict=True)
    ai_context: bool = Field(default=False, strict=True)


class MeetingTextBody(MeetingJoinBody):
    identifier: UUID
    revision: int = Field(ge=1, strict=True)
    roster: list[UUID] = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=2000)
    offset_ms: int = Field(default=0, ge=0, le=86400000, strict=True)


class MeetingSpeechBody(MeetingJoinBody):
    model_config = {"extra": "forbid"}
    identifier: UUID
    revision: int = Field(ge=1, strict=True)
    roster: list[UUID] = Field(min_length=1, max_length=100)
    offset_ms: int = Field(default=0, ge=0, le=86400000, strict=True)
    audio: str = Field(min_length=1, max_length=427000)


class DictationBody(BaseModel):
    model_config = {"extra": "forbid"}
    channel: UUID
    identifier: UUID
    audio: str = Field(min_length=1, max_length=1280100)


class VerifyUploadBody(BaseModel):
    model_config = {"extra": "forbid"}
    identifier: UUID
    parent: UUID | None = None


class MeetingTranscriptEdit(BaseModel):
    model_config = {"extra": "forbid"}
    identifier: UUID
    version: int = Field(ge=0, strict=True)
    body: str = Field(min_length=1, max_length=2000)


class MeetingReviewBody(MeetingTranscriptEdit):
    decision: bool = Field(default=False, strict=True)


class MeetingWithdrawBody(MeetingJoinBody):
    delete: bool = Field(default=False, strict=True)


class MeetingConfirmBody(MeetingJoinBody):
    segments: list[MeetingTranscriptEdit] = Field(min_length=1, max_length=10000)


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
            usage_limits=config.usage_limits,
            company_budget=config.company_budget_microusd,
            free_pool=config.free_pool_microusd,
            free_enabled=config.free_enabled,
            early_access_enabled=config.early_access_enabled,
            hierarchy_enabled=config.space_hierarchy_enabled,
            alert_thresholds=config.budget_alert_thresholds,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_timeout=config.db_pool_timeout,
            development_ai=config.development_ai,
        ),
        Identity(config),
    )
    identity.hierarchy_available = store.hierarchy_available
    asset_version = hashlib.sha256(
        (ROOT / "static/site.css").read_bytes()
        + (ROOT / "static/site.js").read_bytes()
        + (ROOT / "static/preparation.js").read_bytes()
    ).hexdigest()[:12]
    database_events(store.engine)
    payments = Payments(config, store)
    templates = Jinja2Templates(directory=ROOT / "templates")
    leases = MeetingLeases(store, require_external=config.production)
    speech = SpeechService(config, store)
    dictation = DictationService(config, store)

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
            await asyncio.to_thread(_app.state.dots.connections.close)
            for provider in _app.state.dots.providers.values():
                await asyncio.to_thread(provider.close)
            await asyncio.to_thread(speech.close)
            await asyncio.to_thread(dictation.close)
            await asyncio.to_thread(store.engine.dispose)

    app = FastAPI(
        title="Aedrova", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.meeting_leases = leases
    app.state.speech = speech
    app.state.dictation = dictation

    from aedrova_site.uploads import UploadVerifier

    uploads = UploadVerifier(identity, store)
    app.state.uploads = uploads

    @app.post("/api/files/verify")
    def verify_upload(request: Request, body: VerifyUploadBody):
        return uploads.verify(auth(request, change=True), body.identifier, body.parent)

    @app.get("/api/chat/speech/capabilities")
    def dictation_capabilities(request: Request):
        identity.user(auth(request))
        return {"enabled": config.chat_speech_enabled, "max_seconds": 30}

    @app.post("/api/chat/speech")
    def chat_dictation(request: Request, body: DictationBody):
        if not config.chat_speech_enabled:
            raise Denied("Chat dictation is being prepared. You can still type your message.")
        token = auth(request, change=True)
        user = identity.user(token)
        channels = identity.request(
            "/rest/v1/channels?id=eq." + str(body.channel) + "&select=workspace_id", token
        )
        if len(channels) != 1:
            raise Denied("Channel access changed.")
        workspace = channels[0]["workspace_id"]
        identity.require(token, workspace)
        context = identity.billing_context(token, workspace)
        return dictation.transcribe_draft(
            user["id"], body, workspace=workspace, billing_workspace=context["billing_workspace"]
        )

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
        return await call_next(request)

    app.add_middleware(BodyLimit)
    app.add_middleware(TrafficLimits, store=store)
    app.add_middleware(Admission, maximum=config.gateway_max_concurrency)
    app.add_middleware(RequestEvents)
    app.add_middleware(BrowserErrors)
    app.add_middleware(ResponseHeaders, config=config)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _exc):
        # Pydantic's default response includes input values (including audio/tokens).
        return JSONResponse(
            {"error": "Some request fields are invalid. Check your input."}, status_code=422
        )

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

    from aedrova_site.dots import install as install_dots

    install_dots(app, config, store, identity, auth)

    def page(request, name, title, **context):
        return templates.TemplateResponse(
            request=request,
            name=name + ".html",
            context={
                "title": title,
                "seo": discovery.metadata(config, request.url.path, title),
                "stripe_test_mode": config.stripe_test_mode,
                "checkout_enabled": config.checkout_enabled,
                "waitlist_only": config.waitlist_only,
                "plan_policy": PLAN_POLICY,
                "public_prices": PUBLIC_PLAN_PRICES,
                "usage_policy": store.usage_policy,
                "free_enabled": config.free_enabled,
                "promotion": promotion.status(),
                "early_access_enabled": config.early_access_enabled,
                "asset_version": asset_version,
                "team_members": TEAM_MEMBERS,
                **context,
            },
        )

    @app.get("/")
    def home(request: Request):
        return page(request, "home", "Talk. Build. Together")

    @app.get("/product")
    def product(request: Request):
        return page(request, "product", "What is Aedrova?")

    @app.get("/faq")
    def public_faq(request: Request):
        return page(request, "faq", "Aedrova FAQ")

    @app.get("/about")
    def public_about(request: Request):
        return page(request, "about", "About Aedrova")

    @app.get("/research/crawlability")
    def public_crawlability(request: Request):
        return page(request, "crawlability", "Aedrova crawlability study")

    @app.get("/robots.txt")
    def crawl_rules():
        return Response(discovery.robots(config), media_type="text/plain")

    @app.get("/sitemap.xml")
    def crawl_sitemap():
        return Response(discovery.sitemap(config), media_type="application/xml")

    @app.get("/waitlist")
    def waitlist(request: Request):
        return page(request, "waitlist", "Join the waitlist")

    @app.post("/api/waitlist")
    def join_waitlist(request: Request, body: WaitlistBody):
        email = body.email.strip().lower()
        if (
            not body.consent
            or not body.age_confirmed
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
        ):
            raise HTTPException(
                422, "Enter a valid email, confirm eligibility and agree to receive launch updates."
            )
        if request.headers.get("origin") != config.origin:
            raise HTTPException(403, "Join from the Aedrova website.")
        store.rate_limit(
            "waitlist:" + (request.client.host if request.client else "unknown"),
            limit=300,
            seconds=3600,
        )
        store.rate_limit(
            "waitlist-email:" + hashlib.sha256(email.encode()).hexdigest(), limit=5, seconds=3600
        )
        store.session(
            "waitlist:" + hashlib.sha256(email.encode()).hexdigest(),
            {
                "kind": "waitlist",
                "email": email,
                "consent": "launch-updates-v1",
                "eligibility": "13-plus-and-guardian-if-required-v1",
                "referral_source": body.referral_source,
                "referral_detail": body.referral_detail.strip()
                if body.referral_source not in {"", "prefer_not"}
                else "",
            },
            lifetime=365 * 86400,
        )
        return {"ok": True}

    @app.get("/unsubscribe")
    def unsubscribe_page(request: Request):
        return page(request, "unsubscribe", "Email preferences")

    @app.post("/api/unsubscribe")
    def stop_launch_updates(request: Request, body: UnsubscribeBody):
        if request.headers.get("origin") != config.origin:
            raise HTTPException(403, "Use the Aedrova website.")
        store.rate_limit(
            "unsubscribe:" + (request.client.host if request.client else "unknown"),
            limit=30,
            seconds=60,
        )
        unsubscribe(store, body.token)
        return {"ok": True}

    @app.get("/onboarding")
    def onboarding(request: Request):
        return page(request, "onboarding", "Make room for your next idea")

    @app.get("/api/early-access")
    def early_access_offer(request: Request):
        store.rate_limit(
            "promotion:" + (request.client.host if request.client else "unknown"),
            limit=120,
            seconds=60,
        )
        return JSONResponse(promotion.status(), headers={"Cache-Control": "no-store"})

    @app.get("/plans")
    def plans(request: Request):
        allowances = {
            name: (
                f"${cast(int, approved['allowance_microusd']) / 1_000_000:g} "
                "included AI usage per billing period"
            )
            for name, approved in PLAN_POLICY.items()
        }
        return page(
            request,
            "plans",
            "Your team, plus AI",
            allowances=allowances,
            billing_interval=(
                "annual" if request.query_params.get("billing") == "annual" else "monthly"
            ),
            usage_policy=store.usage_policy,
            plan_policy=PLAN_POLICY,
        )

    @app.get("/account")
    def account(request: Request):
        if config.waitlist_only:
            return RedirectResponse("/waitlist", status_code=303)
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
            selected_plan=plan if plan in {"monthly", "annual"} else "",
            plan_policy=PLAN_POLICY,
            usage_policy=store.usage_policy,
        )

    @app.get("/welcome")
    def welcome(request: Request):
        if config.waitlist_only:
            return RedirectResponse("/waitlist", status_code=303)
        return page(request, "welcome", "Welcome to what’s next")

    @app.get("/download")
    def download(request: Request):
        if config.waitlist_only:
            return RedirectResponse("/waitlist", status_code=303)
        return page(request, "download", "Aedrova for Mac", release_ready=config.release_ready)

    @app.get("/enterprise")
    def enterprise(request: Request):
        return page(request, "enterprise", "Let’s talk")

    @app.get("/support")
    def support(request: Request):
        return page(request, "support", "Customer support")

    @app.get("/privacy")
    def privacy(request: Request):
        return page(request, "legal", "Privacy", kind="privacy")

    @app.get("/terms")
    def terms(request: Request):
        return page(request, "legal", "Terms", kind="terms")

    @app.get("/data-controls")
    @app.get("/subprocessors")
    @app.get("/cookies")
    @app.get("/acceptable-use")
    @app.get("/security")
    @app.get("/refunds")
    def trust(request: Request):
        kind = request.url.path.strip("/")
        return page(request, "trust", kind.replace("-", " ").title(), kind=kind)

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
        if config.waitlist_only:
            return RedirectResponse("/waitlist", status_code=303)
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
        bud_state = request.query_params.get("bud", "")
        if bud_state and not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", bud_state):
            raise Denied("Invalid Bud authorization.")
        dot_state = request.query_params.get("dot", "")
        if dot_state and not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", dot_state):
            raise Denied("Invalid Dot authorization.")
        store.session(
            state,
            {
                "verifier": verifier,
                "plan": plan if plan in {"monthly", "annual"} else "",
                "dot": dot_state,
                "bud": bud_state,
            },
            lifetime=600,
        )
        target = (
            config.supabase_url
            + "/auth/v1/authorize?"
            + urlencode(
                {
                    "provider": "google",
                    "scopes": "openid email profile",
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
        if session.get("dot"):
            return_path = "/dots/authorize/" + session["dot"]
        if session.get("bud"):
            return_path = "/buds/authorize/" + session["bud"]
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
            "space_hierarchy_enabled": config.space_hierarchy_enabled,
            "early_access_active": config.early_access_enabled and promotion.status()["active"],
            "early_access_ends_at": promotion.ENDS_AT,
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
        if body.parent_id:
            if not config.space_hierarchy_enabled:
                raise Denied("Subspaces are being prepared. No billing change was made.")
            identity.require(token, body.parent_id, billing=True)
            workspace = identity.request(
                "/rest/v1/rpc/create_subspace",
                token,
                method="POST",
                data={"p_parent": body.parent_id, "p_name": body.name.strip()},
            )
            return {"id": workspace}
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
        if config.early_access_enabled:
            store.grant_early_access(user["id"], workspace)
        return {"id": workspace}

    @app.post("/api/subspaces/{workspace}/move")
    def move_subspace(request: Request, workspace: str, body: MoveSpaceBody):
        if not config.space_hierarchy_enabled or not body.confirmed:
            raise Denied("Review and confirm the subspace billing move first.")
        token = auth(request, change=True)
        user = identity.require(token, workspace, billing=True)
        store.rate_limit("move-space:" + user["id"], limit=5)
        result = identity.request(
            "/rest/v1/rpc/move_subspace",
            token,
            method="POST",
            data={
                "p_workspace": workspace,
                "p_parent": body.parent_id,
                "p_expected_parent": body.expected_parent,
            },
        )
        return {"id": result}

    @app.get("/api/balance/{workspace}")
    def balance(request: Request, workspace: str):
        context = identity.billing_context(auth(request), workspace)
        try:
            return {**store.balance(context["billing_workspace"]), **context}
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

    @app.post("/api/free/{workspace}")
    def activate_free(request: Request, workspace: str):
        if not config.free_enabled or config.waitlist_only:
            raise Denied("Free access opens after the waitlist. No AI usage was started.")
        token = auth(request, change=True)
        context = identity.billing_context(token, workspace)
        workspace = context["billing_workspace"]
        user = identity.require(token, workspace, billing=True)
        store.rate_limit("free:" + user["id"], limit=5)
        if config.early_access_enabled and promotion.status()["active"]:
            store.grant_early_access(user["id"], workspace)
            return store.balance(workspace)
        return store.activate_free(user["id"], workspace)

    @app.post("/api/checkout")
    def checkout(request: Request, body: CheckoutBody):
        token = auth(request, change=True)
        context = identity.billing_context(token, body.workspace)
        if context["billing_workspace"] != body.workspace:
            raise Denied(
                "This subspace shares its parent's subscription. Manage team billing "
                "from the parent Space."
            )
        user = identity.require(token, body.workspace, billing=True)
        store.rate_limit("checkout:" + user["id"], limit=10)
        spaces = identity.workspaces(token)
        space = next((space for space in spaces if space["id"] == body.workspace), None)
        if not space:
            raise Denied("Your workspace access changed. Refresh before checking out.")
        name = space["name"]
        owner = user
        if space["role"] != "owner":
            roster = identity.request("/rest/v1/rpc/list_members", token, method="POST", data={})
            owner = next(
                (
                    {"id": m["user_id"], "email": m.get("email", "")}
                    for m in roster
                    if m["workspace_id"] == body.workspace and m["role"] == "owner"
                ),
                None,
            )
            if not owner:
                raise Denied("The workspace billing owner could not be verified.")
        return {
            "url": payments.checkout(
                body.workspace,
                body.plan,
                body.request_id,
                owner=owner["id"],
                owner_email=owner.get("email", ""),
                workspace_name=name,
            )
        }

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
        token = auth(request, change=True)
        context = identity.billing_context(token, body.workspace)
        workspace = context["billing_workspace"]
        user = identity.require(token, workspace, billing=True)
        store.rate_limit("topup:" + user["id"], limit=5)
        return {"url": payments.topup(workspace, body.request_id)}

    @app.post("/api/portal/{workspace}")
    def portal(request: Request, workspace: str):
        token = auth(request, change=True)
        context = identity.billing_context(token, workspace)
        workspace = context["billing_workspace"]
        identity.require(token, workspace, billing=True)
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

    @app.get("/api/meetings/capabilities")
    def meeting_capabilities(request: Request):
        token = meeting_token(request)
        identity.user(token)
        return {
            "meeting_text": config.meeting_context_enabled,
            "audio_transcription": config.speech_enabled,
        }

    def meeting_context_token(request):
        if not config.meeting_context_enabled:
            raise Denied("Meeting text is being prepared. No transcription was started.")
        return meeting_token(request)

    @app.post("/api/meetings/speech")
    def meeting_speech(request: Request, body: MeetingSpeechBody):
        if not config.speech_enabled:
            raise Denied("Audio transcription is not enabled.")
        token = meeting_context_token(request)
        user = identity.user(token)
        # RLS resolves the workspace; never accept a client-supplied billing scope.
        meetings = identity.request(
            "/rest/v1/meetings?id=eq." + str(body.meeting) + "&select=channel_id", token
        )
        if not meetings:
            raise Denied("Meeting access changed.")
        channels = identity.request(
            "/rest/v1/channels?id=eq." + meetings[0]["channel_id"] + "&select=workspace_id", token
        )
        if not channels:
            raise Denied("Channel access changed.")
        workspace = channels[0]["workspace_id"]
        identity.require(token, workspace)
        context = identity.billing_context(token, workspace)
        return speech.transcribe(
            user["id"], body, workspace=workspace, billing_workspace=context["billing_workspace"]
        )

    @app.get("/api/meetings/transcript/{meeting}")
    def meeting_transcript(request: Request, meeting: UUID, page: int = 0, latest: bool = False):
        token = meeting_context_token(request)
        if not 0 <= page <= 199:
            raise Denied("Invalid transcript page.")
        if latest:
            return identity.request(
                "/rest/v1/meeting_transcript_segments?meeting_id=eq."
                + str(meeting)
                + "&select=*&order=created_at.desc,id.desc&limit=20",
                token,
            )
        return identity.request(
            "/rest/v1/meeting_transcript_segments?meeting_id=eq."
            + str(meeting)
            + "&select=*&order=offset_ms.asc,id.asc&limit=50&offset="
            + str(page * 50),
            token,
        )

    @app.get("/api/meetings/history/{channel}")
    def meeting_history(request: Request, channel: UUID):
        token = meeting_context_token(request)
        return identity.request(
            "/rest/v1/meetings?channel_id=eq."
            + str(channel)
            + "&select=id,title,started_at,ended_at&order=started_at.desc&limit=50",
            token,
        )

    @app.post("/api/meetings/transcript/review")
    def meeting_review(request: Request, body: MeetingReviewBody):
        token = meeting_context_token(request)
        version = identity.request(
            "/rest/v1/rpc/review_meeting_segment",
            token,
            method="POST",
            data={
                "p_id": str(body.identifier),
                "p_version": body.version,
                "p_body": body.body,
                "p_decision": body.decision,
            },
        )
        return {"version": version}

    @app.get("/api/meetings/wrapup/{meeting}")
    def meeting_wrapup(request: Request, meeting: UUID):
        token = meeting_context_token(request)
        return identity.request(
            "/rest/v1/rpc/meeting_wrapup_status",
            token,
            method="POST",
            data={"p_meeting": str(meeting)},
        )

    @app.post("/api/meetings/transcript/confirm")
    def meeting_confirm(request: Request, body: MeetingConfirmBody):
        token = meeting_context_token(request)
        count = identity.request(
            "/rest/v1/rpc/confirm_meeting_transcript",
            token,
            method="POST",
            data={
                "p_meeting": str(body.meeting),
                "p_segments": [
                    {"identifier": str(row.identifier), "version": row.version, "body": row.body}
                    for row in body.segments
                ],
            },
        )
        return {"confirmed": count}

    @app.post("/api/meetings/consent")
    def meeting_consent(request: Request, body: MeetingConsentBody):
        token = meeting_context_token(request)
        identity.request(
            "/rest/v1/rpc/set_meeting_consent",
            token,
            method="POST",
            data={
                "p_meeting": str(body.meeting),
                "p_transcription": body.transcription,
                "p_ai": body.ai_context,
            },
        )
        return identity.request(
            "/rest/v1/rpc/meeting_consent_snapshot",
            token,
            method="POST",
            data={"p_meeting": str(body.meeting)},
        )

    @app.post("/api/meetings/text")
    def meeting_text(request: Request, body: MeetingTextBody):
        token = meeting_context_token(request)
        identifier = identity.request(
            "/rest/v1/rpc/append_meeting_text",
            token,
            method="POST",
            data={
                "p_meeting": str(body.meeting),
                "p_id": str(body.identifier),
                "p_revision": body.revision,
                "p_roster": sorted(str(u) for u in body.roster),
                "p_body": body.body,
                "p_offset": body.offset_ms,
            },
        )
        return {"id": identifier}

    @app.post("/api/meetings/text/withdraw")
    def meeting_withdraw(request: Request, body: MeetingWithdrawBody):
        token = meeting_context_token(request)
        identity.request(
            "/rest/v1/rpc/withdraw_meeting_text",
            token,
            method="POST",
            data={"p_meeting": str(body.meeting), "p_delete": body.delete},
        )
        return {"ok": True}

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
        user = identity.require(
            token, body.workspace, billing=store.development_workspace(body.workspace)
        )
        store.rate_limit("runs:" + user["id"], limit=20)
        store.reconcile_expired()
        context = identity.billing_context(token, body.workspace)
        run = store.create_run(
            user["id"],
            body.workspace,
            body.provider,
            body.request_id,
            billing_workspace=context["billing_workspace"],
        )
        store.session(run["token"], {"access_token": token}, lifetime=7200)
        return {
            **run,
            "limits": store.run_limits({"workspace": context["billing_workspace"]}),
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
