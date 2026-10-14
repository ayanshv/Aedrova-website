# Branded website errors

October 14, 2026. Browser navigation errors use Aedrova system typography, blue
controls, charcoal system dark mode, existing Builder/Marketing artwork, support,
and concise recovery copy. Artwork/styles are embedded: no failing-origin asset
request is required. HTTP status and Retry-After remain accurate; errors are not
cached or indexed, sensitive exceptions are omitted, and the strict CSP authorizes
only the page's hashed stylesheet/data images. API, gateway, static assets and
Stripe webhook contracts remain unchanged. The server catches generic browser
4xx/5xx and unexpected exceptions before response transmission. An error after
streaming has begun cannot replace a page already sent.

## Independent origin-outage fallback

`deploy/error-fallback/worker.mjs` wraps ordinary browser GET navigation at the
Cloudflare edge. It passes healthy responses/redirects through and supplies the
standalone branded page for origin 5xx, 520–526 or a fetch failure. APIs, POSTs,
webhooks and assets pass through. No new origin, credentials or DNS change is
needed. Export the shared visual with:

`PYTHONPATH=. .venv/bin/python scripts/export_error_fallback.py`

The generated fallback.mjs is bundled by Wrangler. It contains public artwork,
not credentials. Tests: `node --test deploy/error-fallback/worker.test.mjs`.

Required deployment: authenticated Cloudflare account → Workers & Pages → create
Worker named `aedrova-error-fallback`, deploy this directory with Wrangler (or
upload its bundled module), then Settings → Domains & Routes → Add route:
`aedrova.com/*` and `www.aedrova.com/*`, zone aedrova.com. Select fail-open behavior
if Cloudflare offers it. Do not change DNS, SSL, WAF, budgets, or upgrade a plan.
Remove these routes to roll back. Validate a synthetic upstream 503 in a Worker
preview first; never stop the live origin to test. Ordinary production 404s should
show the server's branded page after its separate deployment.

Cloudflare errors issued before Worker execution (some security challenges, edge
failures), browser DNS/offline/TLS warning pages and provider-owned pages cannot
be guaranteed by an application Worker. Where the current Cloudflare plan permits,
use Rules → Custom Errors to configure provider-generated error responses too.
Do not bypass security challenges or certificate validation. Cloudflare's native
Error Pages do not cover every HTTP status; this is why the Worker fallback is
separate from the server renderer.

References:
https://developers.cloudflare.com/rules/custom-errors/
https://developers.cloudflare.com/workers/configuration/routing/routes/

## Acceptance and remaining gates

26 focused server tests and 13 Worker tests passed. The dark visual preview was
inspected in the browser; Bud backgrounds use a direct data URL (large CSS custom
properties silently hid the atlas in Chromium). Full backend regression results
and live deployment status must be recorded separately. Cloudflare routing is not
active merely because these source files exist. A total DNS/Cloudflare failure
cannot show our hosted page. Instagram OAuth remains pending service setup;
TikTok's approved staging configuration is independent.

### Live publication

PR #15 passed the required GitHub verify check and was squash-merged as 2f083e4.
Render's automatic production deployment became Live in 1m12s. Real browser GET
`https://aedrova.com/missing-page-check` returns branded HTTP 404 with embedded
Buds and hashed CSP; live screenshot saved in work/error-page-live.png. The
production candidate passed all 432 tests; the development backend passed 512.

Cloudflare's in-app dashboard failed loading a dynamic module. Safari successfully
opened the existing authenticated free account (100,000 daily requests), but its
Start with Hello World control did not advance under native automation. No Worker,
new permissions, paid upgrade or domain route was created. Owner handoff: in the
open Safari Cloudflare Create an app screen, click Start with Hello World, name it
`aedrova-error-fallback`, deploy on the existing free plan, leave it open and reply
created. Do not add routes yet; the starter must be replaced with the tested
fallback before any live routing. This still blocks host-outage UI acceptance.
