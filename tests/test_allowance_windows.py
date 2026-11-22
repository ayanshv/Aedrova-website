"""Weekly and five-hour AI allowances, and the margin they must preserve."""

import time

import pytest

from aedrova_site import budgets
from aedrova_site.policy import LEGACY_PLAN_POLICY, PLAN_POLICY, PLAN_TIERS, USAGE_POLICY
from aedrova_site.store import Denied, Store

# Retail price per person, per month on annual billing (the weaker case), from the real plan
# table, and the configured model's provider rates in dollars per million tokens
# (config/models.openai.json).
PRICE = {
    tier: PLAN_POLICY[f"{name}_annual"]["amount_cents"] / 100 / 12
    for tier, name in (("monthly", "pro"), ("annual", "power"))
}
STRIPE = {
    tier: (0.029 * PLAN_POLICY[f"{name}_annual"]["amount_cents"] / 100 + 0.30) / 12
    for tier, name in (("monthly", "pro"), ("annual", "power"))
}
RATES = {"input": 1.75, "cached": 0.175, "output": 14.0}
WEEKS_PER_MONTH = 52 / 12


def blended_dollars_per_million():
    """92% input (75% cached) and 8% output: a typical coding-agent mix."""
    input_cost = 0.25 * RATES["input"] + 0.75 * RATES["cached"]
    return 0.92 * input_cost + 0.08 * RATES["output"]


@pytest.mark.parametrize("plan", ["monthly", "annual"])
def test_paid_plans_stay_profitable_even_when_every_week_is_used_to_the_cap(plan):
    policy = USAGE_POLICY[plan]
    worst_case = policy["weekly_budget"] / 1_000_000 * WEEKS_PER_MONTH
    worst_case = min(worst_case, policy["budget"] / 1_000_000)  # the monthly backstop
    net = PRICE[plan] - STRIPE[plan]
    margin = (net - worst_case) / net
    assert margin >= 0.24, f"{plan}: worst-case gross margin is only {margin:.0%}"


def test_windows_are_ordered_so_a_burst_cannot_exceed_the_week_or_the_month():
    for plan, policy in USAGE_POLICY.items():
        assert 0 < policy["five_hour_budget"] < policy["weekly_budget"] <= policy["budget"], plan
    for key in ("five_hour_budget", "weekly_budget", "budget"):
        tiers = [USAGE_POLICY[name][key] for name in ("free", "monthly", "annual")]
        assert tiers == sorted(tiers) and len(set(tiers)) == 3


def test_tokens_per_window_match_the_published_figures():
    price = blended_dollars_per_million()
    def tokens(plan, key):
        return USAGE_POLICY[plan][key] / price
    assert 1_150_000 < tokens("monthly", "weekly_budget") < 1_250_000
    assert 470_000 < tokens("monthly", "five_hour_budget") < 500_000
    assert 2_300_000 < tokens("annual", "weekly_budget") < 2_500_000
    assert 940_000 < tokens("annual", "five_hour_budget") < 1_000_000


def test_published_prices_are_the_ones_the_margin_is_built_on():
    assert PRICE == {"monthly": 12.0, "annual": 24.0}
    assert PLAN_POLICY["pro_monthly"]["amount_cents"] == 1500
    assert PLAN_POLICY["power_monthly"]["amount_cents"] == 3000


def test_plan_allowances_agree_with_the_usage_policy():
    for key, tier in PLAN_TIERS.items():
        years = 12 if PLAN_POLICY[key]["interval"] == "year" else 1
        assert PLAN_POLICY[key]["allowance_microusd"] == USAGE_POLICY[tier]["budget"] * years


@pytest.fixture
def ledger(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'windows.sqlite'}", free_enabled=True)
    yield store
    store.engine.dispose()


def pro(ledger):
    ledger.customer("one", "cus_one")
    now = int(time.time())
    ledger.subscription(
        "evt", "cus_one", "sub", "monthly", "active", now, now + 30 * 86400,
        LEGACY_PLAN_POLICY["monthly"],
    )
    return ledger.run(ledger.create_run("owner", "one", "codex", "key")["token"])


def test_five_hour_window_pauses_work_before_the_week_is_used(ledger):
    run = pro(ledger)
    five = USAGE_POLICY["monthly"]["five_hour_budget"]
    identifier, _ = ledger.reserve(run, "burst", five - 1)
    ledger.settle(identifier, five - 1, b"done")
    with pytest.raises(Denied, match="five-hour"):
        ledger.reserve(run, "more", 2)
    balance = ledger.balance("one")
    assert balance["five_hour_spent"] == five - 1
    assert balance["weekly_spent"] == five - 1
    assert balance["five_hour_reset_at"] > time.time()


def test_weekly_window_pauses_work_after_five_hour_capacity_returns(ledger, monkeypatch):
    run = pro(ledger)
    weekly = USAGE_POLICY["monthly"]["weekly_budget"]
    five = USAGE_POLICY["monthly"]["five_hour_budget"]
    sessions = weekly // five
    base = int(time.time())
    clock = {"now": base}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    ledger.end_run(run["id"], "owner")

    def fresh(key):
        return ledger.run(ledger.create_run("owner", "one", "codex", key)["token"])

    for index in range(sessions):
        run = fresh(f"session-{index}")
        identifier, _ = ledger.reserve(run, f"session-{index}", five)
        ledger.settle(identifier, five, b"done")
        ledger.end_run(run["id"], "owner")
        clock["now"] += 6 * 3600  # the five-hour window has cleared
    with pytest.raises(Denied, match="Weekly AI allowance"):
        ledger.reserve(fresh("last"), "one-too-many", weekly - sessions * five + 1)
    balance = ledger.balance("one")
    assert balance["weekly_budget"] == weekly
    assert balance["weekly_reset_at"] > clock["now"] - 6 * 3600


def test_usage_ages_out_after_a_week(ledger, monkeypatch):
    run = pro(ledger)
    five = USAGE_POLICY["monthly"]["five_hour_budget"]
    start = int(time.time())
    clock = {"now": start}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    identifier, _ = ledger.reserve(run, "old", five)
    ledger.settle(identifier, five, b"done")
    clock["now"] = start + 8 * 86400
    assert ledger.balance("one")["weekly_spent"] == 0
    assert budgets.window_reset(ledger.engine.connect(), "one", budgets.WEEK) == 0
