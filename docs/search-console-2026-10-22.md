# Search Console remediation — October 22, 2026

Owner requested resolution of the aedrova.com Search Console checklist before
continuing customer recruitment. Existing verified account/property retained;
no ownership, permission, DNS, credential, paid service or public launch change.

## Observed baseline

- Indexing report last updated October 15: nine indexed URLs, five discovered but
  not indexed, three expected canonical redirects, zero crawled-not-indexed.
- Five discovered URLs: `/product`, `/plans`, `/support`, `/terms`, `/data-controls`.
- One appearance warning: indexed but robots-blocked `/download`.
- Sitemap: fourteen discovered pages, October 20 last-read HTTP fetch error.
- Robots report: all four scheme/host variants fetched, no syntax issues.
- HTTPS: ten HTTPS URLs, zero non-HTTPS problems.
- Manual actions and Security issues: no issues detected.
- Core Web Vitals: insufficient real-user data on mobile and desktop, not a
  reported pass or performance failure.
- All fourteen live sitemap URLs returned HTTP 200, matching self-canonicals,
  index/follow metadata, no noindex header, and Googlebot crawl permission.

## Remediation

Google's live product and plans tests succeeded. Product indexing request was
accepted into the priority crawl queue. Remaining requests/validation and hosted
acceptance are recorded below as they complete; they are not assumed completed.

Allow crawling `/download` so Google can observe its existing redirect/noindex;
retain the waitlist and actual release gates and block descendant/API downloads.
Do not index the landing URL or add it to the sitemap solely to remove a warning.

Existing free Worker now contains tested static public robots/sitemap responses.
Deploy version `d987d7f5` succeeded through Safari. Four exact routes are being
configured; no whole-site interception. The separate outage-page Worker remains
outside this task. Python source and generated edge exports match; CI enforces it.

## Validation

590 full website/backend tests and ten Worker tests passed locally. Worker tests
cover GET/HEAD, both public hosts, simulated origin failure, canonical metadata
parity and private-path/method pass-through. Ruff and diff checks passed.
Live page audit evidence: ignored `work/search-console-oct22/live-public-pages.json`.
Saved accepted product indexing screenshot and deployed Worker evidence in the
same ignored folder. Publication, route acceptance and final Google state follow.

## Remaining status

Technical fixes deployed. Do not mark every Search Console issue cleared until Google has
recrawled/reprocessed it. Google alone determines actual indexing; repeated
submissions do not accelerate the priority queue. No owner action currently needed.

## Hosted acceptance

PR #23 passed both required verify checks and merged as c1a3ad2f.
Cloudflare Worker d987d7f5 and all four exact fail-open routes are active.
All four HTTPS crawl URLs return HTTP 200, correct MIME/cache headers, no redirects,
and byte-identical tested policy/sitemap. Google fetched the main new 1,856-byte
robots policy on October 22. Recrawl requests for the three older host/scheme
variants were acknowledged. Sitemap resubmission was accepted; its previous
October 20 fetch-error status remains pending Google's next processing.
All five individual indexing requests (product, plans, support, terms, data-controls)
were accepted. Robots-warning validation shows Started October 22, not Passed.
Canonical redirects, waitlist redirect, private session denial and blocked actual
installer download were rechecked live. Homepage background pedestrians video is
correctly excluded from video search because the homepage is not a watch page;
this does not block ordinary page indexing. No false watch-page claim added.
No owner action now; Google recrawl/indexing/validation remain external processing.

## Preferred Source follow-up

Owner additionally requested a Google Preferred Source badge. Official guide:
https://developers.google.com/search/docs/appearance/preferred-sources
Google source selector https://www.google.com/preferences/source?q=aedrova.com
returned No results on October 22. No working badge can be represented as active
until Google offers this domain. Prepared an ordinary no-script, no-tracking link
in ignored work/search-console-oct22/preferred-source-ready.html for later use.
Do not imply Google endorsement or silently add a third-party script/SDK.

Final follow-up: sitemap report now shows Success, last read October 22, fourteen discovered pages. Screenshot work/search-console-oct22/sitemap-success.png. Previous fetch error resolved; individual indexing and robots-validation processing remain pending.
