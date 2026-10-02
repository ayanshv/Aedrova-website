# Owner setup: required to finish live Milestone 9 acceptance

Local code/tests do not make this a live paid release. Leave checkout disabled until the
following work and the acceptance checks pass. Never send secret keys in chat.

## 1. Domain, Python host and private database

Choose the real website domain and a Python server host. Configure HTTPS and a reverse proxy
that supports unbuffered SSE, an upstream timeout above 180 seconds, an 8 MiB request-body
limit, header-size limits and public request rate limits. Keep access logs disabled for
OAuth callbacks, gateway requests and credential-bearing URLs. Trust forwarded IP headers
only from your actual proxy. No browser script needs third-party API access.

Set `AEDROVA_ORIGIN=https://YOUR_DOMAIN`, `AEDROVA_PRODUCTION=true` and
`AEDROVA_DATABASE=postgresql+psycopg://...` in the server secret store. Use a dedicated database
login with permission to own/create the `aedrova_billing` schema and its tables, rather than
an anonymous Supabase API key or a customer's database credentials. Prefer a separate private
PostgreSQL database; if using Supabase PostgreSQL, use its server connection details and a
restricted billing role. Keep `aedrova_billing` out of exposed Data API schemas. The server
creates its own private billing tables and revokes schema access from PUBLIC. No new desktop
chat migration is required.

Generate a Fernet key once using the cryptography library's `Fernet.generate_key()` and save
it as `AEDROVA_ENCRYPTION_KEY` in the server's secret store. Keep it stable and backed up;
changing it makes prior encrypted sessions, replay content and inquiries unreadable. Back up
and monitor the private database. Production PostgreSQL row-lock/advisory-lock behavior still
requires acceptance against this actual database; embedded schema validation is not that test.

Deploy privately/staged first using:
`uv run uvicorn aedrova_site.app:create_app --factory --host 127.0.0.1 --port 8090 --no-access-log`
behind your host's supervisor/proxy. Do not expose SQLite as a production shared ledger.

## 2. Supabase Google sign-in

Supabase → Authentication → URL Configuration → Redirect URLs: add the exact website callback
`https://YOUR_DOMAIN/auth/callback`. For local preview testing add
`http://127.0.0.1:8090/auth/callback`. Keep the existing desktop loopback redirect allowlist.
Google Cloud's authorized redirect URI stays the Supabase callback
`https://cpelagtufyocepnqcqqd.supabase.co/auth/v1/callback`; do not replace it with the desktop or
website address. Ensure the Google consent screen permits beta testers or is ready for its
intended audience. Use the same Google account on the website and in the Mac app.

The server uses the existing public Supabase URL/publishable key and verifies current user
and workspace membership for every protected operation. Workspace creation calls the already
implemented `onboard_workspace` RPC, saving the selected nickname and initial Codex preference.
Existing team nicknames are never renamed automatically.

## 3. Stripe sandbox first

Complete your Stripe business/payment onboarding. In Stripe sandbox/test mode create:
- A $10 USD recurring Price, interval **week**, interval count 1.
- A $49 USD recurring Price, interval **month**, interval count 1.
- Optionally, a $10 USD **one-time** Price for $5 of additional AI usage.

Copy `config/plans.example.json` to an actual deployment configuration file, replacing the
weekly/monthly `price_id` values. Keep the approved amounts, allowances and concurrency values.
Set `AEDROVA_PLANS_FILE` to that file (or `AEDROVA_PLANS` to its JSON). Do not use test Price IDs
with live keys. If offering the optional purchase, set `AEDROVA_TOPUP_PRICE_ID` to its one-time
Price ID; otherwise that button remains hidden.

Put the Stripe secret in `AEDROVA_STRIPE_KEY` only on the server. Create a webhook destination
at `https://YOUR_DOMAIN/stripe/webhook` for:
`invoice.paid`, `invoice.payment_failed`, `customer.subscription.created`,
`customer.subscription.updated`, `customer.subscription.deleted`,
`checkout.session.completed`, `charge.refunded`, `charge.dispute.created`.
Store its signing secret as `AEDROVA_WEBHOOK_SECRET`. For localhost use Stripe's CLI forwarding
and its local signing secret instead. Configure Stripe Customer Portal for cancellation and
payment-method management. Disable portal plan/quantity changes until their rules are explicitly
supported; do not enable unrelated prices or promotions. Finalize the business's tax and refund
policy before launch; this beta does not automatically configure tax registration/collection.

Canonical subscription state plus a paid invoice enables entitlement, not a success-page visit.
A failed/canceled subscription stops new provider calls. Refunds/disputes reverse purchased AI
credits; a negative credit balance stops builds pending billing review. Won disputes do not
silently restore debited credit: review and resolve them deliberately. No automatic top-up or
provider fallback is allowed. Refund a subscription through Stripe and verify its entitlement
state as part of live acceptance; refunding an invoice alone does not cancel a subscription.

## 4. Provider commercial billing

Enable billing/model access in Aedrova's OpenAI Platform and Anthropic Console projects.
Put their API credentials in `AEDROVA_OPENAI_KEY` and `AEDROVA_ANTHROPIC_KEY` on the server.
Set project spend alerts/limits appropriate to the beta. Customers do not supply these keys.
This funds commercial API usage, not a resale of personal ChatGPT or Claude subscriptions.

`config/models.beta.json` provides the tested protocol selections/rates:
GPT-5.3-Codex and Claude Sonnet 5.5. Rates were checked against official pricing on September 30,
2026. Recheck rates and model availability before activation, then set `AEDROVA_MODELS_FILE`.
Rates are integer micro-USD per million tokens. Cache reads/writes are accounted separately.
Claude beta headers are an explicit allowlist observed from the pinned SDK; retest them when
upgrading. Both marketed providers must be configured before public checkout can open.

Set `AEDROVA_GATEWAY_ENABLED=true` only after keys and models are configured. Coding requests
are stateless, standard-tier, text/tool-result inputs; hosted provider tools and multimedia
are disabled. The beta conservatively bounds encoded request bytes plus 8,192 of protocol overhead to 200,000,
with 16,384 output tokens per ordinary request. Long requests may require a narrower task.
Standalone Codex compaction reserves its larger model output ceiling and can therefore stop
on a small remaining balance before making any provider request.

Interrupted requests whose real cost cannot be established conservatively consume their
reservation and are not automatically retried. Reconcile exceptional uncertain charges with
provider logs before making a manual adjustment. Measure real build costs and reconcile rate
assumptions before advertising general production allowances.

## 5. Signed Mac installer

Join the Apple Developer Program, install a Developer ID Application certificate in this Mac's
Keychain, and create a notarization Keychain profile using Apple's `notarytool store-credentials`.
Keep passwords/tokens in Keychain, not scripts or chat. Set the public managed origin during the
app build, so customers never need a service URL or provider key:

```sh
# Run from the desktop repository; these values are public configuration/certificate labels.
AEDROVA_MANAGED_ORIGIN=https://YOUR_DOMAIN \
AEDROVA_SIGNING_IDENTITY='Developer ID Application: YOUR CERTIFICATE LABEL' \
uv run --no-sync python scripts/package_desktop.py
uv run --no-sync python scripts/build_dmg.py --notary-profile YOUR_KEYCHAIN_PROFILE
```

The release script verifies signing, notarizes/staples the app, builds an Applications-drag DMG,
signs/notarizes/staples the DMG, checks Gatekeeper and writes a SHA-256 release manifest. This
signed branch has not been run without your certificate/profile. The JIT entitlement required
by bundled runtimes needs verification during signed fresh-Mac testing. Fix signing errors
before continuing; do not disable Gatekeeper or strip protections.

Copy `dist/Aedrova.dmg` and `dist/Aedrova.manifest.json` to the server's private release directory.
Set `AEDROVA_DOWNLOAD_PATH` and `AEDROVA_DOWNLOAD_SHA256` to that verified artifact. A preview
manifest is rejected by the website's release gate. Test on a clean Mac, online and offline:
install/launch, Google login, runtime availability, folder selection, IDE/GitHub setup, both
providers' edits/tests/review and cancellation. The local preview is ARM64; Intel/universal
support is not implied. Codex CLI 0.155.1 and the pinned Claude SDK runtime are bundled, so customers do not need
to install a coding CLI or supply a provider key for managed builds. The builder must have
the official OpenAI-signed Codex binary; the packaging script checks version and publisher,
includes its license/notices, and records its source hash. Fresh-Mac signing and both runtime
builds still need acceptance before a turnkey release can be promised.

## 6. Policies and operations

Finalize privacy, terms, support/contact, refunds and data-processing disclosures, including
sending permitted chat/code context to the chosen model provider. The current daytime street hero uses Pexels footage with website/promotional use permitted by
its license; source, creator and hashes are recorded in `aedrova_site/static/media-credits.json`.
Review the license for any future replacement footage. Meeting transcription is still a
future feature and must not be sold as available.

Run `uv run python -m aedrova_site.maintenance` hourly on the host: expire sessions/inquiries,
remove encrypted model replay content after 24 hours, settle abandoned pending requests
conservatively and keep monetary records for reconciliation. Enterprise inquiries are stored
privately for up to 30 days; inspect them with
`uv run python -m aedrova_site.inquiries --output /PRIVATE_PATH/new-inquiries.json`.
The output is private, cannot overwrite an existing file and is not emailed automatically.
Keep the encryption key available to both the web service and maintenance/export jobs.

## 7. Acceptance before switching on checkout

Use sandbox credentials and disposable workspaces. Verify website Google PKCE login, creation
with nickname, desktop discovery of the same workspace, checkout and webhook activation.
Run both real providers through the deployed gateway and reconcile provider usage with the
ledger. Verify low allowance/hard stop, a second concurrent build, cancellation, expired run
access, owner/member restrictions, a removed member, another workspace/account, duplicate and
out-of-order webhooks, failed renewal, canceled subscription, explicit credit purchase,
partial refund/dispute and rollback/recovery after a server restart. Exercise the ledger from
multiple processes against actual PostgreSQL. Repeat checkout/cancel/portal flows and the
clean-Mac installer checks. This work is pending, not covered by local tests.

Only after acceptance, policies and release verification set `AEDROVA_LEGAL_READY=true`,
`AEDROVA_RELEASE_READY=true`, then `AEDROVA_CHECKOUT_ENABLED=true`. Verify all gates using
`/health`. Repeat Stripe setup with separate live keys/Prices/webhook signing secret and a
controlled production acceptance transaction before accepting public customers.

References: [Stripe subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks),
[OpenAI pricing](https://developers.openai.com/api/docs/pricing),
[Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[Codex custom providers](https://learn.chatgpt.com/docs/config-file/config-advanced),
[Claude secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment).
