# OpenAI connection — private owner setup

The provider path already uses OpenAI Responses through Aedrova's shared server.
The Mac receives short-lived, workspace-authorized run tokens, never the provider
key. This setup retains usage reservations, concurrency limits, membership checks,
revocation and conservative accounting for interrupted calls.

## Required owner action now

Run this in your Mac's Terminal:

```sh
cd /Users/ayanshvarma/Documents/Aedrova_site
.venv/bin/python scripts/setup_openai.py
```

Enter the paid OpenAI key at the hidden prompt. Do not paste it into chat. The command
checks the configured model through GET /v1/models/{model}; it sends no inference
request. On success it saves `.env.openai` with owner-only permissions (0600), excluded
by Git and Docker. Invalid credentials don't create or overwrite the file.

Reply **ready** after success. No new Supabase SQL is needed for this step.

## Activation after credentials are verified

The setup does not silently activate paid requests or bypass workspace entitlement.
The internal meeting-service launcher now supports `--with-openai`, loading the
private key and OpenAI-only `config/models.openai.json`. Its default still keeps
managed AI disabled. Public checkout, release downloads and production flags stay
closed. Restarting a service can interrupt meetings; finish active calls first.

The next acceptance checks are: authorized workspace allowance, explicit included
AI desktop mode, one bounded real request, usage reconciliation, context/source
permissions, and failed/revoked access. Local-mode desktop builds still use the
existing provider CLI login until explicitly rebuilt for included access. A paid
provider key is not a substitute for an Aedrova workspace allowance.

For Render activation later, use Environment/secret storage for `AEDROVA_OPENAI_KEY`,
`AEDROVA_MODELS_FILE=config/models.openai.json` and the separately approved gateway
flag. Do not upload the local credential file or put the key in GitHub. Changes in
this task have not been pushed or deployed; the public site remains waitlist-only.

## References

[OpenAI authentication](https://developers.openai.com/api/reference/overview)
requires server-side secret handling. The OpenAI-only model file preserves the
existing tested GPT-5.3-Codex configuration and its standard token rates, checked
against [official pricing](https://developers.openai.com/api/docs/pricing) on
October 7, 2026. It does not assume every account has model access; the credential
probe verifies that separately. A successful model lookup does not certify a paid
inference or a full build; those remain acceptance tests after activation.

## Local acceptance completed — October 7, 2026

The saved key passed model access and a real Responses request. A fresh Google
session then authorized an owner-scoped gateway request and the bundled Codex
runtime created and verified a real file in an isolated temporary Git project.
No user project was modified. The preview app was rebuilt with explicit included
AI mode and loopback origin `http://127.0.0.1:8090`; the API key is not bundled.

The **Aedrova showcase** workspace (`6047c111-9eda-477d-a0d1-e9d5d831227e`)
has a $2 owner-funded **development** allowance for 24 hours, one concurrent build,
and a hard usage stop. This is not a Stripe subscription. Other users/workspaces
cannot spend it. Fresh owner/admin membership is checked at run creation and each
inference. Production, public origins, PostgreSQL, checkout, waitlist and release
mode cannot enable this development funding. Running the grant again does not
reset usage or renew expiry. The acceptance build consumed about $0.271 total
through the gateway, leaving about $1.729. Usage reservations reconciled to zero.

### Required owner actions to try a task

1. Use the rebuilt `Aedrova/dist/Aedrova.app` and sign in with the same Google account.
2. Select **Aedrova showcase**, choose **Codex** for its connected project, and
   connect the local project folder if it is not already connected.
3. Mention your named agent with a small task. Existing automatic planning,
   isolated builds, review/apply and publishing approvals still apply.

The local service must stay running. Restart it after a reboot with:

```sh
cd /Users/ayanshvarma/Documents/Aedrova_site
uv run python scripts/run_local_meetings.py --with-openai
```

To fund a different local validation workspace, first sign in at
`http://127.0.0.1:8090/account` as its owner, then use the trusted operator script
with that exact workspace UUID:

```sh
AEDROVA_DEVELOPMENT_AI=true uv run --env-file .env.meeting-server --env-file .env.openai python -m scripts.grant_development_ai WORKSPACE_UUID
```

This command never accepts or displays provider/session credentials. It verifies
fresh Supabase membership using the encrypted server session. It refuses to
replace an existing subscription or another account's grant. Expired or exhausted
grants require deliberate operator review; they never auto-refill.

Public included AI, live checkout and Render provider secrets remain separate
release work. Claude Code requires its own provider setup; there is no fallback
from Codex to an unconfigured provider. No new SQL is required for local funding.
