# AI allowances

Included AI is limited by a rolling five-hour window and a rolling weekly window, with a
monthly backstop, all measured in provider cost (micro-USD) so they stay accurate if model
prices change. Chat, files and meetings never use them.

| Plan | Weekly | Five-hour | Monthly backstop | Weekly tokens* | Five-hour tokens* |
|---|---|---|---|---|---|
| Free | $0.15 | $0.10 | $0.50 | about 91k | about 61k |
| Pro | $2.00 | $0.80 | $8.70 | about 1.2M | about 487k |
| Teams | $4.00 | $1.60 | $17.40 | about 2.4M | about 974k |

\* Blended at `gpt-5.3-codex` rates ($1.75 / $0.175 cached / $14 per million tokens) with a
coding mix of 92% input (75% cached) and 8% output, about $1.64 per million tokens.

Pricing basis: Pro $15/month or $144/year, Teams $30/month or $288/year, per person, after
Stripe's 2.9% + $0.30. Using the weaker annual price per month, the worst case (every week
used to the cap) leaves about a 25% gross margin; at 35% use it is about 74%.
`tests/test_allowance_windows.py` fails if the worst case drops below 24%.

Allowances in `PLAN_POLICY` derive from `USAGE_POLICY` (the monthly backstop, times 12 for
annual plans). A deployment `plans` setting must carry the same values or the service
refuses to start:

| Plan key | `allowance_microusd` |
|---|---|
| `pro_monthly` | 8700000 |
| `pro_annual` | 104400000 |
| `power_monthly` | 17400000 |
| `power_annual` | 208800000 |

Balance responses add `weekly_budget`, `weekly_spent`, `weekly_reset_at` and
`five_hour_reset_at`. The desktop app reads them and falls back to monthly fields for older
servers. The gateway also accepts the hosted `web_search` tool, capped at five searches per
request and billed at $0.01 each on top of tokens.

## How a request is checked against the windows (November 22, 2026)

A rolling window (five hours or a week) pauses AI work when it is **full**, which is what the
usage meter shows. A request's worst-case hold (its input bound, its full output and up to
five hosted searches at about $0.01 each) can be bigger than a small window on its own, for
example the free plan's five-hour window of $0.10. So a request that arrives alone is judged on
what has already been used. While other requests are still in flight, their holds and this
one's are counted together, so parallel work cannot overspend a window. The monthly allowance
still counts the whole hold, which keeps the worst case inside the margin in this document.
