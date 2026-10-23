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

Work in progress. Do not mark every Search Console issue cleared until Google has
recrawled/reprocessed it. Google alone determines actual indexing; repeated
submissions do not accelerate the priority queue. No owner action currently needed.
