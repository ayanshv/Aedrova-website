# Encrypted backup and isolated restore

This operator path needs no Aedrova subscription, paid backup add-on or new cloud
service. It does require an authorized full database export, matching Storage
objects, a separately held encryption key and an approved off-computer copy.
An archive on the same computer as its key is not disaster recovery.

## Capture a consistent source

Use Supabase's current CLI backup guide with an operator account authorized for
all required schemas. Capture database schema, roles and data including public,
auth, storage metadata, aedrova_private and aedrova_billing. Preserve ownership,
SECURITY DEFINER functions, grants and row policies. Verify tool/server version
compatibility. A plain restricted aedrova_website login is intentionally
insufficient for public/Auth/Storage backup and must not be given wider rights
just to run this procedure.

Copy the corresponding Storage bytes and retain object paths, metadata and
SHA-256 hashes. Database backups contain Storage metadata, not object contents.
Coordinate a consistent cut or a documented maintenance window; do not copy a live
SQLite file or call unmatched database and Storage snapshots a consistent backup.
Retain release/schema versions, the restore point and deletion/withdrawal records.
Keep the persistent application encryption key and any required provider-managed
root-key recovery instructions in separate approved custody. They are not replaced
by the backup encryption key below.

The staged local configuration currently contains only restricted backend database
credentials, not an administrator export credential or Storage service-role key.
No full production export or full hosted restore is claimed by this implementation.

## Create a private bundle

Use trusted private filesystem parent directories. Make a private input directory containing only the reviewed export files and
Storage objects, for example database.dump, roles.sql, storage/, and capture.json.
Do not put the backup key inside the input directory. Use absolute paths.

    python -m aedrova_site.backup_bundle init-key --key-file /private/keys/aedrova-backup.key
    python -m aedrova_site.backup_bundle create --key-file /private/keys/aedrova-backup.key --source /private/snapshot --destination /private/archives/aedrova-backup.aedrovabackup

The key is generated locally with private permissions and never printed. Existing
keys and archives are not overwritten. AES-256-GCM authenticates the format header
and encrypted archive. Each regular file also has an encrypted SHA-256 manifest.
File counts, metadata and total bytes are bounded. Source symlinks are rejected.
No SQL is executed, upload performed, scheduler installed or payment made.

Copy the encrypted archive to an approved separate location. Keep its key in
independent recoverable custody, not beside the sole backup. Select retention and
recovery-point objectives before launch; manually taking one copy is not a
scheduled backup system. Scheduler/alert activation belongs to production operations.

## Restore without touching an active project

    python -m aedrova_site.backup_bundle restore --key-file /private/keys/aedrova-backup.key --source /private/archives/aedrova-backup.aedrovabackup --destination /private/new-isolated-restore

The destination must not exist. Authentication completes before any files are
published there. Wrong keys, altered/truncated ciphertext, unsafe paths, links,
duplicate entries and mismatched hashes fail closed. Files are private; no archived
SQL or executable is automatically run. Bounds default to 2 GiB and 20,000 files;
larger deployments require reviewed sizing, not silently removing limits.

Only then use the reviewed database restore tooling against a new isolated target.
Never use either active production or staging database as the restore destination.
Keep external network egress/provider calls and checkout, AI, meetings, cleanup and
webhook replay disabled. Restore required roles/ownership, matching Storage bytes
and application keys; reapply approved deletion and consent-withdrawal records.
Verify access as owner/member/outsider/private-channel user, Storage hashes, encrypted
sessions/grants, paid/inactive entitlements, ledger totals, pending reservations
and event/request idempotency. Do not refund uncertain provider costs automatically.
Record measured recovery time and observed data loss before approving resumption.

## Evidence and limits

Encrypted bundle acceptance restores a consistent synthetic ledger checkpoint and
Storage fixture bytes, retaining money, encrypted sessions and replay settlement.
Adversarial tests cover wrong keys, ciphertext modification/truncation, existing
files, key permissions, input bounds, symlinks, traversal and manifest mismatch.
The separate PostgreSQL recovery gate restores real role/policy/grant fingerprints,
point-in-time content and application RLS checks. The two-connection revocation
regression runs against a real local PostgreSQL server.

These are executable local checks, not a claim that production backup scheduling,
independent key custody, off-site replication or full hosted recovery has been
activated. Those remain before public launch, including if the owner defers purchases.

References: https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore
and https://supabase.com/docs/guides/platform/backups
