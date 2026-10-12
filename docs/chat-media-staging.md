# Phase 3 — verified uploads and composer dictation (October 12, 2026)

## Implemented

Uploads retain immutable, private Supabase objects and existing channel/workspace
permissions. New files are checked locally and independently on the backend before
chat publication. A direct authenticated finish_attachment RPC can no longer bypass
inspection; only the restricted backend can invoke finish_verified_attachment, which
locks metadata and rechecks uploader, digest, channel access, stored size, expiry and
reply scope. Existing published attachments remain readable. No privileged Storage
key is used. Owner installed the staging migration; restricted role resolution and
EXECUTE were verified true. Production migration is deliberately not installed.

Limits: 10 MiB/file; 10 files/drop; 20 unexpired pending reservations/uploader;
existing 1 GiB workspace quota, including reserved ceiling and deferred orphan charges.
Accepted UTF-8 text/source extensions, PNG/JPEG, PDF and non-macro Office documents.
Images: at most 25 megapixels/12,000 pixels per side. Office: 200 archive entries,
50 MiB declared expansion, 100:1 compression ceiling; encrypted, macro and traversing
entries rejected. Generic archives, executables, HTML and SVG are unsupported.
Content inspection is not antivirus scanning or proof that a document is harmless.
No archive extraction, document rendering or executable processing occurs on server.
Two concurrent streaming file checks; 10 verifications/user/minute; 30-second download
bounds and 10 MiB memory limit. AI context remains existing permission-scoped text
only, 256 KiB/file and 8 MiB aggregate context; binary docs are not silently parsed.

Upload progress lives inside its originating composer. Cancellation stops publication
before final verification; cancellation is unavailable once commit may be underway.
A failed/ambiguous transfer never auto-publishes unverified bytes. Cancelled/orphan
objects use existing cleanup/accounting leases. Channel changes do not redirect
uploads, and account closure invalidates pending transfers.

Dictation adds an accessible microphone beside Send in channel/thread composers.
Explicit press checks service availability before requesting OS microphone access.
Visible listening timer and real audio-level waveform, Done and Cancel, themed light/
dark surfaces and narrow-layout controls. No hardware check/permission on launch.
At most 5 minutes of mono 16 kHz PCM in memory, no audio file. Cancel, account/
channel/thread changes, closing the window, starting a meeting or sending the typed
message stop capture and discard late results. One recording per window. Microphones
without the supported format fail with a clear device error; physical compatibility
still requires live Mac/Windows acceptance.

Done sends one bounded request to the server; provider transcription is appended to
the current editable draft, without replacing interim typing or automatically sending.
The strip animates processing, not fabricated real-time transcript text. whisper-1
returns text after recording (it does not stream partial words). Provider schema checked
against https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create.

Backend verifies Google session, current channel access and billing root through RLS.
Uses the existing shared plan allowance/funder/company budget and concurrency ledger,
with conservative reservation before provider call and settlement afterward. Six
requests/user/minute, four concurrent requests/process, 30-second input, 16 KiB provider
response and 4,000-character transcript caps. Keys stay server-side; raw audio and
transcript are not persisted by Aedrova's dictation service. Third-party processing
uses the existing OpenAI speech provider. No meeting consent or guard dependency.

## Remaining setup and acceptance

Staging upload migration has been run by owner and its restricted grant verified.
Deploy matching backend/native source before testing new upload publication. Do not
apply it to production while older public clients still use direct finalization.

Chat dictation can use the existing free staging web service; no meeting worker or
hosting upgrade is required for this feature. It still needs action-time authorization
before transmitting the existing OpenAI key to Render's staging secret store, then
AEDROVA_SPEECH_KEY, AEDROVA_CHAT_SPEECH_ENABLED=true, and limited Free activation
(AEDROVA_FREE_ENABLED=true, explicit workspace owner/admin activation). Keep meetings,
meeting context, speech_enabled, gateway, checkout and release gates disabled.
A Free web service can sleep; reliable public latency still belongs to release hosting.
No provider inference or physical microphone acceptance claimed by fixture tests.

Live acceptance: two staging accounts; valid/malformed/oversized/private/reply uploads,
cancellation and reconnect; explicit microphone permission, speech, edit, cancel,
conversation switch, allowance denial and expired session. Clean Mac/Windows device
checks remain release gates. Cleanup maintenance must run before public upload release.

## Verification

Full native suite: 755 passed before the two final dictation regression additions;
those six focused dictation tests pass afterward. Full backend suite: 462 passed;
final waitlist gate checked separately. All embedded PostgreSQL migration/RLS tests,
including verified publication, other uploader denial, idempotency and cancellation,
passed. Light/dark native components inspected at 900 and 360 px using fixture states,
not a claim of live microphone recording. Secret scans and scoped lint passed.

Hosted update: owner approved the existing OpenAI key transfer and bounded Free chat
activation. Render free staging service deployed backend 36aba62 successfully
(dep-db693oid0e5s739s1gd0). Meetings/coding/checkout/public release stay disabled.
Upload SQL installed and restricted role EXECUTE verified. Actual workspace allowance
activation and physical microphone/provider acceptance remain pending.
The authenticated owner activated limited Free on existing disposable workspace
Beta isolation 1 eb8958 (100% capacity, 0/40 requests), without paid checkout.
Health ready returned 200; unauthenticated capability access denied 403. Source
native app launched against staging; native sign-in/physical/provider and hosted
upload acceptance remain pending owner actions, not completed tests.

### Subsequent Bud presentation update

October 12: shared website Bud blink script also included on staging pages and OAuth
confirmation/error templates. Public deployment uses isolated website PR #9; no
backend/API/permission changes are part of that PR. Native custom working-style
preferences persist through the existing versioned Bud instruction field and require
no SQL. Phase 3 live dictation/upload acceptance remains pending owner native sign-in.

### Voice recording replaces the default microphone flow — October 12

Owner requested voice messages instead of dictation. Matching file policy now validates only
mono 16 kHz 16-bit PCM WAV of 1–5 minutes, with bounded payload and exact RIFF/frame size.
Existing private upload, rate limit, hash verification and RLS remain enforced. Owner reports
202610120002_voice_messages.sql installed in Staging. Native explicit preview/send uses no
speech-provider/API allowance; only normal workspace storage. Deploy this branch to the existing
staging service; keep production, meetings, checkout and release gates unchanged.
