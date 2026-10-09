"""Pre-release sandbox checkout: no real charges, no return-page entitlement bypass."""

import json
import time

import pytest
import stripe
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_billing import sign

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied


def sandbox(tmp_path, **overrides):
    values = dict(
        database=f"sqlite:///{tmp_path / 'sandbox.sqlite3'}",
        encryption_key=Fernet.generate_key().decode(),
        stripe_key="sk_test_fixture",
        stripe_icon_file="file_test_icon",
        webhook_secret="whsec_fixture",
        stripe_test_mode=True,
        checkout_enabled=True,
        plans={
            name: {**policy, "price_id": "price_" + name} for name, policy in PLAN_POLICY.items()
        },
    )
    values.update(overrides)
    return Config(**values)


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(sandbox(tmp_path))
    store = app.state.store
    store.customer("space-a", "cus_a")
    store.session("browser", {"access_token": "access", "csrf": "csrf"})

    def user(token):
        if token != "access":
            raise Denied("Sign in again.")
        return {"id": "user-a"}

    def require(token, workspace, *, billing=False):
        user(token)
        if workspace != "space-a":
            raise Denied("Workspace access denied.")
        return {"id": "user-a"}

    app.state.identity.user = user
    app.state.identity.require = require
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda identifier, **kw: {
            "active": True,
            "livemode": False,
            "currency": "usd",
            "unit_amount": 20000 if identifier == "price_annual" else 1000,
            "recurring": {
                "interval": "year" if identifier == "price_annual" else "month",
                "interval_count": 1,
            },
        },
    )
    with TestClient(app) as value:
        value.cookies.set("aedrova_session", "browser")
        yield value
    store.engine.dispose()


def body(plan="monthly"):
    return {"workspace": "space-a", "plan": plan, "request_id": "checkout-request-00001"}


def test_sandbox_precedes_release_without_enabling_real_ai(tmp_path):
    config = sandbox(tmp_path)
    config.validate()
    assert not config.gateway_enabled and not config.release_ready
    for values, message in [
        ({"stripe_key": "sk_live_not_allowed"}, "test secret"),
        ({"production": True}, "HTTPS"),
        ({"encryption_key": ""}, "Checkout requires"),
    ]:
        with pytest.raises(ValueError, match=message):
            sandbox(tmp_path, **values).validate()


def test_test_keys_without_sandbox_cannot_open_checkout(tmp_path):
    with pytest.raises(ValueError, match="Checkout requires"):
        sandbox(tmp_path, stripe_test_mode=False).validate()


@pytest.mark.parametrize(
    "plan,amount,interval", [("annual", 20000, "year"), ("monthly", 1000, "month")]
)
def test_plan_checkout_repeats_same_session_and_preserves_cancel_context(
    client, monkeypatch, plan, amount, interval
):
    calls = []

    def create(**kw):
        calls.append(kw)
        return {"url": "https://checkout.stripe.com/c/pay/test", "expires_at": kw["expires_at"]}

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    for _ in range(2):
        response = client.post("/api/checkout", json=body(plan), headers={"x-csrf-token": "csrf"})
        assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["line_items"] == [{"price": "price_" + plan, "quantity": 1}]
    assert calls[0]["mode"] == "subscription"
    assert calls[0]["branding_settings"] == {
        "display_name": "Aedrova",
        "background_color": "#F5F5F7",
        "button_color": "#0066CC",
        "border_style": "pill",
        "font_family": "default",
        "icon": {"type": "file", "file": "file_test_icon"},
    }
    assert (
        "plan=" + plan in calls[0]["cancel_url"] and "workspace=space-a" in calls[0]["cancel_url"]
    )
    assert client.app.state.store.balance("space-a")["status"] == "pending"


def test_uncertain_checkout_retry_reuses_all_stripe_parameters(client, monkeypatch):
    calls = []

    def create(**kw):
        calls.append(kw)
        if len(calls) == 1:
            raise stripe.APIConnectionError("synthetic connection failure")
        return {"url": "https://checkout.stripe.com/c/pay/test", "expires_at": kw["expires_at"]}

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    first = client.post("/api/checkout", json=body(), headers={"x-csrf-token": "csrf"})
    assert first.status_code == 503
    other = {**body(), "request_id": "different-request-00001"}
    assert (
        client.post("/api/checkout", json=other, headers={"x-csrf-token": "csrf"}).status_code
        == 403
    )
    assert (
        client.post("/api/checkout", json=body(), headers={"x-csrf-token": "csrf"}).status_code
        == 200
    )
    assert calls[0] == calls[1]


def test_checkout_requires_csrf_membership_and_approved_plan(client, monkeypatch):
    monkeypatch.setattr("stripe.checkout.Session.create", lambda **kw: pytest.fail("No purchase"))
    assert client.post("/api/checkout", json=body()).status_code == 403
    assert (
        client.post(
            "/api/checkout", json={**body(), "workspace": "other"}, headers={"x-csrf-token": "csrf"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/checkout", json=body("free"), headers={"x-csrf-token": "csrf"}
        ).status_code
        == 403
    )


def test_one_time_or_mispriced_price_fails_closed(client, monkeypatch):
    monkeypatch.setattr(
        "stripe.Price.retrieve",
        lambda *a, **kw: {
            "active": True,
            "unit_amount": 1000,
            "currency": "usd",
            "recurring": None,
        },
    )
    assert (
        client.post("/api/checkout", json=body(), headers={"x-csrf-token": "csrf"}).status_code
        == 403
    )


def test_return_page_never_grants_entitlement_and_rejects_foreign_session(client, monkeypatch):
    current = {
        "metadata": {"workspace": "space-a"},
        "customer": "cus_a",
        "mode": "subscription",
        "livemode": False,
        "payment_status": "paid",
        "status": "complete",
    }
    monkeypatch.setattr("stripe.checkout.Session.retrieve", lambda *a, **kw: current)
    response = client.get("/api/checkout/status?session_id=cs_test_return0001")
    assert response.status_code == 200 and response.json()["billing_status"] == "pending"
    assert client.app.state.store.balance("space-a")["status"] == "pending"
    current["metadata"]["workspace"] = "foreign"
    assert client.get("/api/checkout/status?session_id=cs_test_return0001").status_code == 403
    current["metadata"]["workspace"] = "space-a"
    current["customer"] = "cus_other"
    assert client.get("/api/checkout/status?session_id=cs_test_return0001").status_code == 403
    current["customer"] = "cus_a"
    current["livemode"] = True
    assert client.get("/api/checkout/status?session_id=cs_test_return0001").status_code == 403


@pytest.mark.parametrize(
    "invoice, expected_status",
    [
        ({"paid": True}, "active"),
        ({"status": "paid"}, "active"),
        ({"status": "open"}, "inactive"),
        ({"status": "uncollectible"}, "inactive"),
    ],
)
def test_signed_webhook_uses_paid_invoice_and_rejects_live_events(
    client, monkeypatch, invoice, expected_status
):
    current = {
        "metadata": {"workspace": "space-a", "plan": "monthly"},
        "customer": "cus_a",
        "status": "active",
        "latest_invoice": invoice,
        "items": {
            "data": [
                {
                    "price": {"id": "price_monthly"},
                    "quantity": 1,
                    "current_period_start": 100,
                    "current_period_end": int(time.time()) + 3600,
                }
            ]
        },
    }
    monkeypatch.setattr("stripe.Subscription.retrieve", lambda *a, **kw: current)
    event = {
        "id": "evt_sandbox",
        "livemode": False,
        "type": "invoice.paid",
        "data": {"object": {"subscription": "sub_test"}},
    }

    def send():
        payload = json.dumps(event).encode()
        return client.post(
            "/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sign(payload, "whsec_fixture")},
        )

    assert send().status_code == 200 and send().status_code == 200
    assert client.app.state.store.balance("space-a")["allowance"] == 2_000_000
    assert client.app.state.store.balance("space-a")["status"] == expected_status
    event["livemode"] = True
    event["id"] = "evt_live"
    assert send().status_code == 400
    assert client.app.state.config.gateway_enabled is False


def test_google_oauth_remembers_selected_plan_on_server(client, monkeypatch):
    client.get("/auth/google?plan=annual", follow_redirects=False)
    state = client.cookies.get("aedrova_oauth")
    assert client.app.state.store.session(state)["plan"] == "annual"
    monkeypatch.setattr(
        client.app.state.identity, "request", lambda *a, **kw: {"access_token": "access"}
    )
    response = client.get("/auth/callback?code=test_code", follow_redirects=False)
    assert response.headers["location"] == "/account?plan=annual"


def test_subscription_failure_routes_to_management_instead_of_double_subscription(
    client, monkeypatch
):
    store = client.app.state.store
    store.subscription(
        "evt_inactive",
        "cus_a",
        "sub_existing",
        "monthly",
        "inactive",
        100,
        int(time.time()) + 3600,
        PLAN_POLICY["monthly"],
    )
    monkeypatch.setattr("stripe.Subscription.retrieve", lambda *a, **kw: {"status": "past_due"})
    monkeypatch.setattr("stripe.checkout.Session.create", lambda **kw: pytest.fail("No duplicate"))
    assert (
        client.post("/api/checkout", json=body(), headers={"x-csrf-token": "csrf"}).status_code
        == 403
    )


def test_explicit_portal_configuration_and_workspace_return(client, monkeypatch):
    client.app.state.config.stripe_portal_configuration = "bpc_test_portal"
    calls = []

    def create(**kw):
        calls.append(kw)
        return {"url": "https://billing.stripe.com/p/session/test"}

    monkeypatch.setattr("stripe.billing_portal.Session.create", create)
    response = client.post("/api/portal/space-a", json={}, headers={"x-csrf-token": "csrf"})
    assert response.status_code == 200
    assert calls[0]["configuration"] == "bpc_test_portal"
    assert calls[0]["customer"] == "cus_a"
    assert calls[0]["return_url"].endswith("/account?workspace=space-a")


def test_provisioner_only_creates_approved_test_prices_and_reuses_lookup(tmp_path, monkeypatch):
    from scripts.setup_stripe import provision

    calls = []
    monkeypatch.setattr("stripe.Product.create", lambda **kw: {"id": "prod_fixture"})

    def listing(**kw):
        if "annual" in kw["lookup_keys"][0]:
            return {
                "data": [
                    {
                        "id": "price_annual",
                        "livemode": False,
                        "active": True,
                        "unit_amount": 20000,
                        "currency": "usd",
                        "recurring": {"interval": "year", "interval_count": 1},
                    }
                ]
            }
        return {"data": []}

    monkeypatch.setattr("stripe.Price.list", listing)

    def create(**kw):
        calls.append(kw)
        return {
            "id": "price_monthly",
            "livemode": False,
            "active": True,
            "unit_amount": kw["unit_amount"],
            "currency": kw["currency"],
            "recurring": kw["recurring"],
        }

    monkeypatch.setattr("stripe.Price.create", create)
    output = tmp_path / "plans.json"
    provision(Config(stripe_key="sk_test_fixture"), output)
    data = json.loads(output.read_text())
    assert data["annual"]["price_id"] == "price_annual"
    assert data["monthly"]["amount_cents"] == 1000 and len(calls) == 1
    assert calls[0]["recurring"] == {"interval": "month", "interval_count": 1}
    with pytest.raises(ValueError, match="Only Stripe test"):
        provision(Config(stripe_key="sk_live_fixture"), output)
