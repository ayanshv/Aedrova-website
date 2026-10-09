# Pricing and usage launch preparation

Local implementation; checkout and Free activation remain disabled in waitlist mode.
Public labels: Free, Pro ($10/month), Team ($200/year), Enterprise (Let’s Talk).
Team adds two simultaneous workflows, larger context and longer execution limits.
Public UI displays capacity and reset dates, never the internal provider-cost allocation.

Internal initial monthly estimated API ceilings: Free $0.50, Pro $2, Team $4.
Request ceilings: 40 / 200 / 400. Company ceiling $100; combined Free pool $25.
These are conservative launch assumptions, not invoiced-cost guarantees. Configure
AEDROVA_USAGE_LIMITS, AEDROVA_COMPANY_BUDGET_MICROUSD and
AEDROVA_FREE_POOL_MICROUSD on the server; review model rates before launch.
Free funding-owner limits span workspaces. Different accounts cannot reliably be
identified as the same person; the aggregate Free pool provides a final spending limit.

Store initialization applies additive migrations in the private aedrova_billing schema:
billing.budget_owner, budget_reservations, inference_details, budget_alerts and
billing_holds, with an idempotent historical-spend backfill. Existing money is retained.
Back up the private schema before deploying. PostgreSQL multi-worker validation is
still required; local tests use SQLite. Do not run this migration in public Supabase tables.

Production steps, before enabling checkout:
1. Review the prices: Team $200/year exceeds twelve $10 Pro payments ($120),
   although Team now includes more capacity. No annual-discount claim is made.
2. Provision approved Stripe prices with scripts/setup_stripe_live.py in the intended
   live account; preserve existing subscriptions and migrate them explicitly.
3. Configure the returned price IDs, live secret, signed webhook secret and billing
   encryption key privately on the service. Never commit or paste secrets into chat.
4. Validate checkout, renewal, cancellation, refunds and duplicate/out-of-order webhooks
   against the deployed private ledger. Existing sandbox products are not live products.
5. Only after validation, enable checkout/gateway/Free activation and leave waitlist mode.

Private usage report: uv run python -m scripts.report_ai_usage using the service's
private environment. Reports provider/model/user/workspace costs and plan distribution.
Historical conversion attribution and provider invoice reconciliation remain follow-ups.
No new products, production migrations, deployment or charges were performed here.
Linear is removed from connector catalogs, role suggestions and OAuth routes.
Existing historical grants are preserved but no longer exposed as supported connectors.
