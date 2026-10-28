# Public team and organization discovery — October 27, 2026

Owner requested improved team/company information for Google AI discovery. Google
states that normal Search eligibility and helpful, accessible content apply to AI
Overviews/AI Mode; no special schema guarantees inclusion or a response for every user.

Implemented visible founder/role summaries and linked person anchors on /team,
/about and Home. Product description names the actual audience, workspace, Buds and
coding-agent workflow. Team questions answer who founded Aedrova and who handles
communication, with product, controls, availability and support links. Business
identity disclosure remains accurate: brand Aedrova, no invented registered entity.

Structured data now connects Organization, Person and AboutPage using stable canonical
IDs. Three co-founders are distinguished from the communications director. Names,
roles, biographies and portrait URLs match visible owner-approved content. Home links
the same founder entities; product Organization metadata retains its factual scope.
Organization logo references the stable crawlable /favicon.png. No invented personal
credentials, history, affiliations, reviews, registrations or addresses. About retains
its original publication date and records this substantive update; team is dated today.

Validation: focused discovery/public-page/product checks, JSON-LD parsing, visible
content/ID consistency, private/staging noindex regressions and Ruff. Existing sitemap
URLs are unchanged; no Cloudflare publication or repeat sitemap submission required.
After deployment, verify public graph/HTML and request team/About recrawl in Search
Console. An accepted request or valid JSON-LD does not certify AI Overview inclusion.

Sources:
- https://developers.google.com/search/docs/appearance/ai-features
- https://developers.google.com/search/docs/appearance/structured-data/organization

Stage 1 acceptance remains OPEN with its existing provider-review/audio gates;
funded Claude and reliable meetings remain deferred final launch gates.
