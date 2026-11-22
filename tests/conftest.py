"""Mechanics tests run against fixed, round limits; allowance tests use the real policy."""

import pytest

from aedrova_site.policy import PLAN_POLICY, PLAN_TIERS, USAGE_POLICY

FIXED_LIMITS = {
    "free": {"budget": 500_000, "weekly_budget": 500_000, "five_hour_budget": 500_000},
    "monthly": {"budget": 2_000_000, "weekly_budget": 2_000_000, "five_hour_budget": 2_000_000},
    "annual": {"budget": 4_000_000, "weekly_budget": 4_000_000, "five_hour_budget": 4_000_000},
}


@pytest.fixture(autouse=True)
def fixed_limits(request, monkeypatch):
    if request.module.__name__.endswith("test_allowance_windows"):
        return
    for plan, limits in FIXED_LIMITS.items():
        for key, value in limits.items():
            monkeypatch.setitem(USAGE_POLICY[plan], key, value)
    for key, tier in PLAN_TIERS.items():
        years = 12 if PLAN_POLICY[key]["interval"] == "year" else 1
        monkeypatch.setitem(
            PLAN_POLICY[key], "allowance_microusd", FIXED_LIMITS[tier]["budget"] * years
        )
