# Stripe checkout before M11 — October 2, 2026

Implementation and real Stripe sandbox acceptance are complete for this pre-M11 task.
The owner supplied the test credential and configured the Supabase redirect. M11 has not started. Real paid checkout stays disabled until the
provider, policies, hosting and notarized-release gates pass. No new Supabase SQL is needed.

## Owner setup completed (reference only)

1. In Stripe Dashboard, select/create the Aedrova account and a **sandbox/test environment**.
   Open Developers / API keys (or Workbench → API keys). Copy its **secret test API key**,
   starting `sk_test_`, into `AEDROVA_STRIPE_KEY=` in
   `/Users/ayanshvarma/Documents/Aedrova_site/.env.billing`, using VS Code, and save.
   A publishable `pk_test_` key is not sufficient. Never paste secrets into chat.
   This file is gitignored, restricted to this user, and uses a separate sandbox database
   and stable encryption key. Leave all enable switches as prepared; the developer will
   configure and validate them after the secret is saved.
2. Supabase → Authentication → URL Configuration → Redirect URLs: add the exact
   `http://127.0.0.1:8092/auth/callback`. Keep existing redirects. Google Cloud's redirect
   remains the Supabase callback; do not change it.

These steps are complete. Test prices, portal, signing-secret listener and the sandbox
service were configured and validated. No further owner action is required for this task. Business activation, real card details, a purchased
domain and provider keys are not required for this isolated sandbox step.

## Prepared developer workflow after owner setup

Run from `/Users/ayanshvarma/Documents/Aedrova_site`:

```sh
uv run --env-file .env.billing python -m scripts.setup_stripe --provision-test-prices --configure-test-portal
uv run --env-file .env.billing python -m scripts.listen_stripe
```

The first command uses only test keys, creates/reuses $10/week and $49/month recurring
USD prices, and saves their IDs to ignored `work/stripe-plans.json`. It prepares a restricted
portal (payment method, invoices, customer email/address and cancellation at period end;
plan/quantity changes disabled), saving its configuration ID in `work/stripe-portal.json`.
The listener passes the key privately through `STRIPE_API_KEY`, forwards the eight supported
event types to port 8092, and automatically saves its signing secret in `.env.billing`
without printing it. Keep the listener running. No external tunnel/domain is needed.

Developer sets `AEDROVA_STRIPE_PORTAL_CONFIGURATION` to the saved `bpc_` ID and both
`AEDROVA_STRIPE_TEST_MODE=true` and `AEDROVA_CHECKOUT_ENABLED=true` in `.env.billing`.
Keep gateway, release, legal, production and meetings switches false. Then:

```sh
uv run --env-file .env.billing python -m scripts.setup_stripe
uv run --env-file .env.billing uvicorn aedrova_site.app:create_app --factory --host 127.0.0.1 --port 8092 --no-access-log
```

Open `http://127.0.0.1:8092/onboarding`. Six optional questions → plans → Google sign-in →
workspace creation/selection → plan review → Stripe-hosted checkout → secure confirmation.
The agent nickname from onboarding follows workspace creation. Existing workspace nicknames
are preserved. The server keeps plan selection through Google PKCE and the browser keeps it
when switching/refreshing. The public preview/meeting service on port 8090 is unaffected.

## Real sandbox acceptance completed — October 2

Real Stripe test-account operations (no real cards/funds):

- Provisioned approved USD recurring prices: $10/week and $49/month; configured the restricted portal.
- Real Google PKCE sign-in returned to port 8092 with the monthly plan preserved.
- Created “Billing sandbox monthly 1002” and “Billing sandbox weekly 1002” in Supabase.
  Both Stripe-hosted checkouts completed and signed webhooks activated separate ledger rows,
  with $10 and $1 included usage respectively. Gateway/release remain disabled.
- Weekly checkout back/cancel/retry kept the workspace/plan and reused the same Stripe session.
  Insufficient-funds card stayed unpaid/pending, then simulated 3DS completion succeeded.
- Portal displayed the correct paid monthly invoice and cancellation at the paid-period end.
- A real failed follow-up test invoice suspended access; successful repayment restored it.
- A separate Stripe Test Clock customer and isolated local ledger workspace exercised a paid
  weekly renewal, a failed renewal (past_due/inactive), recovery (paid/active), immediate
  cancellation and replay of an older paid event without reactivation.
- Replayed signed actual events twice: ledger unchanged. Invalid webhook signature rejected.
- Both UI test subscriptions are scheduled to cancel at period end; clock subscription canceled.
  Test workspaces remain available for review. “Billing selection check 1002” is an additional
  unbilled workspace used to validate new-workspace selection; no existing workspace was edited.

Live testing exposed two defects now fixed: newer Stripe invoices expose status=paid without
legacy paid=true, and a URL workspace could override a newly created workspace selection.
The modern unpaid invoice statuses remain inactive. Billing selections now persist in the URL.

Verification: 132 website tests, 15 desktop managed-access tests, Ruff, JavaScript syntax and
Git whitespace checks passed. Account UI confirms allowances and disables duplicate checkout.
Unit/fixture tests cover CSRF, workspace/member authorization, limits and failure handling;
those are not a two-person production deployment acceptance test. Browser fixture checks in
this task's preparation covered the six-question onboarding, pricing, account actions and
light/dark mobile layouts. This run additionally used actual Supabase and Stripe sandbox APIs.

Evidence: ignored work/stripe-check/lifecycle-report.json and checkout screenshots. Sandbox
server: http://127.0.0.1:8092; preview/meetings on port 8090 are unaffected. Keep the listener
running while testing. The sandbox is local and must not be used for production billing.

## Later launch-only owner setup

Complete Stripe business verification, refund/support/tax policies and live-account branding
(brand logo, restrained blue accent), live prices/webhook and actual hosting. Configure
commercial provider keys and verify the public installer before enabling real checkout.
Use separate credentials/databases; sandbox events/keys cannot enable public paid access.
M11 permission will be requested again after the Stripe acceptance handoff is resolved.

References: [Stripe-hosted Checkout](https://docs.stripe.com/checkout/quickstart),
[subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks),
[test payments](https://docs.stripe.com/testing),
[CLI environment keys](https://docs.stripe.com/cli/api_keys).

## Checkout appearance — October 2

Subscription and credit Checkout Sessions now use Aedrova's name, #F5F5F7 background,
#0066CC blue action color, pill controls and Stripe's default system typography. The existing
512px Mac icon is copied unchanged to aedrova_site/static/checkout-icon.png. A real sandbox
session was visually checked with the uploaded icon and branding parameters; billing amounts,
webhooks and authentication remain unchanged. Stripe controls the hosted form layout and
wallet branding; this is a consistent light checkout, not a custom CSS/dynamic dark theme.

Sandbox setup is complete; no owner action now. Recreate the sandbox icon if needed with:
uv run --env-file .env.billing python -m scripts.setup_stripe --configure-test-branding
Set AEDROVA_STRIPE_ICON_FILE to the icon_file in ignored work/stripe-branding.json and restart
the service. This command accepts test keys only. Existing open sessions retain their original
branding; newly created sessions receive the new appearance.

Before live launch: Stripe Dashboard → Settings → Branding → Checkout: upload
/Users/ayanshvarma/Documents/Aedrova_site/aedrova_site/static/checkout-icon.png as the icon.
Use the same neutral background, blue button, default font and pill borders; also match
Settings → Branding for portal/invoices. A live Stripe File ID can optionally be configured
in the deployment's AEDROVA_STRIPE_ICON_FILE. Test File IDs cannot be reused in live mode.
