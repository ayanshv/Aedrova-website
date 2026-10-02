"""Beta prices and hard limits chosen under the owner's September 30 authorization."""

PLAN_POLICY = {
    "weekly": {
        "amount_cents": 1000,
        "currency": "usd",
        "interval": "week",
        "allowance_microusd": 1_000_000,
        "concurrency": 1,
    },
    "monthly": {
        "amount_cents": 4900,
        "currency": "usd",
        "interval": "month",
        "allowance_microusd": 10_000_000,
        "concurrency": 1,
    },
}
