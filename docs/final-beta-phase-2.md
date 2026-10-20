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

### Stripe business information saved — service agreement handoff

Owner reported saved; dashboard independently confirms business website
https://aedrova.com, public name Aedrova, and industry/product description provided.
Business information no longer shows Incomplete. Opened Service agreement → Review
without submitting. Next owner requirement: review the Stripe Services Agreement
and Acquirer Disclosure in the open Terms of service modal; click Continue personally
only if authorized and in agreement. The modal also includes consent to Stripe text
messages and a representation that business information is complete/correct. No
agreement accepted by the agent. Representative/public details/descriptor still
incomplete; full verification and Stripe external testing remain blocked. Phase2
is active; no later phase or live billing enabled.

### Stripe agreement completed — public support details handoff

Owner reports agreement done; independent dashboard observation shows Service
agreement no longer listed as Incomplete. Opened Public details → Edit public
details → Add customer support details without entering/submitting fields. Next
owner requirement is to complete truthful support phone/address/email/URL and
applicable published privacy/terms URLs, then Save personally. Business name and
website already show Aedrova/https://aedrova.com. The form defaults to showing the
support phone on receipts/invoices; owner must choose the appropriate public
contact information. Representative and descriptor remain Incomplete. Full Stripe
verification/external testing and Phase2 acceptance remain open; no billing enabled.

### October11 — policies live and Stripe URLs saved

Website PR4 https://github.com/ayanshv/Aedrova-website/pull/4 merged after green
CI38120908946; main commit8bb942d, mainCI38121001131 also green. Render website
srv-db0a8o7avr4c73eqcj4g auto-deploymentdep-db5jhsmk1f9s73eeecdg succeeded.
Live browser verification confirms new Privacy/Terms effectiveOctober11 and Support
with authorized phone(408)634-5254. Waitlist retained; release/billing gates untouched.
Current website development branch integrates the same pages:431 tests passed,
tracked secret check passed.

Entered https://aedrova.com/support, https://aedrova.com/privacy and
https://aedrova.com/terms into configured Stripe form and clicked Save under explicit
owner authorization. Modal closed; Customer-facing information no longer Incomplete
and saved Terms plus other provided URLs appear. No private address guessed/entered.
Stripe still marks representative/statement descriptor incomplete. Active Account
status task: Provide an external account; Stripe says no bank account on file.
Opened task details, no bank information entered. Next owner requirement: click
Start on this task and provide their valid bank account privately/personally.
This is Stripe account readiness, not evidence of full connector external-testing
acceptance. No later milestone started. Legal/business identity and jurisdiction
review remain required before paid public Beta; policies are not a compliance guarantee.
