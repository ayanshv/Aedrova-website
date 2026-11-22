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


# Provider-cost allowances in micro-USD, sized from the price charged for each plan.
#
# Three ceilings apply together. `five_hour_budget` and `weekly_budget` are rolling windows
# that pause AI work when reached; `budget` is a monthly backstop that keeps the worst case
# profitable. Chat, files and meetings never consume these. The tiers are named "monthly"
# (Pro) and "annual" (Teams) for historical reasons; both bill monthly or yearly.
#
# Basis (provider cost per 1M tokens for gpt-5.3-codex at a typical coding mix of 92% input,
# 75% of it cached, and 8% output: about $1.64 blended):
#   Pro   $12/mo on the annual plan, $11.63 after Stripe. Weekly $2.00 -> 1.2M tokens,
#         5 hours $0.80 -> 487k tokens. Worst case (every week at the cap) costs $8.67/mo:
#         25% margin on the annual plan, 39% on monthly. At 35% use, about 74%.
#   Teams $24/mo on the annual plan, $23.28 after Stripe. Weekly $4.00 -> 2.4M tokens,
#         5 hours $1.60 -> 974k tokens. Worst case $17.33/mo: 25% margin. At 35% use, ~74%.
#   Free  weekly $0.15 -> 91k tokens; 5 hours $0.10 -> 61k tokens, inside the shared free pool.
# Recompute these if a model rate or a plan price changes.
USAGE_POLICY = {
    "free": {
        "budget": 500_000,
        "weekly_budget": 150_000,
        "five_hour_budget": 100_000,
        "requests": 40,
        "input_tokens": 32_000,
        "output_tokens": 2048,
        "run_seconds": 300,
        "run_calls": 12,
        "tools": 16,
        "tool_calls": 32,
    },
    "monthly": {
        "budget": 8_700_000,
        "weekly_budget": 2_000_000,
        "five_hour_budget": 800_000,
        "requests": 200,
        "input_tokens": 96_000,
        "output_tokens": 8192,
        "run_seconds": 900,
        "run_calls": 40,
        "tools": 48,
        "tool_calls": 200,
    },
    "annual": {
        "budget": 17_400_000,
        "weekly_budget": 4_000_000,
        "five_hour_budget": 1_600_000,
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
    "annual": "Teams",
    "pro_monthly": "Pro",
    "pro_annual": "Pro",
    "power_monthly": "Teams",
    "power_annual": "Teams",
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
