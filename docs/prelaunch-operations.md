# Prelaunch operations — October 13, 2026

Owner authorized completing launch gates before Apple enrollment. Engineering checks
may proceed; purchases, public payment/download activation, destructive production
operations and unapproved provider grants remain gated.

## Monitoring prepared and tested

On the backend's existing private operator environment, run:

    python -m scripts.check_operations

This uses existing configuration without printing secrets or user/workspace IDs. It
performs read-only ledger queries and a bounded readiness request to the configured
origin. Exit 1 means attention is required: readiness/configuration failure, either
company or shared Free pool at 90%, or expired in-flight inference reservations.
Pending reservations include potentially incurred provider costs; the probe never
refunds, changes billing, deletes data or calls an AI provider. Estimated spending
is not an invoice reconciliation. No migration or new credential is required.

Configure an approved operator scheduler to run the probe every five minutes and
alert on nonzero exit. Configure log-based alerts for HTTP 5xx, database_slow,
ai_admission_rejected and ai_budget_threshold; use only content-free metadata.
Do not send private URLs, request bodies, tokens or customer content to alerts.
Scheduler/alert delivery is NOT installed or validated by these local tests.
A free service that sleeps is not certified for continuously available production.

## Backup and restore acceptance — still required on hosted infrastructure

The automated disposable SQLite drill verifies snapshot integrity, unchanged money,
pending reservations, duplicate-event protection, replay, encrypted sessions and
failure with the wrong encryption key. It does not certify Supabase recovery.

Before production deployment, the owner/operator must record the actual database and
Storage backup coverage, retention, region, restore point and encryption-key custody.
Database backups are not proof of corresponding Storage object backups. Keep the
persistent encryption key separately recoverable in approved private custody; never
commit it or attach it to a support request. No new hosted key permission was granted.

Perform a restore to a separate approved staging target, never over production:
1. Restore matching public application schema/data, private billing/connector ledger
   and authorized Storage objects; record the exact schema/build versions.
2. Restore the matching private encryption key without displaying or transmitting it
   to a new service without explicit approval.
3. Keep checkout, AI, meetings and cleanup disabled during validation. Reapply approved
   deletion/withdrawal records before making restored data accessible.
4. Test owner/member/private-channel denial, file byte integrity, encrypted grants and
   sessions, paid/inactive entitlements, event replay, pending requests and ledger totals.
5. Reconcile uncertain requests against provider records before resuming paid inference;
   restore must not silently reset budgets or resend requests with uncertain outcomes.
6. Record actual recovery time/data loss and an authorized go/no-go. Resume service only
   after those checks; do not treat a successful database restore as full recovery.

No real backup, provider token, account deletion or restored database was uploaded or
modified this turn. Hosted restore, external alert delivery and real PostgreSQL
multi-worker accounting remain open release gates.

## Incident actions

- Credential leak: pause the affected capability, revoke/rotate the credential through
  the owning provider, preserve content-free audit evidence, identify affected scopes,
  validate replacement privately, then resume. Do not rotate unrelated keys blindly.
- Unexpected AI spending: disable gateway/Free activation, retain reservations and
  reconcile provider invoices; investigate repeated jobs and authorization before
  restarting. Do not bypass server ceilings or erase the money ledger.
- Connector compromise: disable affected grants and provider access, preserve minimum
  evidence, notify authorized operator, validate scoped reconnect; do not expose tokens.
- Data exposure: stop the affected path, preserve access evidence, identify actual data
  and impacted workspaces, obtain qualified notification guidance and restore isolation.
- Database/provider outage: fail closed, retain uncertain work, show retry/status, restore
  only through the reviewed procedure above. Never substitute another workspace or key.

Escalation contact: contact@aedrova.com. Confirm mailbox delivery, an incident owner
and independent review of highest-risk areas before public launch. These documents do
not claim the incidents or notification obligations have been professionally reviewed.
