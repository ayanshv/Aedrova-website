# Step 8 captions API foundation — October 16, 2026

The existing authenticated transcript endpoint now accepts `latest=true` and reads
at most 20 rows, ordered by created_at/id descending, using the caller's Supabase
RLS token and existing meeting-context feature gate. Normal page-based transcript
review is unchanged. No new migration, key, scope, recording permission or AI
allowance. Eight focused context/wrapup tests pass, including missing auth,
disabled gate and bounded latest query/token forwarding.

This is source implementation, not hosted acceptance. Meetings remain unavailable
on staging pending the owner's deferred always-on API + independent guard setup.
Do not enable meeting flags to bypass the guard. Deploy this branch alongside the
updated desktop before testing captions; do not promote to production or claim
full meeting feature delivery. Full feature status and consolidated owner actions:
Aedrova/docs/meeting-step-8.md and meeting-step-8-status.json.
