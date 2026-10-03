-- Run once in the existing Aedrova project's Supabase SQL Editor as postgres.
-- No secrets belong in this file. The new role cannot log in until you set its password.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aedrova_website') THEN
    CREATE ROLE aedrova_website NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'aedrova_website'
      AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members
    WHERE member = (SELECT oid FROM pg_roles WHERE rolname = 'aedrova_website')
  ) THEN
    RAISE EXCEPTION 'Existing aedrova_website role has unexpected permissions; stop and review.';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_namespace
    WHERE nspname = 'aedrova_billing'
      AND nspowner <> (SELECT oid FROM pg_roles WHERE rolname = 'aedrova_website')
  ) THEN
    RAISE EXCEPTION 'Existing private schema has another owner; stop and review before migration.';
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS aedrova_billing AUTHORIZATION aedrova_website;
REVOKE ALL ON SCHEMA aedrova_billing FROM PUBLIC, anon, authenticated, service_role;
GRANT CONNECT ON DATABASE postgres TO aedrova_website;
ALTER ROLE aedrova_website SET search_path = aedrova_billing;
ALTER ROLE aedrova_website SET statement_timeout = '15s';
ALTER ROLE aedrova_website SET lock_timeout = '5s';
ALTER DEFAULT PRIVILEGES FOR ROLE aedrova_website IN SCHEMA aedrova_billing
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE aedrova_website IN SCHEMA aedrova_billing
  REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE aedrova_website IN SCHEMA aedrova_billing
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated, service_role;
COMMIT;
-- Keep aedrova_billing OUT of Supabase Data API exposed schemas.
-- Owner next step: set a strong private password for this role and enable LOGIN.
-- Never reset the existing postgres password or paste a password into chat/GitHub.
