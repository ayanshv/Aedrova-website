"""Explicit launch gates. Public configuration never includes private credentials."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from aedrova_site.policy import PLAN_POLICY


@dataclass
class Config:
    origin: str = "http://127.0.0.1:8090"
    database: str = "sqlite:///work/site.sqlite3"
    production: bool = False
    supabase_url: str = "https://cpelagtufyocepnqcqqd.supabase.co"
    supabase_key: str = "sb_publishable_k0ShwloMENXCGppXHEG5NA_-DAmfDgR"
    encryption_key: str = field(default="", repr=False)
    stripe_key: str = field(default="", repr=False)
    topup_price_id: str = ""
    webhook_secret: str = field(default="", repr=False)
    openai_key: str = field(default="", repr=False)
    anthropic_key: str = field(default="", repr=False)
    checkout_enabled: bool = False
    gateway_enabled: bool = False
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
            elif name in {"plans", "models"}:
                kwargs[name] = json.loads(raw)
            else:
                kwargs[name] = raw
        config = cls(**kwargs)
        config.validate()
        return config

    def validate(self):
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
        if self.checkout_enabled and not (
            self.stripe_key
            and self.webhook_secret
            and set(self.plans) == {"weekly", "monthly"}
            and self.legal_ready
            and self.release_ready
            and self.gateway_enabled
            and set(self.models) == {"codex", "claude_code"}
        ):
            raise ValueError(
                "Checkout requires approved plans, billing, legal, release and gateway gates."
            )
