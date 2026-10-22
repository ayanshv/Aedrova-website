# Shared early access — owner-approved October 21, 2026

Status: pricing/countdown and server enforcement implemented. Public site remains
waitlist-only; this does not open app downloads, remove release gates or activate AI.

## Fixed window — do not restart it

Owner chose a single shared promotional period, NOT 60 days per signup/workspace.
Recorded start: October 21, 2026 9:58:40 p.m. Pacific (2026-10-22T04:58:40Z).
Original 60-day duration was extended at owner's request to finish the final day
at 11:59 p.m. Pacific. Hard cutoff: December 20, 2026 11:59:59 p.m. Pacific
(2026-12-21T07:59:59Z). This is the same deadline for all eligible participants.
Late arrival, reactivation, reload, tier change or server redeployment does not
create a fresh 60 days. Do not silently extend/reset the promotion. Any future
change requires owner approval and truthful updated public disclosures.
Canonical schedule: aedrova_site/promotion.py. Server calculates remaining seconds;
browser advances them with a monotonic clock, not its editable date/localStorage.
At cutoff the discount/countdown disappear and planned regular prices return.
No-JavaScript responses also use current server state.

## Public presentation

Pro and Team: legible subtle strikethrough on regular price and large $0.00.
Monthly/annual switch preserved. Pro 3 teammate icons, Team 5. Free and Enterprise
unchanged. Public catalog remains Pro $15/month or $120/year; Team $25/month or
$250/year, all per team. These are planned rates, not a claim of prior paid sales.
Terms disclose the shared deadline, late-join limit, plan caps, waitlist restriction,
no card/subscription/automatic charge, and fallback to Free where available.

## Access and cost enforcement

AEDROVA_EARLY_ACCESS_ENABLED defaults false. Enabling requires FREE_ENABLED=true
and waitlist mode off, with the existing configured AI/speech requirements. This
flag is NOT enabled on production by the marketing update. No owner action now;
configure it only as part of the authorized Beta/public release, before the cutoff.
A new independent workspace can receive a Team-capacity gift at ordinary workspace
creation (already-authenticated CSRF-protected POST). Existing eligible Free spaces
use the existing owner/admin Start Free flow, without Stripe or a subscription.
No extra subscription activation, payment method or renewal commitment is needed.
Subspaces share their parent, and cannot obtain a separate promotional allowance.
Existing paid/pending/development records are not overwritten or refunded.

The gift has the fixed server deadline, no subscription and a synthetic Free customer
reference. Retries do not reset counters/extend access/switch tier. User-supplied
expiry/time/price values are ignored. Monthly Pro/Team, request, rolling five-hour,
run/concurrency and company limits remain. Gifts additionally consume the aggregate
Free pool and shared funding-owner budget across workspaces. There is no unlimited
AI or automatic overage. No increased budget ceilings or provider spending was
activated by this change.

Every new inference reservation rechecks entitlement; the clock/flag is not just
UI. At expiry or kill-switch disable, gift spaces fall back to Free where enabled
and Free concurrency, without payment. Existing paid subscriptions keep their actual
state. New live paid checkout is blocked throughout the shared promotion, even if
an operator mistakenly enables checkout without enabling gift grants. Explicit
Stripe test-mode checkout remains available for isolated regression tests.

## Before launch / after expiry

Keep existing signing, security, legal-operator and release gates. Grant configuration
must be deployed/verified in staging and enabled only within the authorized release.
The fixed countdown is already running while the public site is waitlist-only; it
will not wait for launch. If launch happens after cutoff, do not advertise $0 or grant
this expired offer. No promised full 60 days for a later registrant.
Before enabling regular sales, complete the separate four-SKU Stripe catalog
migration, actual business/merchant verification and full billing lifecycle tests.
Legacy retail billing keys were not rewritten by this offer. No Stripe resources,
existing subscriptions, cards, hosting payments or current legal entity were changed.

The public /api/early-access clock-sync endpoint is read-only, returns no account
information, has no-store responses and a 120/minute per-IP bound. Plans resync
once per visible minute and on returning to the tab so sleep/device-clock changes
do not reset the offer. The backend deadline still decides actual entitlement.
No GET endpoint activates a grant. Current production/staging flag state was not
changed by this code update; grant activation/live-user acceptance is a release gate.

Validation: 589 full website/backend tests passed. Coverage includes start/end
boundaries, shared late-join/replay expiry, no usage replenishment, concurrent
attempts, owner/Free-pool limits, kill switch, paid-plan preservation, CSRF and
workspace authorization, post-expiry Free activation/concurrency, no paid checkout,
public clock-sync rate limit/no account data, no-JS expiry, browser clock spoofing,
server resync/reload and in-place countdown expiry. Desktop/mobile screenshots
reviewed. Ruff, diff and release-secret scan checks passed.
