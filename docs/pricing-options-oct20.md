# Approved public pricing — October 20, 2026

Pro: $15/month per team or $120/year per team.
Team: $25/month per team or $250/year per team.
Monthly is the default. A keyboard-accessible billing switch changes both cards,
with URL-based annual selection also working without JavaScript. Pro illustrates
three teammates; Team illustrates five. These are illustrations, not seat limits.
Free, Enterprise, existing AI capacity and workspace coverage remain unchanged.

The public paid cards retain Join waitlist. This is a marketing pricing update,
not activation of purchases or modification of existing subscriptions.
Legacy backend Stripe policy still has two historical keys (monthly=Pro,
annual=Team). It is intentionally not rewritten: deployed configuration would
otherwise fail validation, and existing entitlements must not be reinterpreted.
Before opening checkout, migrate to separate tier/interval identifiers and create
and verify four corresponding immutable Stripe prices. Then validate monthly and
annual checkout/webhooks/renewal/cancellation for each tier. No owner action is
required now; live billing configuration remains a prelaunch gate, not complete.

Validation: 574 full-suite checks passed, including 85 focused public-page, real-browser, waitlist, checkout and config
checks passed. Browser checks cover 3/5 icons, all four prices, keyboard switching,
reload persistence through URL, aligned desktop buttons, and 390/768px layouts.
