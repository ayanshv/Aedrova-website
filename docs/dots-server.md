# Dots shared service

Implementation: `aedrova_site/dots.py`, installed into the existing authenticated
FastAPI application. Grants and short-lived authorization sessions are encrypted by
`Store.cipher` and held in the existing private database schema. Public Dot identities
are fetched through the user's Supabase JWT/RLS; privileged Supabase keys are not used.

Read the desktop repo's `docs/dots.md` for migration, exact GitHub App setup, scope,
revocation and live acceptance steps. The app code and server must be updated together.

Local setup: copy `deploy/dots.env.example` to ignored `.env.dots`, fill the GitHub App
client ID/secret locally, and layer it over the existing local server env file using
`uv run --env-file <existing-server-env> --env-file .env.dots uvicorn aedrova_site.app:create_app --factory --host 127.0.0.1 --port 8090 --no-access-log`.
Set the local origin to `http://127.0.0.1:8090`; use the existing encryption key and DB.
Do not run another listener on the same port; restart the current service instead.
If the current service is launched with meeting/billing env files, preserve those files
and flags. Never print them or move secrets into public desktop config.

GitHub callback: `<AEDROVA_ORIGIN>/dots/github/callback`. Same Aedrova Google account
must be authenticated in the desktop and browser; first authorization can route through
Google and return to GitHub. OAuth states are single-use, PKCE-protected, browser-bound,
workspace/user/version-bound and expire after ten minutes.

The production waitlist service is unchanged. It cannot complete Dot authorization
while sign-in is gated. Do not turn off the waitlist launch gate or enable paid services
without approved release work. A private hosted API deployment is a later setup step.

GitHub tools are read-only and capped; other initial providers are metadata-only and
unavailable. No mock data is returned by production routes. Tests use an injected
HTTP transport. Do not market the other providers as live integrations.
