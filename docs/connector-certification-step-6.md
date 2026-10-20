# Connector live acceptance — October 15–16, 2026

Authoritative results/owner handoff:
/Users/ayanshvarma/Documents/Aedrova/docs/connector-certification-step-6.md.

GitHub/Supabase/Figma/Notion passed actual staging callbacks, scoped resource
selection, real reads, local disconnect and denied reads afterward. GitHub also
passed fresh reconnect. All four test grants removed; native session signed out.
Instagram/TikTok reach actual provider login but need signed-in test accounts.
Stripe/Vercel/Search authenticated starts correctly reject missing owner setup.
No all-nine launch certification, live renewal or provider-global revocation claim.

Fix a55cf9d adds standard OpenID scopes to browser Google handoffs, retaining PKCE.
It deployed Live on staging (dep-db8s578n74is73cknu6g); fresh product handoff reached
provider pages. Shared Notion app was reduced to No user information, preserving
Read content; reloaded consent verified page-only access. No email/profile data read.
Fix 6a3cc90 gives cancelled OAuth a branded recovery screen without claiming access;
regression preserves failed state and cookie removal. Full suite 528 passed after
changes; Ruff/diff pass. 6a3cc90 is Live (Render reports success, 1m03s). A reused live cancellation URL
still returned 403; fresh valid live cancellation remains separately unaccepted.

Existing eight credential additions and saved callbacks remain intact. No new key,
broader grant, purchase, production deployment or installer release. No privacy
policy claim of blanket account access. Current grants remain explicitly scoped.

Owner social checks: Aedrova Staging → Marketing Bud → Connectors → Instagram →
Connect your account → @aedrova_ai; then TikTok → approved @aedrova sandbox account.
Use fresh login buttons; leave read-only consent open. Never paste credentials.
Stop if TikTok reports maximum attempts. Stripe setup stays deferred until release.
Step 7 meeting reliability has not started and needs owner approval with remaining
external connector gates explicit. Public launch remains gated.
