# Checkout transaction idempotency

Subscription and optional-credit Checkout Session creation both send explicit Stripe
SDK idempotency_key options. Stripe's SDK sends these as Idempotency-Key headers.
Customer creation already uses its separate workspace-scoped Stripe key.

The client retains a transaction request ID per workspace/purchase kind for retries.
Credit checkout now shares the same retained-ID behavior as subscriptions. The
server hashes the scoped transaction ID; its checkout reservation prevents another
transaction from opening while a checkout is pending. Cached successful requests
return the original URL. Uncertain failures keep the reservation and may retry the
same Stripe key, never a replacement key.

Before sending a create request, the server atomically persists an encrypted copy
of the complete Stripe parameters, including its key and expiry, in the existing
private sessions table. Concurrent workers use the first committed snapshot. Stripe
API secrets are excluded and rejected by the snapshot helper. Later retries retain
identical metadata, names, expiry, price, URLs and branding even if inputs change.
Expired checkout reservations reject replay; keys are never recycled to restart an
expired transaction after Stripe's retention window. A new purchase needs a new
transaction. Existing webhook deduplication remains in place for entitlement/credit
application. This prevents duplicate Checkout Session creation for one transaction;
it is not a guarantee against separately authorized purchases using new IDs.

No schema or credential migration, price change, checkout enablement or real payment.
The existing durable database and stable encryption key must remain configured.
Losing the database destroys local transaction history; no replacement key should
be generated automatically to work around an uncertain result.

Validation includes simulated response loss for both session types, retries after
a clock advance and workspace rename, concurrent snapshot writers, cached retries,
secret rejection, and real Stripe SDK header capture using an offline HTTP client.
Existing billing webhook and duplicate-event tests continue to pass. No real Stripe
transaction was submitted. Live paid acceptance remains a release gate.

Stripe reference: https://docs.stripe.com/api/idempotent_requests
