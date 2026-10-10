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
- Stripe: install/approve the read-only Stripe App; account selected automatically.
- Instagram: sign in/approve with a professional Business/Creator account; account
  selected automatically. Personal accounts are not supported by this API.
- Vercel: install/approve the integration, then pick an authorized project by name.
- Search: Enable web search, enter a topic. Aedrova owns the Brave subscription;
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

1. Choose/fund a Brave Search API plan at https://api-dashboard.search.brave.com/.
   Any purchase or new agreement needs owner action; no purchase has been made.
2. Save AEDROVA_SEARCH_BUD_KEY server-side only. Default caps: 100 requests/day across
   the entire service, 10 requests/day per workspace, shared across users/Buds.
   Verification reads count. Caps use UTC calendar days and the durable limits table.
   Requests above caps never reach Brave. These are request caps, not a monetary budget;
   set the provider billing cap too and verify pricing before enabling.
3. Deploy and test Enable web search. Verify server key rotation, caps, disconnect
   and membership isolation. Existing advanced personal-token search stays available.

Reference: https://api-dashboard.search.brave.com/documentation/guides/authentication

## Verification / release gates

Mock HTTP and native tests validate code behavior; they do not prove provider approval.
New Stripe/Instagram/Vercel apps and Search funding are missing. Existing GitHub,
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
