# Instagram and TikTok — Marketing Bud connectors

Instagram's existing scoped-token adapter reads professional-account profile and
up to ten posts. Instagram OAuth app registration remains pending; no connection
or publishing has been claimed. Meta developer login is required first.

TikTok's deployed OAuth implementation requests only user.info.basic and video.list.
It uses the existing encrypted, account-bound, one-time OAuth state and confirmation.
Set resource to `me` for browser sign-in: the callback resolves the authorized open_id,
then verifies the actual profile/public-video reader before showing Connected.
Token refresh is serialized and rejects any account identity change. Tokens remain
server-side. No publishing, messaging or paid-ad scopes are requested.

Register TikTok Login Kit + Display API in the developer portal. Exact redirect:
https://aedrova-connectors.onrender.com/buds/oauth/tiktok/callback
Store AEDROVA_TIKTOK_BUD_CLIENT_ID (TikTok client key) and
AEDROVA_TIKTOK_BUD_CLIENT_SECRET in ignored .env.dots and the approved isolated
connector service. Commit `3e29d836b40448604d5cccc327878d7bed4fc7da` was pushed
and deployed with owner approval. Render deployment `dep-db4pnuvlot8c73cio1v0` is
Live and `/health/ready` returns 200. App review, completed account consent, refresh
and live-reader validation remain pending. The public website remains waitlist-only. With owner approval, TikTok sandbox
credentials are stored in ignored, mode-0600 .env.dots and the isolated Render connector
service's environment. They were initially saved with Save only, then activated
by the approved manual deployment.

References:
https://developers.tiktok.com/docs/en/login-kit-web
https://developers.tiktok.com/docs/en/oauth-user-access-token-management
https://developers.tiktok.com/docs/en/display-api-get-started
https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/

## October 9 developer account check
TikTok login is verified. With owner approval, the individually owned **Aedrova Buds**
app was created: app ID `7694803472533112852`.
Production draft fields are prepared for Productivity, Web + Desktop, the hosted
Web OAuth callback above, Login Kit, user.info.basic and video.list. Desktop native
redirects accept only loopback addresses; the hosted service uses the Web callback.
Terms, privacy and website URLs use aedrova.com. These edits are **not saved**:
TikTok requires verified URLs, an app icon and a sandbox demonstration video
before saving the production form. No review was submitted.
Domain verification requires a DNS TXT record at the aedrova.com root:
`tiktok-developers-site-verification=rvMBe7neiWYxmfDW9YAZHAR94MGMPtmY`.
After the owner signed in to Cloudflare, this TXT record was added without changing
existing website or email records. TikTok confirmed **aedrova.com Verified**.
With owner approval, sandbox `Aedrova Buds validation` was created, ID
`7694747241717778453`. Its configuration was saved and verified by the portal's
Saved confirmation: existing Aedrova icon, Productivity category, Web platform,
aedrova.com website/legal URLs, Login Kit, hosted Web callback, user.info.basic
and video.list. Credentials were captured and stored in the two approved locations,
then remasked. The owner approved linking their account as a sandbox target user.
Continue initially did not open the authorization popup in the in-app browser.
After a manual Safari handoff, the portal confirms one target user, `aedrova`,
added October 9, 2026. Sandbox target-user linking is verified. This does not yet
verify an Aedrova OAuth grant or live profile/video read. The OAuth code is tested
locally and deployed. In the actual native app, a new Marketing Bud setup selected
TikTok with resource `me` and a 24-hour access lifetime. Connect account opened the
hosted account-bound flow in Safari; the existing Aedrova Google account signed in
and redirected to TikTok Login Kit. Safari now requires TikTok sign-in. No completed
TikTok OAuth consent or live account read has been claimed.
The production form still needs a genuine sandbox demo video; its fields were not saved.
Meta sign-in was reported by the owner, but developer pages are missing required
JavaScript dependencies and the Graph API Explorer renders blank in the in-app
browser. Instagram developer enrollment/app registration remains unverified.

## Verified native TikTok connection
The owner signed into the sandbox-approved `aedrova` account and completed consent
for user.info.basic and video.list. The deployed callback showed **TikTok is connected**
for Marketing Bud **Orbit**, and the native connector page independently showed
**Connected. Your Bud’s access has been verified.** Callback success requires a real
profile/public-video reader verification. The native setup was completed and Orbit
appears in the workspace sidebar. Access was requested for 24 hours.
Safari's earlier `aedrova5` account was not on the sandbox target list and correctly
failed with non_sandbox_target; no permissions were bypassed.
Production app review and a live refresh acceptance test remain pending. Instagram
OAuth setup remains pending.

## October 14 staging activation

With the owner's explicit approval, the existing sandbox client key and secret
were copied from the ignored private local configuration into the two private
TikTok settings on Render `aedrova-beta-staging`. The existing sandbox now also
allows `https://aedrova-beta-staging.onrender.com/buds/oauth/tiktok/callback`;
the older connector-service callback remains registered. Scopes remain
`user.info.basic` and `video.list`, and the existing target user remains `aedrova`.
No production settings, scopes, purchases or SQL migrations were changed.

Render deployment `dep-db80612j9qps73b4soq0` is Live (environment update;
existing deployed source `e375bdc10ac513c0273fc393c60471c5b263dd23`).
Staging HTTPS readiness returned 200 and 58 focused OAuth tests passed locally.
The real source preview, signed into the first staging Google account, created
the synthetic Marketing Bud `TikTok staging audit` in `Beta isolation 1 eb8958`.
Its Marketing gallery offers Connect TikTok. Connect account requests 24-hour
read-only access and opens account-bound Google sign-in, then TikTok's real login
page with the staging callback, without manual codes or resource IDs.

Required live acceptance step: in Safari's open TikTok login tab, the owner must
sign in to sandbox target `@aedrova` and leave the consent screen open. A fresh
grant, staging callback completion and profile/video reader verification remain
pending; the earlier successful old-service connection does not prove these.
The owner signed in during this attempt, but TikTok returned
`non_sandbox_target`. The developer portal still lists only `aedrova`; no target
users were added or restrictions bypassed. The next attempt must use that account
or obtain separate approval to link another intended sandbox test account.
Production app review/demo and token-refresh acceptance are still release gates.
Instagram remains unconfigured in staging and correctly shows Service setup
required. Evidence is saved locally under `work/social-oauth-staging/` (deployment
and live login handoff screenshots); no credentials are stored in these docs.

## October 14 account mismatch and Instagram prerequisite

After the owner prioritized social OAuth, the actual signed-in Safari TikTok
profile link was inspected: @aedrova5. This explains non_sandbox_target: the
existing sandbox lists @aedrova only. Add account opens a concrete Connect TikTok
account dialog; linking @aedrova5 as an additional tester is pending owner approval.
No sandbox target was silently added. Existing callbacks and read-only scopes stay
unchanged.

Meta developer registration is now accessible in the in-app browser. It shows
Create a Meta for Developers account: Register incomplete, Verify account/Contact
info/About you pending. Continue explicitly accepts Meta Platform Terms and
Developer Policies, so action-time approval is requested before submitting it.
Instagram client ID/secret are absent from the ignored local configuration; no
credentials can be deployed until the Instagram app is registered. Next stages:
registration, Instagram Login app with instagram_business_basic only, exact
staging callback https://aedrova-beta-staging.onrender.com/buds/oauth/instagram/callback,
private server credentials, professional tester login, callback and actual reader
verification. Public App Review/live approval is a separate provider gate.

The owner reported creating the error fallback Worker. Safari confirms its actual
name aedrovaerrorfallback with no custom domain or routes. It remains untouched and
unrouted while social OAuth is the priority.

Owner approved adding @aedrova5 and Meta registration. Meta registration was
completed after owner-performed SMS verification; existing contact email confirmed
without marketing opt-in, founder role selected. The Instagram app draft is now
Aedrova Buds / contact@aedrova.com, Instagram API use case, no business portfolio
claimed. Final Create app presents applicable terms and is awaiting separate
approval. No app credentials exist yet.

Owner signed into the developer account in Safari. Sandbox Add account → Continue
successfully opens TikTok's native tester-link popup there (in-app browser popup
failed). TikTok requires a fresh account login; the owner reached password reset.
Credential change/code entry must be completed personally. Tester addition and
fresh Aedrova OAuth callback remain unverified until that login and provider
confirmation finish. Existing user @aedrova is preserved.

## October 14 Instagram app and staging credentials installed

Owner approved the final app terms and completed password confirmations. Parent
Meta app `3077883259220045` (Aedrova Buds) is created, unpublished, with
contact@aedrova.com and no business portfolio claimed. Instagram app
`2156018749127516` (Aedrova Buds-IG) has the exact HTTPS staging callback saved.
Only instagram_business_basic was added; Meta marks it Ready for testing. The
publishing, messaging, comments and insights permissions were not added.

With explicit approval, the Instagram ID/secret were stored in ignored .env.dots
(mode 0600) and the two private Render aedrova-beta-staging environment settings.
The secret was remasked by reloading Meta. Environment-only deployment
`dep-db85045g1s2s7392hcs0` became Live in 51.3s, reusing e375bdc. The real native
Marketing gallery now offers Connect Instagram. No production credentials/settings
or purchases changed. The owner must identify the exact professional Instagram
handle and approve its Instagram Tester role; that question is pending. Then
accept its tester invitation and validate the actual account grant/profile/media.
Public review/access verification, token renewal and revocation acceptance remain
separate gates.

TikTok's tester-link confirmation was completed in Safari. On reloading the saved
sandbox, the target list contains @aedrova (one item) with Oct 14 4:14 PM; the flow
resolved to this account rather than adding @aedrova5. A fresh source staging
session and Google account-bound grant were started. TikTok's valid authorization
page now renders blank in Safari, including after one reload. Owner handoff asks
them to complete the existing read-only grant if it renders, or report blank.
No successful fresh staging callback or profile/video read is claimed yet.

Follow-up requested after social OAuth: add an accessible + next to Direct Messages
using the existing coworker DM picker; assess Bud DMs; report remaining signed DMG
and Windows launch-build gates. Do not let these displace the OAuth acceptance work.

## October 14 — Instagram live staging acceptance passed

The owner identified @aedrova_ai, accepted its Instagram Tester invitation, and
personally clicked Allow on the exact instagram_business_basic consent screen.
Meta Roles no longer shows Pending. The Instagram professional account is confirmed
by its signed-in settings and professional-account controls. The source Marketing
Bud (synthetic name "TikTok staging audit") opened the account-bound staging flow
without manual codes, keys or resource IDs. The branded callback says Instagram is
connected; native accessibility also reported Connection verified and Connected.
The connect implementation reads BOTH catalog tools, profile and posts, against
the real provider before saving a Connected grant. Thus both API endpoints passed;
this does not establish that the account contains posts or that generated advice
is correct. Requested connection lifetime was 24 hours. No publishing/message access.

Evidence: work/social-oauth-staging/instagram-tester-accepted.png and
instagram-callback-connected.png. A background native screenshot returned an older
TikTok view despite current accessibility showing Instagram success; do not use
instagram-native-connected.png as visual acceptance evidence. No code fix or new
test run was needed for this grant. Refresh, revocation/reconnect acceptance and
public App Review/access verification remain open, as does production configuration.

TikTok now reports "Maximum number of attempts reached. Try again later" to the
owner. Stop initiating authorizations; do not bypass or invent a cooldown duration.
After TikTok permits login again, resume ONE staging connection as approved @aedrova
and verify callback plus profile/public-video reads. Until then fresh staging TikTok
acceptance remains blocked. Instagram success does not close the overall social or
Phase 2 gate. DM + / Bud DM assessment remains queued after social completion.
