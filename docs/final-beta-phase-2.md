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
