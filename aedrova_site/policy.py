"""Owner-requested prices. All amounts are estimated provider cost, in micro-USD."""

PLAN_POLICY = {
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

# Team adds capacity to the same implemented collaboration features. No unlimited AI.
USAGE_POLICY = {
    "free": {
        "budget": 500_000,
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
        "requests": 400,
        "input_tokens": 128_000,
        "output_tokens": 8192,
        "run_seconds": 1200,
        "run_calls": 60,
        "tools": 64,
        "tool_calls": 300,
    },
}

PLAN_NAMES = {"free": "Free", "monthly": "Pro", "annual": "Team"}
