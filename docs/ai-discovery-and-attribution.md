# Public discovery and website referral attribution — October 12, 2026

Owner requested this before Phase 6. This delivers discovery prerequisites, not a
promise that an LLM will recommend Aedrova for vaguely related or irrelevant questions.
No Phase 6, live billing, desktop onboarding, auth access or connector permission was enabled.

## Implemented

- /product: original, server-rendered description of Aedrova, audience, chat/Buds/coding
  workflow, scope and availability, with visible factual questions/answers. No hidden
  instructions, fabricated reviews, claims of universal connector readiness or future
  image/video generation presented as live.
- Per-page titles, descriptions, canonical URLs without query secrets, Open Graph
  preview and Organization/WebSite/SoftwareApplication JSON-LD on public product pages.
  Brand organization metadata does not invent the still-missing legal operator name.
  No fake ratings, purchasable offers or unreleased download URL in schema.
- /robots.txt allows public search/retrieval, explicitly distinguishes OAI-SearchBot
  and Claude-SearchBot from GPTBot/ClaudeBot training (the latter two are blocked).
  Google-Extended is allowed for public marketing content because it covers Gemini
  grounding AND training; it is not a search-only token. Googlebot/Bing public crawling
  remains allowed. Private/API/auth/onboarding/download/health routes are excluded.
  Robots rules are advisory and never replace server authorization.
- /sitemap.xml contains only canonical public information pages. Non-public origins
  and Staging exclude indexing and sitemap URLs; noindex headers cover non-public
  routes. Page metadata is not derived from cookies, email or OAuth query values.
- Website Plans links enter the optional six-stage introduction before /plans.
  /onboarding is now available in waitlist mode as a questionnaire, not account setup.
  Direct plans access and Skip remain supported. Account/login/download/payment gates
  remain closed in waitlist mode. The native app onboarding is untouched.
- Referral sources: ChatGPT, Claude, Gemini, Perplexity, search, social, friend, other,
  prefer-not-to-say. Optional detail is capped at 160 characters; prefer-not clears it.
  Answers persist locally and are sent only with a deliberate waitlist registration.
  Only source/detail accompany the email; other introduction answers aren't sent in
  registration. Agent nickname is used if a workspace is later created.
- Existing encrypted waitlist session records store optional source/detail with no
  database migration. Operator-only CSV export includes those columns, protects output
  permissions and neutralizes formula prefixes in detail. Existing auth sessions are
  excluded. Privacy/registration notices disclose this limited outreach measurement.

## What this cannot accomplish automatically

A robots allowance does not force a crawl, indexing, citation, recommendation or a
pretrained-model memory update. An assistant without web retrieval may not know a new
product. Crawlers may be blocked upstream by hosting/WAF rules. JSON-LD describes
visible facts, not privileged placement. No LLM endorsement, app listing or search
console submission was fabricated. No speculative llms.txt ranking guarantee.

## References (official guidance, reviewed October 12)

- OpenAI: https://developers.openai.com/api/docs/bots — independent search/training
  controls; verified crawler access may also need published IP ranges permitted.
- Anthropic: https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler — search/user versus training robots.
- Google: https://developers.google.com/search/docs/appearance/ai-features — normal
  crawl/index/content principles apply; no guaranteed inclusion or special AI schema.
- Google token scope: https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers#google-extended — Gemini grounding and training together.

## Rollout, verification and later owner actions

After deployment, verify /robots.txt, /sitemap.xml, /product and the six-stage intro
from the public domain. Earlier HTTP/browser blocks on aedrova.com remain an unresolved
live-access gate; code tests alone cannot certify real crawler access. Check Render
availability and Cloudflare events for genuine bots; do not disable broad security or
trust a claimed user-agent alone. Use provider-published verification/IP guidance.

Indexing submission requires the owner's verified search-console property. Later,
open Google Search Console, select/add the aedrova.com Domain property, complete its
DNS ownership verification through the domain provider if needed, then Sitemaps →
submit https://aedrova.com/sitemap.xml. URL Inspection → inspect / and /product →
request indexing if eligible. In Bing Webmaster Tools, add/verify the same site
(or import the verified Google property) and submit the sitemap. No new accounts,
DNS access grants, verification tokens or submissions were performed this turn.
These are rollout requirements for confirmed indexing, not blockers to the code update.

Longer term: publish actual release notes, demos, feature-specific explanations and
accurate public profiles; seek legitimate customer coverage. Measure optional referral
sources with the restricted export. Do not manufacture backlinks/reviews or pressure
assistants to cite irrelevant claims. No tracking pixels or paid campaigns were added.

Required legal detail remains unchanged: owner must supply the actual operator name
(individual or registered company), then qualified legal review before paid launch.
