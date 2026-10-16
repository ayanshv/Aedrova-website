# Connector certification — October 15, 2026

Current authoritative audit, all-nine provider status and consolidated owner handoff:
/Users/ayanshvarma/Documents/Aedrova/docs/connector-certification-step-6.md.
Step 6 is in progress, not launch-certified. Fresh authenticated staging catalog
now reports GitHub/Supabase/Figma/Notion plus Instagram/TikTok OAuth enabled,
with no active grants in the named test workspace. The four existing credential
pairs were specifically approved, saved privately to staging, and deployed with
verified staging callbacks while retaining existing callbacks/scopes/settings. Stripe bank/business setup stays
deferred; Vercel registration and Brave Search setup remain separate gates.

Prepared non-secret staging overlay checklist:
deploy/staging-connector-certification.env.example. Never import its blank values
as a complete environment. Existing database/encryption/AI/speech/social values and
provider callbacks must be preserved. No new keys or broader scopes requested.

Source fixes preserve intentional token-exchange authorization errors, distinguish
429/5xx from grant loss, normalize equivalent TikTok scope delimiters without
accepting extra scopes and remove stale manual-token fallback copy. No automatic
exchange retry was added. Added all-nine synthetic-provider grant lifecycle and
isolation checks. Full backend suite 528 passed after final changes; Ruff/diff pass.
These are controlled tests, not fresh provider consent/renewal/publication evidence.

Staging deployment da30ebf390627f0d289896b58a125b6035008431 is Live on
Render dep-db8s0huq1p3s7396bdfg. Eight variables added; all 34 prior variables
retained. No secrets printed/committed, new keys, scope expansion, purchase or
production change. Fresh authenticated catalog and health 200 passed, managed AI
true and checkout false. Backend rerun: 528 passed; Ruff/diff pass. Fresh native
session signed out and private login URL cleaned. All four callback lists were
re-read after save; Figma/Notion also verified after reload.

No owner action is required for this completed configuration batch. Fresh provider
consent, named-resource reads, renewal/revocation and public provider review remain
open. No real fresh grant was completed. Step 6 remains open; Step 7 has not started.
Prepare exact provider sign-in/consent handoffs sequentially; do not reuse expired
links or request secrets in chat.
