# Aedrova Buds Stripe OAuth registration

Headless read-only Stripe App manifest for the existing Python Bud OAuth backend.
This contains no Stripe UI extension or payment functionality. The Finance Bud
uses the verified authorized account and its balance only. Customer OAuth tokens
are encrypted by the connector service and never bundled into the desktop app.

Version 0.1.0 uploaded successfully on October 10, 2026 after the owner explicitly
approved CLI authorization and the Stripe Apps Developer Agreement. Stripe reports
Approved for testing. The registered app ID is `com.aedrova.buds`. It has not been
installed, enabled for external testing, or published to the Marketplace.

Current blocker: the app Details dashboard says “Verify your business to get started
with external testing.” The owner must complete Stripe business verification.

1. After verification, configure External test and obtain its real OAuth test
   install URL and client ID. Public distribution requires separate review.
2. Configure the matching developer test API key and app credentials server-side,
   then test account/balance reads, refresh, revocation and account isolation.
3. For future uploads from this directory use
   `stripe apps upload --non-interactive --wait`; do not force validation.

Never grant payment/payout writes or enable Aedrova checkout as part of this setup.
See ../../docs/account-connector-setup.md for credential/environment handoff.
Manifest reference: https://docs.stripe.com/stripe-apps/reference/app-manifest

## October 20 update

The owner approved selecting v0.1.0 for external testing. Stripe now displays the
external test version and Test OAuth install links; it remains unpublished and has
zero tested accounts. The older business-verification blocker text above describes
October 10 and must not be used as the current external-testing status.

v0.1.1 is prepared locally with the additional Aedrova Beta Staging HTTPS callback.
It preserves both read permissions and the original callback. Upload and moving
matching test developer credentials into staging await the explicit approval request;
preparing/committing the manifest is not evidence the version is uploaded or active.
