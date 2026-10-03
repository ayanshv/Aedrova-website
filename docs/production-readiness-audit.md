# Aedrova production-readiness audit — October 2, 2026

## Audit before source changes

Scope: both Python repositories; Qt desktop/virtualized chat, FastAPI website/API,
Supabase Auth/PostgREST/PostgreSQL RLS/storage/private realtime, Stripe ledger/gateway,
Codex CLI/Claude SDK local execution, LiveKit RTC/native capture/lease guard, container,
release/update scripts, tests and owner deployment documentation. This is source/fixture
analysis, not deployed penetration testing or a capacity certification. Existing M9/M10/M11
release gates remain open. No confirmed catastrophic P0 data leak was found in the reviewed
paths; that is not proof that none exists.

Flows traced:
- Google PKCE -> Supabase JWT -> RLS workspace inventory -> keyset chat RPC -> targeted
  content-free user wakeup -> desktop worker refresh/optimistic idempotent send.
- Explicit agent mention -> local queue/file lock -> fresh membership/channel revision
  checks -> local evidence/snapshot -> sandboxed provider -> server run token (included
  mode) -> atomic allowance reservation -> bounded stream/accounting -> review/apply.
- Selected file -> 10 MiB client bound -> reserved immutable object path -> private storage
  RLS -> size/hash verification -> published attachment -> supported small-text context.
- Explicit meeting join -> channel-authorized RPC -> encrypted durable lease -> scoped
  short-lived LiveKit token -> native opt-in capture/latest-frame mailbox -> heartbeats ->
  independent guard rechecks/removal. Transcription/meeting AI context are not accepted yet.

## Findings and impact/risk order

1. P1 Async gateway and meeting-leave handlers perform synchronous SQL/auth calls on the
   event loop. DB lock waits can stall unrelated connections. Offload complete synchronous
   operations; retain transaction boundaries. Low implementation risk.
2. P1 One active build per workspace does not constrain concurrent inference calls within
   that build or across all workspaces. Add a durable one-pending-request-per-run check and
   bounded per-process provider admission; reject overload before provider spend. Medium risk.
3. P1 Streaming read timeouts reset on each chunk; a trickling stream can run indefinitely.
   Add a total provider deadline, preserve uncertain-charge/no-replay accounting and cleanup.
4. P1 Meeting guard reads every live lease and creates a task per lease every three seconds.
   Bound batches/fan-out and ensure health reflects completion of the entire scan. Keep outage
   revocations durable and fail closed; do not delay revocations silently. Medium risk.
5. P1 Full-context gathering keyset-pages all workspace messages per build (8 MiB/180 s
   cap). Use bounded recent/thread evidence plus permission-scoped indexed query retrieval;
   clearly mark non-exhaustive context and keep fresh membership/revision validation.
6. P1 Direct Supabase RPCs bypass website rate limits. Add database-side per-user write
   budgets for messages/uploads/workspace/channel/invitation creation; retain RLS and retries.
7. P1 Billing active-run counts and expired limiter lookup scan tables. Before measurement:
   100,000 fixture rows/table, 40 warmed SQLite reads: active-run median 2.446 ms/p95 2.570;
   expired-key median 1.059 ms/p95 1.126. Add only query-aligned indexes; PostgreSQL acceptance
   remains required. Other expired/session/checkout/inference queries need aligned indexes.
8. P1 Production DB pool lacks explicit bounds/pre-ping/statement and lock deadlines.
   Configure bounded connections and recoverable service-unavailable responses.
9. P1 No sanitized request IDs/latency/error/SQL/provider/admission visibility. Add structured
   metadata only; never log query strings, raw paths with IDs, tokens, SQL parameters,
   payloads, chat bodies, provider output or exception messages.
10. P2 HTTP identity operations recreate connections. Reuse a bounded client and close it
    and the engine at server shutdown; do not cache authorization across revocations.
11. P2 Static CSS/JS hashing runs on every page. Compute once per app instance.
12. P2 Rate-limit cleanup scans/deletes on every request. Use indexed expiry and maintenance;
    preserve shared SQL enforcement and expose real 429/Retry-After without breaking errors.
13. P1 Remaining: dashboard polls eight inventory calls and exact unread counts every 3 s,
    even with realtime healthy. Metadata/RPC row ceilings, unread history scans, full model
    resets and unbounded user-driven local history cache need hosted workload profiling and
    a separately tested incremental inventory contract. Avoid caching stale permissions.
14. P1 Remaining: broadcasts fan out to each authorized workspace member per message.
    Private channels/DM filtering is correct, but large-workspace fan-out requires measured
    Supabase plan quotas and targeted/coalesced notification design before large launch.
15. P1 Remaining: message writes serialize on workspace row to preserve committed cursor
    order and authorization. Do not remove that lock without replacing cursor/permission
    correctness. Highly active single-workspace throughput must be measured.
16. P1 Remaining: storage has per-file bounds and pending-upload limits, but no team storage
    quota or orphan-object cleanup worker. Cannot claim unlimited simultaneous uploads.
17. P1 Remaining: no deployed multi-worker PostgreSQL/billing race/load or real paid-provider
    acceptance; local fixtures cannot prove external quotas, economics or failure timing.
18. P1 Remaining: health endpoint reports process/config only, not DB readiness. Add separate
    bounded database readiness; keep liveness independent to avoid outage restart cascades.
19. P2 Remaining: encrypted replay content can be 16 MiB/request, retained 24 h; run/event
    ledger grows deliberately. Schedule indexed expiry, monitor sizes, plan safe archival.
20. P1 Remaining: reverse-proxy public rate/slow-body/header bounds, trusted forwarded-IP
    configuration, static/video/DMG CDN delivery, backups/PITR, supervised maintenance/guard,
    host redundancy and alert routing require actual infrastructure/owner setup.
21. P2 Remaining: local snapshots/review may hold two 200 MiB project inventories; bounded
    but potentially heavy on small Macs. Measure representative repos before optimizing.
22. P2 Remaining: realtime retry has deterministic backoff; add jitter and verify close/
    credential changes. SDK auto-reconnect plus manual loop must remain bounded.
23. P1 Remaining: chat/context privacy relies on database policies and local files; model
    prompts treat evidence as untrusted, but prompts alone do not prove injection resistance.
    Keep sandbox/tool restrictions, secrets exclusion and M13 adversarial acceptance.

Already sound: workspace RLS and object access; parameterized SQL; private billing schema;
PKCE/CSRF/secure cookies; immutable idempotent message IDs; bounded keyset history; one active
workspace run, billing row locks, idempotent settlement/webhooks, hard allowances; server-only
provider secrets; fail-closed media guard; bounded RTC frame/stream buffers; safe local review/
backup checks. No Redis/microservice rewrite is justified by the available evidence.

## Implementation sequence

A. Event-loop isolation, pooled identity client/shutdown, DB bounds/indexes and cached asset hash.
B. AI admission/deadline/durable pending limits; bounded meeting sweep; typed overload handling.
C. Supabase indexed bounded context and direct-write limits; realtime retry jitter.
D. Sanitized observability/readiness; regression/concurrency/load measurements; second audit.
E. Owner applies prepared SQL; hosted PostgreSQL/provider/RTC stress and release acceptance
   before marketing large-scale capacity. Do not deploy, publish or enable gates during this task.

This document is the pre-change baseline. Post-change evidence and remaining risks are appended
only after implementation/testing. No user-count claim is authorized by these microbenchmarks.

## Post-change / second audit

Implemented: event-loop SQL isolation; pooled Supabase HTTP client/shutdown; bounded DB
pool/pre-ping/recycling and PostgreSQL statement/lock deadlines; serialized private DDL;
query-aligned private indexes; per-worker AI admission (8 default, not cluster-wide), one
pending inference/run and two active runs/account; total 240-second provider deadline;
conservative cancellation/malformed-response settlement; 429/Retry-After; bounded lease
paging/fan-out with compare-and-set protection against stale heartbeat revocation; indexed
permission-scoped context with bounded recent/matched-thread evidence and coverage labels;
Supabase direct write/search budgets; realtime retry jitter; 64 KiB forms/1 MiB webhooks/
8 MiB gateway bodies with 30-second receive deadline; cached asset hash; content-free JSON
request IDs/status/latency, slow SQL, provider completion/interruption and overload events;
independent DB readiness and HTTP process admission/drain limits.

The second pass found/fixed: stale lease revocation, idempotent send rejection at the write
cap, duplicate buffered-body retention, missing form/slow-body limits, hardcoded installed
update version, and malformed provider event shapes. Review confirmed admission releases
on cancellation, monetary transactions retain their lock/idempotency boundaries, private
channels/foreign workspaces remain excluded and no new UI/redesign was introduced.

Evidence:
- Desktop suite: 408 tests passed; website/backend: 154 tests passed.
- Supabase migrations/RLS/RPC suite including new search/private-channel/rate/idempotence
  regression SQL passes in embedded PostgreSQL; private billing/meeting DDL passes there.
  This is not networked PostgreSQL race or Supabase production acceptance.
- Basic mypy checks (ignore missing external stubs; untyped bodies not fully checked) pass
  across 58 desktop and 14 website source files. Scoped Ruff/compile/whitespace checks pass.
- 32 simultaneous fixture reservation attempts with 8 threads admit one pending inference;
  guard fixture scans 205 leases in 100-row batches with at most 10 checks in flight;
  admission fixture rejects 30 excess requests rather than queueing them, including cleanup
  after cancellation. Provider deadline/stream close/malformed events are tested without spend.
- Local TCP burst: 400 requests to /plans and /health/ready, 40 maximum client concurrency,
  all 200; 1.280 seconds total, median 86.599 ms, p95 307.809 ms. SQLite, no Auth/chat/RTC/
  paid-provider traffic; these figures do not imply 40 supported production users.
- The same 100,000-row/table SQLite microbenchmark after indexes: run count median 0.014 ms,
  p95 0.020; expired-key lookup median 0.011 ms, p95 0.013. Query plans now use covering/
  expiry indexes. Before/after fixture JSON is in work/scale-audit.
- Desktop packaged successfully; development signature, regenerated preview DMG and both
  theme launch smokes pass. Installer remains public_release=false. Docker is unavailable
  on this Mac: website Python source compiles, but no container-image build is claimed.

Remaining production risks: findings 13–17,19–21,23 remain open; 18/22 are improved. Dashboard
metadata/unread polling, realtime member fan-out and workspace write serialization still
require representative hosted load tests. Storage quotas/orphan cleanup and safe ledger
archival remain separate work. Selected context is intentionally non-exhaustive; it does
not give the local agent an on-demand arbitrary historical-search tool. Provider admission
is per worker; choose worker count and account/provider budgets together. Readiness tests
only the DB; Supabase/Stripe/provider/LiveKit health and commercial acceptance remain external
release checks. Do not call the whole product large-scale production-ready on this evidence.

## Owner setup and deployment recommendation

Required before using the rebuilt app's indexed context: in Supabase → SQL Editor, run the
DESKTOP repository's `supabase/migrations/202610020001_scalability.sql` once, after existing
migrations. It creates indexed scoped search, write budgets and supporting indexes. Never
run files under `supabase/tests` in Supabase. This pending action blocks hosted context/rate
acceptance, not the local fixture results. With a large existing table, stage/test the
migration and use a maintenance window or separately staged concurrent index builds; the
included transactional beta migration is not a zero-lock production index rollout.

For hosted acceptance, start with a supervised Python API instance, private PostgreSQL
with backups/PITR, dedicated independent meeting guard and scheduled maintenance. A host
HTTPS URL is sufficient; purchased domain remains optional. Use `.env.example` defaults
for 5+5 DB connections/worker, 5-second checkout wait, 8 gateway calls/worker and 240-second
provider lifetime; these are starting bounds, not measured sizing recommendations. Account
for every worker/guard/maintenance connection against the database budget. Use a direct or
session-mode PostgreSQL connection; current connection initialization uses session settings,
so transaction-mode PgBouncer/Supavisor needs a separately verified configuration.

Run `python -m scripts.serve` with TLS termination at a trusted proxy. It bounds admission
at 128 HTTP connections/tasks, backlog 256, keepalive 5 s and graceful drain 270 s. Configure
proxy request/header/IP limits, body receive limits, SSE buffering off and timeout above
270 s; trust only actual proxy IPs. Put static/video/DMG assets behind appropriate caching/CDN
when hosted. Serve versioned immutable DMGs; never overwrite an active download in place.

Schedule `python -m aedrova_site.maintenance` hourly with the same DB/persistent encryption
key. In Supabase schedule this private cleanup daily via your authorized maintenance system:
`delete from aedrova_private.write_budgets where window_start < extract(epoch from now())::bigint-86400;`
It removes old limiter windows, not chats. Leave usage/financial records intact. Ship JSON
logs to the host's private log/metric collector; alert on 503/429/AI interruption, p95 latency,
slow SQL, guard heartbeat absence, DB connection/storage growth and maintenance failures.
No monitoring vendor, cloud account, external database or secret was created/changed here.

Before public launch: measure representative workspace sizes, sender bursts, unread history,
real upload/RTC/provider workloads, PostgreSQL multi-worker reservations and failure/draining
scenarios against approved budgets. Complete Developer ID/notarization/fresh-Mac and deferred
meeting/commercial AI release gates. No specific supported user count is established.

References: [SQLAlchemy pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html),
[PostgreSQL full-text indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html).
