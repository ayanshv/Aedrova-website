"""Prepare live Stripe assets without opening checkout or creating payments."""

import argparse
import json
import os
from pathlib import Path

import stripe

from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from scripts.listen_stripe import EVENTS
from scripts.setup_stripe import provision, validate_price


def require_live(key):
    if not key.startswith(("sk_live_", "rk_live_")):
        raise ValueError("Configure a live secret key in .env.billing.live, never in chat.")


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)


def prepare(key, output):
    require_live(key)
    account = stripe.Account.retrieve(api_key=key)
    if not account.get("charges_enabled"):
        raise ValueError("Complete Stripe account activation before live preparation.")
    provision(Config(stripe_key=key), output / "plans.json", live=True)
    icon = Path(__file__).resolve().parents[1] / "aedrova_site/static/checkout-icon.png"
    with icon.open("rb") as asset:
        uploaded = stripe.File.create(purpose="business_icon", file=asset, api_key=key)
    portal = stripe.billing_portal.Configuration.create(
        features={
            "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
            "invoice_history": {"enabled": True},
            "payment_method_update": {"enabled": True},
            "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
            "subscription_update": {"enabled": False},
        },
        business_profile={
            "headline": "Aedrova",
            "privacy_policy_url": "https://aedrova.com/privacy",
            "terms_of_service_url": "https://aedrova.com/terms",
        },
        metadata={"application": "aedrova", "environment": "live"},
        idempotency_key="aedrova-live-portal-v1",
        api_key=key,
    )
    save(output / "branding.json", {"icon_file": uploaded["id"]})
    save(output / "portal.json", {"configuration": portal["id"]})
    print("Live prices, icon and restricted portal prepared. No checkout or charge created.")


def preflight(config):
    require_live(config.stripe_key)
    if config.stripe_test_mode or set(config.plans) != {"monthly", "annual"}:
        raise ValueError("Configure both live plans and disable sandbox mode.")
    account = stripe.Account.retrieve(api_key=config.stripe_key)
    if not account.get("charges_enabled") or not account.get("payouts_enabled"):
        raise ValueError("Complete Stripe business activation and payout setup.")
    for name, policy in PLAN_POLICY.items():
        price = stripe.Price.retrieve(config.plans[name]["price_id"], api_key=config.stripe_key)
        validate_price(price, policy, live=True)
    if not config.stripe_portal_configuration:
        raise ValueError("Configure the live restricted portal.")
    portal = stripe.billing_portal.Configuration.retrieve(
        config.stripe_portal_configuration, api_key=config.stripe_key
    )
    if portal.get("livemode") is not True or not portal.get("active"):
        raise ValueError("The portal must be active and belong to live mode.")
    if not config.webhook_secret.startswith("whsec_"):
        raise ValueError("Configure the live destination signing secret.")
    expected = set(EVENTS.split(","))
    destination = config.origin.rstrip("/") + "/stripe/webhook"
    endpoints = stripe.WebhookEndpoint.list(limit=100, api_key=config.stripe_key)
    if not any(
        item.get("url") == destination
        and item.get("status") == "enabled"
        and item.get("livemode") is True
        and expected.issubset(set(item.get("enabled_events", [])))
        for item in endpoints.auto_paging_iter()
    ):
        raise ValueError("Configure the enabled live webhook with all eight supported events.")
    print("PASS live account, prices, portal and webhook destination configuration.")
    print("Signing-secret presence only: signed delivery acceptance remains required.")
    print("Public checkout remains governed by waitlist, legal, release and AI gates.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("work/stripe-live"))
    args = parser.parse_args()
    if args.prepare:
        prepare(os.environ.get("AEDROVA_STRIPE_KEY", ""), args.output)
    else:
        preflight(Config.load())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, stripe.StripeError, OSError):
        print(
            "Live Stripe setup did not pass. Check activation, private credentials, "
            "live assets and connectivity. No upstream private details are displayed."
        )
        raise SystemExit(1) from None
