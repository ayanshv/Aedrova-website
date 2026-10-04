# M13 website security audit — October 3, 2026

M13A follow-up: service-only storage cleanup is now implemented locally. See
`docs/storage-cleanup.md` and the desktop M13A report for the migration, quotas, tests and
deferred hosted-job setup. Current website/backend suite: 231 passing tests.

The shared audit report is in the desktop repository:
`/Users/ayanshvarma/Documents/Aedrova/docs/milestone-13-security-audit.md`.

Website changes remain local. Updated cryptography to 50.0.2 and regenerated the lockfile;
pip-audit reports no known vulnerabilities. Invalid request validation no longer echoes
private input. Model request traversal has explicit depth/item bounds. Speech responses
have bounded retention, a total processing deadline and shorter transport timeouts.

216 website/backend tests and Ruff pass. Private PostgreSQL schema/role and lease tests
pass in the embedded engine. Hosted race/load/paid-provider acceptance and Linux container
validation are not claimed. Live read-only readiness/page probes pass after warm-up with
security headers present and paid/managed AI gates disabled; initial 12-second cold-start
timeouts occurred. No waitlist record, live secret, SQL or hosted configuration was changed.

Publish the audited patch before public activation. Remaining storage aggregate quotas,
orphan cleanup, private-snapshot retention, ledger archival, representative load and
hosted acceptance are documented in `production-readiness-audit.md` and the shared report.
No new owner action is required for this local audit. Obtain permission for M13A release
hardening next; deferred owner activation tasks remain in M14. The owner moved the M13B
codebase walkthrough until after the entire application is complete and deployed.
