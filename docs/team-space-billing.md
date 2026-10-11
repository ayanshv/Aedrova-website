# Team pricing and Space billing — October 11, 2026

Owner-authorized implementation during Stripe bank-account configuration. Existing
prices and tier keys remain Pro/monthly $10 and Team/annual $200, USD, per entire
independent team Space. Members do not purchase subscriptions or add quantity to
Stripe's single line item. Website stays in waitlist mode; no paid launch authorized.

## Architecture

Supabase is the single source of truth for hierarchy and membership. Additive
`202610110001_space_billing.sql` adds `workspace_parents`, private configurable
limits (depth4,100 descendants), authorized context/create/move functions and a
restricted backend-only resolver. Existing Spaces remain independent. Subspace
creation does not touch Stripe or the billing database. Access to the origin AND
root is required for billed AI; inviting into a child alone never grants root access.
Moves require the same actor to own both billing roots and the child, explicit UI
confirmation, current-parent compare, no cycles, all subtree members already in
the destination, and depth/count bounds. Context/files/connectors stay with the
child; only subsequent billing attribution changes. No independent conversion
flow existed, so none is silently introduced.

The existing private SQL ledger reserves all managed AI costs atomically. Runs
retain their origin; every inference has immutable billing root/origin/user/provider
attribution. In production the root is resolved in the reservation transaction
under the hierarchy advisory lock, serializing with moves. Settlement uses the
recorded root, even after a move, and remains idempotent. Chat, Buds, builder and
research use the managed gateway; enabled meeting transcription uses the same
ledger. BYOK/local provider execution remains externally billed, not platform
credits. Unimplemented media/background products must adopt this gateway before
launch; ordinary chat/connectors/files do not consume credits.

Monthly included capacity follows the subscription anniversary, including monthly
windows within annual subscriptions and end-of-month clamping. Free and company
anti-abuse pools retain UTC calendar windows. Rolling five-hour included capacity
shares the root and is configurable per plan via `five_hour_budget`; initial values
match existing monthly caps, with no invented allowance increase. Explicit optional
purchased credits retain existing wallet semantics and do not silently refill or
charge a card. Company ceilings still account for the full provider estimate.
Private estimated costs remain normalized in existing micro-USD units with central
model rates; the public UI shows capacity, not provider cost balances.
Owner/admin usage warnings are shown in team billing at default75/90 percent,
configurable via `AEDROVA_BUDGET_ALERT_THRESHOLDS=75,90`; the ledger deduplicates
threshold records. These are in-product billing warnings, not outbound emails.

## Files

Native account creation, workspace tooltips, preferences, identity snapshots;
Supabase migration/tests and database runner. Website policy/config, budgets/Store,
Identity/Payments, account/Space APIs, gateway/speech, pricing/account templates,
site CSS/JS and Stripe provisioning. Focused ledger and billing tests accompany them.

## Required before activating subspaces

1. Owner: Supabase **Aedrova Staging** → SQL Editor → New query. Run
   `supabase/migrations/202610110001_space_billing.sql` from this repo. This is an
   additive schema/authorization install, not a fixture or full schema reset. Never
   run `supabase/tests/space_billing.sql` against hosted data.
2. Agent after that confirmation: enable `AEDROVA_SPACE_HIERARCHY_ENABLED=true`
   on the staging backend, deploy the matching backend/native build, validate actual
   two-member creation/nesting/moves/AI usage. Do not enable it without the migration.
3. Only after staging acceptance and production rollout approval: apply that same
   migration to production, verify the backend resolver role grant, then enable the
   flag. Existing subscriptions, customers, history and allowances are not reset.
   Disabling the creation flag does not detach existing children: the installed
   backend resolver continues enforcing their parent billing pool. Never remove
   that resolver while children exist or reinterpret them as billable roots.

Native discovers the installed context RPC; missing migration leaves independent
creation intact. The server feature gate controls availability and fails closed
when enabled but unresolved. Root sharing is implemented but **not yet activated
or live-accepted** until these steps.

## Stripe configuration and acceptance

Owner finishes the bank account personally. No bank detail is entered by the agent.
Provisioning now names the shared product **Aedrova Team — Workspace subscription**,
with entire-team description and per-team Price nicknames, updating linked existing
Aedrova products without changing their immutable Price amounts or creating seats.
Before launch, apply this presentation in the correct Stripe environment, verify
both existing approved Price IDs ($10/month, $200/year,quantity1), owner contact,
portal renewal/cancellation, receipts, signed webhooks and a real hosted checkout.
The backend passes workspace name, root ID and team coverage to Checkout, and uses
the actual workspace owner as billing contact even if an admin initiates checkout.
Checkout remains gated; no live charge or bank test is performed in this task.

Automated billing lifecycle tests cover retries, renewal, cancellation, payment
failure, entitlement changes, signatures and customer mapping. Actual hosted Stripe
checkout, receipts/emails and paid renewal require separate live/sandbox acceptance;
a test double is not live acceptance. Cluely footer/legal depth review is saved for
Phase5; it is not being executed now.

## Verification at handoff

Native suite: 733 passed. Website suite: 439 passed. Ruff checks and the real
PostgreSQL migration/RLS suite passed, including the new Space tests. Browser
pricing checks covered desktop and mobile. Hosted Stripe acceptance and staging
hierarchy activation remain pending; these are not represented as completed.
