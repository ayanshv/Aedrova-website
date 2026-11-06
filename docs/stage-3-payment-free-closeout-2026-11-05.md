# Stage 3 payment-free closeout

Completed November 5, 2026. No purchase, paid provider call, production data restore
or new public feature was enabled. The payment-free code, independent agent review,
current-instance hosted checks and backup-tool preparation are complete. Production
backup activation, full hosted restore and final paid-capacity acceptance remain
explicit launch gates, not certified results.

## Independent review and fixed finding

A separate read-only security agent reviewed current native changes and backend
boundaries. It found one medium-severity race: save_shared_agent_work checked
membership/source permission before waiting on a per-record lock, allowing an
in-flight write to finish after membership or source access was revoked.

Additive migration 202611050001_shared_work_revocation_lock.sql now locks the
workspace row before permission checks, matching remove_member/set_channel_member.
A real two-connection PostgreSQL regression reproduced the old late insert and
proved that the fix rejects both workspace-membership and private-source revocation
races with SQLSTATE 42501 and zero late rows. Full embedded migration/RLS checks
passed. The fix was applied only to Aedrova Staging and verified from the hosted
function definition. Production receives reviewed migrations at the final rollout.

The independent follow-up found no additional substantiated issue in the fix,
concurrency harness or encrypted backup additions. This is a separate agent source
review, not a professional third-party human penetration-test certificate.

## Hosted limits and concurrency

On existing staging, ten login-start requests were accepted and attempt eleven was
429 with Retry-After. Varying forged X-Forwarded-For/Forwarded headers did not bypass
the rejection. Twelve readiness requests at maximum four in flight all returned 200.
This is a bounded current-instance smoke check, not a large-scale capacity claim.

Two independent engine pools against staging PostgreSQL made sixteen simultaneous
attempts against a dedicated synthetic limiter key with a limit of five. Exactly
five were admitted and eleven were rate-limited. No billing or account counters were
reset. The one synthetic limiter window expires normally; no customer record changed.

Arbitrary forwarding headers remain untrusted. The current conservative socket-peer
scope may group visitors behind a proxy; these tests do not certify visitor-IP
fairness or a multi-replica rollout. Confirm Render's trusted proxy topology before
production scale-up and do not enable wildcard proxy trust. Deployment topology and
paid capacity acceptance stay with the final hosting/production-operations gates.

## Quota review

The Supabase warning concerns the previous billing cycle's egress. The current
October 27 to November 27 period shows 0.914/5 GB egress (18%), 37.71 MB maximum
project database size, and about 0.002/1 GB Storage usage. No current egress overage
is displayed. No deletion, upgrade or billing change is needed to perform this
review. The historical grace-period warning still names November 24; monitor usage
and service status instead of claiming the provider warning was dismissed.

## Backup preparation and restore checks

The website repository's aedrova_site.backup_bundle implements streaming AES-256-GCM
bundles with private keys/files, an authenticated header, bounded regular-file
archives and a SHA-256 manifest. Restoration authenticates before publishing files,
rejects traversal/symlinks/tampering/duplicate or mismatched content, and refuses an
existing destination. Input snapshots and filesystem parents must be trusted private
operator paths. No SQL is run or external upload performed by unpacking a bundle.

Twelve encrypted-bundle/recovery tests passed. A consistent synthetic ledger snapshot
and Storage bytes survived encryption/restoration, including money, encrypted
sessions and replay settlement. Full backend suite: 708 passed. The prior PostgreSQL
backup restore, row-policy/grant fingerprints and owner/outsider access tests remain
valid separately; they are not represented as a full managed Supabase restore.

The complete free operator runbook is docs/payment-free-backup-runbook.md in the
website repository. Existing local credentials are intentionally restricted backend
roles, without full public/Auth/Storage export access. Production activation needs
an approved full export method, matching object bytes, separate key custody, an
off-computer copy and an isolated restore target. Keep all such setup and any costs
at the owner-controlled final launch gate. Do not widen backend privileges.

## Next stage and preserved launch gates

Await owner permission for Stage 4, production operations: error/spending alerts,
support routing, incident procedures, deletion/revocation and production configuration
inventory. Operationalize the prepared backups and complete the live restore before
public launch. No launch gate has been silently waived. Claude funding, the production
meeting guard, two-device meeting acceptance, signing/Apple login, Stripe and final
rollout remain in the launch timeline.

Evidence: ignored work/stage3-closeout-nov5 in both repositories, including the
independent review, hosted-ingress.json, shared-postgres-limiter.json,
revocation-race.json, staging-migration-verification.json and backend-tests.log.
