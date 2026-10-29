# Reader-specific localization — October 29, 2026

/api/language reads and updates only the authenticated user's language and automatic
conversation translation preference in Supabase Auth metadata. /api/translations checks
workspace membership and bills the existing included AI ledger before invoking OpenAI
Responses with strict structured output, no tools and store:false. No migration,
new secret or paid activation is required. Preserve existing gateway/company caps.

See the desktop repository docs/multilingual-support.md for reader workflow and final
acceptance. Server cache is memory-only, reader/workspace/target scoped, 15 minutes,
256 entries. Inputs and outputs are bounded; technical tokens are protected, and
original text remains available on failure. Source text is never logged by this service.
Translations consume workspace allowance; this must remain visible in the interface.

The footer shares a signed-in account's language preference. Unsigned visitors receive
core Hindi navigation; full-page and other languages require authenticated workspace AI.
This is not complete offline localization of every public marketing/legal page. The
English legal source remains canonical; automatic translations are informational.

Local tests use mocked provider HTTP and real metering. Production deployment and
native-language quality review have not been established by these tests. Deploy to
existing staging first, preserve the waitlist production gates, and validate with two
readers on different language settings before claiming live acceptance. No purchase,
production AI enablement or public release is authorized by this feature alone.

Staging deployment b5e3fee was visibly Live on October 29. /health returned 200 with
managed AI enabled and checkout disabled; /api/language returned 403 without sign-in.
This confirms deployment and the unauthenticated boundary, not live translation quality.
Full local service suite: 657 passed. Final two-reader/natural-language acceptance still
requires the owner to sign in to Staging; no new setup, payment or migration is needed.
