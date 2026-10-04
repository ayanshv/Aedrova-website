# M12B — shared Render meeting staging


**October 3 owner deferral:** the owner actions below are scheduled for **M14**, the
latest hosted meeting activation milestone. Do not request paid service setup, secrets
or a second Mac during current development. Prepared files remain available; no paid
service is authorized by this deferral. Public meetings and transcription stay gated
pending M14 live/consent acceptance. M12 local implementation can continue separately.

Prepared October 3, 2026. The owner approved the next shared meeting deployment task.
The waitlist website is live at aedrova.com. This task does not enable meetings on the
public website, transcription, checkout, managed AI or app downloads.

## Prepared

`deploy/render-meetings.yaml` defines a separate Docker API and independent guard worker.
Both use Render's smallest paid always-on compute plan, one instance each. They use the
existing private Supabase schema and session pooler; no new database is purchased.
The live website's root `render.yaml` is unchanged. Importing that root file again does
not create meeting services. Import the separate path only after cost approval.

The API exposes database readiness at /health/ready. Call readiness at /health/meetings
requires a fresh independent guard heartbeat. This distinction avoids a startup cycle:
the API can initialize its tables before the worker starts; joins remain blocked until
the guard is healthy. Each meeting process has pool size 1, no overflow; the website's
maximum 3 plus these 2 is at most 5 per steady-state deployment. Rolling deploy overlap
can temporarily exceed that role budget and fail connections; acceptance must check this.
The guard now honors those limits and sanitizes fatal startup errors.

## Owner actions deferred to M14 before live acceptance

1. Approve the two always-on Render services. Published base compute is currently $7/month
   each, about $14/month total, excluding bandwidth, taxes and LiveKit/Supabase usage.
   Review the actual Render price summary before submitting. No paid resource is created
   by committing this file. Do not upgrade the free waitlist website for this task.
2. Render → Environment Groups → New environment group, name `aedrova-meeting-staging`.
   Personally enter these shared values, never in chat or GitHub:
   - AEDROVA_ORIGIN=https://aedrova-meetings.onrender.com
   - AEDROVA_DATABASE: same restricted Supabase session-pooler URL used by the website.
   - AEDROVA_ENCRYPTION_KEY: same existing website Fernet key (do not regenerate).
   - AEDROVA_LIVEKIT_URL, AEDROVA_LIVEKIT_API_KEY, AEDROVA_LIVEKIT_API_SECRET: transfer from
     `/Users/ayanshvarma/Documents/Aedrova/.env.meetings` into Render's secret fields.
   Existing shared tables require the same encryption key. Never export server keys into
   the desktop app. The group must contain these values before Blueprint import.
3. Render → New → Blueprint → `ayanshv/Aedrova-website`, main; Blueprint name
   `aedrova-meeting-staging`, Blueprint Path `deploy/render-meetings.yaml`.
   Review API + worker only and their charges. Personally submit the paid deployment.
   If Render assigns a different API hostname, change AEDROVA_ORIGIN in the shared group
   to that exact HTTPS origin and redeploy both. No Cloudflare DNS is required.
4. Wait for both services to start. Do not assume a worker's "Live" status means successful
   revocation. The agent must check /health/meetings and scoped joins/guard failure/recovery.
   The shared SQL already applied supplies ordinary meeting tables. Keep meeting-context
   disabled. M14 text-context activation additionally requires desktop migration
   `supabase/migrations/202610030001_meeting_context.sql`, retention maintenance and
   consent/isolation acceptance. No new SQL or owner action is required now.
5. Send only the public API hostname and whether both services started. The agent can then
   run HTTPS preflight and update the internal Mac build's meeting origin. Google Cloud's
   Supabase callback and desktop loopback redirects remain unchanged. Website sign-in on
   this separate origin is not needed for desktop meetings; add its auth callback to Supabase
   only if separately testing that browser login route.

The current restricted login has CONNECTION LIMIT 5. Do not arbitrarily raise it during
setup. Guard startup or overlapping deploy failures may require a measured budget change
or draining a previous deployment. It must never cause joins with an unhealthy guard.
For actual proxy CIDRs, ingress/request-body bounds, platform log controls and two-Mac
hardware checks, follow `meeting-hosting.md`. Don't set wildcard proxy trust.

## Acceptance and next gate

Local tests can prove bounded worker construction, cleanup, redaction, schema permissions,
lease behavior and fail-closed guard health. They do not prove live Render supervision,
Supabase pooled concurrency, physical media or recovery. Record those after deployment.
A second Mac is still required for final real two-device audio/screen/network acceptance.
No silent recording or transcription is enabled. Ask owner permission before beginning
transcription/meeting-to-agent context as the next task.

References: https://render.com/pricing and https://render.com/docs/blueprint-spec

Local verification: 190 website/backend tests passed; Ruff, Python compilation and
whitespace checks passed. Both Blueprints validate against Render's official JSON schema.
Embedded PostgreSQL role-isolation, private ledger and atomic lease checks passed. These
checks do not replace dashboard Blueprint import or live service/hardware acceptance.
