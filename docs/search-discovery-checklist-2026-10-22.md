# Search discovery implementation — October 22, 2026

Owner requested the twenty-item public search/AI checklist. This change does not
promise placement in AI responses, rankings, or Google rich results.

1. Public AI crawler access: wildcard and named agents allow public pages, including
   GPTBot and ClaudeBot. Private/API/auth routes remain restricted and authenticated.
2. Robots: production-only crawl policy; previews remain disallowed.
3. Sitemap: canonical inventory expanded from 14 to 17 pages; regenerate independent
   Cloudflare assets with export_search_discovery and bundle_search_discovery.
4. Structured data: existing Organization/WebSite/SoftwareApplication plus truthful
   publisher/date metadata on the new pages. No invented reviews or certifications.
5. Semantic HTML: server-rendered article, headings, navigation and footer.
6–8. Titles, descriptions, canonicals: shared metadata covers every inventory page.
9. Indexing: prior Search Console sitemap Success and five indexing requests recorded
   in search-console-2026-10-22.md. Google processing is not a completed indexing gate.
10–11. HTML rendering and descriptive headings: no JavaScript needed to read new pages.
12–13. Dedicated FAQ covers access, plans, Buds, permissions and feature limitations.
14. Research cites Google's official documentation.
15–16. Real organizational publisher (Aedrova team), publication dates on new content,
   and reviewed date on product page; no fabricated individual byline.
17–18. Product information reviewed and footer/internal links connect all new pages.
19. Original research: reproducible first-party crawlability study of 14 pre-change
   URLs. This is a technical measurement, not customer research or ranking evidence.
20. Visibility: existing Search Console evidence retained; recheck production after
   deployment. Indexing and preferred-source eligibility remain Google's decisions.

## Favicon

Use the existing square 512px PNG at the stable /static/checkout-icon.png URL.
Remove the competing SVG-with-embedded-raster favicon declaration and version query.
The PNG already existed; therefore the generic globe alone does not prove an asset
failure. This simplifies discovery, but Google must recrawl and may still choose
not to show the icon. Homepage indexing can be requested after deployment.
Guidance: https://developers.google.com/search/docs/appearance/favicon-in-search

## Deployment

Website main deployment and the separate Cloudflare Worker both need the new source.
Do not describe the 17-page sitemap as live until the Worker payload is verified.
No owner payment or personal action is required for these source changes.
