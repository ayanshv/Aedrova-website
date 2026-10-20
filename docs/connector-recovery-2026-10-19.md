# Connector browser recovery and actual error-page logo

BrowserErrors previously replaced every browser HTTP error, including our own OAuth
account-mismatch recovery page. Explicit server response marking now preserves the
actionable template while stripping the internal marker before sending. API errors,
generic sanitized errors and state/account/proof/CSRF checks retain their contracts.
Unknown/expired authorization states render a fresh-link explanation that sends the
user back to the Bud for a new attempt, rather than suggesting another Google login.
Actual brand.png is embedded as a data URL in standalone errors, so origin outage
fallback does not depend on fetching the logo from a broken origin. Export regenerated.

Validation: 571 full local tests passed, 67 focused browser/OAuth follow-ups passed,
13 edge fallback tests passed, Ruff and diff checks passed. Tests cover a real browser
Accept header preserving account recovery, no internal response marker leakage,
expired state recovery, logo inclusion, status/CSP preservation and no secret leaks.
No new provider grant, credentials, scope, paid service or commercial gate change.
Cloudflare whole-site outage fallback remains unactivated; source export is ready,
not proof of live edge routing. Free-host wake latency remains an operational limit.
