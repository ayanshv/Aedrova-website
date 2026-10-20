# Post-meeting transcript confirmation

The owner explicitly requested the meeting-ended review screen on October 11.
New authenticated `/api/meetings/wrapup/{meeting}` and
`/api/meetings/transcript/confirm` routes retain the meeting-context feature gate.
The service forwards the user's JWT to new Supabase RPCs; the desktop never chooses
the reviewer role, grants AI consent or supplies speaker identity.

Confirmation sends all versioned transcript edits in one transaction. Invalid,
incomplete, stale, duplicated or cross-meeting snapshots fail without partially
reviewing text. Existing originals, citations, decision flags and AI permissions
remain unchanged. Request bodies are capped at 2 MiB only for this route; SQL caps
the review JSON at 1.5 MB, 10,000 parts and 2,000 characters/part, with five attempts
per minute. Standard API routes retain their smaller existing body caps.

Before staging deployment, the owner must apply companion app migration
`supabase/migrations/202610110002_meeting_wrapup.sql` in Aedrova Staging only.
Then manually deploy the matching staging commit and native source/build and test
two-account end/final-leave, retained consent, corrections and confirmation.
Local development backend suite: 441 passed; application/scripts/tests lint and
tracked-secret checks passed. No production deployment or paid release activated.

Stripe remains deferred until release preparation. The private Vercel registration
draft is prepared but awaits action-time agreement/Create approval; Phase 2 live
connector/provider acceptance remains open. This specific meeting feature was
separately requested; voice dictation and file-context Phase 3 work is not certified.
