# Dedicated storage maintenance — M13A

Full policy, safety boundaries, tests and owner setup:
`/Users/ayanshvarma/Documents/Aedrova/docs/milestone-13a-release-hardening.md`.

This repository supplies `python -m aedrova_site.storage_cleanup` and
`deploy/storage-cleanup.env.example`. The worker is disabled by default. It must run in a
separate private job environment with its own Supabase secret/service-role key; never add
that key to the public website environment or the desktop app. Do not create paid hosting
or enable the worker before M14 owner approval and hosted validation.

Apply desktop `202610030003_storage_retention.sql` after preceding migrations before any
worker run. Validate a disposable expired upload in staging, observe Storage API deletion
and verify the accounting counter decreases once. Finalized chat files must remain
untouched. Monitor leased/ready queue backlog and failures; repeated errors retain quota
instead of claiming successful deletion. No live deletion or hosted SQL was done in M13A.

Schedule hourly after acceptance. SQL claims/deletions are capped at 10 objects per worker
pass; batching and schedule frequency require measured staging load. A service crash or
failed API call leaves leases to expire and accounting conservative. Preserve retired
paths and restore the ledger/cleanup tables together with attachments in backup drills.
