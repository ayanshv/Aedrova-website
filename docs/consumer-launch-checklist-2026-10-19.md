# Public-site safety checklist — October 19, 2026

Owner requested all 20 items in IMG_6604.jpeg plus SQL-injection prevention. This
record distinguishes implemented controls from legal/business or live acceptance.
No code or policy can make liability protection “bulletproof.” Paid launch remains
closed until the actual operator and applicable consumer obligations are finalized.

1. Privacy policy: retained the existing 25-section factual policy; updated age,
   optional preference storage and encrypted unsubscribe/suppression disclosures.
2. Terms: retained the existing 27-section terms, consumer-rights reservations and
   AI/connector limits. Operator/address placeholders remain explicitly unresolved.
3. Refund policy: added /refunds and footer/support links, consistent with existing
   terms, explaining request, cancellation, review and mandatory consumer rights.
   No new refund window, fee, tax decision or payment activation was invented.
4. Cookie policy: /cookies now explains essential choice storage versus optional
   persistent preferences, browser clearing, no advertising/analytics and lifetimes.
5. Consent banner: equally prominent Essential only/Allow preferences buttons,
   no preselected optional storage and a footer control to change the choice.
   Site JS holds new optional values in page memory until permission. Existing
   optional values are not read without permission; Essential only removes them.
6. Form consents: waitlist marketing and minimum-age/guardian confirmations are
   separate unchecked required boxes, enforced with strict booleans server-side.
   Enterprise inquiry explains response-only processing, not marketing signup.
   Existing checkout still requires explicit workspace renewal confirmation.
7. Data minimization: no date of birth collected; no new tracking SDK, full address
   or payment data requested. Referral detail remains optional/bounded. Suppression
   stores a minimal registration hash/reference rather than another raw email.
8. SDK review: public templates load local JS, CSS, fonts and media, not third-party
   analytics/ad scripts. Provider sign-in/payment pages remain independent. Backend
   locked dependency audit passed. /subprocessors lists actual service categories;
   provider contracts, residency and production settings still need owner review.
9. Dark patterns: equal storage choices; no cookie wall, prechecked marketing or
   manufactured urgency. Clear renewal/cancellation and launch availability notices.
   Preparation animation does not claim to allocate paid capacity or create a workspace.
10. Hidden fees: recurring price/interval, per-workspace coverage, applicable taxes
    and third-party usage remain disclosed. No automatic AI overages; no seat fees.
    Final live Stripe product/price/tax parity must be accepted before checkout opens.
11. Fake reviews: no public testimonials, customer counts or aggregateRating markup
    were found; none added. Product screenshots are described as preview captures.
12. Unsupported claims: preview/provider limitations retained; Free price no longer
    says “forever”. No SOC 2, E2EE, guaranteed uptime, unlimited AI or search-ranking
    guarantee introduced. Advertising availability still requires live certification.
13. Alt text: checked public page images for alt attributes; product captures use
    descriptive alternatives, decorative images/Buds use empty alt or aria-hidden.
14. Contrast: fixed low-contrast team-avatar text and demo diff red/green, including
    dark variants. Checked core muted/action colors. Not a WCAG certification or a
    substitute for a full assistive-technology audit of desktop and all visual states.
15. Keyboard: skip link now explicitly targets focusable main; tested actual mobile
    keyboard focus and Enter for storage controls. Existing menu Escape/focus trap,
    modal focus/reduced motion preserved; no positive tabindex added.
16. Business details: brand contact@aedrova.com and (408) 634-5254 displayed. Actual
    legal operator, authorized business address and jurisdiction remain placeholders
    by owner's prior instruction. These are unresolved commercial-launch gates.
17. Children: under-13 use prohibited under current policy; explicit waitlist
    eligibility confirmation now enforced without collecting DOB. No child-directed
    onboarding or parental-consent system is represented as implemented. Counsel
    must approve age policy and account-level eligibility before consumer launch.
18. Unsubscribe: /unsubscribe requires explicit POST confirmation, not GET/link
    scanner visits. Fernet tokens are purpose-bound and hide email; invalid/wrong
    purpose tokens fail closed. Export now includes unsubscribe_url and skips valid
    suppressions. Repeat confirmation is idempotent and does not erase auth sessions.
    No marketing-email sender is configured or mail sent. Operator must regenerate
    the export immediately before sending, include each URL, sender identity and
    valid postal address, and configure suppression in the eventual mail provider.
19. Licensing: existing Instrument Serif OFL notice and Pexels media provenance are
    present; fonts/media self-hosted. Screenshots/brand/Bud source provenance and all
    distributed open-source notices still require ownership/release review. Do not
    infer a legal license for every image merely from its presence in the repo.
20. Deletion: visible /data-controls#requests and support process already describe
    identity/authority verification, export/deletion scope, backup limits and billing
    distinction. Operator-only verified waitlist removal tooling exists. No public
    unauthenticated endpoint can erase an account or whole workspace.

## SQL-injection prevention

Reviewed SQLAlchemy text/execute sites. Values are passed in parameter dictionaries;
remaining dynamic schema, operation and lock/cursor clauses come from source constants,
not request text. No request-controlled SQL interpolation was found. Added adversarial
regressions for OR/UNION/DROP input across sessions, rate limits, lookups and billing
locks, asserting attack text never appears in executed SQL and other sessions survive.
Added an AST regression rejecting direct f-string/format interpolation at text sinks.
Do not “sanitize” SQL by deleting apostrophes from messages: parameter binding is the
protection. Restricted backend role/RLS and existing resource authorization remain
separate defense layers. No general security guarantee is claimed.

## Deployment and evidence

Full audit details: security-audit-2026-10-19.md. New tests: checklist_security,
checklist_browser; prior full suite 568 passed before final browser/contrast checks.
Final test/deployment evidence will be recorded after publication. New public opt-out
and refund routes are included in the route inventory; opt-out is noindex/no-store.
Prepared exact-path robots Worker is independent of the sleeping Render origin.

## Consolidated owner actions before commercial launch

- Finalize operator, incorporation/ownership, lawful business/postal address and
  market/age eligibility with qualified legal/tax advisers. Replace placeholders in
  policies, Stripe and public notices consistently. No third party's address may be
  used without authorization.
- Approve final consumer/refund/renewal terms for actual markets and product behavior.
- Before sending launch emails, configure a sender with domain authentication,
  opt-out/suppression handling and a valid sender postal address. Use newly exported
  contacts/URLs, never stale CSVs; export alone does not send or unsubscribe at a
  third-party mailing provider.
- Supply ownership/license evidence for custom assets and complete independent
  security/accessibility review and the remaining hosted acceptance gates.

Primary references reviewed October 19:
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/
- https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
