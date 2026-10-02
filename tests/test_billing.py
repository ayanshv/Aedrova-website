"""Billing invariants use the real ledger and signature validator, with no paid requests."""

import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.services import Payments
from aedrova_site.store import Denied, Store


@pytest.fixture
def store(tmp_path):
    value = Store(f"sqlite:///{tmp_path / 'billing.sqlite'}")
    value.customer("space-a", "cus_a")
    value.subscription(
        "evt_first",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        100,
        int(time.time()) + 86400,
        PLAN_POLICY["monthly"],
    )
    yield value
    value.engine.dispose()


def run(store, key="request-00000001"):
    access = store.create_run("user-a", "space-a", "codex", key)
    return store.run(access["token"]), access


def test_parallel_runs_respect_workspace_concurrency(store):
    def attempt(index):
        try:
            return store.create_run("user-a", "space-a", "codex", str(index))
        except Denied:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(value is not None for value in pool.map(attempt, range(8))) == 1


def test_parallel_reservations_cannot_overspend(store):
    active, _ = run(store)

    def attempt(index):
        try:
            return store.reserve(active, str(index), 6_000_000)
        except Denied:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(value is not None for value in pool.map(attempt, range(8))) == 1
    assert store.balance("space-a")["reserved"] == 6_000_000


def test_parallel_settlement_charges_once_and_encrypts_replay(store):
    active, _ = run(store)
    identifier, _ = store.reserve(active, "same-body", 100_000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: store.settle(identifier, 50_000, b"private source code"), range(8)))
    assert store.balance("space-a")["spent"] == 50_000
    assert store.balance("space-a")["reserved"] == 0
    assert store.reserve(active, "same-body", 100_000)[1] == b"private source code"
    with store.tx() as db:
        assert (
            "private source code" not in db.execute(text("SELECT response FROM inference")).scalar()
        )


def test_uncertain_failure_stops_replay_and_consumes_reservation(store):
    active, _ = run(store)
    identifier, _ = store.reserve(active, "body", 80_000)
    store.settle(identifier, None)
    assert store.balance("space-a")["spent"] == 80_000
    with pytest.raises(Denied, match="uncertain"):
        store.reserve(active, "body", 80_000)


def test_renewal_does_not_charge_old_pending_request_to_new_period(store):
    active, _ = run(store)
    identifier, _ = store.reserve(active, "body", 80_000)
    assert store.subscription(
        "evt_renew",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        200,
        int(time.time()) + 90000,
        PLAN_POLICY["monthly"],
    )
    store.settle(identifier, 40_000, b"done")
    assert store.balance("space-a")["spent"] == 0
    assert store.balance("space-a")["reserved"] == 0
    assert not store.subscription(
        "evt_renew",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        200,
        int(time.time()) + 90000,
        PLAN_POLICY["monthly"],
    )
    with pytest.raises(Denied, match="backwards"):
        store.subscription(
            "evt_old",
            "cus_a",
            "sub_a",
            "monthly",
            "active",
            100,
            int(time.time()) + 90000,
            PLAN_POLICY["monthly"],
        )


def test_closed_expired_and_other_workspace_tokens_are_denied(store):
    active, access = run(store)
    store.end_run(access["id"], "other-user")
    assert store.run(access["token"])["workspace"] == "space-a"
    store.end_run(access["id"], "user-a")
    with pytest.raises(Denied):
        store.run(access["token"])
    with pytest.raises(Denied):
        store.reserve(active, "after-close", 1)
    with pytest.raises(Denied):
        store.create_run("user-b", "space-b", "codex", "new")
    with pytest.raises(Denied):
        store.create_run("user-a", "space-a", "codex", "request-00000001")


def test_session_token_is_hashed_payload_encrypted_and_expiry_enforced(store):
    store.session("opaque-token", {"access_token": "supabase-secret"})
    with store.tx() as db:
        row = db.execute(text("SELECT id,payload FROM sessions")).one()
        assert row[0] != "opaque-token" and "supabase-secret" not in row[1]
    assert store.session("opaque-token")["access_token"] == "supabase-secret"
    store.delete_session("opaque-token")
    with pytest.raises(Denied):
        store.session("opaque-token")


def sign(payload, secret):
    stamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), stamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return f"t={stamp},v1={signature}"


def test_signed_webhook_canonical_state_prevents_delayed_reactivation(store, monkeypatch):
    config = Config(
        webhook_secret="whsec_test",
        plans={"monthly": {**PLAN_POLICY["monthly"], "price_id": "price_monthly"}},
    )
    payments = Payments(config, store)
    current = {
        "id": "sub_a",
        "customer": "cus_a",
        "metadata": {"workspace": "space-a", "plan": "monthly"},
        "status": "canceled",
        "latest_invoice": {"paid": True},
        "items": {
            "data": [
                {
                    "price": {"id": "price_monthly"},
                    "quantity": 1,
                    "current_period_start": 100,
                    "current_period_end": int(time.time()) + 1000,
                }
            ]
        },
    }
    monkeypatch.setattr("stripe.Subscription.retrieve", lambda *a, **k: current)
    payload = json.dumps(
        {"id": "evt_delayed", "type": "invoice.paid", "data": {"object": {"subscription": "sub_a"}}}
    ).encode()
    payments.webhook(payload, sign(payload, config.webhook_secret))
    payments.webhook(payload, sign(payload, config.webhook_secret))
    assert store.balance("space-a")["status"] == "inactive"
    current["status"] = "active"
    current["customer"] = "cus_foreign"
    bad = payload.replace(b"evt_delayed", b"evt_foreign")
    with pytest.raises(Denied, match="belong"):
        payments.webhook(bad, sign(bad, config.webhook_secret))


def test_webhook_tampering_rejected_before_stripe_request(tmp_path, monkeypatch):
    app = create_app(
        Config(database=f"sqlite:///{tmp_path / 'app.sqlite'}", webhook_secret="whsec_test")
    )
    monkeypatch.setattr(
        "stripe.Subscription.retrieve", lambda *a, **k: pytest.fail("No Stripe API request")
    )
    payload = b'{"type":"invoice.paid"}'
    with TestClient(app) as client:
        assert (
            client.post(
                "/stripe/webhook",
                content=payload + b" ",
                headers={"stripe-signature": sign(payload, "whsec_test")},
            ).status_code
            == 400
        )
        assert client.post("/stripe/webhook", content=payload).status_code == 400
    app.state.store.engine.dispose()


def test_checkout_rejects_price_mismatch_before_creating_session(store, monkeypatch):
    payments = Payments(
        Config(
            checkout_enabled=True,
            plans={"monthly": {**PLAN_POLICY["monthly"], "price_id": "price_monthly"}},
        ),
        store,
    )
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda *a, **k: {
            "active": True,
            "unit_amount": 999,
            "currency": "usd",
            "recurring": {"interval": "month"},
        },
    )
    monkeypatch.setattr("stripe.checkout.Session.create", lambda **k: pytest.fail("No charge"))
    with pytest.raises(Denied, match="price"):
        payments.checkout("space-a", "monthly", "request")


def test_purchased_credits_are_explicit_idempotent_and_carry_over(store):
    assert store.grant_credit("cs_credit", "space-a", "pi_credit", 5_000_000)
    assert not store.grant_credit("cs_credit", "space-a", "pi_credit", 5_000_000)
    active, _ = run(store)
    identifier, _ = store.reserve(active, "large", 12_000_000)
    balance = store.balance("space-a")
    assert balance["reserved"] == 10_000_000 and balance["credit_reserved"] == 2_000_000
    store.settle(identifier, 11_000_000, b"done")
    assert store.balance("space-a")["credit_balance"] == 4_000_000
    store.subscription(
        "evt_next",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        200,
        int(time.time()) + 90000,
        PLAN_POLICY["monthly"],
    )
    assert store.balance("space-a")["available"] == 14_000_000


def test_pending_wallet_reservation_survives_period_renewal(store):
    store.grant_credit("cs_credit", "space-a", "pi_credit", 5_000_000)
    active, _ = run(store)
    identifier, _ = store.reserve(active, "large", 12_000_000)
    store.subscription(
        "evt_next",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        200,
        int(time.time()) + 90000,
        PLAN_POLICY["monthly"],
    )
    assert store.balance("space-a")["credit_reserved"] == 2_000_000
    store.settle(identifier, None)
    assert store.balance("space-a")["credit_reserved"] == 0
    assert store.balance("space-a")["credit_balance"] == 3_000_000
    assert store.balance("space-a")["spent"] == 0


def test_partial_refund_dispute_and_out_of_order_reversal(store):
    store.reverse_credit("pi_early", 500, 1000)
    store.grant_credit("cs_early", "space-a", "pi_early", 5_000_000)
    assert store.balance("space-a")["credit_balance"] == 2_500_000
    store.reverse_credit("pi_early", 1000, 1000)
    store.reverse_credit("pi_early", 500, 1000)
    assert store.balance("space-a")["credit_balance"] == 0
    store.grant_credit("cs_next", "space-a", "pi_next", 5_000_000)
    active, _ = run(store)
    identifier, _ = store.reserve(active, "large", 12_000_000)
    store.settle(identifier, 12_000_000, b"done")
    store.reverse_credit("pi_next", 1000, 1000)
    assert store.balance("space-a")["credit_balance"] == -2_000_000
    with pytest.raises(Denied, match="refund or dispute"):
        store.reserve(active, "another", 1)


def test_signed_credit_purchase_verifies_canonical_payment_and_duplicate_delivery(
    store, monkeypatch
):
    payments = Payments(Config(webhook_secret="whsec_test", topup_price_id="price_credits"), store)
    session = {
        "id": "cs_credits",
        "mode": "payment",
        "metadata": {"kind": "ai_credits", "workspace": "space-a"},
        "customer": "cus_a",
        "payment_status": "paid",
        "amount_total": 1000,
        "currency": "usd",
        "payment_intent": "pi_credits",
        "line_items": {"data": [{"price": {"id": "price_credits"}, "quantity": 1}]},
    }
    monkeypatch.setattr("stripe.checkout.Session.retrieve", lambda *a, **kw: session)
    monkeypatch.setattr(
        "stripe.PaymentIntent.retrieve",
        lambda *a, **kw: {
            "status": "succeeded",
            "amount_received": 1000,
            "currency": "usd",
            "latest_charge": {"amount_refunded": 0},
        },
    )
    payload = json.dumps(
        {
            "id": "evt_credits",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_credits"}},
        }
    ).encode()
    payments.webhook(payload, sign(payload, "whsec_test"))
    payments.webhook(payload, sign(payload, "whsec_test"))
    assert store.balance("space-a")["credit_balance"] == 5_000_000
    session["customer"] = "cus_foreign"
    with pytest.raises(Denied, match="belong"):
        payments.webhook(payload, sign(payload, "whsec_test"))


def test_expired_private_content_cleanup_preserves_money_ledger(store):
    active, access = run(store)
    store.session("expired", {"access_token": "secret"}, lifetime=-1)
    identifier, _ = store.reserve(active, "pending", 100)
    with store.tx() as db:
        db.execute(text("UPDATE runs SET expires=0"))
    store.maintain()
    assert store.balance("space-a")["reserved"] == 0
    assert store.balance("space-a")["spent"] == 100
    with pytest.raises(Denied):
        store.session("expired")


def test_credit_checkout_is_explicit_one_time_and_idempotent(store, monkeypatch):
    calls = []
    payments = Payments(Config(checkout_enabled=True, topup_price_id="price_credits"), store)
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda *a, **kw: {
            "active": True,
            "unit_amount": 1000,
            "currency": "usd",
            "recurring": None,
        },
    )

    def create(**kw):
        calls.append(kw)
        return {
            "url": "https://checkout.stripe.com/c/pay/test",
            "expires_at": int(time.time()) + 1800,
        }

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    assert payments.topup("space-a", "request-00000001") == payments.topup(
        "space-a", "request-00000001"
    )
    assert len(calls) == 1 and calls[0]["mode"] == "payment"
    assert calls[0]["line_items"] == [{"price": "price_credits", "quantity": 1}]
    with pytest.raises(Denied, match="already open"):
        payments.topup("space-a", "different-request")
    assert store.balance("space-a")["credit_balance"] == 0


def test_duplicate_parallel_credit_events_cannot_grant_twice(store):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: store.grant_credit("cs_credit", "space-a", "pi_credit", 5_000_000),
                range(8),
            )
        )
    assert sum(results) == 1 and store.balance("space-a")["credit_balance"] == 5_000_000


def test_subscription_checkout_uses_reused_customer_and_fixed_approved_price(store, monkeypatch):
    store.customer("space-new", "cus_new")
    config = Config(
        checkout_enabled=True,
        plans={"monthly": {**PLAN_POLICY["monthly"], "price_id": "price_monthly"}},
    )
    payments = Payments(config, store)
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda *a, **kw: {
            "active": True,
            "unit_amount": 4900,
            "currency": "usd",
            "recurring": {"interval": "month", "interval_count": 1},
        },
    )
    monkeypatch.setattr(
        "stripe.Customer.create", lambda **kw: pytest.fail("Existing customer reused")
    )
    calls = []

    def create(**kw):
        calls.append(kw)
        return {
            "url": "https://checkout.stripe.com/c/pay/test",
            "expires_at": int(time.time()) + 1800,
        }

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    assert payments.checkout("space-new", "monthly", "request-00000001") == payments.checkout(
        "space-new", "monthly", "request-00000001"
    )
    assert len(calls) == 1 and calls[0]["mode"] == "subscription"
    assert calls[0]["customer"] == "cus_new"
    assert calls[0]["line_items"] == [{"price": "price_monthly", "quantity": 1}]
    assert calls[0]["subscription_data"]["metadata"] == {
        "workspace": "space-new",
        "plan": "monthly",
    }
    assert store.balance("space-new")["status"] == "pending"
