# Reuse Aedrova's Supabase database for the website

The owner selected the existing Supabase project instead of a second paid Render database.
Do not create the $6.30/month Render database. The website remains a Python Docker web
service on Render; Supabase stores website data as well as existing desktop workspace data.
Existing plan quotas, pause behavior, storage and backup limits still apply.

## Owner steps required now

1. In Supabase project `cpelagtufyocepnqcqqd` → SQL Editor → New query, paste and run
   `sql/supabase-website.sql` from this website repository. It creates `aedrova_website`
   without login and gives it ownership of only `aedrova_billing`. It does not alter any
   chat table, workspace, existing login password or RLS policy. The SQL grants the SQL
   Editor administrator membership in the restricted website role so it can assign schema
   ownership; it does not grant the website membership in the administrator role. If it reports an existing
   role/schema conflict, stop and report the error without secrets; do not drop anything.
2. Generate a unique 32+ character password in your password manager for `aedrova_website`.
   You must personally enable its login and set its password in Supabase SQL Editor:
   `ALTER ROLE aedrova_website WITH LOGIN PASSWORD '<your-new-private-password>';`
   Replace the placeholder yourself. Never commit or paste the real statement into chat.
   Prefer a generated alphanumeric password to avoid SQL quoting/URL encoding mistakes.
   Do not save the password-bearing query as a shared snippet. Do not reset `postgres`.
3. Supabase → Connect → Session pooler. Copy the actual host from the displayed connection
   string; do not guess it. Use port 5432, database postgres, and change the username from
   postgres.cpelagtufyocepnqcqqd to aedrova_website.cpelagtufyocepnqcqqd. Use the NEW role
   password, change the scheme to postgresql+psycopg and append `?sslmode=require`.
   Example SHAPE only (HOST and PASSWORD are placeholders):
   `postgresql+psycopg://aedrova_website.cpelagtufyocepnqcqqd:PASSWORD@HOST:5432/postgres?sslmode=require`
   URL-encode reserved password characters. Do not use transaction mode/port 6543:
   this server uses session settings, PostgreSQL advisory locks and prepared statements.
4. Enter this URL only in Render's `AEDROVA_DATABASE` secret field when importing the
   repository's Blueprint. Set `AEDROVA_ENCRYPTION_KEY` to one persistent Fernet key,
   generated locally with `uv run python -c 'from cryptography.fernet import Fernet;
   print(Fernet.generate_key().decode())'`. Keep a secure backup of both secrets. Render's
   generic Generate button is not a substitute for a valid Fernet key.
5. Supabase → Data API settings: keep `aedrova_billing` OUT of exposed schemas. Do not
   grant the website role membership in authenticated, service_role or administrator roles.
   If database network restrictions are enabled, allow only the required Render egress
   ranges for the website; do not disable restrictions globally.

The Blueprint selects the free initial web preview and caps its DB pool at 2 connections
plus 1 overflow. No Render Postgres resource or paid database subscription is needed.
The schema must be prepared before first server startup. The restricted role creates its
private tables on startup. Waitlist addresses and website sessions remain encrypted.
No Supabase service-role API key is required for this waitlist-only deployment.

## Agent acceptance after owner setup

Verify Render starts with the restricted role over TLS; private schema initialization and
health/ready succeed; public pages and a consented test waitlist signup work on the HTTPS
origin; anon/authenticated Data API access cannot retrieve private website data. Confirm
existing desktop sign-in and workspace access remain unchanged. Local tests and embedded
PostgreSQL checks do not substitute for live pooled-connection acceptance. DNS/domain and
public privacy/contact details remain separate deployment gates. Launch emails still need
an email provider or a separately authorized manual sending workflow.

References:
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/database/postgres/roles
- https://supabase.com/docs/guides/api/using-custom-schemas
