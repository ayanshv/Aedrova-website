# Service Phase 2 progress

Owner approved Phase2 after confirming Phase1 desktop acceptance and GitHub rulesets.
See companion Aedrova/docs/final-beta-phase-2.md for the full acceptance matrix.

Implemented private Anthropic model-access setup, Claude-only configuration and
explicit local opt-in. No rates/model selection changed. Existing OpenAI model
metadata check passed on October10 without inference. All426 backend tests pass.
Normal connector login/resource selection has140 initial focused regression tests
passing; these do not replace live provider review/customer acceptance. GitHub,
Supabase, Figma, Notion and TikTok client pairs exist locally (values not recorded);
Stripe, Instagram, Vercel and Search local credentials are absent. Anthropic absent.

First owner requirement is docs/anthropic-setup.md. Registration/review, actual
consent/scoped reads, refresh/revoke/reconnect and staging gateway cost acceptance
remain open. No service deploy, production merge, billing/download activation or
Phase3 started.

## Latest follow-up supersedes initial credential inventory

Anthropic key/model metadata now independently verified, private regular0600 file;
no inference. Official Sonnet5.5 cache-hit price corrected to $0.10/MTok in both
configs. Added gateway rejection of unpriced premium region/speed before reservation
and requests. All430 tests pass locally. Initial Phase2 native/site CI green.
https://platform.claude.com/docs/en/about-claude/pricing

Stripe app page still blocks external testing until developer business verification.
Opened Business details→Edit business details for owner to complete actual industry,
website and product description. No sensitive fields submitted. Stripe connector
remains blocked pending verification and later install/credential/live acceptance.
No deployment, production merge or paid/public access enabled.
