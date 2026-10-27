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

## Published verification

PR27 passed both checks and merged to main as9e26da8. Render production aedrova-website
reports that commit Live (automatic deploy,1m09s); no paid plan or new backend feature
was enabled. Live /team renders all4 confirmed names and supplied portrait; PNG/ICO
and the original public icon all return200 with correct image MIME and no noindex.
HTTP verification: ../work/team-search-oct27/live-verification.json (primary checkout).
Search Console reports /team already indexed. Homepage recrawl request accepted after
the favicon deployment; screenshot home-indexing-requested.png. No repeat team request
was submitted because the page is already indexed. Google display remains external.

Existing independent sitemap Worker still serves17 pages, excluding/team. Prepared
18-page bundle is tested but not published: Cloudflare login explicitly says Continue
accepts its terms/privacy/cookie policies. Need owner action-time agreement approval,
or owner personal sign-in, before updating the existing Worker. Existing exact4routes
and free plan must remain. No broad new Worker route, DNS or paid service is required.
Bios and remaining team portraits are pending owner input; names/credentials are not
invented. Desktop agent-permissions work is separate from this production website PR.

## Owner-confirmed portrait follow-up

Added supplied photographs: first attachment Abhinav Thirumala, second Minh-Khoa
Nguyen. Ayansh's role is now Co-Founder & CEO / CTO. Re-encoded web JPEGs contain no
EXIF payload; originals are unchanged. Shared template now uses each person's own
name, role and intrinsic dimensions rather than hardcoded Ayansh alternative text.
Bios remain pending owner input after this response; Joash retains his monogram.
37 public/discovery/product checks passed; Ruff passed. Scope excludes backend
staging commits, billing, credentials and permissions.
