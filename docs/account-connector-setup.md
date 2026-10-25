# Remaining sign-in connectors — October 10

Implementation is ready for provider registration, not public customer acceptance.
The isolated connection service handles confidential exchanges, read verification,
account-bound grants and the existing Bud confirmation screens. No SQL migration.
Do not put secrets in chat, Git, screenshots or the desktop app.

## Customer experience

- GitHub: sign in/approve, pick an installed repository by name.
- Supabase: sign in/approve, pick a project by name.
- Notion: sign in/approve, pick a shared page by name.
- Figma: sign in/approve, paste a file link (not an API key or file ID).
  Figma's current file-content scope does not provide an account-wide file picker.
- TikTok: sign in/approve; the authorized account is selected automatically.
- Stripe: log in to Stripe, choose the account in Stripe’s own install screen,
  approve the read-only app, and return automatically to the configured Finance Bud.
  No customer key, account ID, or authorization code entry is required.
- Instagram: sign in/approve with a professional Business/Creator account; account
  selected automatically. Personal accounts are not supported by this API.
- Vercel: install/approve the integration, then pick an authorized project by name.
- Search: Enable web search, enter a topic. Aedrova uses its existing OpenAI service;
  customers do not copy keys or create another account. Disabled until funded.

## Required-now provider setup (owner gates)

Finish one provider at a time. Existing live permissions are not broadened.

### Stripe

1. Sign in at https://dashboard.stripe.com/apps and complete your passkey/2FA.
   October 10 browser inspection reached this exact identity-verification gate.
2. Create/upload a Stripe App named Aedrova Buds (OAuth, public distribution),
   with ONLY connected_account_read and balance_read permissions. Do not enable payment/payout writes.
3. Register https://aedrova-connectors.onrender.com/buds/oauth/stripe/callback.
4. Start External test; save the actual provider-issued test install URL as
   AEDROVA_STRIPE_BUD_AUTHORIZE_URL. Public install links require Stripe App review.
5. Save app client ID as AEDROVA_STRIPE_BUD_CLIENT_ID and the matching environment's
   app developer API key as AEDROVA_STRIPE_BUD_CLIENT_SECRET in ignored .env.dots
   (0600), then the isolated Render service only. Do not reuse checkout keys implicitly.
6. Deploy, authorize a dedicated test account, verify account/balance reads,
   token renewal, uninstall/revocation and account isolation. No payment is initiated.

Reference: https://docs.stripe.com/stripe-apps/api-authentication/oauth

### Instagram

1. Complete Facebook Developer registration at https://developers.facebook.com/apps/.
   Existing browser account displays "Register as a Facebook Developer"; no apps exist.
   Owner must approve/accept any new platform agreement and identity verification.
2. Create Aedrova Buds with Instagram API / Instagram Login. Use
   instagram_business_basic ONLY. No publishing, messaging or comment permissions.
3. Register https://aedrova-connectors.onrender.com/buds/oauth/instagram/callback.
4. Save Instagram app ID/secret as AEDROVA_INSTAGRAM_BUD_CLIENT_ID/CLIENT_SECRET
   server-side (Instagram app credentials, not an unrelated Facebook app pair).
5. Add a professional account as tester, approve an actual grant and verify profile
   and recent-public-post reads. Test long-lived token renewal and revocation.
6. Business verification, App Review and live mode are required as applicable before
   public customers can sign in. Do not represent tester success as public approval.

Reference: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/

### Vercel

1. Open Integrations → Integrations Console → Create in your Vercel team dashboard.
2. Create an external/connectable integration named Aedrova Buds; suggested slug
   aedrova-buds. Set Projects Read and Deployments Read only; no writes, environment
   variables, billing or log access. Prepare actual brand logo and legal URLs.
3. Register https://aedrova-connectors.onrender.com/buds/oauth/vercel/callback.
4. Review/accept the integration agreement personally or provide action-time approval.
5. Store AEDROVA_VERCEL_BUD_CLIENT_ID, CLIENT_SECRET and SLUG server-side. Installation
   codes exchange on Vercel's integration endpoint; identity-only Sign in with Vercel
   is not a substitute. Tokens retain the installation team for every read.
6. Test named project selection, deployment snapshots, wrong-team isolation and
   uninstall/revocation. Marketplace availability/review remains a separate gate.

Reference: https://vercel.com/docs/integrations/create-integration/vercel-api-integrations

### Managed Search

1. Existing `AEDROVA_OPENAI_KEY` plus enabled included AI (`AEDROVA_GATEWAY_ENABLED`)
   enables OpenAI Responses live search. No separate Search account, key, card or
   Brave subscription is needed. Waitlist mode remains closed. Connecting a topic
   saves an authorized capability without incurring inference; it does not claim
   that an actual search has already succeeded. Actual reads require a usable plan.
2. Default caps remain 100 requests/day service-wide and 10/day per originating
   workspace, shared across users/Buds, on UTC calendar days. AI reservations also
   enforce company, Free-pool, funding-owner, billing workspace and rolling limits.
   Borrowed agent runs must match the authenticated user/workspace/billing root.
3. Pinned `gpt-5.4-mini-2026-03-17`, low reasoning, one hosted web-search call and
   2048 total output tokens per request. Reserve 128000 input tokens plus output
   ceiling and $0.01 tool fee before sending. Settle reported usage at $0.75/$4.50
   per million input/output tokens plus tool fee; no cached-input discount assumed.
   Missing/uncertain usage or transport outcomes conservatively charge reservation;
   explicit HTTP rejections settle zero. No automatic retries. Provider request
   receives the ledger reservation as Idempotency-Key; completed reads are not cached.
4. Only saved topic is sent, with `store:false`; no workspace files/history in the
   search request. Responses are bounded, require completed search and HTTPS source
   annotations, and are untrusted evidence. Desktop appends actual source links after
   permission recheck, never fabricated references. Source-backed final synthesis
   remains separately metered through the existing agent run.
5. Old explicit Brave-token grants remain legacy compatibility; the managed path
   prefers OpenAI. No new Brave activation is required. Disconnect disables local
   tool access; no claim of globally revoking the shared OpenAI operator credential.

Official references, verified October 25, 2026:
https://developers.openai.com/api/docs/guides/tools-web-search
https://developers.openai.com/api/docs/models/gpt-5.4-mini
https://developers.openai.com/api/docs/pricing

## Verification / release gates

Mock HTTP and native tests validate code behavior; they do not prove provider approval.
Stripe registration has progressed to an uploaded test version (see the latest status below). Instagram/Vercel registration and Search funding remain pending. Existing GitHub,
Supabase, Figma, Notion and TikTok configuration remains as documented previously;
fresh consent/discovery, refresh and revocation acceptance still require actual accounts.
This work does not enable checkout, publish Marketing media, or advance M14.

## Stripe preparation after dashboard login

The owner signed in to the Aedrova account (test mode). Its Created apps list was
empty. Stripe Apps CLI plugin v1.21.0 installed locally; proposed headless OAuth
manifest and 300×300 existing brand icon prepared in integrations/stripe-buds/.
Local checks confirmed only connected_account_read and balance_read permissions
and the existing HTTPS callback. No upload, install or publication occurred.

The browser is now at Stripe CLI Review and authorize: Aedrova Test mode,
Super Administrator, with Stripe's notice that authorization enables CLI access
for all team members on the selected account. Owner must personally review and
click Authorize if acceptable. This is developer CLI access, not the permissions
of the customer-facing Bud app. No live account selected. Until this is authorized,
the app upload/client ID/external-test setup remains blocked. The temporary device
pairing may expire; regenerate the CLI login flow if necessary. Do not share secrets.
The Stripe Apps Agreement remains a separate review/acceptance gate before upload.

### CLI authorization completed; Apps Agreement gate

Owner explicitly authorized clicking Authorize. CLI confirmed Aedrova sandbox/test
account acct_1UMFdU9nkulz5rfT on October 10; no live environment was added.
A normal validated test upload was attempted without --accept-tos or --force.
Stripe rejected it because the Stripe Apps Developer Terms and Conditions have
not been accepted. No app was uploaded. The signed-in browser is prepared at:
https://dashboard.stripe.com/acct_1UMFdU9nkulz5rfT/apps/accept-terms
Owner must review https://stripe.com/legal/app-developer-agreement and accept
for Aedrova, or explicitly authorize this agreement acceptance. CLI-access approval
does not imply acceptance of this separate agreement. This blocks app upload and
external OAuth testing; subsequent credentials/review/live acceptance remain pending.

### Apps Agreement accepted; test upload complete (October 10, 2026)

Owner explicitly approved Accept. Stripe confirmed “Terms and Conditions accepted.”
Aedrova Buds com.aedrova.buds v0.1.0 then passed normal CLI validation and upload
without forcing validation or enabling live CLI access. Its dashboard reports
“Approved for testing”; it is not installed or published to the Marketplace.
The headless package now includes a real npm lockfile with no dependencies.
Permissions remain connected_account_read and balance_read only.

The live-mode app Details page explicitly reports:
“Verify your business to get started with external testing.” Attempts to select
an external test version did not activate a test channel; there was no displayed
error in that dialog. Business verification is the current owner gate.
Open https://dashboard.stripe.com/acct_1UMFdU9nkulz5rfT/apps/created/com.aedrova.buds
and complete Stripe's business verification in the Aedrova account. The owner must
supply and submit their actual business/identity information privately in Stripe.
No verification information, payment, or live API authorization was submitted.

After verification: enable external testing, obtain the actual OAuth client ID and
install link, configure matching developer credentials only on the connector server,
and perform approved install/consent, account/balance, refresh, and revocation tests.
The Stripe connector is NOT complete. Checkout/public billing and M14 remain deferred.

### Prepared customer workflow while developer verification is pending

The owner chose to defer Aedrova developer business verification and prepare the
customer connector without activation. Existing OAuth and automatic account binding
implement the customer flow: Finance Bud → Connect Stripe → Stripe login → select
an account in Stripe → approve account/balance reads → automatic Aedrova confirmation.
The account selected in Stripe is bound from the exchanged token and verified with
GET /v1/account and GET /v1/balance before displaying Connected. Failure or a mismatched
account cannot create a grant. Customers do not supply tokens, IDs or manual codes.
Customers require Stripe Apps administrator rights to install this app.

Verified customer accounts do NOT replace developer verification. This account’s
Stripe dashboard blocks external testing until Aedrova business verification. Public
OAuth links also require publication after app review. The current sandbox/test
upload is not a live customer release, and external testing is not a public launch.
No checkout, subscription or payout functionality is enabled by this connector.

Required later (not to begin Phase 1): owner completes Aedrova business verification
in Stripe, enables external testing, securely configures matching app credentials
and issued install link on the isolated connector service, and authorizes fresh
account/refresh/disconnect acceptance. Publish only after Stripe review. Keep Connect
unavailable until that setup exists; do not substitute a fabricated install link.
Official flow: https://docs.stripe.com/stripe-apps/api-authentication/oauth
External-test restrictions: https://docs.stripe.com/stripe-apps/test-app

### Phase2 owner handoff — business information form

Signed-in October10 review still reports developer verification required for external
testing. Owner form prepared: Settings→Business→Business details→Edit business
details. Select your actual industry, set business website https://aedrova.com and
write a truthful2–3sentence product/charging description, then Save personally.
Account representative, public details and service agreement are also marked
incomplete; walk through them one requirement per response. Do not enable checkout
or assume this first form alone completes Stripe verification. This blocks Stripe
Bud external OAuth acceptance, not ongoing independent connector tests.

### Stripe business information saved — service agreement handoff

Owner reported saved; dashboard independently confirms business website
https://aedrova.com, public name Aedrova, and industry/product description provided.
Business information no longer shows Incomplete. Opened Service agreement → Review
without submitting. Next owner requirement: review the Stripe Services Agreement
and Acquirer Disclosure in the open Terms of service modal; click Continue personally
only if authorized and in agreement. The modal also includes consent to Stripe text
messages and a representation that business information is complete/correct. No
agreement accepted by the agent. Representative/public details/descriptor still
incomplete; full verification and Stripe external testing remain blocked. Phase2
is active; no later phase or live billing enabled.

### Stripe agreement completed — public support details handoff

Owner reports agreement done; independent dashboard observation shows Service
agreement no longer listed as Incomplete. Opened Public details → Edit public
details → Add customer support details without entering/submitting fields. Next
owner requirement is to complete truthful support phone/address/email/URL and
applicable published privacy/terms URLs, then Save personally. Business name and
website already show Aedrova/https://aedrova.com. The form defaults to showing the
support phone on receipts/invoices; owner must choose the appropriate public
contact information. Representative and descriptor remain Incomplete. Full Stripe
verification/external testing and Phase2 acceptance remain open; no billing enabled.

### October11 — policies live and Stripe URLs saved

Website PR4 https://github.com/ayanshv/Aedrova-website/pull/4 merged after green
CI38120908946; main commit8bb942d, mainCI38121001131 also green. Render website
srv-db0a8o7avr4c73eqcj4g auto-deploymentdep-db5jhsmk1f9s73eeecdg succeeded.
Live browser verification confirms new Privacy/Terms effectiveOctober11 and Support
with authorized phone(408)634-5254. Waitlist retained; release/billing gates untouched.
Current website development branch integrates the same pages:431 tests passed,
tracked secret check passed.

Entered https://aedrova.com/support, https://aedrova.com/privacy and
https://aedrova.com/terms into configured Stripe form and clicked Save under explicit
owner authorization. Modal closed; Customer-facing information no longer Incomplete
and saved Terms plus other provided URLs appear. No private address guessed/entered.
Stripe still marks representative/statement descriptor incomplete. Active Account
status task: Provide an external account; Stripe says no bank account on file.
Opened task details, no bank information entered. Next owner requirement: click
Start on this task and provide their valid bank account privately/personally.
This is Stripe account readiness, not evidence of full connector external-testing
acceptance. No later milestone started. Legal/business identity and jurisdiction
review remain required before paid public Beta; policies are not a compliance guarantee.
