# Stage 3 security and recovery

Owner authorized this stage on November 4, 2026. Scope is the current desktop working tree and website/backend, application authorization, request and spending bounds, credential patterns, dependency advisories and isolated recovery. No payment, customer-data restore, provider inference or production database write is authorized by this report.

## Findings and fixes

- Critical dependency advisory GHSA-6q48-6c7w-9gw2: the pinned certifi 2026.7.22 trust store included a compromised CA chain. Updated both locks to 2026.10.23 and added a minimum safe-version constraint. This addresses the upstream trust-store advisory; it does not establish that interception occurred.
- Moderate dependency advisory GHSA-xcq7-p3pf-p88h: OpenTelemetry 1.45.0 had unbounded tracestate parsing. Updated both locks to 1.45.2 and constrained future resolutions to patched versions. Exposure depends on instrumentation and ingress limits; no exploit was sent to the hosted service.
- Recovery coverage gap: existing recovery acceptance exercised a disposable SQLite ledger, not restored PostgreSQL access rules. Added a repeatable native-repository `scripts/check_postgres_recovery.py` drill. The actual hosted backup and Storage recovery gates remain open.
- Six desktop regressions were stale fixtures for priority Bud requests, forked meeting credentials and source-channel provenance. Updated fixtures without weakening session-identity checks or removing provenance. The affected security/UI selection passed 118 tests.

## Verified boundaries

The actual route graph has 106 routes with an assigned boundary category. Anonymous-schema-valid endpoint regression checks, OAuth state/PKCE, browser proof, CSRF, owner/member billing access, malformed/oversized input, SQL-value binding, webhook signatures and scoped gateway tokens pass in the backend suite. Route classification is an inventory, not proof of authorization by itself.

Login starts are bounded to 10 per five minutes per trusted ingress address, OAuth callbacks to 30 per five minutes; generic writes to 180/minute and reads to 600/minute. Additional account, operation, database write, provider-admission and monetary reservations apply. Liveness is independently bounded without relying on the database. Forwarded addresses are not trusted unless the configured proxy allowlist permits them; actual deployment ingress topology still requires acceptance.

Spending checks cover parallel reservations, owner-wide Free pools, company and workspace budgets, failed/uncertain responses, one pending inference per run, replay and subscription lifecycle. Provider tests here use fixtures and do not spend money. Existing SQLite recovery verifies unchanged money, pending reservations, event/replay idempotency, encrypted sessions and wrong-key denial.

The desktop's full PostgreSQL migration/RLS runner and backend private-schema/role isolation runner passed locally. These include foreign workspace, private channel, Bud conversation, verified file and shared-work access restrictions. They use embedded PostgreSQL and do not certify hosted multi-worker races.

Actual installed Codex and Claude runtimes passed synthetic project-write/outside-read/write denial and subprocess credential-scrubbing checks. Neither reached the network canary; the Claude network command was denied without stalling. These results apply to this Mac and its installed runtimes, not packaged Windows binaries or every future runtime version.

Read-only HTTP checks on production and staging returned readiness 200, private workspace/balance 403 and unknown route 404, with CSP, frame denial, nosniff, no-store and HSTS. No customer session or mutation was used. This is anonymous boundary acceptance, not a new two-user hosted penetration test.

## Credential and dependency scans

Pattern scans covered 512 desktop working files and 1,697 reachable historical blobs; no matches. Website scan covered 919 working files and 5,351 reachable blobs; no current-source matches. Two historical AWS-shaped matches were in encoded Prettier parser tables. Both files were byte-identical to the official prettier 3.9.9 npm archive, whose integrity digest was verified. They are classified as vendor-data false positives. No history rewrite or credential rotation was performed.

Both patched runtime dependency exports passed pip-audit with no known vulnerabilities. This is advisory coverage at scan time, not a guarantee that unknown vulnerabilities or arbitrary/encoded passwords are absent.

## PostgreSQL restoration evidence

The drill installs 31 current migrations into a synthetic database, commits a real channel message, fingerprints roles, row policies, grants and saved content, writes a compressed backup, makes a later database change, closes the original instance, and restores from that archive into a fresh instance. The original fingerprint matched and the later write was absent. Owner access succeeded; outside-account reads returned no data. Five restored suites passed: verified uploads, voice messages, Bud conversations, Bud limits and shared agent work.

The archive contains synthetic data only, is written with private file permissions and is removed with the temporary directory. The report retains its SHA-256, byte count and assertions. PGlite's data-directory backup is intentionally for the same embedded engine. It is not a portable pg_dump archive, a Supabase backup or a Storage-object backup.

Evidence is kept locally under `work/stage3-security-nov4/` in each repository. Initial backend suite: 697 passed; patched backend suite: 697 passed. Initial desktop suite: 1,155 passed and six fixture failures, subsequently corrected; final full-run results are recorded below when complete. Ruff passed after corrections.

## Hosted blockers and owner actions

Stage 3 remains OPEN. Direct dashboard inspection found that both Supabase projects are Free and do not include project backups. The organization also displays an over-quota warning with possible project restrictions beginning November 24, 2026. No upgrade was selected or purchased.

Before release, the owner must resolve the quota warning in Supabase organization Usage/Billing, and approve a production database plus Storage backup arrangement. A paid managed backup plan is one option; a properly scheduled, encrypted external backup with separate key custody is another. The existing restricted backend credential cannot be assumed to export every application/Auth schema or Storage object. Do not paste administrator passwords or keys into chat.

After backup coverage is configured, restore a real backup to a new isolated target, never over either active project. Include application/Auth/private-ledger schema and data, matching Storage bytes and separately held encryption keys. Reapply deletion/withdrawal records, verify role access, hashes, money/replay/pending states and rollback, then record actual recovery time/data loss. Keep AI, billing, meetings and cleanup disabled during restoration. Existing runbook: `docs/prelaunch-operations.md`.

An independently performed human security assessment and hosted multi-worker/ingress acceptance have not been certified by this agent's source review. No public launch is approved by this report. Deferred paid Claude, production meeting guard and real two-device acceptance remain final launch gates. Stage 4 has not been started.

References: [certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2), [OpenTelemetry advisory](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-xcq7-p3pf-p88h), [PGlite backup API](https://pglite.dev/docs/api), [Supabase backups](https://supabase.com/docs/guides/platform/backups).
