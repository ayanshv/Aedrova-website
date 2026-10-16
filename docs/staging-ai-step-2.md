# Staging AI activation — October 15, 2026

Prepared, not deployed. Authoritative implementation and consolidated owner handoff:
Aedrova desktop repository docs/ai-responsiveness-step-2.md.

Use deploy/staging-ai.env.example only on aedrova-beta-staging after the specific
key-transfer/inference approval. Existing production and staging credentials,
database, encryption and connector settings must not be replaced by the example.
The overlay enables the existing funded OpenAI model and Free access, preserves
shared plan limits, and adds a $1/month staging accounting ceiling. It does not
open public checkout/downloads or purchase hosting. Validate /health, real authenticated
requests, owner-activated Free allowance and metered settlement after deployment.

Existing OpenAI key/model lookup and real loopback inference passed. Anthropic
key/model lookup passed but inference returned a credit-balance rejection; leave
Claude disabled until its owner funds the provider and approves its deployment.
No secret values are included in this document or the deployment overlay.
