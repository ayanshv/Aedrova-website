"""Explicit launch gates. Public configuration never includes private credentials."""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url

from aedrova_site.policy import PLAN_POLICY


@dataclass
class Config:
    origin: str = "http://127.0.0.1:8090"
    database: str = "sqlite:///work/site.sqlite3"
    production: bool = False
    waitlist_only: bool = False
    supabase_database: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 5
    gateway_max_concurrency: int = 8
    provider_deadline_seconds: int = 240
    supabase_url: str = "https://cpelagtufyocepnqcqqd.supabase.co"
    supabase_key: str = "sb_publishable_k0ShwloMENXCGppXHEG5NA_-DAmfDgR"
    encryption_key: str = field(default="", repr=False)
    stripe_key: str = field(default="", repr=False)
    stripe_portal_configuration: str = ""
    stripe_icon_file: str = ""
    topup_price_id: str = ""
    webhook_secret: str = field(default="", repr=False)
    openai_key: str = field(default="", repr=False)
    anthropic_key: str = field(default="", repr=False)
    dots_enabled: bool = False
    github_dot_client_id: str = ""
    github_dot_client_secret: str = field(default="", repr=False)
    github_dot_webhook_secret: str = field(default="", repr=False)
    figma_bud_client_id: str = ""
    figma_bud_client_secret: str = field(default="", repr=False)
    notion_bud_client_id: str = ""
    notion_bud_client_secret: str = field(default="", repr=False)
    supabase_bud_client_id: str = ""
    supabase_bud_client_secret: str = field(default="", repr=False)
    linear_bud_client_id: str = ""
    linear_bud_client_secret: str = field(default="", repr=False)
    meetings_enabled: bool = False
    meeting_context_enabled: bool = False
    speech_enabled: bool = False
    speech_key: str = field(default="", repr=False)
    livekit_url: str = ""
    livekit_api_key: str = field(default="", repr=False)
    livekit_api_secret: str = field(default="", repr=False)
    stripe_test_mode: bool = False
    checkout_enabled: bool = False
    gateway_enabled: bool = False
    development_ai: bool = False
    plans: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)
    download_path: str = ""
    download_sha256: str = ""
    release_ready: bool = False
    legal_ready: bool = False

    @classmethod
    def load(cls):
        kwargs = {}
        for name, item in cls.__dataclass_fields__.items():
            raw = os.environ.get("AEDROVA_" + name.upper())
            if name in {"plans", "models"} and raw is None:
                config_file = os.environ.get("AEDROVA_" + name.upper() + "_FILE")
                if config_file:
                    kwargs[name] = json.loads(Path(config_file).read_text())
                    continue
            if raw is None:
                continue
            if item.type is bool:
                kwargs[name] = raw.lower() == "true"
            elif item.type is int:
                kwargs[name] = int(raw)
            elif name in {"plans", "models"}:
                kwargs[name] = json.loads(raw)
            else:
                kwargs[name] = raw
        config = cls(**kwargs)
        config.validate()
        return config

    def validate(self):
        for name, minimum, maximum in (
            ("db_pool_size", 1, 50),
            ("db_max_overflow", 0, 50),
            ("db_pool_timeout", 1, 30),
            ("gateway_max_concurrency", 1, 64),
            ("provider_deadline_seconds", 30, 600),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"Configure a bounded {name} between {minimum} and {maximum}.")
        if self.encryption_key:
            try:
                Fernet(self.encryption_key.encode())
            except (ValueError, TypeError) as error:
                raise ValueError("Configure a valid persistent server Fernet key.") from error
        parsed = urlparse(self.origin)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.path not in {"", "/"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Set a valid website origin, without a path.")
        if self.production:
            if parsed.scheme != "https" or not self.database.startswith("postgresql"):
                raise ValueError("Production requires HTTPS and PostgreSQL.")
            if not self.encryption_key:
                raise ValueError(
                    "Configure the server encryption key in the deployment secret store."
                )
        if self.supabase_database:
            try:
                database = make_url(self.database)
                database_port = database.port
            except Exception:
                raise ValueError(
                    "Configure a valid private Supabase database connection."
                ) from None
            if (
                database.drivername != "postgresql+psycopg"
                or database.username != "aedrova_website.cpelagtufyocepnqcqqd"
                or not database.password
                or not (database.host or "").endswith(".pooler.supabase.com")
                or database_port != 5432
                or database.database != "postgres"
                or database.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}
                or self.db_pool_size + self.db_max_overflow > 3
            ):
                raise ValueError(
                    "Use the restricted Aedrova website role, Supabase session pooler "
                    "on port 5432, TLS and at most three pooled connections."
                )
        if self.waitlist_only and (
            self.checkout_enabled or self.gateway_enabled or self.meetings_enabled
        ):
            raise ValueError(
                "Waitlist launch must keep checkout, managed AI and meetings disabled."
            )
        if self.dots_enabled and not self.encryption_key:
            raise ValueError("Dots require a persistent server encryption key.")
        if bool(self.github_dot_client_id) != bool(self.github_dot_client_secret):
            raise ValueError("Configure both GitHub Dot OAuth credentials server-side.")
        for provider in ("figma", "notion", "supabase", "linear"):
            if bool(getattr(self, provider + "_bud_client_id")) != bool(
                getattr(self, provider + "_bud_client_secret")
            ):
                raise ValueError(
                    "Configure both " + provider + " Bud OAuth credentials server-side."
                )
        if self.meeting_context_enabled and not self.meetings_enabled:
            raise ValueError("Meeting context requires the enabled meeting service.")
        if self.speech_enabled and (
            not self.meeting_context_enabled or not self.supabase_database or not self.speech_key
        ):
            raise ValueError(
                "Speech needs meeting context, restricted Supabase PostgreSQL "
                "and a server-only speech key."
            )
        if self.meetings_enabled:
            media = urlparse(self.livekit_url)
            if (
                media.scheme != "wss"
                or not media.hostname
                or media.username
                or media.password
                or media.query
                or media.fragment
                or media.path not in {"", "/"}
                or not self.livekit_api_key
                or len(self.livekit_api_secret) < 32
                or not media.hostname.endswith(".livekit.cloud")
                or not self.encryption_key
            ):
                raise ValueError(
                    "Meetings require LiveKit Cloud credentials and a persistent "
                    "server encryption key."
                )
        if self.development_ai and (
            self.production
            or self.checkout_enabled
            or self.release_ready
            or self.waitlist_only
            or not self.database.startswith("sqlite:///")
            or urlparse(self.origin).hostname not in {"127.0.0.1", "localhost", "::1"}
            or urlparse(self.origin).scheme != "http"
        ):
            raise ValueError("Development AI is restricted to private loopback SQLite testing.")
        if self.gateway_enabled:
            if not self.models:
                raise ValueError("Managed AI requires approved models and rates.")
            for provider in self.models:
                if not (self.openai_key if provider == "codex" else self.anthropic_key):
                    raise ValueError("Configure every enabled provider's server-only API key.")
        for name, plan in self.plans.items():
            if name not in {"weekly", "monthly"} or not plan.get("price_id", "").startswith(
                "price_"
            ):
                raise ValueError("Use approved weekly/monthly Stripe price identifiers.")
            for key in ("amount_cents", "allowance_microusd", "concurrency"):
                if type(plan.get(key)) is not int or plan[key] <= 0:
                    raise ValueError(
                        "Plans require positive approved price, allowance and concurrency."
                    )
            if any(plan.get(key) != value for key, value in PLAN_POLICY[name].items()):
                raise ValueError("Plan limits must match the published beta policy.")
            expected = (1000, "week") if name == "weekly" else (4900, "month")
            if (plan["amount_cents"], plan.get("interval")) != expected:
                raise ValueError("Use the owner's approved $10/week and $49/month prices.")
            if plan.get("currency", "usd") != "usd":
                raise ValueError("This beta checkout currently supports USD plans.")
        for provider, model in self.models.items():
            if provider not in {"codex", "claude_code"} or not model.get("id"):
                raise ValueError("Configure an explicitly approved provider model.")
            for key in ("input_rate", "output_rate"):
                if type(model.get(key)) is not int or model[key] <= 0:
                    raise ValueError("Configure micro-USD per million token rates for every model.")
        if self.stripe_portal_configuration and not self.stripe_portal_configuration.startswith(
            "bpc_"
        ):
            raise ValueError("Use a Stripe billing portal configuration identifier.")
        if self.topup_price_id and not self.topup_price_id.startswith("price_"):
            raise ValueError("Use a Stripe price identifier for optional AI credit purchases.")
        if self.release_ready:
            path = Path(self.download_path)
            if not path.is_file() or path.suffix != ".dmg" or len(self.download_sha256) != 64:
                raise ValueError("Release requires a verified DMG and its SHA-256 digest.")
            with path.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            manifest_path = path.with_suffix(".manifest.json")
            if not manifest_path.is_file():
                raise ValueError("Public release requires its signing/notarization manifest.")
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("public_release") is not True or manifest.get("sha256") != checksum:
                raise ValueError("Preview or unverified installers cannot be released.")
            if checksum != self.download_sha256:
                raise ValueError("The Mac installer does not match its release digest.")
            if (
                not re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", str(manifest.get("version", "")))
                or manifest.get("architecture") not in {"arm64", "x86_64", "universal2"}
                or not re.fullmatch(r"\d{1,2}\.\d{1,2}", str(manifest.get("minimum_macos", "")))
            ):
                raise ValueError(
                    "Release manifest requires version, processor and macOS requirements."
                )
        if self.stripe_test_mode and not self.stripe_key.startswith(("sk_test_", "rk_test_")):
            raise ValueError(
                "Stripe sandbox mode requires a test secret key; live keys are rejected."
            )
        if self.stripe_test_mode and self.database == "sqlite:///work/site.sqlite3":
            raise ValueError("Use a separate sandbox billing database.")
        if self.stripe_test_mode and self.gateway_enabled:
            raise ValueError("Sandbox payments cannot enable paid model execution.")
        if self.stripe_test_mode and self.production:
            raise ValueError("Stripe sandbox checkout must use a non-production staging server.")
        billing_ready = (
            self.stripe_key
            and self.webhook_secret
            and set(self.plans) == {"weekly", "monthly"}
            and self.encryption_key
        )
        public_ready = (
            self.legal_ready
            and self.release_ready
            and self.gateway_enabled
            and set(self.models) == {"codex", "claude_code"}
            and self.stripe_key.startswith(("sk_live_", "rk_live_"))
        )
        if self.checkout_enabled and not (
            billing_ready and (self.stripe_test_mode or public_ready)
        ):
            raise ValueError(
                "Checkout requires approved plans, persistent encryption, billing and "
                "either explicit sandbox mode or every legal, release and gateway gate."
            )
