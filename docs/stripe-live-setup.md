# Live Stripe preparation

Keep public checkout gated while verifying the live Stripe account and configuration.
No SQL is required for this preparation step. Existing sandbox credentials and records are preserved.

## Owner action now

1. Stripe Dashboard: select the actual Aedrova account, leave the sandbox, and complete
   Activate account / business verification and payout bank details. Use truthful legal-owner
   information; public brand Aedrova, website https://aedrova.com, support contact@aedrova.com.
   This verification must be completed by the owner and unlocks live charges/payouts.
2. In the live Dashboard → Developers / Workbench → API keys, configure the private key
   in `/Users/ayanshvarma/Documents/Aedrova_site/.env.billing.live` under `AEDROVA_STRIPE_KEY=`.
   Use a live server key (`sk_live_`, or a suitably permissioned `rk_live_`), not a publishable key.
   Never paste it into chat. This separate gitignored file has owner-only permissions;
   `.env.billing` and its test database must remain separate. A restricted preparation key
   needs account read, product/price read-write, File write, portal configuration read-write,
   and webhook endpoint read. Production runtime needs its own appropriate permissions.
3. Reply “ready” after saving. The developer will prepare the actual live prices/icon/portal
   and validate API access. No need to create these products manually.

The setup command does not charge anyone, create checkout sessions, enable the site,
change banking details, or create a webhook endpoint. It requires charges_enabled first.
The launch catalog is Pro at $15/month or $144/year and Power at $30/month or $288/year. Free costs $0. Enterprise is contact only. Keep any existing legacy price IDs in the service configuration for renewal and cancellation events.

The tool uses separate live lookup and idempotency keys and validates prices before saving. It creates a portal that supports cancellation at the end of the billing period with plan and quantity changes disabled. It also uploads the Aedrova checkout icon.
Use the current budget limits and workflow capacity in [billing launch preparation](billing-launch.md). Confirm prices and AI allowances with the owner before enabling checkout.
The enterprise Contact Us path has no Stripe subscription price.

## Developer workflow after owner setup

From `/Users/ayanshvarma/Documents/Aedrova_site`:

```sh
uv run --env-file .env.billing.live python -m scripts.setup_stripe_live --prepare
```

Private ignored output is `work/stripe-live/plans.json`, `portal.json`, `branding.json`.
Set the live environment's `AEDROVA_STRIPE_PORTAL_CONFIGURATION` and
`AEDROVA_STRIPE_ICON_FILE` to those output IDs. This preserves the neutral #F5F5F7,
blue #0066CC, system font, pill styling already used by Checkout Sessions. Configure
Stripe Settings → Branding for portal/invoices to match; sandbox File IDs cannot be reused.

## Hosted acceptance and public sales later

First deploy the audited receiver code. On Stripe live Dashboard → Workbench → Webhooks,
create an event destination for `https://aedrova.com/stripe/webhook`, for this account,
selecting these exact events:

- invoice.paid
- invoice.payment_failed
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- checkout.session.completed
- charge.refunded
- charge.dispute.created

Copy that destination's signing secret privately into Render's `AEDROVA_WEBHOOK_SECRET`.
A Stripe CLI/sandbox signing secret is a different secret and must not be reused.
Store the live server key and portal/icon IDs in Render's environment secret store;
set `AEDROVA_PLANS` to the generated plans JSON (the local ignored file is not in Docker).
Use the existing persistent production database/encryption key; never copy sandbox
customer, subscription or ledger rows into production. Keep sandbox on its own local DB.

Read-only preflight (requires configured live plans, portal and signing-secret presence):

```sh
uv run --env-file .env.billing.live python -m scripts.setup_stripe_live
```

This checks charges/payouts enabled, all four actual live prices, live active portal,
and an enabled webhook URL with all supported events. It does NOT prove the signing
secret matches; signed delivery must be verified separately after deployment. CLI
failure output excludes upstream exception bodies and credentials.

Leave `AEDROVA_WAITLIST_ONLY=true`, `AEDROVA_CHECKOUT_ENABLED=false`,
`AEDROVA_STRIPE_TEST_MODE=false`, and gateway/release/legal flags false until the real
managed-AI service, allowance enforcement, signed/notarized public installer, policies
and deployment acceptance are complete. Do not turn flags on to bypass missing release work.
Opening public sales needs explicit owner authorization. Continue payment behavior tests
in the sandbox; do not perform artificial live-card test purchases.

## Finance closeout before opening checkout

- Review the legal operator, payout settings, statement descriptor, support contact, and tax treatment with the owner.
- In Stripe test mode, verify upgrade, renewal, cancellation, and refunds. Check that the matching entitlement and balance appear exactly once in Aedrova, including after a duplicate or out-of-order webhook.
- Verify the live destination can deliver a signed event without creating a live customer charge. Check that Stripe and Aedrova record the same event outcome.
- Keep Stripe settlements separate from provider costs. Match invoices, fees, refunds and disputes to Stripe balance transactions and payouts. Compare estimated AI usage in the private Aedrova ledger with provider invoices, then review any unexplained difference.
- Keep checkout gated until the account, prices, signed webhook and operating budget are verified and the owner approves opening sales.
