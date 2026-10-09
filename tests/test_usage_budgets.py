"""Money-boundary tests: no model is contacted and no live database is used."""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from aedrova_site import budgets
from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied, Store


@pytest.fixture
def ledger(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'budget.sqlite'}", free_enabled=True)
    yield store
    store.engine.dispose()


def access(store, workspace, key="first", user="owner"):
    return store.run(store.create_run(user, workspace, "codex", key)["token"])


def test_free_owner_budget_is_shared_across_workspaces_and_members(ledger):
    ledger.activate_free("owner", "one")
    ledger.activate_free("owner", "two")
    run = access(ledger, "one", user="invited-member")
    identifier, _ = ledger.reserve(run, "first", 400_000)
    ledger.settle(identifier, 400_000, b"done")
    other = access(ledger, "two")
    with pytest.raises(Denied, match="Monthly AI budget"):
        ledger.reserve(other, "next", 100_001)
    assert ledger.balance("two")["available"] == 100_000
    with pytest.raises(Denied, match="funding owner"):
        ledger.activate_free("another-owner", "one")


def test_parallel_free_requests_cannot_overspend_across_workspaces(ledger):
    runs = []
    for i in range(2):
        ledger.activate_free("owner", str(i))
        runs.append(access(ledger, str(i), str(i)))

    def reserve(i):
        try:
            return ledger.reserve(runs[i], str(i), 300_000)
        except Denied:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sum(x is not None for x in executor.map(reserve, range(2))) == 1


def test_annual_does_not_allow_a_year_of_cost_in_one_month(ledger):
    ledger.customer("one", "cus_one")
    now = int(time.time())
    ledger.subscription(
        "evt", "cus_one", "sub", "annual", "active", now, now + 365 * 86400, PLAN_POLICY["annual"]
    )
    run = access(ledger, "one")
    with pytest.raises(Denied, match="included AI"):
        ledger.reserve(run, "too-big", 4_000_001)
    assert ledger.balance("one")["available"] == 4_000_000
    first, _ = ledger.reserve(run, "ok", 3_900_000)
    ledger.settle(first, 3_900_000, b"done")
    with pytest.raises(Denied):
        ledger.reserve(run, "second", 100_001)


def test_failed_request_releases_cost_but_counts_attempt_and_replay_once(ledger):
    ledger.activate_free("owner", "one")
    run = access(ledger, "one")
    identifier, _ = ledger.reserve(run, "fail", 200_000)
    ledger.settle(identifier, 0, b"failed")
    ledger.settle(identifier, 200_000)
    assert ledger.balance("one")["available"] == 500_000
    assert ledger.balance("one")["monthly_requests"] == 1
    assert ledger.reserve(run, "fail", 200_000)[1] == b"failed"
    assert ledger.balance("one")["monthly_requests"] == 1


def test_uncertain_reservation_consumes_budget_and_stops_retry(ledger):
    ledger.activate_free("owner", "one")
    run = access(ledger, "one")
    identifier, _ = ledger.reserve(run, "uncertain", 500_000)
    ledger.settle(identifier, None)
    assert ledger.balance("one")["available"] == 0
    with pytest.raises(Denied, match="uncertain"):
        ledger.reserve(run, "uncertain", 1)


def test_free_expiry_resets_month_but_same_month_reactivation_does_not(ledger):
    ledger.activate_free("owner", "one")
    run = access(ledger, "one")
    identifier, _ = ledger.reserve(run, "first", 100_000)
    ledger.settle(identifier, 100_000, b"ok")
    ledger.activate_free("owner", "one")
    assert ledger.balance("one")["available"] == 400_000
    start, end = budgets.month()
    with ledger.tx() as db:
        db.execute(text("UPDATE billing SET period_end=0"))
        db.execute(text("UPDATE budget_reservations SET period=:p"), {"p": start - 86400})
    assert ledger.balance("one")["available"] == 500_000
    assert ledger.balance("one")["reset_at"] == end


def test_requests_workflow_and_global_pool_limits(ledger):
    ledger.activate_free("owner", "one")
    ledger.usage_policy["free"]["run_calls"] = 2
    run = access(ledger, "one")
    for i in range(2):
        identifier, _ = ledger.reserve(run, str(i), 1)
        ledger.settle(identifier, 1, b"ok")
    with pytest.raises(Denied, match="model-call limit"):
        ledger.reserve(run, "third", 1)
    ledger.end_run(run["id"], "owner")
    ledger.usage_policy["free"]["requests"] = 2
    run = access(ledger, "one", "new")
    with pytest.raises(Denied, match="request limit"):
        ledger.reserve(run, "fourth", 1)
    ledger.activate_free("other-owner", "two")
    ledger.company_budget = 2
    with pytest.raises(Denied, match="Monthly AI budget"):
        ledger.reserve(access(ledger, "two", user="other-owner"), "fifth", 1)


def test_plan_prices_configuration_and_waitlist_launch_gate():
    assert PLAN_POLICY["monthly"]["amount_cents"] == 1000
    assert PLAN_POLICY["annual"]["amount_cents"] == 20000
    assert PLAN_POLICY["annual"]["interval"] == "year"
    with pytest.raises(ValueError, match="Waitlist"):
        Config(waitlist_only=True, free_enabled=True).validate()
    with pytest.raises(ValueError, match="Team limits"):
        Config(usage_limits={"annual": {"budget": 1_000_000}}).validate()


def test_cancellation_falls_back_to_free_only_after_server_enable(ledger):
    ledger.customer("one", "cus_one")
    with ledger.tx() as db:
        db.execute(text("UPDATE billing SET budget_owner='owner'"))
    ledger.subscription(
        "canceled",
        "cus_one",
        "sub",
        "monthly",
        "inactive",
        100,
        int(time.time()) + 1000,
        PLAN_POLICY["monthly"],
    )
    assert ledger.balance("one")["plan"] == "free"
    assert ledger.balance("one")["available"] == 500_000
    # A canonical reactivation restores Pro, preserving the underlying Stripe customer.
    now = int(time.time())
    ledger.subscription(
        "reactivated",
        "cus_one",
        "sub",
        "monthly",
        "active",
        now,
        now + 30 * 86400,
        PLAN_POLICY["monthly"],
    )
    assert ledger.balance("one")["plan"] == "monthly"


def test_threshold_alerts_and_private_report_preserve_usage(ledger):
    from scripts.report_ai_usage import report

    ledger.company_budget = 500_000
    ledger.activate_free("owner", "one")
    identifier, _ = ledger.reserve(
        access(ledger, "one"),
        "threshold",
        450_000,
        {"id": "approved-model", "input_rate": 1_000_000},
    )
    # Reservations are included so an operator can intervene before they settle.
    assert ledger.budget_health()["alerts"] == []  # reserve emitted each alert once
    ledger.settle(identifier, 400_000, b"ok", {"input_tokens": 123, "output_tokens": 45})
    result = report(ledger)
    assert result["usage"][0]["estimated_microusd"] == 400_000
    assert result["usage"][0]["model"] == "approved-model"
    assert result["usage"][0]["input_tokens"] == 123
    assert result["budget"]["estimated_microusd"] == 400_000


def test_upgrading_does_not_reset_current_month_spending(ledger):
    ledger.activate_free("owner", "one")
    run = access(ledger, "one")
    identifier, _ = ledger.reserve(run, "free-call", 400_000)
    ledger.settle(identifier, 400_000, b"ok")
    with ledger.tx() as db:
        db.execute(text("UPDATE billing SET customer='cus_one' WHERE workspace='one'"))
    now = int(time.time())
    ledger.subscription(
        "upgrade",
        "cus_one",
        "sub",
        "monthly",
        "active",
        now,
        now + 86400 * 30,
        PLAN_POLICY["monthly"],
    )
    assert ledger.balance("one")["available"] == 1_600_000


def test_budget_configuration_can_be_changed_without_code():
    budget = 1_000_000
    configured = {name: {"budget": budget} for name in ("monthly", "annual")}
    plans = {
        name: {
            **policy,
            "allowance_microusd": budget * (12 if name == "annual" else 1),
            "price_id": "price_" + name,
        }
        for name, policy in PLAN_POLICY.items()
    }
    Config(usage_limits=configured, plans=plans).validate()


def test_free_cannot_spend_purchased_pro_credits(ledger):
    ledger.activate_free("owner", "one")
    ledger.grant_credit("credit", "one", "payment", 5_000_000)
    assert ledger.balance("one")["available"] == 500_000
    with pytest.raises(Denied, match="Free AI allowance"):
        ledger.reserve(access(ledger, "one"), "over", 500_001)
