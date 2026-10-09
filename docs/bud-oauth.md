# Bud account connections — local implementation and owner setup

Browser-based OAuth is implemented for GitHub Apps, Figma, Notion, Supabase
Management API, and Linear. The native connector card opens the browser after
saving any changed Bud settings, then quietly checks completion. It never
activates another desktop window. Connected requires real successful reads of
all advertised tools for the chosen resource, not just a completed login.

Tokens, refresh tokens, desktop session, PKCE verifier and browser proof are
server-only and encrypted in the private database. Authorization state is hashed,
expires after ten minutes, and is single-use. Browser and desktop accounts must
match. Grants are scoped to one user, workspace, Bud version and resource.
Automatic refresh is serialized across workers; it never extends the user's
selected grant lifetime or recreates a disconnected grant. Revoking access at a
provider requires reauthorization. Aedrova's Disconnect removes its stored grant;
revoke the app in the provider too if you want to remove provider-side consent.

## Current acceptance status

Code and deterministic HTTP/security tests pass locally. Private PostgreSQL DDL
and role isolation are validated in embedded PostgreSQL. Actual provider consent,
refresh and successful reads with owner accounts still require app registration
and real credentials. GitHub is now configured and the owner confirmed live Bud replies.
Supabase's credential pair is configured; its hosted callback is pending approval.
Figma, Notion and Linear credential pairs remain unconfigured.
Networked PostgreSQL concurrency and live provider acceptance remain gates.
This task does not deploy or change aedrova.com's waitlist mode.

Stripe balance, Instagram professional account data, TikTok Display API, Vercel
and Brave Search continue using verified scoped token connections. Their native
OAuth/installation flows are not part of this phase. No publishing, database
writes, financial transfers or third-party write access are implemented.
Research uses the existing workspace AI provider plus connected search/notes;
there is no invented separate LLM connector.

## Required setup, one provider at a time

These app credentials are registered once by the Aedrova owner. Customers will
click Connect account and consent with their own provider account; they do not
need to create their own developer app.

1. Create a **GitHub App**, not an OAuth App, at
   https://github.com/settings/apps/new. Use a unique name such as
   `Aedrova Buds Development`, homepage `https://aedrova.com`, and callback
   `http://127.0.0.1:8090/buds/oauth/github/callback`. Keep expiring user tokens
   enabled. Disable webhooks during local testing. Repository permissions:
   **Contents, Issues, Pull requests, Deployments: Read-only**; Metadata is
   automatically read-only. Leave account/organization permissions and events
   off. Select **Only on this account** for initial private testing. Create it.
2. On the app's General page, copy its **Client ID** (not numeric App ID),
   generate a client secret and save both locally in the ignored file
   `/Users/ayanshvarma/Documents/Aedrova_site/.env.dots` as
   `AEDROVA_GITHUB_DOT_CLIENT_ID` and `AEDROVA_GITHUB_DOT_CLIENT_SECRET`.
   Never paste secrets into chat, frontend code or Git. This file is mode 0600.
3. Install the GitHub App on **only the repository being tested** using Install
   App. User authorization alone does not grant uninstalled repository access.
4. Restart the local service using `uv run python scripts/run_local_meetings.py
   --with-openai`. Check without exposing credentials:
   `uv run --env-file .env.dots python scripts/check_bud_oauth_setup.py`.
5. Reopen `Aedrova/dist/Aedrova.app`, choose a Bud's GitHub card, enter
   `owner/repository`, choose grant lifetime, click **Connect account**. Sign in
   to the service with the same Google account as the desktop if requested,
   then authorize GitHub. Confirm Connected and request repository evidence.
   Verify refresh, disconnect and second-account isolation before public release.

No new Supabase SQL is introduced by OAuth. The existing connector migration
`/Users/ayanshvarma/Documents/Aedrova/supabase/migrations/202610070004_bud_connectors.sql`
remains necessary to save Buds using the expanded primary providers. The private
OAuth table is created automatically by the service in its restricted schema.

## Additional app registrations

Use the callback whose host matches the service where you are testing. The local
callbacks below work only while the service runs on this Mac. If a provider
requires HTTPS, use an approved shared HTTPS staging service, set its exact
`AEDROVA_ORIGIN`, register that callback and add the same service's Google auth
redirect in Supabase. Do not silently tunnel or enable production release gates.

| Provider | App registration and minimal access | Server fields | Local callback |
|---|---|---|---|
| Figma | https://www.figma.com/developers/apps — file_content:read only; private app for initial team testing, public apps require review | AEDROVA_FIGMA_BUD_CLIENT_ID / CLIENT_SECRET | http://127.0.0.1:8090/buds/oauth/figma/callback |
| Notion | https://www.notion.so/profile/integrations — public integration, Read content only; authorize only the intended page | AEDROVA_NOTION_BUD_CLIENT_ID / CLIENT_SECRET | http://127.0.0.1:8090/buds/oauth/notion/callback |
| Supabase | Organization Settings → OAuth Apps — Projects Read only; no secrets or database access | AEDROVA_SUPABASE_BUD_CLIENT_ID / CLIENT_SECRET | https://<approved-service>/buds/oauth/supabase/callback |
| Linear | Settings → API → OAuth applications — user actor, read scope only | AEDROVA_LINEAR_BUD_CLIENT_ID / CLIENT_SECRET | http://127.0.0.1:8090/buds/oauth/linear/callback |

The full variable names end in `_BUD_CLIENT_ID` and `_BUD_CLIENT_SECRET`; the
example file `deploy/dots.env.example` contains every exact key. Fill complete
pairs only. Figma files use file keys, Notion uses a page UUID, Supabase uses a
project ref, Linear uses a team UUID. API readers use fixed hosts and do not follow
redirects. Provider errors never expose returned token payloads.

Production callbacks use `https://<approved-service>/buds/oauth/<provider>/callback`.
Register those separately after the shared service is deployed and authorized.
Keep the legacy GitHub `/dots/github/callback` callback only if its older connection
flow is still used. Public app approval, least-privilege review and live acceptance
are required before offering these integrations to all customers.

## Primary implementation references

- GitHub App user tokens: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
- Figma OAuth: https://developers.figma.com/docs/rest-api/oauth-apps/
- Figma refresh endpoint update: https://developers.figma.com/docs/rest-api/changelog/
- Notion authorization: https://developers.notion.com/guides/get-started/authorization
- Supabase Management OAuth: https://supabase.com/docs/guides/integrations/build-a-supabase-oauth-integration
- Supabase scopes: https://supabase.com/docs/guides/integrations/build-a-supabase-oauth-integration/oauth-scopes
- Linear OAuth: https://linear.app/developers/oauth-2-0-authentication

## October 8 confirmation and role-gallery pass

All ten current read adapters remain implemented. New OAuth and legacy GitHub
callbacks share the Bud confirmation template, with provider-specific capability
copy. Scoped-token connections show the same Bud/checkmark hierarchy inline in
the native app. Success appears only after real verification. The gallery defaults
to the selected Bud’s specialty; All tools remains an explicit override.

Supabase OAuth registration is the next owner gate. The app’s existing Supabase
auth/database settings do not authorize a Bud to read a customer’s project.
Figma, Notion and Linear registrations and the remaining scoped provider tokens
still require owner setup and live acceptance. No new deployment or SQL is required
for this presentation change.

## Supabase HTTPS requirement — corrected October 8

Owner credentials are now present locally. Live authorization failed because
Supabase rejected the HTTP loopback callback. Supabase OAuth remains blocked
until an HTTPS service origin and matching registered callback are configured.
The service now reports that requirement and blocks invalid starts before
creating state. Do not change the callback alone: the service, native client,
Google sign-in redirect, and cookies must all use the same approved HTTPS origin.
Do not expose the local service through a tunnel silently. An isolated Render
connection service is the next setup task; aedrova.com stays waitlist-only.
Scoped-token verification remains available independently of OAuth.

The isolated HTTPS service is now deployed and readiness verified at
https://aedrova-connectors.onrender.com. Exact callback registration, authenticated
browser handoff and successful provider reads remain pending; see
docs/render-connectors.md. The native app has not yet switched its connector origin.

Resource help now appears beside every connector’s resource input. For Supabase:
open the intended project → Project Settings → General → Reference ID, or copy
the value after /project/ in its dashboard URL. This is a project reference,
not a database password, publishable key, or service-role key.
