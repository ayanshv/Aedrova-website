"""Signed-event lifecycle against the real ledger; Stripe is a deterministic fixture."""

import json
import time

import pytest
from sqlalchemy import text
from test_billing import sign

from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.services import Payments
from aedrova_site.store import Denied, Store


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    store = Store(f"sqlite:///{tmp_path / 'lifecycle.sqlite'}")
    store.customer("workspace", "cus_team")
    store.customer("other-workspace", "cus_other")
    plans = {
        p: {**PLAN_POLICY[p], "price_id": "price_" + p} for p in ("monthly", "annual")
    }
    config = Config(webhook_secret="whsec_fixture", plans=plans)
    current = {
        "id": "sub_team",
        "customer": "cus_team",
        "metadata": {"workspace": "workspace", "plan": "monthly"},
        "status": "active",
        "latest_invoice": {"id": "in_paid", "status": "paid"},
        "items": {"data": [{
            "price": {"id": "price_monthly"}, "quantity": 1,
            "current_period_start": int(time.time()) - 100,
            "current_period_end": int(time.time()) + 86400,
        }]},
    }
    monkeypatch.setattr("stripe.Subscription.retrieve", lambda *a, **kw: current)
    payments = Payments(config, store)

    def deliver(identifier, kind="customer.subscription.updated"):
        payload = json.dumps({"id": identifier, "type": kind, "data": {"object": {
            "subscription": "sub_team", "id": "sub_team",
        }}}).encode()
        payments.webhook(payload, sign(payload, config.webhook_secret))

    yield store, payments, current, deliver
    store.engine.dispose()


@pytest.mark.parametrize("status", ["past_due", "unpaid", "incomplete", "canceled", "paused"])
def test_failed_or_incomplete_payment_removes_access(lifecycle, status):
    store, _, current, deliver = lifecycle
    deliver("evt_initial")
    current["status"] = status
    current["latest_invoice"]["status"] = "open"
    deliver("evt_failure", "invoice.payment_failed")
    assert store.balance("workspace")["status"] == "inactive"
    with pytest.raises(Denied):
        store.create_run("member", "workspace", "codex", "after-failure")
    assert store.balance("other-workspace")["status"] == "pending"


def test_cancel_at_period_end_preserves_only_paid_current_period(lifecycle):
    store, _, current, deliver = lifecycle
    current["cancel_at_period_end"] = True
    deliver("evt_scheduled_cancel")
    assert store.balance("workspace")["status"] == "active"
    current["status"] = "canceled"
    deliver("evt_canceled", "customer.subscription.deleted")
    deliver("evt_late_paid", "invoice.paid")
    assert store.balance("workspace")["status"] == "inactive"


def test_plan_changes_do_not_replenish_spending_and_renewal_resets_once(lifecycle):
    store, _, current, deliver = lifecycle
    deliver("evt_initial")
    with store.tx() as db:
        db.execute(text("UPDATE billing SET spent=123456 WHERE workspace='workspace'"))
    for index, plan in enumerate(("annual", "monthly")):
        current["metadata"]["plan"] = plan
        current["items"]["data"][0]["price"]["id"] = "price_" + plan
        deliver(f"evt_change_{index}")
        balance = store.balance("workspace")
        assert balance["plan"] == plan and balance["spent"] == 123456
        assert balance["allowance"] == PLAN_POLICY[plan]["allowance_microusd"]
    line = current["items"]["data"][0]
    line["current_period_start"] += 50
    deliver("evt_renew", "invoice.paid")
    with store.tx() as db:
        db.execute(text("UPDATE billing SET spent=10 WHERE workspace='workspace'"))
    deliver("evt_renew", "invoice.paid")
    assert store.balance("workspace")["spent"] == 10


def test_full_subscription_refund_blocks_delayed_paid_event(lifecycle, monkeypatch):
    store, payments, current, deliver = lifecycle
    deliver("evt_initial")
    monkeypatch.setattr("stripe.Charge.retrieve", lambda *a, **kw: {
        "amount": 1000, "amount_refunded": 1000, "invoice": "in_paid",
        "customer": "cus_team", "payment_intent": "pi_team",
    })
    monkeypatch.setattr("stripe.Invoice.retrieve", lambda *a, **kw: {
        "parent": {"subscription_details": {"subscription": "sub_team"}},
    })
    payload = json.dumps({"id": "evt_refund", "type": "charge.refunded",
                          "data": {"object": {"id": "ch_team"}}}).encode()
    payments.webhook(payload, sign(payload, "whsec_fixture"))
    deliver("evt_delayed_paid", "invoice.paid")
    assert store.balance("workspace")["status"] == "inactive"
    assert store.balance("other-workspace")["status"] == "pending"
    current["items"]["data"][0]["current_period_start"] += 50
    deliver("evt_new_period", "invoice.paid")
    assert store.balance("workspace")["status"] == "active"


def test_canonical_change_during_validation_fails_without_partial_entitlements(
    lifecycle, monkeypatch
):
    store, _, current, deliver = lifecycle
    calls = []

    def retrieve(*args, **kwargs):
        calls.append(1)
        result = json.loads(json.dumps(current))
        if len(calls) > 1:
            result["status"] = "canceled"
        return result

    monkeypatch.setattr("stripe.Subscription.retrieve", retrieve)
    with pytest.raises(Denied, match="changed"):
        deliver("evt_racing")
    assert store.balance("workspace")["status"] == "pending"
    with store.tx(write=False) as db:
        assert db.scalar(text("SELECT count(*) FROM events WHERE id='evt_racing'")) == 0
