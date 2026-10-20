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

## Activation result

Owner approved October 15. Render staging deployment dep-db8o043l550s73ej2i90 is
Live, reusing backend e375bdc. Saved gateway/model/cap settings and live health were
verified. Real fresh native-session main/Bud replies, private assistant save/reopen
and metered settlement passed. See the desktop Step 2 record for exact timings,
coverage and limitations. Production/checkout/downloads remain unchanged.

Required owner credential rotation before broader testing: the masked Render field
was unexpectedly exposed in a browser automation DOM snapshot. No credential was
committed. Create replacement in OpenAI privately, update staging OPENAI_KEY and
SPEECH_KEY if shared, save/deploy, revoke old key and update ignored local config.
Do not paste credentials into chat. Repeat hosted smoke after replacement. Claude
remains separately unfunded and disabled. The pending wording above is historical;
this record supersedes it for the actual deployment status.

October 15 owner decision: retain the existing OpenAI key; do not generate or revoke
keys. Desktop automation runtime was cleared and tracked desktop source/Step 2
artifacts were checked without printing the credential. This cannot erase the
earlier tool output or undo the exposure. No Render settings or credentials were
changed in the follow-up. Rotation above remains the original recommendation,
not a newly required owner action. See desktop docs/workspace-ai-setup-step-3.md.
