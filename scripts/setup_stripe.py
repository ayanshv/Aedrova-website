"""Provision only sandbox prices and check billing readiness without revealing credentials."""

import argparse
import json
from pathlib import Path

import stripe

from aedrova_site.budgets import policies
from aedrova_site.config import Config
from aedrova_site.policy import PLAN_NAMES, PLAN_POLICY


def provision(config, output, *, live=False):
    environment = "live" if live else "sandbox"
    prefixes = ("sk_live_", "rk_live_") if live else ("sk_test_", "rk_test_")
    if not config.stripe_key.startswith(prefixes):
        mode = "live" if live else "test"
        raise ValueError(f"Only Stripe {mode} keys are accepted by this setup command.")
    product = stripe.Product.create(
        name="Aedrova workspace",
        description="Private team workspace with a named coding agent and shared AI allowance.",
        metadata={"application": "aedrova", "environment": environment},
        idempotency_key=f"aedrova-{environment}-product-v1",
        api_key=config.stripe_key,
    )
    stripe.Product.create(
        name="Aedrova Enterprise — Let’s Talk",
        description="Custom scope and AI budget agreed before purchase. Contact Aedrova.",
        metadata={"application": "aedrova", "environment": environment, "contact_only": "true"},
        idempotency_key=f"aedrova-{environment}-enterprise-v2",
        api_key=config.stripe_key,
    )
    plans = {}
    for name, price_policy in PLAN_POLICY.items():
        policy = {
            **price_policy,
            "allowance_microusd": policies(config.usage_limits)[name]["budget"]
            * (12 if name == "annual" else 1),
        }
        lookup = "aedrova_" + environment + "_" + name + "_v2"
        found = stripe.Price.list(lookup_keys=[lookup], active=True, api_key=config.stripe_key)
        if found["data"]:
            price = found["data"][0]
        else:
            price = stripe.Price.create(
                product=product["id"],
                currency="usd",
                unit_amount=policy["amount_cents"],
                recurring={"interval": policy["interval"], "interval_count": 1},
                lookup_key=lookup,
                nickname="Aedrova " + PLAN_NAMES[name],
                metadata={"application": "aedrova", "environment": environment},
                idempotency_key="aedrova-" + environment + "-price-" + name + "-v2",
                api_key=config.stripe_key,
            )
        validate_price(price, policy, live=live)
        plans[name] = {**policy, "price_id": price["id"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plans, indent=2) + "\n")
    output.chmod(0o600)
    print(environment.capitalize() + " monthly/annual prices saved to " + str(output))


def validate_price(price, policy, *, live=False):
    recurring = price.get("recurring") or {}
    if (
        price.get("livemode") is not live
        or not price.get("active")
        or price.get("unit_amount") != policy["amount_cents"]
        or price.get("currency") != "usd"
        or recurring.get("interval") != policy["interval"]
        or recurring.get("interval_count") != 1
    ):
        raise ValueError(
            "Stripe price differs from the approved mode, $10/month or $200/year plan."
        )


def provision_branding(config, output):
    if not config.stripe_key.startswith(("sk_test_", "rk_test_")):
        raise ValueError("Only test keys can configure sandbox branding.")
    icon = Path(__file__).resolve().parents[1] / "aedrova_site/static/checkout-icon.png"
    with icon.open("rb") as asset:
        uploaded = stripe.File.create(
            purpose="business_icon", file=asset, api_key=config.stripe_key
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"icon_file": uploaded["id"]}) + "\n")
    output.chmod(0o600)
    print("Aedrova sandbox checkout icon saved to " + str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provision-test-prices", action="store_true")
    parser.add_argument("--configure-test-portal", action="store_true")
    parser.add_argument("--configure-test-branding", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("work/stripe-plans.json"))
    args = parser.parse_args()
    # Provisioning can start before the output plan file exists.
    import os

    if args.provision_test_prices or args.configure_test_portal or args.configure_test_branding:
        config = Config(stripe_key=os.environ.get("AEDROVA_STRIPE_KEY", ""))
        if not config.stripe_key.startswith(("sk_test_", "rk_test_")):
            raise ValueError("Only test keys can provision this setup.")
        if args.provision_test_prices:
            provision(config, args.output)
        if args.configure_test_branding:
            provision_branding(config, args.output.with_name("stripe-branding.json"))
        if args.configure_test_portal:
            portal = stripe.billing_portal.Configuration.create(
                features={
                    "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
                    "invoice_history": {"enabled": True},
                    "payment_method_update": {"enabled": True},
                    "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
                    "subscription_update": {"enabled": False},
                },
                metadata={"application": "aedrova", "environment": "sandbox"},
                idempotency_key="aedrova-sandbox-portal-v1",
                api_key=config.stripe_key,
            )
            path = args.output.with_name("stripe-portal.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"configuration": portal["id"]}) + "\n")
            path.chmod(0o600)
            print("Sandbox subscription portal saved to " + str(path))
        return
    config = Config.load()
    if not config.stripe_test_mode:
        raise ValueError("Enable explicit sandbox mode for the pre-M11 checkout test.")
    for name, policy in PLAN_POLICY.items():
        if name not in config.plans:
            raise ValueError("Provision both test prices first.")
        price = stripe.Price.retrieve(config.plans[name]["price_id"], api_key=config.stripe_key)
        validate_price(price, policy)
    if not config.webhook_secret.startswith("whsec_"):
        raise ValueError("Configure the Stripe CLI or sandbox destination signing secret.")
    if not config.encryption_key:
        raise ValueError("Configure a persistent encryption key before signing in.")
    print("PASS sandbox keys, approved prices, encryption and webhook-secret presence.")
    print("Signed webhook delivery and an actual test checkout still need live acceptance.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, stripe.StripeError, OSError):
        # Never print upstream exception bodies or request headers containing credentials.
        print(
            "Stripe setup did not pass. "
            "Check test credentials, price configuration and connectivity."
        )
        raise SystemExit(1) from None
