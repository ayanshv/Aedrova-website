# Anthropic private setup and acceptance

Run directly in Terminal:

```sh
cd /Users/ayanshvarma/Documents/Aedrova_site
uv run python -m scripts.setup_anthropic
```

Paste your Anthropic API key only at the hidden terminal prompt. Never send it in
chat. The script calls GET /v1/models/{configured_model} on api.anthropic.com with
the required API-version header. It runs no Messages inference. A successful exact
model lookup saves .env.anthropic atomically with mode0600, ignored by Git and
excluded from Docker. Failed verification preserves any existing file.

The selected model and rates are inherited from the existing beta configuration;
no new pricing or capability claims are made by this setup. An unavailable model
must be explicitly reviewed; no automatic fallback or silent model substitution.
Before paid inference, verify current rates and supported CLI features, prepare an
authorized test workspace allowance, and approve a bounded request/maximum spend.

Gateway activation remains separate. --with-anthropic is an explicit loopback
validation option for scripts/run_local_meetings.py, using Claude-only models.
Combining it with --with-openai loads both saved keys and the existing dual-model
configuration. Both modes retain local development-only entitlement, membership,
reservations and provider binding; production/checkout/download flags stay off.
Do not start the launcher merely to check a key or restart active meetings. No key
is bundled into desktop assets. No production secret upload is part of setup.

A metadata lookup is not a paid-inference or complete Claude Code acceptance test.
Missing keys, current pricing, actual requests/accounting, fresh runtime and staging
acceptance remain Phase2 gates.

Official API: https://platform.claude.com/docs/en/api/models/retrieve

## Private setup accepted

Owner saved the key; independent fresh metadata access verified claude-sonnet-5-5
and regular0600 local storage. No inference or service activation occurred. Official
standard pricing rechecked: input$2/output$10 per million; cache5m-write$2.50,
1h-write$4 and read$0.10. Cache read config corrected from the older $0.20 baseline.
Gateway rejects premium region/speed overrides before reserving or calling provider.
Source: https://platform.claude.com/docs/en/about-claude/pricing .
Live requests, staging gateway and full Claude Code/runtime acceptance remain open.
