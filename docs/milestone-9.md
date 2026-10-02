# Milestone 9: locally verified, live acceptance gated

September 30, 2026. The owner approved website/billing development and delegated the initial
AI allowance decision. Public prices stay $10/week, $49/month and negotiated enterprise.
The beta includes $1/week or $10/month, one active build/workspace and no automatic overages.
Optional purchased credits are $10 for $5 of usage, explicitly initiated and never auto-refilled.
These limits require measured paid-build costs before public launch; no production economics
claim is made.

Implemented: cinematic website, four-step optional introduction, preserved nickname transfer,
Google PKCE entry/session/CSRF handling, workspace creation, billing account/portal controls,
Stripe subscription and one-time credit checkout, verified canonical/idempotent webhooks,
private encrypted sessions/content, atomic reservations/settlement, run/provider binding,
fresh workspace membership checks, rate/body/context bounds, failure/replay handling,
credit refunds/disputes, maintenance and private enterprise inquiry export.

Desktop: Aedrova is the original agent name; existing custom names remain intact. Context
collection passes the current user's access to the managed service in memory. Server-created
build access controls model and provider; shared API keys remain server-only. Configured managed
builds fail closed rather than reverting to personal provider usage. Plan/usage controls live
in existing Settings. The package includes the official pinned Codex CLI and Claude SDK runtime.
The original dashboard layout is preserved. Tab mention completion also received a regression fix.

Website images now show the actual Qt application using local sample data. In-chat agent
activity is labeled a demonstration, not a real successful provider build. No meeting mockup
remains. Hero scenery automatically changes every five seconds; pause, reduced motion,
background visibility and unavailable media preserve readable content.

## Verification

- 294 desktop Python tests passed, including provider-token handling, secure origins, no
  personal-runtime fallback in packaged builds, onboarding defaults and Tab completion.
- 72 website/backend tests passed: navigation/assets/labels, preview gates, prices, PKCE/CSRF,
  owner/member/workspace isolation, revoked access, provider binding, atomic concurrency and
  spending, cache accounting, compaction, stream failures, replay, renewal, encrypted content,
  signed/tampered/duplicate/out-of-order webhooks, optional credits, refunds/disputes and cleanup.
- Existing embedded PostgreSQL migration/RLS suites passed. New private billing schema parses
  and creates all ten tables in embedded PostgreSQL. Multi-process live PostgreSQL ledger locking
  is still unverified; the ledger concurrency tests used real SQLite transactions.
- Installed Codex CLI 0.155.1 and Claude Agent SDK 0.2.160 reached loopback protocol fixtures
  using scoped run tokens, executed local file writes and completed a tool-result round trip.
  This tests actual runtime compatibility, not provider quality or paid API acceptance.
- The first Codex probe exposed ignored global override placement and used the existing account
  for a short confirmation. Fixed by placing overrides after `exec` and using an empty temporary
  CODEX_HOME for managed runs. Subsequent probes reached only loopback fixtures. Custom providers,
  no remote plugins/hooks/subagents, sandboxing and no automatic client replay are covered.
- All nine website pages fit 320px widths in both themes; 390px onboarding and pricing inspected.
  Next/Back, answer persistence, nickname editing, pricing/account handoff, navigation/Escape,
  theme switching, actual app screenshot assets and timed Golden hour→Still water rotation checked.
- Both-theme packaged smoke launches, bundle signature verification and baseline first-party
  secret-pattern checks passed. Codex bundled executable reports the pinned version. A local
  preview DMG was produced; the public signing/notarization path is implemented but not run.
- Python Ruff and browser JavaScript syntax checks passed. There is a non-failing Starlette
  deprecation warning about its current TestClient/httpx integration.

No production credentials, real Stripe purchase, live website OAuth callback, hosted gateway
build or public notarization were validated. No deployment, Git push or public release occurred.
A signed clean-Mac build and a measured provider-cost pilot are still required.

## Launch blockers / owner actions

Follow [owner-setup.md](owner-setup.md): domain/HTTPS/private PostgreSQL and stable encryption
key; website Supabase callback allowlist; Stripe sandbox/live business, prices, signing secret
and portal; provider billing/keys/model access; Apple Developer ID/notary profile; public app
origin and verified DMG/manifest; production policies/media rights; maintenance; staged acceptance.
Customer-facing checkout remains closed until those gates pass. Meetings stay planned for
Milestone 10; premium onboarding remains Milestone 11a and the final safety audit Milestone 13.
Do not advance to the next milestone or call the paid beta ready on the strength of local tests.
