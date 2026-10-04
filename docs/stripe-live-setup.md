# Live Stripe preparation before M14 — October 3, 2026

Local tooling is ready; the Stripe live account has NOT yet been configured or validated.
The public website remains a waitlist, and no purchases or paid hosting changes were made.
No SQL is required for this preparation step. Existing sandbox credentials and records are preserved.

## Owner action now

1. Stripe Dashboard: select the actual Aedrova account, leave the sandbox, and complete
   Activate account / business verification and payout bank details. Use truthful legal-owner
   information; public brand Aedrova, website https://aedrova.com, support aedrovaai@gmail.com.
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
It creates $10/week and $49/month recurring USD prices, with separate live lookup keys and
idempotency keys; validates prices before saving; creates a cancellation-at-period-end
portal with plan/quantity changes disabled; uploads the original Aedrova checkout icon.
Included allowances stay at $1/week and $10/month of provider usage with one active build.
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

This checks charges/payouts enabled, both actual live prices, live active portal,
and an enabled webhook URL with all supported events. It does NOT prove the signing
secret matches; signed delivery must be verified separately after deployment. CLI
failure output excludes upstream exception bodies and credentials.

Leave `AEDROVA_WAITLIST_ONLY=true`, `AEDROVA_CHECKOUT_ENABLED=false`,
`AEDROVA_STRIPE_TEST_MODE=false`, and gateway/release/legal flags false until the real
managed-AI service, allowance enforcement, signed/notarized public installer, policies
and deployment acceptance are complete. Do not turn flags on to bypass missing release work.
Opening public sales needs explicit owner authorization. Continue payment behavior tests
in the sandbox; do not perform artificial live-card test purchases.

## Render sleep resolution

Render Free web services sleep after 15 minutes without incoming requests. Upgrade this
web service's compute (not the workspace subscription) to the lowest paid option,
currently 0.5 CPU / 512 MB, $7/month. Additional bandwidth/build usage can incur charges.
The Supabase database remains in use: no Render Postgres purchase is needed.

Owner approval of recurring spend is pending. After approval:
Render Dashboard → aedrova-website → Compute → select the $7/month paid 512 MB tier →
Save/Apply; verify health and the public waitlist afterward. Update the Blueprint's
`render.yaml` plan to the documented equivalent in the same change, preventing future
Blueprint sync from resetting the service to Free. No paid resource is provisioned by
this local preparation. No keep-alive workaround was added.

## Verification

243 website tests passed, including 12 new live-preparation/preflight checks. Ruff passes.
No live Stripe operations, deployments, database mutations or purchases were performed.

Sources: https://docs.stripe.com/get-started/account/set-up,
https://docs.stripe.com/keys, https://render.com/docs/free,
https://render.com/docs/compute-plans, https://render.com/pricing.
