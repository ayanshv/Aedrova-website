# M10 shared meeting staging


**October 3 owner deferral:** the owner actions below are scheduled for **M14**, the
latest hosted meeting activation milestone. Do not request paid service setup, secrets
or a second Mac during current development. Prepared files remain available; no paid
service is authorized by this deferral. Public meetings and transcription stay gated
pending M14 live/consent acceptance. M12 local implementation can continue separately.

October 3 update: the waitlist website is deployed on Render at aedrova.com using the
existing restricted Supabase schema. Shared meetings require separate always-on API and
worker services; the free website does not satisfy that gate. Follow `render-meetings.md`
and the separately imported `deploy/render-meetings.yaml`. Paid deployment approval,
server secret setup and a second Mac remain live acceptance blockers.
Transcription and meeting-to-agent retrieval are not implemented or enabled; M10 is not complete.
The owner authorized continuing all of M10. No repeated approval is needed to resume that scope
when the setup below is ready. Paid hosting/account commitments still belong to the owner.

## Owner steps when ready

1. Create/select a Python container host that supports **both an always-on HTTP service and
   an independent always-on worker**, plus a private PostgreSQL database. A free HTTP service
   that sleeps, request-only/serverless functions, or a local SQLite file cannot supervise live
   call revocation. Use its provided HTTPS URL; buying a custom domain is unnecessary.
2. Build this repository's `Dockerfile` once. HTTP command is `python -m scripts.serve`;
   worker command is `python -m scripts.meeting_guard`. Give each independent restart
   supervision and one instance initially. Start the HTTP service/database initialization
   before the worker. Container runs as UID 10001, access logs are off, and `.dockerignore`
   allows only application files, examples and pinned dependency files.
3. In **both services' secret/environment settings**, configure the names in
   `deploy/meetings.env.example`. Use the same private PostgreSQL URL and persistent Fernet
   encryption key for both. The DB login needs schema/table ownership in `aedrova_billing`.
   Keep this schema outside Supabase's exposed API schemas. The owner selected the existing
   restricted Supabase role; use its session pooler, shared encryption key and bounded pools.
   Transfer the existing LiveKit values from the local `.env.meetings` directly into the host's
   secret store. Keep credentials out of chat, GitHub, Docker build arguments and the Mac app.
   The existing private `.env.meeting-server` key can be retained for this staging service;
   do not regenerate it on every deploy. Back it up privately with the database.
4. Set `AEDROVA_ORIGIN` to the host's HTTPS address and `AEDROVA_PRODUCTION=true` in both.
   Set `AEDROVA_MEETINGS_ENABLED=true` **only in this acceptance stage**. Keep gateway,
   checkout, legal and release switches false. Production HTTP processes deliberately do not
   start an embedded access guard. Joins require the external guard's shared heartbeat.
5. Terminate TLS at the host proxy. Set `AEDROVA_TRUSTED_PROXY_IPS` on the API to the actual
   ingress proxy IPs/CIDRs if the host can supply trusted forwarded client addresses. Wildcard
   trust is rejected. Disable proxy/platform request logging for auth/gateway URLs; enforce
   8 MiB request bodies, bounded headers, public rate limits and appropriate timeouts. Prevent
   bypass of that proxy through a public container port. Worker needs no public endpoint.
   Keep clocks synchronized. Monitor both services and database backups separately.
6. API liveness is `/health`; call readiness is `/health/meetings` (503 until a healthy external
   monitor has swept, 200 when ready). A successful API liveness check alone is insufficient.
   Run `python -m scripts.check_meeting_setup --probe` in the server environment. This checks
   configuration and public HTTPS readiness without user tokens, joining, recording or charges.
   It does not prove physical calls, provider setup or production database race behavior.
7. For website sign-in on this staging address, add its exact `/auth/callback` HTTPS URL in
   **Supabase → Authentication → URL Configuration → Redirect URLs**. Desktop loopback and
   Google Cloud's Supabase callback remain unchanged. The existing meeting SQL is already
   applied; this task requires no additional Supabase SQL. Private server tables initialize
   automatically and are never exposed as public REST tables.
8. Share the public HTTPS service address (not credentials) so the internal Mac app can be
   rebuilt with `AEDROVA_MANAGED_ORIGIN=https://HOST_ADDRESS`, `AEDROVA_AI_ACCESS_MODE=local`
   and the stable Apple Development signing identity. Both Macs need a trusted signed build
   using that same origin. This is a development distribution, not the notarized public DMG.
   Never copy `.env.meetings` or server database keys to the second Mac.

## Two-Mac acceptance — owner participation required

Use two approved Google accounts joined to the same isolated test workspace and channel.
Approve camera, microphone and screen recording only for the checks explicitly started.
Each participant must confirm the following; do not count generated-media probes as hardware evidence:

- Receive the other person's voice and video in both directions. Confirm mute and camera
  state labels describe the current state and devices stop on leave/logout/window close.
- Test headphones, then ordinary speaker playback and speech for echo/feedback. Lower speaker
  volume if feedback occurs. ADM echo cancellation being configured does not prove this.
- Share each Mac's screen in turn, verify readability at the other Mac, then stop sharing;
  verify macOS capture stops and the recipient's shared tile disappears.
- Disconnect/reconnect each Mac's network during a call. Confirm the reconnect state, paused
  devices, no silent device reactivation, fresh authorized join if necessary and recoverable UI.
- Leave/rejoin, have the host end the call, and remove the second participant's access while
  connected. Confirm forced removal and refusal of new/cached credentials.
- Stop the API while the independently supervised guard keeps running; revoked/expired leases
  must still be removed. Restart the API, verify the encrypted leases survived. Stop the guard:
  after its 10-second readiness window, new joins must fail. Restart it and confirm recovery.
  A total LiveKit/network outage can delay forced removal; polling is not instant revocation.

Record the Mac models/OS versions, app build, network conditions and observed pass/fail results.
Actual PostgreSQL concurrent joins, restart/failure scenarios, HTTPS proxy/logging and physical
audio/reconnect remain acceptance gates. Do not enable public meetings based only on unit tests.

## Following tasks within M10

After the call gate: select a server-side speech provider and enable its project billing/key
privately. Implement separate per-participant transcription and AI-reuse grants, visible
capture state, bounded in-memory audio, revision/roster barriers and attributed transcripts.
Persist with channel ACLs, deletion/withdrawal/retention controls, then include eligible text
and reviewed decisions in agent retrieval with source citations. Screen/video understanding
is separate from audio transcription. No existing call is being recorded or sent to AI.

Build guidance: [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/).
Deployment startup guidance: [Docker dependency health checks](https://docs.docker.com/compose/how-tos/startup-order/).


## M12D speech and review (local implementation, M14 activation)

See the desktop repository `docs/milestone-12-speech-review.md` for owner steps,
privacy boundaries and verification. Apply both October 3 meeting migrations before
staging activation; the new speech functions grant execute only to the existing
restricted `aedrova_website` database role. Speech uses that direct private database
connection for authorization/reservation and user JWTs for transcript reads/review.
No service-role key is shipped. Keep the public waitlist flags false.

Configure `AEDROVA_SPEECH_ENABLED=true` and `AEDROVA_SPEECH_KEY` only on the meeting API,
after cost/provider/privacy approval and real-account acceptance at M14. This is an
OpenAI API key with approved speech access, independent of Codex/Claude subscriptions.
The guard does not need the speech key. The example file deliberately leaves it blank.
The server currently uses `whisper-1`, ten-second mono PCM chunks, one active request
per account, four per API process, and a durable one-hour combined workspace allowance
in a rolling 24-hour window. Failed reservations consume allowance; there are no
client retries or overage purchases. This is a staging bound, not an approved paid
plan entitlement or a claim about measured provider cost.
