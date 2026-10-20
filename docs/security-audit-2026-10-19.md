# Security audit and search verification — October 19, 2026

## Scope and outcome

Reviewed the actual 84-route website/backend graph plus desktop loopback OAuth and
static preview boundaries. Inventory: `uv run python -m scripts.audit_endpoints`.
It classifies 46 session/resource routes, four scoped build-token gateway routes,
24 public/read or release-gated routes, six OAuth/browser-proof routes, two bounded
public submissions and two signed webhooks. Tests send schema-valid unauthenticated
requests to all 50 private/gateway routes; all reject access. Some release-gated
routes reject before authentication, so this is not a substitute for hosted tenant
isolation or enabled-feature acceptance.

Reviewed authentication, CSRF/origin checks, OAuth state/PKCE and callback proofs,
connector provider allowlists/redirect behavior, file verification and limits,
billing/webhook idempotency and workspace entitlements, model admission/accounting,
meeting leases/RLS, rate-limit boundaries and local previews. No destructive live
traffic, payment, production key change or load testing was performed.

## Fixed locally

- JSON structure/control/non-finite limits now apply to mixed-case and `+json`
  media types, and gateway requests even with absent/misleading content type.
- Security headers, private no-store and noindex now wrap early rejection,
  throttling, unmatched routes and errors, including the standalone connector
  service. Branded error CSP is preserved.
- Unexpected API errors return sanitized JSON without exception details, provided
  response headers have not already been sent. Existing browser errors stay branded.
- Both dependency locks resolve aiohttp 3.14.5, with a >=3.14.4 constraint, addressing
  three dependency advisories in the previous resolved version.
- Desktop preview now bounds active workers and idle connections, rejects duplicate
  Host/Origin headers and oversized paths, and releases slots on failures.
- The standalone tracked-secret release scanner now imports correctly outside the
  repository working directory.

## Validation

- Website: 562 full tests passed; desktop: 893 full tests passed.
- Follow-up discovery/endpoint-boundary/inventory checks: 25 passed.
- Five independent robots edge-worker tests passed, including an unavailable origin,
  both public hosts, GET/HEAD and unchanged unrelated/private requests.
- Both repositories: Ruff, tracked credential scans and locked all-extra dependency
  audits passed; no known dependency vulnerabilities reported at audit time.
- Embedded PostgreSQL app migrations/RLS tests and restricted private backend
  schema/atomic lease SQL passed. Networked concurrency remains a hosted gate.
- Evidence logs and route inventory are in ignored `work/security-audit-2026-10-19/`
  in each repository. Do not commit private operational evidence or credentials.

## Search Console — verified live

The existing domain property `sc-domain:aedrova.com` is owned by the signed-in brand
Google account. Google reports seven indexed pages and the homepage is indexed.
The sitemap is successful, last read October 18, with 13 discovered pages.

The product-page indexing request failed Google's live inspection with “Blocked by
robots.txt”. Google's cached robots file is only 26 bytes, while the currently live
file allows the product page. This is consistent with Render Free's documented
behavior of returning a disallow-all robots file while the service sleeps; this is
an inference, not a confirmed capture of the sleeping response. Requested a canonical
robots recrawl successfully. Google controls recrawl and indexing timing.

Prepared `deploy/search-discovery/worker.mjs` to serve the existing public crawler
policy at the exact `/robots.txt` path independently of Render. It preserves the
training-bot policy and private-path exclusions and passes unrelated traffic through.
Regenerate its data after crawler-policy changes with:
`uv run python -m scripts.export_search_discovery`.
Routes are commented out and nothing was deployed. The existing Cloudflare Worker
`aedrovaerrorfallback` has no domain routes; do not assume it protects the live site.
No hosting purchase is required for the prepared edge approach; confirm account
free-plan availability before activation. Do not replace an existing Worker blindly.

## Remaining release gates and owner action

**These changes are local, not deployed.** Website AGENTS.md says “Do not push,
deploy or publish without authorization.” Obtain approval for source push and normal
website/staging deployments plus the exact-path Cloudflare robots route. Keep billing,
paid hosting and public installers disabled. No new key, SQL or payment is needed
for the source changes in this audit.

After deployment verify early-error headers, auth/tenant checks, trusted ingress IP
handling, hosted multi-worker limits, real provider authorization and resource
permissions, and subscription transitions in the appropriate sandbox. Run independent
security review before launch. Operational alerts/backups/recovery and existing launch
gates remain open unless separately evidenced. This review cannot establish that all
possible vulnerabilities or endpoint issues have been eliminated.

References:
- https://render.com/docs/free
- https://support.google.com/webmasters/answer/9012289
