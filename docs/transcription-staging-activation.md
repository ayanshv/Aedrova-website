# Consented transcription staging activation — October 11

Owner explicitly brought transcription activation forward from its deferred gate.
Existing OpenAI key resolves whisper-1 metadata (200); no audio/provider inference
sent. Existing LiveKit credentials present. Owner ran sql/staging-speech-grants.sql;
restricted staging backend EXECUTE privilege is verified true for both speech RPCs.
The role was created after migration, which explains why its optional grant was absent.

Prepared .env.transcription-staging privately (0600, Git ignored): staging restricted
DB/key, existing LiveKit key, server speech key, enabled meeting/context/speech flags.
Checkout, coding gateway, public release remain disabled. Limited Free allowance can
now be enabled for a speech-only service: same server ledger, shared workspace and
funder pool, call/concurrency/spending limits; no new plan or free unlimited speech.
Workspace owner/admin must explicitly activate its Free plan through existing UI.

## Required owner action now

Render → aedrova-beta-staging → Compute: selected $7/month 0.5c-512mb, not saved.
Owner must click Save personally to start recurring charge. Existing free service
cannot provide continuously supervised meeting access. Then authorize transfer of
existing LiveKit credentials and existing OpenAI key to this staging service only.
No production password, service-role key or desktop secret is required.

Next create independent worker using deploy/render-beta-meeting-guard.yaml after
owner reviews/submits its $7/month charge. This references only required staging API
secrets and excludes the speech/provider key. Total base compute about $14/month;
provider, bandwidth and tax costs separate. Do not import the production meetings
manifest or upgrade the waitlist website. No purchase or secret upload performed yet.

## Agent steps after owner hosting/access approval

Configure current staging API with the prepared fields; deploy matching development
backend. Create/deploy the independently supervised guard, retaining private DB pool
size 1/no overflow. Verify /health/meetings 200, then run server-side
python -m scripts.check_meeting_setup --speech --database --probe.
This validates configuration, SQL execution privilege and API/guard readiness; it
never claims a provider capture or two-Mac test passed.

Launch native source using scripts/run_staging.py --config work/staging/public-config.json
--meeting-context. The opt-in is source-only, staging-only, ignored by frozen release
and production Supabase. Server capability/consent gates still apply.

Sign in two staging accounts, invite into a disposable workspace, explicitly activate
its limited Free plan, join, consent to storage and separately AI reuse, start microphone
and Start transcription. Verify attributed provider text, pause on mute/consent changes,
member/outsider permissions, limits/provider failure, last leave, owner/admin editable
wrap-up Confirm, reviewed AI context, withdrawal and rejoin. Test physical audio on two
Macs separately; synthetic fixtures do not certify physical media or transcription.
Configure existing expire_meeting_text maintenance before public release.

Verification: 743 full desktop tests, 444 full backend tests passed; tracked secret and
scoped lint checks passed. Live paid hosting/capture acceptance remains blocked on the
owner actions above; public website stays waitlist-only.
