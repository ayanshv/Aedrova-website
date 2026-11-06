# Apple login release preparation

The account page includes a gated Sign in with Apple button below Google, using the Apple logo and native system typography. AEDROVA_APPLE_LOGIN_ENABLED defaults false. Apple and Google share the existing PKCE exchange, single-use server state, bounded login-start throttle, secure session and workspace-authorization path.

Apple team J64LC76P77 now has primary App ID com.aedrova.desktop, Services IDs com.aedrova.login.staging and com.aedrova.login, and a Sign in with Apple-only key. Callback URLs match each Supabase project's /auth/v1/callback. Generated 179-day client secrets are stored only in the approved Supabase settings and private local custody; the .p8 is not shipped or committed. The CLI scripts/apple_client_secret.py writes a new private file and reports rotation metadata without printing its token. Rotate at least 30 days before expiry.

Staging's provider is enabled. Native handoff reached Apple's real account/Touch ID sheet and cancellation returned cleanly. A personal completed sign-in is still required to certify session exchange and workspace access. Production's provider credentials are saved but remain disabled until that acceptance, and the website feature flag remains false. Do not infer incorporation or the legal operator from the Apple certificate holder.

Owner reports paid production hosting, verified in Render as 0.5c-512mb. render.yaml deliberately omits plan so sync preserves that existing choice rather than reverting to Free. Creating a new service from this blueprint may use Render's default paid plan and requires a separate owner decision; no new service or purchase was made here. Reference: https://render.com/docs/blueprint-spec.

Production health is ready, but managed AI and checkout remain disabled and the current environment has no managed model-provider key/model configuration. Reviewed production migrations, provider and spending setup, recovery/operations, operator details and final installer acceptance remain public-launch gates. Apple setup and paid compute alone do not close these gates.

All personal actions are consolidated in the native repository's docs/apple-and-local-meeting-release-2026-11-05.md. Do not ask for the completed hosting purchase, notary credentials or signing unlock again. No payments may be submitted by the agent.
