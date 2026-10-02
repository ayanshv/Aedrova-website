"""Public beta gates fail closed when prices, release or backend configuration drift."""

import hashlib
import json

import pytest

from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY


def test_owner_approved_policy_cannot_be_silently_changed():
    Config(plans={"monthly": {**PLAN_POLICY["monthly"], "price_id": "price_test"}}).validate()
    with pytest.raises(ValueError, match="policy"):
        Config(
            plans={
                "monthly": {
                    **PLAN_POLICY["monthly"],
                    "price_id": "price_test",
                    "allowance_microusd": 99,
                }
            }
        ).validate()


def test_preview_dmg_cannot_be_public_download(tmp_path):
    path = tmp_path / "preview.dmg"
    path.write_bytes(b"synthetic fixture, not an installer")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".manifest.json").write_text(
        json.dumps({"public_release": False, "sha256": checksum})
    )
    with pytest.raises(ValueError, match="Preview"):
        Config(release_ready=True, download_path=str(path), download_sha256=checksum).validate()


def test_checkout_requires_every_release_billing_and_gateway_gate():
    with pytest.raises(ValueError, match="Checkout requires"):
        Config(checkout_enabled=True).validate()


def test_production_rejects_local_database_and_unencrypted_sessions():
    with pytest.raises(ValueError, match="PostgreSQL"):
        Config(production=True, origin="https://aedrova.example").validate()
    with pytest.raises(ValueError, match="encryption"):
        Config(
            production=True,
            origin="https://aedrova.example",
            database="postgresql+psycopg://example",
        ).validate()
