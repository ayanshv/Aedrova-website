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
final reads/disconnect and sole-project callback acceptance remain open.
Stripe external testing is enabled; staging callback/credentials and actual grant
acceptance remain open. Brave Search needs the owner's own activation/credential.
Figma still requires a file link because the implemented scope offers no account-wide
file discovery; login-only must not be advertised for this connector's entire flow.

## Required owner handoffs

1. Respond to the pending Stripe v0.1.1/staging-credential approval request. Nothing
   will be uploaded or copied to the server until that specific approval is received.
2. In the open Meta/Facebook checkpoint, select an email you control, click Next,
   and enter its confirmation code privately. This blocks Instagram admin/review access.
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
