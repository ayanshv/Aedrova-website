# Connector certification — October 15, 2026

Current authoritative audit, all-nine provider status and consolidated owner handoff:
/Users/ayanshvarma/Documents/Aedrova/docs/connector-certification-step-6.md.
Step 6 is in progress, not launch-certified. Fresh authenticated staging catalog
reports only Instagram/TikTok OAuth enabled and no active grants in the named test
workspace. Four existing local pairs (GitHub/Supabase/Figma/Notion) need specific
staging callback/credential-transfer approval. Stripe bank/business setup stays
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

Current staging Render deployment remains e375bdc / dep-db8o043l550s73ej2i90.
This source patch is not deployed. One fresh start per social provider succeeded;
TikTok's web handoff stalled in Google's account chooser before provider login,
and Instagram's provider page was not opened afterward. Temporary native sessions
and login/authorization files were cleaned. No new provider grant, app secret
transfer, registration change, paid service, production promotion or installer
release occurred. Exact approval is requested at the final owner handoff.
