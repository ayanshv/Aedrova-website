# Connector completion — October 20, 2026

All-nine commercial certification remains OPEN. Controlled tests are not live acceptance.

## Work completed

- Fresh native staging Google authentication and the authenticated nine-provider
  catalog passed. Six previous OAuth providers enabled; no active test grants at start.
- 117 connector lifecycle/discovery/account/isolation tests passed before changes.
- Created the owner-approved unlisted Vercel integration `aedrova-buds`, contact
  contact@aedrova.com, existing brand logo and actual current 1920x1080 product image.
  Saved scopes: Integration Configuration Read, Projects Read, Deployments Read;
  all other scope selectors None. No public listing, write, environment-variable,
  source-file or billing access. Staging HTTPS callback registered.
- Owner specifically approved private Vercel ID/secret storage in ignored mode-0600
  .env.dots and Render aedrova-beta-staging. Saved all three settings including slug;
  existing free service deployment succeeded at existing source 404105f.
- Owner approved installing on team ayansh (ayansh2) for ONLY amicus-website-mq.
  Real provider consent confirmed Read Installation/Deployments/Projects. Callback
  exchange and project discovery passed and exposed only that selected project.
  Initial manual selection was attempted after the ten-minute state expired and
  correctly rejected. No real project/deployment reads or disconnect claimed yet.
- Fixed the redundant Vercel second picker: a sole provider-authorized project is
  selected automatically and both actual readers must succeed before Connected.
  Multiple authorized projects still require an explicit choice; zero resources
  remain unconnected. New tests cover failed reads, team context and callback replay.
  Full backend suite now 573 passed.
- Stripe v0.1.0 Approved for testing was selected as external test version under
  explicit owner approval. Dashboard now exposes Test OAuth links (0/25 testers).
  This is not publication, a tested customer grant, or completed business verification.
- Prepared Stripe v0.1.1 manifest with the additional staging callback, preserving
  the original callback and exactly connected_account_read / balance_read. Upload
  and staging-key transfer await the separately requested owner approval.
- One fresh Instagram and TikTok start each reached the correct real service login
  with existing scopes. No passwords entered, new consent or fresh social reads yet.
- Meta developer account now blocks access with identity confirmation via email.
  Did not send a code, bypass the checkpoint or change the account's security.
- Brave Search has no configured owner key; browser reaches Login. No plan, card,
  subscription, credit purchase or new agreement was submitted.

## Honest provider status

GitHub/Supabase/Notion/Figma retain October 15–16 scoped-read/local-disconnect
acceptance. Fresh renewals, provider-side revocation and public eligibility must
still be certified; see companion app docs/connector-certification-step-6.md.
Instagram retains historical October 14 read acceptance; fresh tests/public review
remain open, additionally blocked by Meta identity confirmation for admin changes.
TikTok production is Draft with no production scopes/products and no genuine
end-to-end review video. Its existing sandbox remains distinct from public approval.
Vercel now has real registration, staging configuration and scoped callback/discovery;
sole-project callback, both real readers and local disconnect/denial now passed (see final acceptance below).
Stripe v0.1.1 external testing is enabled with the staging callback; matching developer API key, hosted activation and actual grant acceptance remain open. Brave Search needs the owner's own activation/credential.
Figma still requires a file link because the implemented scope offers no account-wide
file discovery; login-only must not be advertised for this connector's entire flow.

## Required owner handoffs

1. Stripe activation approval was received and v0.1.1 uploaded/selected. The CLI
   session has no reusable test developer API key in its configuration. Do not reuse
   checkout credentials or copy a CLI user-access token. In Stripe, obtain an existing
   matching TEST app-developer API secret (not a publishable key), then save it privately
   as AEDROVA_STRIPE_BUD_CLIENT_SECRET in ignored mode-0600 .env.stripe-bud-staging.
   The actual provider-issued external test URL/client ID are already saved there.
   Never send this file/key in chat. This blocks Render activation/token exchange;
   no partial ID-only Render configuration was saved because config requires both.
2. Meta email and owner CAPTCHA completed. Developer app access restored and
   live roles page verified. No further identity action is needed now; public app
   review remains required (Unpublished).
3. Sign in to the open Instagram login as professional tester @aedrova_ai and TikTok
   login as sandbox-approved @aedrova. If an attempt limit appears, stop. No credentials
   in chat. Fresh authorization links may be needed after their ten-minute lifetime.
4. Log in or create the Brave Search API account yourself, review its plan/payment
   requirements and activate only what you intend to fund. Agent cannot make payments.
   Keep its key private; key destination/activation must be specifically authorized.

No blanket “done” claim, public connector promotion, production-key transfer, paid
hosting or installer launch follows from this work. Official provider references:
https://vercel.com/docs/integrations/create-integration/vercel-api-integrations
https://developers.tiktok.com/docs/en/app-review-guidelines
https://docs.stripe.com/stripe-apps/api-authentication/oauth
https://api-dashboard.search.brave.com/documentation/quickstart

## Final acceptance this turn

- Website PR #19 passed both required checks and merged as 3a1f43b; Render production
  reports Live. Equivalent staging f06e0bd reports Live. Both hosted health checks
  return 200; browser HTML 404s use the actual embedded PNG logo and no-store.
- Vercel: fresh callback automatically selected the sole provider-authorized project
  amicus-website-mq, then returned branded Connected. Actual project and deployments
  tools both passed. Local disconnect passed; a later project read was denied.
  Provider installation remains until uninstall (provider_revoked=false); this is
  not evidence of provider-side revocation or public approval.
- GitHub: fresh real callback, repository selection, repository/changes/issues/
  deployments tools all passed. Local disconnect passed; later repository read denied.
- Supabase: fresh existing Aedrova organization Projects READ consent and callback
  passed. Selected only Aedrova Staging; actual project read passed. Disconnect and
  post-disconnect denial passed. Production project was not selected/read.
- Notion: fresh consent retained only the already-approved Aedrova connector validation
  page; other private pages remained unchecked. Callback, page/block read, local
  disconnect and post-disconnect denial passed.
- Stripe: owner approved v0.1.1 callback/upload/credential activation. Official CLI
  test upload succeeded and Stripe reports Approved for testing. Selected external
  test version 0.1.1; actual external-test redirect list includes staging. Saved the
  provider-issued external Test mode URL and client ID privately. CLI config uses
  a session credential rather than an app-developer API key; no credential was
  invented/extracted from unrelated stores, no checkout key reused, and no partial
  invalid server config deployed. Actual customer install/read remains BLOCKED.
- Existing Figma Oct 15-16 and Instagram Oct 14 reads remain historical evidence,
  not new acceptance this turn. No fresh TikTok grant, Brave activation or public
  connector approval claimed. No payments or scope expansion.

Controlled backend suite: 573 passed. Focused desktop connector/recovery suite:35
passed. The rebuilt internal staging DMG is source 31d5d2a, sha256
977c7ed7c2d2acc74a8b87763f37904d0dc32f6d461afa3d1954fe159d033458; image
CRC and deep/strict app signature checks passed. This is an ad-hoc preview with
public_release=false, not a commercial signed/notarized release.

Private evidence (not committed): companion app work/connector-completion-oct20/
live-batch.json, vercel-connected.png, stripe-staging-version.png; private provider
settings remain ignored and mode 0600. All successful grants in this batch were
locally disconnected. Public review, live renewal and provider-wide revocation
remain launch gates.

## Later approved social follow-up (same date)

Owner authorized completion of the three account handoffs. Meta email confirmation
completed using only its requested official verification email; new CAPTCHA remains.
IAB Instagram/TikTok fresh staging starts reached login. Safari Instagram is blocked
by a daily usage reminder on a professional-account conversion URL; active handle
not verified, no conversion or usage-limit changes made. Owner must dismiss that
reminder and select professional @aedrova_ai before fresh staging acceptance.

TikTok existing Safari session asked for email verification; selecting Email returned
Maximum number of attempts reached. Try again later before a code could be entered.
Stopped immediately, no retries/resends or limit workaround. No account handle was
shown in that challenge, so do not claim @aedrova grant acceptance.

Brave registration is prepared with owner name and brand Google email, password
empty. Browser safety requires owner to create/submit the password personally. No
terms accepted, account created, plan selected, payment made or key copied. Owner
should complete registration/login/email confirmation and leave the dashboard open;
any payment remains their own action. No API key in chat.

Native staging test session cleaned and signed out locally. Current start-only
follow-up report is companion app work/connector-completion-oct20/social-followup.json.
Prior live read acceptance remains the earlier tool evidence and records above;
this new follow-up does not add social reader/renewal/public-review acceptance.

## Fresh Instagram acceptance after owner confirmation

Meta developer access is restored; live roles page confirms @aedrova_ai Instagram
Tester and Unpublished app status. The owner completed Instagram in IAB, not the
Safari session with the reminder. Old callback was not replayed after generic403.
A fresh staging state in the correct signed-in IAB session reached consent explicitly
naming aedrova_ai and previously connected Aedrova Buds-IG. Renewed unchanged basic
read access with staging callback/24h local grant. Branded Connected callback, actual
profile and posts tools all passed. Locally disconnected only the synthetic audit
Bud grant; subsequent profile read was denied. Provider-wide revocation was not
performed (provider_revoked=false). Local native test session signed out; pending
URL files cleaned. No broader scope, posting, messaging, production change or payment.

Private fresh evidence is companion app work/connector-completion-oct20/
instagram-acceptance-oct20.json and instagram-connected-oct20.png. This supersedes
the fresh-login blocker above for Instagram. General public review, real renewal/
provider-wide revocation and all-nine certification remain open. TikTok not retried
after its limit; Brave account setup and Stripe test developer key remain pending.
