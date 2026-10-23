# Stable public crawler files

The existing free Cloudflare Worker `aedrovaerrorfallback` serves only public
robots policy and the canonical sitemap, independently of a sleeping/unavailable
Render origin. No credentials, database access, API routing or paid binding.
Other URLs and methods pass through unchanged. This is not the separate branded
502 outage fallback in `deploy/error-fallback`.

Regenerate after changing discovery metadata:

```
uv run python -m scripts.export_search_discovery
uv run python -m scripts.bundle_search_discovery
node --test deploy/search-discovery/worker.test.mjs
```

Tests compare both edge exports with Python metadata. CI runs these checks.
Deploy regenerated `worker-bundled.js` to the Worker whenever public pages or
crawler policy change; website deployment alone does not update the Worker.

The only intended routes (zone `aedrova.com`) are:

- `aedrova.com/robots.txt`
- `www.aedrova.com/robots.txt`
- `aedrova.com/sitemap.xml`
- `www.aedrova.com/sitemap.xml`

Use fail-open/origin fallback because this Worker serves public static metadata,
not security checks. No whole-site wildcard, custom domain, DNS change or upgrade.
Normal HTTP/HTTPS and www/non-www canonical redirects remain valid.

The public `/download` landing URL is crawlable so Google can see its current
waitlist redirect, or its existing noindex response outside waitlist mode. It is
not included in the sitemap. `/download/` descendants and `/api/` remain blocked;
authentication, private files and release gates are unchanged. robots.txt is not
an authorization mechanism.

October 22 deployment and Search Console acceptance are recorded separately in
`docs/search-console-2026-10-22.md`. Google processing is asynchronous; an accepted
submission or live fetch does not establish indexing or a ranking guarantee.
