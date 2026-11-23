# Invited beta gate

The Plans page ends with a "Part of the Beta?" box. Testers enter one shared password; a
correct entry opens the download page for seven days on that browser.

- **Where the password lives:** only in the `AEDROVA_BETA_PASSWORD` environment value on the
  service (at least 12 characters). It is never in the repository, the page or the cookie.
  Leaving it empty turns the gate off.
- **What it protects:** `/download` and `/api/download`. Without the password, `/download`
  sends visitors to the Plans page. Plans, pricing and legal pages stay public.
- **How it works:** the form posts to `/beta/unlock`, which checks the password in constant
  time, limits attempts per address (30 per hour) and sets a signed HttpOnly cookie that
  expires after seven days.
- **Changing or revoking it:** change the environment value and redeploy. Every tester is
  signed out at once.
- **Limits:** a shared password cannot tell testers apart or remove one person. Pair it with
  the planned sign-in allowlist before inviting anyone outside a small trusted group.
