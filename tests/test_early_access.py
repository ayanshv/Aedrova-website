"""Fixed global expiry, bounded free access and payment bypass regressions."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_access_gateway import MODELS

from aedrova_site import promotion
from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.services import Payments
from aedrova_site.store import Denied, Store


@pytest.fixture
def clock(monkeypatch):
    now = [promotion.STARTS_AT + 60]
    monkeypatch.setattr("time.time", lambda: now[0])
    return now


@pytest.fixture
def ledger(tmp_path, clock):
    store = Store(
        f"sqlite:///{tmp_path / 'offer.sqlite'}", free_enabled=True, early_access_enabled=True
    )
    yield store
    store.engine.dispose()


def test_fixed_window_exact_boundaries():
    assert 60 * 86400 <= promotion.ENDS_AT - promotion.STARTS_AT < 61 * 86400
    assert promotion.ENDS_ISO == "2026-12-21T07:59:59+00:00"
    assert not promotion.status(promotion.STARTS_AT - 1)["active"]
    assert promotion.status(promotion.STARTS_AT)["active"]
    assert promotion.status(promotion.ENDS_AT - 1)["active"]
    assert not promotion.status(promotion.ENDS_AT)["active"]
    assert promotion.status(promotion.ENDS_AT + 999)["remaining_seconds"] == 0


@pytest.mark.parametrize("plan", ["monthly", "annual"])
def test_late_join_and_replay_never_extend_window_or_replenish(ledger, clock, plan):
    clock[0] = promotion.ENDS_AT - 100
    assert ledger.grant_early_access("owner", "one", plan)
    access = ledger.create_run("owner", "one", "codex", "one")
    run = ledger.run(access["token"])
    identifier, _ = ledger.reserve(run, "usage", 100_000)
    ledger.settle(identifier, 100_000, b"done")
    prior = ledger.balance("one")
    assert prior["early_access"] and not prior["has_billing"]
    assert prior["period_end"] == promotion.ENDS_AT
    assert prior["monthly_spent"] == 100_000
    assert ledger.grant_early_access("owner", "one", plan)
    assert ledger.balance("one")["monthly_spent"] == 100_000
    clock[0] = promotion.ENDS_AT
    assert not ledger.grant_early_access("owner", "one", plan)
    expired = ledger.balance("one")
    assert expired["plan"] == "free"
    assert expired["concurrency"] == 1
    assert not expired["early_access"]
    assert ledger.activate_free("owner", "one")["plan"] == "free"
    with ledger.tx() as db:
        row = ledger.billing_lock(db, "one")
        assert row["subscription"] == ""  # no automatic subscription after expiry


def test_shared_owner_and_company_free_pool_limits(ledger):
    for workspace in ("one", "two"):
        ledger.grant_early_access("owner", workspace)
    runs = [ledger.run(ledger.create_run("owner", w, "codex", w)["token"]) for w in ("one", "two")]
    with ledger.tx() as db:
        row = ledger.billing_lock(db, "one")
        from aedrova_site import budgets

        scopes = [scope for scope, _, _ in budgets.scopes(ledger, row)]
    assert "free-pool" in scopes and "owner:owner" in scopes
    identifier, _ = ledger.reserve(runs[0], "first", 3_000_000)
    ledger.settle(identifier, 3_000_000, b"done")
    assert ledger.balance("two")["available"] == 1_000_000
    with pytest.raises(Denied, match="Monthly AI budget"):
        ledger.reserve(runs[1], "second", 1_000_001)
    ledger.free_pool = 3_000_000
    with pytest.raises(Denied, match="Monthly AI budget"):
        ledger.reserve(runs[1], "pool", 1)


def test_expiry_or_disabled_flag_checked_inside_every_reservation(ledger, clock):
    clock[0] = promotion.ENDS_AT - 10
    ledger.grant_early_access("owner", "one")
    run = ledger.run(ledger.create_run("owner", "one", "codex", "one")["token"])
    clock[0] = promotion.ENDS_AT
    # A long-lived request cannot continue using Team capacity after the cutoff.
    with pytest.raises(Denied):
        ledger.reserve(run, "after-deadline", 500_001)
    assert ledger.balance("one")["plan"] == "free"
    assert not ledger.grant_early_access("owner", "two")


def test_disabled_kill_switch_downgrades_gift(ledger):
    ledger.grant_early_access("owner", "one")
    ledger.early_access_enabled = False
    assert ledger.balance("one")["plan"] == "free"
    assert not ledger.grant_early_access("owner", "two")


def test_parallel_grants_and_other_owner_do_not_reset(ledger):
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert all(executor.map(lambda _: ledger.grant_early_access("owner", "one"), range(2)))
    assert not ledger.grant_early_access("intruder", "one")
    assert ledger.balance("one")["period_end"] == promotion.ENDS_AT


def test_existing_paid_plan_is_never_overwritten(ledger, clock):
    ledger.customer("one", "cus_paid")
    ledger.subscription(
        "evt",
        "cus_paid",
        "sub_paid",
        "monthly",
        "active",
        clock[0],
        clock[0] + 86400,
        PLAN_POLICY["monthly"],
    )
    assert not ledger.grant_early_access("owner", "one")
    assert ledger.balance("one")["plan"] == "monthly"
    assert ledger.balance("one")["has_billing"]


def test_disabled_by_default_and_cannot_bypass_waitlist():
    assert not Config().early_access_enabled
    with pytest.raises(ValueError, match="Early access requires"):
        Config(early_access_enabled=True).validate()
    with pytest.raises(ValueError):
        Config(early_access_enabled=True, free_enabled=True, waitlist_only=True).validate()


def test_promotion_uses_server_window_not_query_or_browser_time(tmp_path, clock):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'public.sqlite'}", waitlist_only=True))
    with TestClient(app) as client:
        page = client.get("/plans?days=999&now=0").text
        assert "data-offer-price>$0.00" in page
        assert promotion.ENDS_LABEL in page
        assert "website is still accepting waitlist" in page
        clock[0] = promotion.ENDS_AT
        expired = client.get("/plans?days=999&now=0").text
        assert "data-offer-price>$0.00" not in expired
        assert 'class="plans early-access-active"' not in expired
    app.state.store.engine.dispose()


def test_csrf_workspace_checks_and_no_paid_checkout(tmp_path, clock, monkeypatch):
    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'api.sqlite'}",
            free_enabled=True,
            early_access_enabled=True,
            gateway_enabled=True,
            models=MODELS,
            openai_key="fixture",
            anthropic_key="fixture",
        )
    )
    store = app.state.store
    store.session("browser", {"access_token": "access", "csrf": "csrf"})

    def require(token, workspace, *, billing=False):
        if token != "access" or workspace != "one":
            raise Denied("Workspace access denied.")
        return {"id": "owner"}

    app.state.identity.require = require
    app.state.identity.user = lambda token: {"id": "owner"}
    app.state.identity.billing_context = lambda token, w: {"billing_workspace": w}
    with TestClient(app) as client:
        client.cookies.set("aedrova_session", "browser")
        assert client.post("/api/free/one").status_code == 403
        assert client.post("/api/free/other", headers={"X-CSRF-Token": "csrf"}).status_code == 403
        result = client.post("/api/free/one", headers={"X-CSRF-Token": "csrf"})
        assert result.status_code == 200 and result.json()["early_access"]
        # GET never activates a new plan and expiry is not client-controlled.
        assert client.get("/api/balance/one").json()["early_access_ends_at"] == promotion.ENDS_AT

        def no_stripe(*args, **kwargs):
            raise AssertionError("Stripe must not be called")

        monkeypatch.setattr("stripe.Price.retrieve", no_stripe)
        with pytest.raises(Denied, match="early access is free"):
            Payments(
                app.state.config
                if hasattr(app.state, "config")
                else Config(early_access_enabled=True),
                store,
            ).checkout("one", "monthly", "test")
    store.engine.dispose()


def test_public_offer_blocks_live_checkout_even_without_grants_enabled(ledger):
    with pytest.raises(Denied, match="early access is free"):
        Payments(Config(checkout_enabled=True), ledger).checkout("one", "monthly", "test")


def test_free_activation_after_expiry_does_not_require_prior_balance_read(ledger, clock):
    ledger.grant_early_access("owner", "one")
    clock[0] = promotion.ENDS_AT
    assert ledger.activate_free("owner", "one")["plan"] == "free"


def test_public_clock_sync_is_bounded_and_does_not_activate_access(tmp_path, clock):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'clock.sqlite'}", waitlist_only=True))
    with TestClient(app) as client:
        response = client.get("/api/early-access?remaining_seconds=999999999")
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["ends_at"] == promotion.ENDS_AT
        assert response.json()["remaining_seconds"] == promotion.ENDS_AT - clock[0]
        with app.state.store.tx() as db:
            assert db.scalar(text("SELECT COUNT(*) FROM billing")) == 0
        for _ in range(119):
            assert client.get("/api/early-access").status_code == 200
        limited = client.get("/api/early-access")
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) > 0
    app.state.store.engine.dispose()
