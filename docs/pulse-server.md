# Pulse service

`aedrova_site/pulse.py` is installed in the existing FastAPI service, using its existing
JWT/cookie authentication and Dot authorization. It introduces no separate public site.

- GET `/api/pulse?workspace=<uuid>&period=7d`: cached authorized projections, source
  statuses and recent observed activity. No external provider reads. Supported periods:
  `24h`, `7d`, `30d`, `90d`, `12m`.
- POST `/api/pulse/refresh`: strict `{workspace, dot, period}` body; one authorized
  source, up to three bounded overview tools. Existing CSRF rules apply to cookies.
  Requests are rate limited. Partial failures return safe tool IDs, not API payloads.
- `dot_evidence_cache` joins the existing private encrypted store. The encryption key
  and database must persist. Cache reuse binds Dot/user/workspace/version/tool to the
  exact grant fingerprint; no raw provider token or evidence reaches public tables.
- Explicit refresh bypasses the five-minute cache; agent reads reuse the same evidence.
  Failed reads retain labeled stale evidence when authorization is still valid. Cache
  data expires within 24 hours, never beyond grant expiry. Webhooks invalidate freshness.
- Membership, live identity version and grant are rechecked before a snapshot is returned.
  Disconnect/remove purge cache. Sensitive data is never stored in desktop preferences.

GitHub currently projects observed commits, sampled open PRs and deployment records.
Other providers are registered/unavailable. Add real official provider authorization and
bounded tools to Dots, then a projection/overview capability in Pulse. No fake metric
fallback or global service-role analytics query is permitted. Period comparison and
anomaly claims require adequate actual history and a tested coverage contract.

No new public Supabase migration is required after the Dots migration. Restart the
shared service with its existing ignored configuration and Dots/GitHub App credentials.
The desktop and service must both run their updated versions. For owner consent/setup,
use the desktop repository's `docs/pulse.md` and `docs/dots.md`. Never paste secrets here.

The production website remains waitlist-only; no push/deploy or launch gate change was
performed. This feature still needs live configured-account acceptance after setup.
