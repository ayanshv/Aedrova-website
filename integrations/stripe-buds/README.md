# Aedrova Buds Stripe OAuth registration

Headless read-only Stripe App manifest for the existing Python Bud OAuth backend.
This contains no Stripe UI extension or payment functionality. The Finance Bud
uses the verified authorized account and its balance only. Customer OAuth tokens
are encrypted by the connector service and never bundled into the desktop app.

Prepared locally; NOT uploaded, installed, approved or published. The app ID is
proposed and not yet validated for global uniqueness by Stripe. Do not claim a
working public connector until provider registration and live acceptance pass.

1. Approve Stripe CLI login for the Aedrova developer account.
2. Review/accept the Stripe Apps Agreement personally before upload.
3. From this directory run `stripe apps upload --non-interactive --wait` once
   account/terms authorization is satisfied. Do not use `--force` or skip validation.
4. Inspect the created app in Stripe, configure External test and obtain its real
   OAuth test install URL and client ID. Public distribution requires review.
5. Configure the matching developer test API key and app credentials server-side,
   then test account/balance reads, refresh, revocation and account isolation.

Never grant payment/payout writes or enable Aedrova checkout as part of this setup.
See ../../docs/account-connector-setup.md for credential/environment handoff.
Manifest reference: https://docs.stripe.com/stripe-apps/reference/app-manifest
