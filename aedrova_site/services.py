"""Supabase identity and Stripe operations stay on the server."""

import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import stripe
from sqlalchemy import text

from aedrova_site.store import Denied


class Identity:
    def __init__(self, config):
        self.config = config

    def request(self, path, token="", *, method="GET", data=None):
        headers = {"apikey": self.config.supabase_key}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            response = httpx.request(
                method,
                self.config.supabase_url + path,
                headers=headers,
                json=data,
                timeout=15,
                follow_redirects=False,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Denied(
                "Could not verify your workspace. Sign in again or retry shortly."
            ) from exc

    def user(self, token):
        user = self.request("/auth/v1/user", token)
        if not user.get("id"):
            raise Denied("Sign in with Google to continue.")
        return user

    def workspaces(self, token):
        user = self.user(token)
        memberships = self.request(
            "/rest/v1/workspace_members?"
            + urlencode({"select": "workspace_id,role", "user_id": "eq." + user["id"]}),
            token,
        )
        spaces = self.request("/rest/v1/workspaces?select=id,name", token)
        return [
            {**space, "role": member["role"]}
            for space in spaces
            for member in memberships
            if space["id"] == member["workspace_id"]
        ]

    def require(self, token, workspace, *, billing=False):
        user = self.user(token)
        memberships = self.request(
            "/rest/v1/workspace_members?"
            + urlencode(
                {"select": "role", "workspace_id": "eq." + workspace, "user_id": "eq." + user["id"]}
            ),
            token,
        )
        if not memberships or (billing and memberships[0]["role"] not in {"owner", "admin"}):
            raise Denied(
                "Only an authorized workspace owner or admin can manage billing."
                if billing
                else "You no longer have access to this workspace."
            )
        return user


class Payments:
    def __init__(self, config, store):
        self.config, self.store = config, store

    def checkout(self, workspace, plan, request_id):
        config = self.config
        if not config.checkout_enabled or plan not in config.plans:
            raise Denied("Paid beta checkout is being prepared. No payment has been taken.")
        approved = config.plans[plan]
        price = stripe.Price.retrieve(approved["price_id"], api_key=config.stripe_key)
        if (
            not price.get("active")
            or price.get("unit_amount") != approved["amount_cents"]
            or price.get("currency") != "usd"
            or price["recurring"]["interval"] != approved["interval"]
            or price["recurring"].get("interval_count", 1) != 1
        ):
            raise Denied("The configured Stripe price does not match the published plan.")
        with self.store.tx() as db:
            existing = db.execute(
                text("SELECT customer FROM billing WHERE workspace=:w"), {"w": workspace}
            ).scalar()
        if existing:
            row = self.store.customer(workspace, existing)
        else:
            customer = stripe.Customer.create(
                metadata={"workspace": workspace},
                idempotency_key="aedrova-customer-" + workspace,
                api_key=config.stripe_key,
            )
            row = self.store.customer(workspace, customer["id"])
        if row["status"] in {"active", "trialing"}:
            raise Denied("This workspace already has a plan. Use Manage subscription.")
        identifier = hashlib.sha256((workspace + plan + request_id).encode()).hexdigest()
        with self.store.tx() as db:
            self.store.billing_lock(db, workspace)

            prior = (
                db.execute(text("SELECT * FROM checkout WHERE id=:id"), {"id": identifier})
                .mappings()
                .first()
            )
            if prior:
                if prior["url"] and prior["expires"] > int(time.time()):
                    return prior["url"]
                raise Denied("Checkout is already being prepared or expired. Try a new checkout.")
            waiting = db.execute(
                text("SELECT id FROM checkout WHERE workspace=:w AND expires>:now"),
                {"w": workspace, "now": int(time.time())},
            ).first()
            if waiting:
                raise Denied(
                    "A checkout is already open for this workspace. Finish "
                    "it or wait for it to expire."
                )
            db.execute(
                text("INSERT INTO checkout VALUES(:id,:w,:p,NULL,:expires)"),
                {"id": identifier, "w": workspace, "p": plan, "expires": int(time.time()) + 1800},
            )
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=row["customer"],
            line_items=[{"price": approved["price_id"], "quantity": 1}],
            client_reference_id=workspace,
            metadata={"workspace": workspace, "plan": plan},
            subscription_data={"metadata": {"workspace": workspace, "plan": plan}},
            success_url=config.origin + "/welcome?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=config.origin + "/plans?cancelled=1",
            expires_at=int(time.time()) + 1800,
            allow_promotion_codes=False,
            idempotency_key="aedrova-checkout-" + identifier,
            api_key=config.stripe_key,
        )
        with self.store.tx() as db:
            db.execute(
                text("UPDATE checkout SET url=:url,expires=:expires WHERE id=:id"),
                {"url": session["url"], "expires": session["expires_at"], "id": identifier},
            )
        return session["url"]

    def topup(self, workspace, request_id):
        if not self.config.checkout_enabled or not self.config.topup_price_id:
            raise Denied("Optional AI credits are not available yet. No payment taken.")
        balance = self.store.balance(workspace)
        if balance["status"] != "active" or balance["period_end"] <= int(time.time()):
            raise Denied("AI credits require an active workspace subscription.")
        price = stripe.Price.retrieve(self.config.topup_price_id, api_key=self.config.stripe_key)
        if (
            not price.get("active")
            or price.get("unit_amount") != 1000
            or price.get("currency") != "usd"
            or price.get("recurring")
        ):
            raise Denied("Optional AI credit pricing does not match the published offer.")
        with self.store.tx() as db:
            customer = self.store.billing_lock(db, workspace)["customer"]
        identifier = hashlib.sha256((workspace + "ai_credits" + request_id).encode()).hexdigest()
        with self.store.tx() as db:
            self.store.billing_lock(db, workspace)
            prior = (
                db.execute(text("SELECT * FROM checkout WHERE id=:id"), {"id": identifier})
                .mappings()
                .first()
            )
            if prior:
                if prior["url"] and prior["expires"] > int(time.time()):
                    return prior["url"]
                raise Denied("This AI credit checkout is already pending or expired.")
            if db.execute(
                text("SELECT id FROM checkout WHERE workspace=:w AND expires>:now"),
                {"w": workspace, "now": int(time.time())},
            ).first():
                raise Denied(
                    "A checkout is already open for this workspace. No additional purchase started."
                )
            db.execute(
                text("INSERT INTO checkout VALUES(:id,:w,'ai_credits',NULL,:expires)"),
                {"id": identifier, "w": workspace, "expires": int(time.time()) + 1800},
            )
        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer,
            line_items=[{"price": self.config.topup_price_id, "quantity": 1}],
            metadata={"workspace": workspace, "kind": "ai_credits"},
            success_url=self.config.origin + "/account?credits=pending",
            cancel_url=self.config.origin + "/account?cancelled=1",
            expires_at=int(time.time()) + 1800,
            allow_promotion_codes=False,
            idempotency_key="aedrova-credit-"
            + hashlib.sha256((workspace + request_id).encode()).hexdigest(),
            api_key=self.config.stripe_key,
        )
        with self.store.tx() as db:
            db.execute(
                text("UPDATE checkout SET url=:url,expires=:expires WHERE id=:id"),
                {"url": session["url"], "expires": session["expires_at"], "id": identifier},
            )
        return session["url"]

    def credit_webhook(self, event):
        item = event["data"]["object"]
        if event["type"] == "checkout.session.completed":
            current = stripe.checkout.Session.retrieve(
                item["id"], expand=["line_items"], api_key=self.config.stripe_key
            )
            if (
                current.get("mode") != "payment"
                or current.get("metadata", {}).get("kind") != "ai_credits"
            ):
                return
            lines = current.get("line_items", {}).get("data", [])
            if (
                current.get("payment_status") != "paid"
                or not self.config.topup_price_id
                or current.get("amount_total") != 1000
                or current.get("currency") != "usd"
                or len(lines) != 1
                or lines[0].get("quantity") != 1
                or lines[0]["price"]["id"] != self.config.topup_price_id
            ):
                raise Denied("AI credit payment is not a verified approved purchase.")
            workspace = current["metadata"].get("workspace", "")
            with self.store.tx() as db:
                if self.store.billing_lock(db, workspace)["customer"] != current.get("customer"):
                    raise Denied("AI credit payment does not belong to this workspace.")
            payment = current.get("payment_intent")
            if not isinstance(payment, str) or not payment.startswith("pi_"):
                raise Denied("AI credit payment has no verified payment identifier.")
            intent = stripe.PaymentIntent.retrieve(
                payment, expand=["latest_charge"], api_key=self.config.stripe_key
            )
            charge = intent.get("latest_charge") or {}
            if (
                intent.get("status") != "succeeded"
                or intent.get("amount_received") != 1000
                or intent.get("currency") != "usd"
                or not isinstance(charge, dict)
            ):
                raise Denied("AI credits await a completed payment.")
            refunded = charge.get("amount_refunded", 0)
            if charge.get("disputed"):
                refunded = 1000
            if refunded:
                self.store.reverse_credit(payment, refunded, 1000)
            self.store.grant_credit(current["id"], workspace, payment, 5_000_000)
        else:
            identifier = (
                item.get("charge") if event["type"].startswith("charge.dispute") else item["id"]
            )
            charge = stripe.Charge.retrieve(identifier, api_key=self.config.stripe_key)
            refunded = charge.get("amount_refunded", 0)
            if event["type"].startswith("charge.dispute"):
                refunded = charge["amount"]
            if (
                type(refunded) is not int
                or type(charge.get("amount")) is not int
                or charge["amount"] <= 0
                or refunded < 0
            ):
                raise Denied("Invalid credit reversal amount.")
            self.store.reverse_credit(charge.get("payment_intent", ""), refunded, charge["amount"])

    def portal(self, workspace):
        if not self.config.stripe_key:
            raise Denied("Subscription management is not configured yet.")
        with self.store.tx() as db:
            row = self.store.billing_lock(db, workspace)
            customer = row["customer"]
        result = stripe.billing_portal.Session.create(
            customer=customer,
            return_url=self.config.origin + "/account",
            api_key=self.config.stripe_key,
        )
        return result["url"]

    def webhook(self, payload, signature):
        if not self.config.webhook_secret:
            raise Denied("Webhook verification is not configured.")
        event = stripe.Webhook.construct_event(payload, signature, self.config.webhook_secret)
        kind = event["type"]
        if kind in {"checkout.session.completed", "charge.refunded", "charge.dispute.created"}:
            self.credit_webhook(event)
            return
        if kind not in {
            "invoice.paid",
            "invoice.payment_failed",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "customer.subscription.created",
        }:
            return
        item = event["data"]["object"]
        if kind.startswith("invoice."):
            subscription = item.get("subscription") or item.get("parent", {}).get(
                "subscription_details", {}
            ).get("subscription")
        else:
            subscription = item["id"]
        if not subscription:
            return
        # Current canonical Stripe state prevents delayed events from reactivating stale plans.
        current = stripe.Subscription.retrieve(
            subscription, expand=["latest_invoice"], api_key=self.config.stripe_key
        )
        metadata = current.get("metadata", {})
        plan = metadata.get("plan")
        if plan not in self.config.plans:
            raise Denied("Subscription uses an unknown plan.")
        approved = self.config.plans[plan]
        lines = current["items"]["data"]
        if (
            len(lines) != 1
            or lines[0]["price"]["id"] != approved["price_id"]
            or lines[0].get("quantity", 1) != 1
        ):
            raise Denied("Subscription pricing does not match an approved plan.")
        invoice = current.get("latest_invoice") or {}
        paid = isinstance(invoice, dict) and invoice.get("paid") is True
        status = current["status"] if paid and current["status"] == "active" else "inactive"
        start = lines[0].get("current_period_start", current.get("current_period_start", 0))
        end = lines[0].get("current_period_end", current.get("current_period_end", 0))
        with self.store.tx() as db:
            row = self.store.billing_lock(db, metadata.get("workspace", ""))
            if row["customer"] != current["customer"]:
                raise Denied("Subscription does not belong to this workspace.")
            if (
                row["subscription"]
                and row["subscription"] != subscription
                and row["status"] == "active"
            ):
                raise Denied("A different workspace subscription is already active.")
        self.store.subscription(
            event["id"], current["customer"], subscription, plan, status, start, end, approved
        )


def random_token():
    return secrets.token_urlsafe(32)
