# Instagram and TikTok — Marketing Bud connectors

Instagram's existing scoped-token adapter reads professional-account profile and
up to ten posts. Instagram OAuth app registration remains pending; no connection
or publishing has been claimed. Meta developer login is required first.

TikTok's new local OAuth implementation requests only user.info.basic and video.list.
It uses the existing encrypted, account-bound, one-time OAuth state and confirmation.
Set resource to `me` for browser sign-in: the callback resolves the authorized open_id,
then verifies the actual profile/public-video reader before showing Connected.
Token refresh is serialized and rejects any account identity change. Tokens remain
server-side. No publishing, messaging or paid-ad scopes are requested.

Register TikTok Login Kit + Display API in the developer portal. Exact redirect:
https://aedrova-connectors.onrender.com/buds/oauth/tiktok/callback
Store AEDROVA_TIKTOK_BUD_CLIENT_ID (TikTok client key) and
AEDROVA_TIKTOK_BUD_CLIENT_SECRET in ignored .env.dots and the approved isolated
connector service. The new code must be deployed there before using this callback.
App review/sandbox testing, account consent, refresh and live-reader validation remain
pending. The public website remains waitlist-only. With owner approval, TikTok sandbox
credentials are stored in ignored, mode-0600 .env.dots and the isolated Render connector
service's environment. They were saved with Save only; no deployment was triggered.

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
locally but remains undeployed.
The production form still needs a genuine sandbox demo video; its fields were not saved.
Meta sign-in was reported by the owner, but developer pages are missing required
JavaScript dependencies and the Graph API Explorer renders blank in the in-app
browser. Instagram developer enrollment/app registration remains unverified.
