"""Approved retail catalogs and bounded internal provider-cost usage policies."""

LEGACY_PLAN_POLICY = {
    "monthly": {
        "amount_cents": 1000,
        "currency": "usd",
        "interval": "month",
        "allowance_microusd": 2_000_000,
        "concurrency": 1,
    },
    "annual": {
        "amount_cents": 20000,
        "currency": "usd",
        "interval": "year",
        "allowance_microusd": 48_000_000,
        "concurrency": 2,
    },
}


USAGE_POLICY = {
    "free": {
        "budget": 500_000,
        "five_hour_budget": 500_000,
        "requests": 40,
        "input_tokens": 32_000,
        "output_tokens": 2048,
        "run_seconds": 300,
        "run_calls": 12,
        "tools": 16,
        "tool_calls": 32,
    },
    "monthly": {
        "budget": 2_000_000,
        "five_hour_budget": 2_000_000,
        "requests": 200,
        "input_tokens": 96_000,
        "output_tokens": 8192,
        "run_seconds": 900,
        "run_calls": 40,
        "tools": 48,
        "tool_calls": 200,
    },
    "annual": {
        "budget": 4_000_000,
        "five_hour_budget": 4_000_000,
        "requests": 400,
        "input_tokens": 128_000,
        "output_tokens": 8192,
        "run_seconds": 1200,
        "run_calls": 60,
        "tools": 64,
        "tool_calls": 300,
    },
}

PLAN_NAMES = {
    "free": "Free",
    "monthly": "Pro",
    "annual": "Power",
    "pro_monthly": "Pro",
    "pro_annual": "Pro",
    "power_monthly": "Power",
    "power_annual": "Power",
}
BUD_LIMITS = {"free": 1, "pro": 5, "team": 15}

PLAN_TIERS = {
    "pro_monthly": "monthly",
    "pro_annual": "monthly",
    "power_monthly": "annual",
    "power_annual": "annual",
}
PLAN_POLICY = {
    key: {
        **LEGACY_PLAN_POLICY[PLAN_TIERS[key]],
        "amount_cents": amount,
        "interval": interval,
        "allowance_microusd": USAGE_POLICY[PLAN_TIERS[key]]["budget"]
        * (12 if interval == "year" else 1),
    }
    for key, amount, interval in (
        ("pro_monthly", 1500, "month"),
        ("pro_annual", 14400, "year"),
        ("power_monthly", 3000, "month"),
        ("power_annual", 28800, "year"),
    )
}
SUBSCRIPTION_POLICY = {**LEGACY_PLAN_POLICY, **PLAN_POLICY}

PUBLIC_PLAN_PRICES = {
    tier: {
        cycle: PLAN_POLICY[f"{tier}_{cycle}"]["amount_cents"] // 100
        for cycle in ("monthly", "annual")
    }
    for tier in ("pro", "power")
}
