# Aedrova website and managed AI

Python/FastAPI website, short optional onboarding, Google sign-in via Supabase PKCE,
workspace-scoped Stripe billing and a server-side model gateway. The desktop keeps local
coding, its existing permissions and review flow. Shared provider keys never enter the app.

Run the local preview from this directory:

```sh
uv sync
uv run uvicorn aedrova_site.app:create_app --factory --host 127.0.0.1 --port 8090 --no-access-log
uv run pytest -q
uv run ruff check aedrova_site tests
```

Preview checkout/download/provider calls are disabled. All marketing questions are optional.
Answers stay in the browser; a valid nickname transfers when creating a new workspace. The
original agent name is Aedrova, and teams may choose another name. Screenshots are captures of
the actual Qt application with local sample data. Agent progress is explicitly a demonstration.
Scenery cycles every five seconds and respects pause/reduced-motion preferences.

The approved retail prices are $10/week and $49/month, with enterprise pricing agreed directly.
The initial beta policy includes $1/week or $10/month of provider usage, shared by the workspace,
one active run, hard budget reservations, no automatic overages. Monthly is positioned around
its larger AI allowance rather than falsely claiming cheaper calendar-month billing. Optional
credits are a separate explicit $10 purchase providing $5 of AI usage; they carry over, require
an active subscription to use, and never auto-refill. Included allowance is consumed first.
These are initial commercial choices, not measured production unit economics.

Setup, live acceptance and release gates: [docs/owner-setup.md](docs/owner-setup.md).
Local verification and limits: [docs/milestone-9.md](docs/milestone-9.md).
The Git remote is connected; no commit, push, deployment or public charge has been performed.
