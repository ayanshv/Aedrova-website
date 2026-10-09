# Dedicated HTTPS Bud connector staging — October 8, 2026

Owner authorized a separate Render HTTPS service and all current connector setup.
The existing aedrova.com service, main branch and root render.yaml remain unchanged.
The isolated deployment uses codex/bud-connectors-https and the connector-only
entry point. No checkout, model gateway, meetings, transcription or downloads.
A separate public connector_origin preserves the local AI/meeting managed_origin.

## Concrete deployment configuration

- Service: aedrova-connectors; Docker; Oregon; Free ($0 base compute).
- Branch: codex/bud-connectors-https; automatic deploys Off.
- Command: python -m scripts.serve_connectors.
- Readiness: /health/ready. Root describes the Bud service rather than duplicating
  the website. Only authenticated Bud APIs, OAuth, static assets and health routes
  are exposed. All unrelated routes return 404.
- Restricted existing Supabase session-pooler URL, one connection, no overflow.
  Reuse the existing website database URL and encryption key; never use service_role
  or regenerate the key for shared encrypted data. No additional database purchase.
- Only configured Bud OAuth credentials are transferred into Render’s secret fields.
  Do not copy OpenAI, LiveKit or Stripe server credentials to this service.
- Exact AEDROVA_ORIGIN is the actual hostname assigned by Render, without a path.
  Do not assume a requested service name guarantees the URL.

## Provider and authentication acceptance gates

The assigned HTTPS origin must be allowed in Supabase Auth Redirect URLs with
/auth/callback. Supabase Management OAuth’s registered redirect must be the same
origin with /buds/oauth/supabase/callback. Google’s existing Supabase callback is
unchanged. GitHub’s private App may retain its localhost callback and additionally
register the HTTPS /buds/oauth/github/callback for this service.

The free instance can sleep and consume the workspace’s shared free-hours quota.
This is development staging; always-on production hosting remains deferred to M14.
No paid upgrade is authorized here. Check account quota before creating the service.

Do not switch the desktop connector_origin until HTTPS readiness, disabled product
routes, authenticated identity and provider callbacks are verified. Existing local
SQLite grants are not automatically migrated to the shared PostgreSQL grant store;
reauthorize each Bud on HTTPS. Live provider reads are required before claiming
connection. No provider credentials belong in Git or the packaged app.

## Current status

Deployed after the owner's explicit credential-transfer and deployment approval:
https://aedrova-connectors.onrender.com (Render service srv-db43abnlk1mc73elnki0,
commit 5c93b32). Live HTTPS checks returned root/readiness 200, unauthenticated
connector catalog 403, plans/meetings 404, and an unsolicited OAuth callback 403.
The service uses the approved restricted database/encryption key and the configured
GitHub/Supabase OAuth pairs. No unrelated provider secrets were transferred.

All three callback changes were approved, saved and verified: Supabase Auth
/auth/callback, Supabase Management /buds/oauth/supabase/callback, and GitHub
/buds/oauth/github/callback, all on the origin above. GitHub retains its local
callback. Permissions remain unchanged (Supabase Projects Read only).
The signed desktop preview now bundles this HTTPS connector_origin separately
from the local AI/meeting origin. Deep signature verification and 48 focused
desktop tests pass. Native Google sign-in and hosted /api/dots/providers and
/api/dots reads passed (HTTP 200); the role-filtered gallery loaded. Supabase
OAuth completed with the owner-approved Aedrova / Projects Read grant and the
correct HTTPS callback. Pebble passed a real project health/region read and the
native app displayed Connection verified. No rows, SQL or keys are authorized.
Bud requests now allow 90 seconds for free-host wake-up in the background worker
and use a connector-specific network error. Reauthorize each Bud on HTTPS;
private SQLite grants are not automatically migrated.

Figma app Aedrova Buds was created under Ayansh Varma's team with explicit
Developer Terms approval. Its credentials are saved only in ignored local
.env.dots (0600). The actual Aedrova logo and read-only description are saved.
The owner approved activation: HTTPS callback saved, file_content:read enabled,
and app published privately to Ayansh Varma’s team. The credential pair was
transferred only to aedrova-connectors on Render. Save and deploy succeeded
(dep-db474nbtqb8s73eakdrg, existing code 5c93b32); HTTPS readiness returned 200.
Pebble completed hosted OAuth and passed a real read of the existing Figma basics
file; both browser and native app displayed verified read-only connection.
No file was edited. Private publication is not public customer approval. Notion requires sign-in. Linear Google sign-in succeeded;
this account has no workspace and is at Create a workspace. Figma/Notion/
Linear registrations and the five scoped-token providers still require account
authorization and real least-privilege reads. This deployment is not acceptance
of all ten integrations. No paid upgrade was selected.
