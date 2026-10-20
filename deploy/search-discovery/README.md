# Stable public robots policy

This exact-path Worker avoids a sleeping Render Free service returning its own
Disallow-all robots policy. It uses the same public policy as discovery.py.

Regenerate: `uv run python -m scripts.export_search_discovery` then
`uv run python -m scripts.bundle_search_discovery`.
Tests: `node --test deploy/search-discovery/worker.test.mjs`.

The existing Cloudflare account has a starter Worker named `aedrovaerrorfallback`.
It currently has no domain routes and is not an active outage safeguard. The
embedded editor did not accept automation edits; no Worker deployment/route was
completed in this task. Do not mistake a populated local file for a live Worker.

Owner handoff if the editor remains blocked:
1. Cloudflare → Workers & Pages → aedrovaerrorfallback → Edit code.
2. Replace worker.js with the contents of worker-bundled.js from this folder.
   Click Deploy on the existing free plan; do not upgrade.
3. Domains & Routes → Add → Route: zone aedrova.com, pattern
   `aedrova.com/robots.txt`. Add `www.aedrova.com/robots.txt` as well. Do not use a
   wildcard whole-site route, custom domain or new DNS record. Preserve existing
   routes/settings. These routes serve only public crawler policy, never APIs.
4. Verify both HTTPS robots URLs return the full policy and public pages remain
   allowed, with GPTBot/ClaudeBot restrictions preserved. Then request Google robots
   recrawl and retry /product live inspection when Google's cache refreshes.

This Worker does NOT activate the separate branded 502 outage fallback. That
feature remains independently documented in deploy/error-fallback. Keep these
purposes separate until both are reviewed/tested together.
