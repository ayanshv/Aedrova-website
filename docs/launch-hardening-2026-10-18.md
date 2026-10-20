# Launch hardening — October 18, 2026

Owner requests API caching, optimistic UI, icon tooltips, all-endpoint limits,
credential scanning/private configuration and malformed/oversized-input rejection.
These are Mac launch acceptance requirements, not a new product pivot.

## Implemented server boundary

All HTTP routes, static assets, unknown routes and dedicated connector-service
early responses pass the ingress limiter before consuming a request body.
Product limits use the existing shared database, retaining narrower authenticated,
per-feature, concurrency and spending limits. Raw forwarded headers do not select
the limiter key. Production ASGI proxy trust must match the real ingress; do not
trust arbitrary client-supplied X-Forwarded-For. High-volume/DDoS protection still
requires ingress/network controls, not only application/database writes.

Initial limits (not universal optimum; tune from traffic/429 and shared-NAT data):

- Google login and Bud OAuth starts: 10 per 5 minutes per IP.
- OAuth callbacks: 30 per 5 minutes per IP, separately bucketed.
- General reads/unknown GET routes: 600 per minute per IP.
- General mutations/unknown write routes: 180 per minute per IP.
- Static assets: 1,200 per minute per IP.
- Stripe webhooks: 600 per minute per IP; signatures/idempotency remain mandatory.
- Readiness/meeting health: 120 per minute per IP.
- `/health` liveness: 1,200 per minute **per process**, bounded local counter so
  a database outage does not masquerade as a dead process.

429 responses include Retry-After and no-store. Limits use fixed windows, so bursts
across window boundaries remain possible. This does not replace provider/Supabase
Auth, PostgREST, Storage or external-service limits. Hosted Supabase Auth settings
and actual trusted-proxy behavior remain release acceptance checks. Google handles
Google account authentication; Aedrova does not collect Google passwords.

Ingress now bounds path, query length, header count and total header bytes.
Existing actual streamed-byte/time limits apply to all mutating methods, including
DELETE. JSON parsing rejects malformed encoding, non-finite numbers, excessive
nesting/item counts and disallowed control characters without echoing input.
Raw body bytes remain unchanged for webhook signature verification. Main API DTOs
reject unknown fields and have bounded default strings in addition to explicit
field limits. Other connector/gateway/provider-specific validators remain in force.
Do not strip HTML/code blindly: validate structure, parameterize SQL and escape at
rendering boundaries so legitimate chat/code remains intact.

## Credentials

Current tracked-file scans passed in both repositories. Historical source scans:
1,029 desktop and 2,925 website objects. The single historical AWS-shaped match
was confirmed inside base64-decoded WebAssembly in a vendored Prettier parser;
not an AWS credential. First-party sensitive-name string-assignment review found
no nonempty literals. These checks cover recognizable patterns and simple literals,
not every possible encoded/custom secret or an independent security audit.

No live secret was found to migrate or rotate in this pass. Shared server credentials
remain private environment/secret configuration. Per-user OAuth grants belong in
the existing encrypted server store; local user credentials in OS Keychain. Do not
move all users' tokens into a shared environment variable or put secrets into the
desktop binary/frontend. Public Supabase publishable keys are intentionally public
and rely on RLS; service-role credentials must never enter client configuration.

## Desktop behavior

30-second in-memory connector catalog cache, max two allowlisted routes. Scoped
to origin/user/token fingerprint; cleared on mutation, token/user/origin change and
sign-out. Defensive copies; failures not cached. No message, grant, OAuth status,
resource content or execution permission response cached by this addition.

Existing optimistic chat/Bud sends, stable request IDs, failed-send retry/draft
recovery and access-change cache invalidation retained. Billing, grant confirmation
and execution approval must not show success before server acknowledgement.
Shared icon-assignment/factory helpers now provide action tooltips while preserving
explicit help text. This is not proof that every transient/custom icon has been
manually inspected; include those screens in final native acceptance.

Local tests and source changes are not hosted staging acceptance. Deploy the tested
backend, exercise real 429/callback/recovery and proxy behavior, rebuild the DMG from
the updated desktop commit, and rerun package acceptance before public launch.
