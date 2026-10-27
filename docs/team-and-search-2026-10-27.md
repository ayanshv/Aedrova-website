# Team page, portrait and search signals — October 27, 2026

Move the full founders-first hierarchy to /team. Home retains a short invitation;
About and the shared footer link to the dedicated page. Metadata/canonical/sitemap
include /team. No biography or portrait is invented. Ayansh's supplied photograph
is a web-sized JPEG copy produced by the desktop image codec; its hidden GPS EXIF
was removed and the resulting file has zero EXIF fields. Original remains unchanged.
The website frames it with CSS and applies no theme inversion or brightness filter.

Favicon: the homepage declared a valid square 512px PNG, but the shared response
middleware also set X-Robots-Tag:noindex on that public icon. Add exact public icon
exceptions, stable /favicon.png and multi-resolution /favicon.ico GET/HEAD endpoints,
and consistent icon links. Other static assets, errors and private pages retain
noindex. Staging is still entirely noindex. No authentication or access policy changed.
This removes an avoidable discovery signal; it does not prove Google's reason for
showing a globe or guarantee a favicon in search results.

Live Search Console observations before deployment: homepage indexed, crawl allowed,
page fetch successful, canonical https://aedrova.com/, recorded crawl October 21.
Sitemaps report: Success, last read October 27, 17 discovered pages. A current brand
query showed the official website/sitelinks and no AI Overview. This is one query/session,
not a universal visibility or penalty assessment. Public Google guidance says Overviews
only trigger when useful, require normal index/snippet eligibility, and are not guaranteed.

Regenerated Cloudflare crawler exports include /team (18 public pages). The website
release alone does not publish those independent edge assets. Existing Worker
`aedrovaerrorfallback`, exact robots.txt/sitemap.xml routes, must receive the prepared
bundle. Cloudflare's browser sign-in currently states that continuing accepts its
terms; pause before that agreement without action-time confirmation. No DNS, WAF,
permissions, paid settings or new Worker is needed.

Validation: 48 focused brand/public/discovery/trust/capture tests passed, including
favicon GET/HEAD MIME/indexability, private/staging noindex and team hierarchy.
Ruff passed. Google recrawl/request and final live deployment results are recorded
separately; don't equate an accepted request with a displayed icon or AI citation.

Sources:
- https://developers.google.com/search/docs/appearance/favicon-in-search
- https://developers.google.com/search/docs/appearance/ai-features

Owner items at completion: bios for four members; headshots for the other members
if desired; action-time approval for Cloudflare's displayed Continue/terms screen
if the browser login is needed to publish the already tested sitemap bundle.
Stage 1 acceptance remains open for its prior provider/audio gates; payments deferred.
