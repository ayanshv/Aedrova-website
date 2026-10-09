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

Prepared implementation and deployment form; secret transfer and final deployment
are pending. Subsequent setup covers Figma, Notion, Linear and the five scoped-token
providers, with their own real account authorization and least-privilege validation.
