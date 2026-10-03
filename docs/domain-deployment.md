## October 2 follow-up: waitlist launch, deployment paused

The owner requested onboarding/hero repairs before publication and a waitlist-only public
website. `AEDROVA_WAITLIST_ONLY=true` is set in the blueprint. Public onboarding, account,
Google login, welcome and download pages redirect to the waitlist; existing internal beta
flows remain available when the flag is false. Checkout, managed AI and meetings must be
disabled in waitlist mode. Emails are encrypted in the existing private server session
store for up to one year, deduplicated, consented and rate limited. No email provider is
configured: signups are collected; launch messages must be sent separately when ready.
Operator export: in the server environment with its database/encryption configuration,
run `python -m scripts.export_waitlist /private/path/waitlist.csv`. The file is created
owner-readable only and never overwritten; it contains waitlist entries, not auth sessions.
Keep exported addresses private. Export does not send email.
Privacy/business contact and removal procedures still need owner finalization before
collecting real public addresses. No new Supabase SQL is needed for this website feature.

Render web configuration is staged in a browser form, not deployed. Database form is
staged at Oregon, PostgreSQL 18, $6/month compute + 1 GB at $0.30/month = $6.30/month
shown by Render, autoscaling disabled. No purchase or service creation occurred. The owner
must review and submit Create database/payment steps personally. GitHub already contains
the prior tested deployment baseline; the waitlist/UI changes are prepared for the authorized GitHub deployment push.
Render currently shows an empty workspace; the persistent database still has to be created
by the owner before importing the website blueprint. DNS/HTTPS acceptance is pending.

# aedrova.com — Cloudflare DNS and Render deployment

October 2, 2026. Owner bought aedrova.com through Cloudflare, confirms registrar email
verification and selected Render. The domain is not yet connected to a verified live
website. Buying a domain does not upload or run the local Python application.

## Prepared locally

`render.yaml` describes one Docker web service, custom domain aedrova.com, database
readiness health checks, a 300-second shutdown grace and deployment after GitHub checks
pass. It explicitly selects free web compute for the first preview rather than silently
creating a paid subscription. Free compute can sleep and is not the target for paid AI,
meetings or dependable production response times; review paid compute before those gates.
No database or paid service is automatically created by this blueprint.

`.github/workflows/website-checks.yml` runs locked dependency installation, Ruff, Python
compilation, the entire backend test suite, Docker build and a disposable container startup
check. These checks run on pushes to main and pull requests; no live secrets are needed.
Docker is not installed on this Mac, so container build/startup must pass on GitHub/Render.
Render's own Blueprint validation is still required when importing it.
The local blueprint passed SchemaStore's Render JSON Schema validation. All 164 backend/
website tests, repository Ruff, Python compilation and whitespace checks pass. The new
HTTPS preflight is tested against failure fixtures and the actual application response
contract. No Docker build, Render resource, DNS mutation or live-domain test occurred here.

`python -m scripts.check_website_deployment --probe` is a credential-safe, read-only check
of the public HTTPS pages, DB readiness and closed checkout/AI gates. It does not prove
Google sign-in, payments, private database access controls or two-device meetings.

## Owner actions that block connection now

1. In the Render sign-in tab, complete GitHub authorization yourself. If creating a Render
   account, review/accept its terms yourself. When connecting repositories, install/authorize
   Render only for `ayanshv/Aedrova-website` rather than all repositories. The assistant has
   not clicked Authorize, accepted terms, granted repository access or created services.
2. Arrange a persistent private PostgreSQL database. Existing Supabase chat SQL and its
   public publishable key do not supply a server SQL connection. A separate Render Postgres
   database is the straightforward option; select/review its actual charges yourself.
   Use its internal connection URL for the web service and restrict external access. A
   dedicated restricted billing database/role on an existing PostgreSQL service is another
   option. Do not use an expiring free database as a durable production billing ledger.
3. Make the current website source and deployment files available on the linked GitHub
   branch, after tests and a secret review. The local repository has uncommitted product
   changes; nothing in this domain-setup task has been committed or pushed yet. Never add
   `.env*`, local databases, work/ reports or provider credentials. `.env.example` is public.
4. Render → New → Blueprint → choose `ayanshv/Aedrova-website`, branch `main`. Import
   `render.yaml`, inspect its resource/cost summary and supply the two prompted secrets:
   `AEDROVA_DATABASE=postgresql+psycopg://...` (replace an ordinary `postgresql://` prefix
   with `postgresql+psycopg://`) and `AEDROVA_ENCRYPTION_KEY`, a Fernet key generated once.
   To generate it on your local Terminal, from the website folder run:
   `uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.
   Enter it only in Render's secret field, retain a secure backup and keep it unchanged
   between releases. Never paste either secret into chat or GitHub. No live Stripe/model/
   LiveKit secrets are required for the first website-only deployment.
5. Keep all checkout/managed-AI/meeting/release/legal gates false as in the blueprint.
   Inspect Render's build logs and verify `/health/ready` on the generated host address.
   `AEDROVA_ORIGIN` is the canonical `https://aedrova.com`, so Google sign-in acceptance
   must use that domain once its DNS/TLS connection is complete.

## Connect Cloudflare after the Render service exists

Render → website service → Settings → Custom Domains: verify aedrova.com is listed.
Render adds a corresponding www domain with a redirect to the root. Copy the actual
service hostname shown by Render; the target is not known until the service exists.

Cloudflare → aedrova.com → DNS → Records:
- CNAME, Name `@`, Target the actual Render hostname (without `https://`), DNS only.
- CNAME, Name `www`, Target the same hostname, DNS only.

Check for conflicting web A/AAAA/CNAME records at those two names and resolve only the
conflicts. Preserve unrelated MX/TXT email records and other subdomains. Keep Cloudflare
as the registrar/DNS provider; changing nameservers is unnecessary. Render needs DNS-only
records for initial domain verification/certificate issuance. After Render shows both
certificates valid, leave DNS-only for the simplest initial configuration. Cloudflare
proxying can be considered after acceptance; use valid origin TLS and never cache auth,
account, API, gateway or Stripe paths as public pages.

Then Render → Custom Domains → Verify. Confirm https://aedrova.com has valid HTTPS and
https://www.aedrova.com redirects to it. Do not bypass a browser certificate warning.

## Google sign-in and public acceptance

Supabase → Authentication → URL Configuration:
- Add the exact redirect `https://aedrova.com/auth/callback` to Redirect URLs.
- Set Site URL to `https://aedrova.com` once it is the canonical live site.
- Preserve the desktop `http://127.0.0.1:43827/auth/**` redirect and local test redirects.

Google Cloud's authorized redirect URI remains the Supabase callback,
`https://cpelagtufyocepnqcqqd.supabase.co/auth/v1/callback`, not the website callback.
Review Google OAuth testing/publishing status and approved test users. For broader access,
complete any consent-screen domain/branding requirements shown by Google. Do not guess or
remove working desktop sign-in settings. Confirm sign-in, return, account and logout on
the actual HTTPS domain in a fresh browser session, plus mobile/light/dark page checks.
Review/finalize public privacy/terms/contact details before inviting real external users.

Run the preflight in Render's environment after deployment:
`python -m scripts.check_website_deployment --probe`.
Arrange DB backups/restore, private logs/alerts, hourly billing maintenance and public
request/abuse controls before commercial activation; see production-readiness-audit.md.

## How later local changes become live

Local editing changes only this Mac. The release flow is:
edit locally → test → commit → push to GitHub main → checks pass → Render builds a fresh
Docker image → readiness succeeds → Render switches live traffic. The domain keeps pointing
to the same service; normal code/content edits need no DNS change.

Use branches/PR review and require the Website checks job on main. Confirm Render's service
Settings → Auto-Deploy is After CI Checks Pass and that the GitHub app can see check results.
Do not mark cancelled/skipped checks as a substitute for a successful release review.
For an urgent rollback use Render's service Events/deploy controls to redeploy the previous
verified commit; review compatibility before rolling back database-related changes.

Database migrations are separate from website deployment. Apply additive, backward-compatible
Supabase migrations before the app that requires them; a Git push does not run SQL in Supabase.
Runtime secrets remain in Render's environment and must not be overwritten by local `.env`.
Changing an environment setting requires deploying/restarting the service with that setting.

## Still gated after the marketing site is online

Live paid checkout needs approved live Stripe products/prices, the canonical HTTPS webhook
`https://aedrova.com/stripe/webhook`, its server-only signing secret, provider credentials,
allowance/payment acceptance and completed legal/release gates. Local Stripe sandbox tests
do not activate it. Managed AI and meetings need separate server configuration, independent
meeting guard and shared-host acceptance. Public Mac downloads still require Apple Developer
ID/signing, notarization and fresh-Mac verification in M13. Apple setup does not block a
website-only deployment. No public DMG or live checkout is enabled by buying the domain.

References: https://render.com/docs/configure-cloudflare-dns,
https://render.com/docs/blueprint-spec, https://render.com/docs/deploys,
https://render.com/docs/free and https://developers.cloudflare.com/dns/concepts/.
