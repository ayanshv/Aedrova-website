"""Live preparation stays isolated and never creates payments."""

import json
from types import SimpleNamespace

import pytest

from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from scripts.listen_stripe import EVENTS
from scripts.setup_stripe import provision, validate_price
from scripts.setup_stripe_live import preflight, prepare, require_live


def price(name, live=True):
    policy = PLAN_POLICY[name]
    return {
        "id": "price_" + name,
        "livemode": live,
        "active": True,
        "currency": "usd",
        "unit_amount": policy["amount_cents"],
        "recurring": {"interval": policy["interval"], "interval_count": 1},
    }


@pytest.mark.parametrize("key", ["", "pk_live_example", "sk_test_example", "rk_test_example"])
def test_reject_other_keys(key):
    with pytest.raises(ValueError):
        require_live(key)


def test_mode_and_price_mismatch():
    with pytest.raises(ValueError):
        validate_price(price("annual", False), PLAN_POLICY["annual"], live=True)
    changed = price("monthly")
    changed["unit_amount"] = 11000
    with pytest.raises(ValueError):
        validate_price(changed, PLAN_POLICY["monthly"], live=True)


def test_provision_live_namespaced_and_private(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "stripe.Product.create", lambda **kw: calls.append(kw) or {"id": "prod_live"}
    )
    monkeypatch.setattr(
        "stripe.Price.list",
        lambda **kw: (
            calls.append(kw)
            or {"data": [price("annual" if "annual" in kw["lookup_keys"][0] else "monthly")]}
        ),
    )
    target = tmp_path / "plans.json"
    provision(Config(stripe_key="sk_live_fixture"), target, live=True)
    assert any(call.get("metadata", {}).get("contact_only") == "true" for call in calls)
    assert json.loads(target.read_text())["monthly"]["amount_cents"] == 1000
    assert target.stat().st_mode & 0o777 == 0o600
    assert calls[0]["metadata"]["environment"] == "live"
    assert all("aedrova_live_" in call["lookup_keys"][0] for call in calls if "lookup_keys" in call)


def test_inactive_account_no_assets(tmp_path, monkeypatch):
    monkeypatch.setattr("stripe.Account.retrieve", lambda **kw: {"charges_enabled": False})
    monkeypatch.setattr("stripe.Product.create", lambda **kw: pytest.fail("must not mutate"))
    with pytest.raises(ValueError):
        prepare("sk_live_fixture", tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "bad", ["none", "test_price", "inactive_portal", "missing_event", "wrong_url"]
)
def test_read_only_live_preflight(monkeypatch, bad):
    config = Config(
        stripe_key="sk_live_fixture",
        origin="https://aedrova.com",
        webhook_secret="whsec_fixture",
        stripe_portal_configuration="bpc_live",
        plans={
            name: {**policy, "price_id": "price_" + name} for name, policy in PLAN_POLICY.items()
        },
    )
    monkeypatch.setattr(
        "stripe.Account.retrieve", lambda **kw: {"charges_enabled": True, "payouts_enabled": True}
    )
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda identifier, **kw: price(identifier.removeprefix("price_"), bad != "test_price"),
    )
    monkeypatch.setattr(
        "stripe.billing_portal.Configuration.retrieve",
        lambda *a, **kw: {"livemode": True, "active": bad != "inactive_portal"},
    )
    endpoint = {
        "url": "https://aedrova.com/stripe/webhook",
        "status": "enabled",
        "livemode": True,
        "enabled_events": EVENTS.split(","),
    }
    if bad == "missing_event":
        endpoint["enabled_events"].pop()
    if bad == "wrong_url":
        endpoint["url"] = "https://example.com/stripe/webhook"
    monkeypatch.setattr(
        "stripe.WebhookEndpoint.list",
        lambda **kw: SimpleNamespace(auto_paging_iter=lambda: iter([endpoint])),
    )
    if bad == "none":
        preflight(config)
    else:
        with pytest.raises(ValueError):
            preflight(config)
