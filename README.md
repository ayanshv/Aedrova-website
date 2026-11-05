# Aedrova website and services

Your team, plus Agents

This Python/FastAPI project serves [aedrova.com](https://aedrova.com/), the public product pages, onboarding, waitlist, account flows, workspace billing, and managed services used by the Aedrova desktop app.

## What is included

- Responsive product pages with real desktop screenshots, Bud illustrations, light/dark appearance, and reduced-motion support.
- Optional website onboarding, referral attribution, pricing, downloads, team information, FAQ, support, and policy pages.
- Google sign-in through Supabase PKCE and workspace-scoped account management.
- Stripe checkout, portal integration, webhook handling, entitlements, and checkout idempotency.
- Managed AI access with quota reservations, concurrency controls, request limits, and spending protection.
- Bud OAuth connections, lifecycle handling, and permission-scoped provider access, including Buffer social workflows.
- Private attachment verification, voice-message support, and configured meeting/transcription services.
- Search metadata, canonical URLs, crawler rules, sitemaps, and independent Cloudflare fallback workers.

Public access is controlled by release configuration. Waitlist mode keeps public checkout and installers gated. A page or provider implementation does not establish production approval. See [owner setup](docs/owner-setup.md) and the [desktop release timeline](https://github.com/ayanshv/Aedrova/blob/main/docs/pre-launch-timeline.md).

## Local preview

Use Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen
uv run uvicorn aedrova_site.app:create_app --factory --host 127.0.0.1 --port 8090 --no-access-log
```

Open http://127.0.0.1:8090. Local preview uses the configured database and service settings. Real provider calls require explicit configuration.

Runtime configuration is defined by `aedrova_site/config.py`. Settings use the `AEDROVA_` environment prefix. Keep database credentials, encryption material, provider secrets, Stripe credentials, and webhook secrets in private environment or secret-file settings.

Follow [owner setup](docs/owner-setup.md) before connecting hosted services. Use separate staging credentials and databases for acceptance work.

## Plans and billing

The public catalog is defined in `aedrova_site/policy.py`.

- Free includes 1 Bud.
- Pro is $15 monthly or $120 annually per workspace, with up to 5 Buds.
- Team is $25 monthly or $250 annually per workspace, with up to 15 Buds.
- Enterprise is configured by agreement.

One workspace subscription covers its eligible members. Pricing, AI allowances, active promotions, Stripe price IDs, and entitlements are separate configuration concerns. Match them before enabling commercial checkout. The temporary early-access offer uses a shared deadline and does not automatically charge users.

See [Stripe live setup](docs/stripe-live-setup.md) and [sandbox setup](docs/stripe-sandbox-setup.md).

## Verify

```sh
uv run ruff check aedrova_site scripts tests
uv run pytest -q
uv run python -m compileall -q aedrova_site scripts
uv run python -m scripts.check_release_secrets
```

GitHub CI also validates the PostgreSQL schema, crawler-worker behavior, deployment image, startup, and database readiness. Browser checks require the Playwright browser dependencies for the environment.

## Repository layout

- `aedrova_site/` contains FastAPI routes, configuration, billing, provider services, and persistence.
- `aedrova_site/templates/` and `aedrova_site/static/` contain server-rendered pages and browser assets.
- `sql/` contains website schema and setup scripts.
- `deploy/` contains deployment and Cloudflare discovery/error fallback components.
- `scripts/` contains schema, release, and asset verification tools.
- `tests/` contains service, authorization, billing, and website regressions.
- `docs/` contains deployment instructions, integration setup, and acceptance evidence.

## Deployment and release

The existing Render service builds the repository's Docker image from the protected `main` branch. Changes go through a pull request and required checks before merge. Verify the public site after deployment.

Production rollout requires reviewed migrations, working support and disclosures, provider approvals, billing acceptance, and signed desktop downloads. See [domain deployment](docs/domain-deployment.md), [owner setup](docs/owner-setup.md), and [Buffer integration](docs/marketing-social-buffer.md).

The desktop application lives in [ayanshv/Aedrova](https://github.com/ayanshv/Aedrova). Contact contact@aedrova.com for product and support questions.
