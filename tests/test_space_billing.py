"""Real credit ledger invariants; synthetic identity roots never touch production."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from aedrova_site import budgets
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied, Store


@pytest.fixture
def ledger(tmp_path):
    value = Store(
        f"sqlite:///{tmp_path}/spaces.sqlite",
        hierarchy_enabled=True,
        usage_limits={
            "annual": {"five_hour_budget": 1_000_000},
            "monthly": {"five_hour_budget": 1_000_000},
        },
    )
    for w in ("root", "other"):
        value.customer(w, "cus_" + w)
        value.subscription(
            "event_" + w,
            "cus_" + w,
            "sub_" + w,
            "annual",
            "active",
            int(time.time()) - 60,
            int(time.time()) + 86400 * 365,
            PLAN_POLICY["annual"],
        )
    yield value
    value.engine.dispose()


def access(ledger, origin, root="root", user="u"):
    token = ledger.create_run(user, origin, "codex", "operation-" + origin, billing_workspace=root)
    return ledger.run(token["token"])


def test_subspaces_share_pool_independent_space_does_not(ledger):
    a, b = access(ledger, "child-a"), access(ledger, "child-b", user="v")
    identifier, _ = ledger.reserve(a, "one", 300_000)
    ledger.settle(identifier, 200_000, b"ok")
    second, _ = ledger.reserve(b, "two", 300_000)
    ledger.settle(second, 300_000, b"ok")
    assert ledger.balance("root")["monthly_spent"] == 500_000
    assert ledger.balance("other")["monthly_spent"] == 0
    with ledger.tx(write=False) as db:
        assert db.execute(text("SELECT COUNT(*) FROM billing")).scalar() == 2
        rows = db.execute(
            text("SELECT billing_workspace,originating_workspace FROM inference_attribution")
        ).all()
        assert set(rows) == {("root", "child-a"), ("root", "child-b")}


def test_parallel_subspaces_cannot_overspend_rolling_capacity(ledger):
    a, b = access(ledger, "child-a"), access(ledger, "child-b", user="v")

    def attempt(run):
        try:
            return ledger.reserve(run, "charge", 700_000)[0]
        except Denied:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (a, b)))
    assert sum(bool(x) for x in results) == 1
    assert ledger.balance("root")["five_hour_spent"] == 700_000


def test_rolling_expiry_releases_capacity_without_monthly_reset(ledger):
    run = access(ledger, "child")
    identifier, _ = ledger.reserve(run, "one", 900_000)
    ledger.settle(identifier, 900_000, b"ok")
    with pytest.raises(Denied, match="five-hour"):
        ledger.reserve(run, "two", 200_000)
    with ledger.tx() as db:
        db.execute(text("UPDATE inference SET created=:t"), {"t": int(time.time()) - 18001})
    assert ledger.balance("root")["five_hour_spent"] == 0
    assert ledger.reserve(run, "two", 200_000)[0]


def test_moving_subspace_preserves_charge_root_and_replay(ledger):
    run = access(ledger, "child")
    identifier, _ = ledger.reserve(run, "one", 100_000)
    ledger.settle(identifier, 80_000, b"ok")
    ledger.end_run(run["id"], run["user_id"])
    token = ledger.create_run("u", "child", "codex", "new-operation", billing_workspace="other")
    moved = ledger.run(token["token"])
    second, _ = ledger.reserve(moved, "two", 100_000)
    ledger.settle(second, 90_000, b"new")
    ledger.settle(identifier, 80_000, b"ok")
    assert ledger.balance("root")["monthly_spent"] == 80_000
    assert ledger.balance("other")["monthly_spent"] == 90_000


def test_failed_request_releases_reservation_and_cannot_charge_twice(ledger):
    run = access(ledger, "child")
    identifier, _ = ledger.reserve(run, "one", 100_000)
    ledger.settle(identifier, 0)
    ledger.settle(identifier, 100_000)
    assert ledger.balance("root")["monthly_spent"] == 0
    assert ledger.balance("root")["five_hour_spent"] == 0


def test_annual_monthly_anniversary_handles_short_months(monkeypatch):
    def stamp(y, m, d):
        return int(datetime(y, m, d, 12, 30, tzinfo=UTC).timestamp())

    monkeypatch.setattr(time, "time", lambda: stamp(2026, 2, 28) + 10)
    start, end = budgets.billing_month(
        {"plan": "annual", "period_start": stamp(2026, 1, 31), "period_end": stamp(2027, 1, 31)}
    )
    assert start == stamp(2026, 2, 28)
    assert end == stamp(2026, 3, 31)


def test_billing_routes_reject_child_checkout_and_member_changes(tmp_path):
    from fastapi.testclient import TestClient

    from aedrova_site.app import create_app
    from aedrova_site.config import Config

    app = create_app(
        Config(database=f"sqlite:///{tmp_path}/routes.sqlite", space_hierarchy_enabled=True)
    )
    app.state.store.session("browser", {"access_token": "access", "csrf": "csrf"})
    identity = app.state.identity
    identity.billing_context = lambda token, w: {
        "workspace": w,
        "billing_workspace": "root",
        "parent_id": "root" if w == "child" else None,
        "user_id": "member",
    }

    def require(token, w, *, billing=False):
        if billing:
            raise Denied("Only an authorized workspace owner or admin can manage billing.")
        return {"id": "member"}

    identity.require = require
    with TestClient(app) as client:
        client.cookies.set("aedrova_session", "browser")
        response = client.post(
            "/api/checkout",
            json={"workspace": "child", "plan": "monthly", "request_id": "request-00000001"},
            headers={"x-csrf-token": "csrf"},
        )
        assert response.status_code == 403 and "shares" in response.text
        assert (
            client.post("/api/portal/child", json={}, headers={"x-csrf-token": "csrf"}).status_code
            == 403
        )
        assert (
            client.post(
                "/api/subspaces/child/move",
                json={"parent_id": "other", "expected_parent": "root", "confirmed": False},
                headers={"x-csrf-token": "csrf"},
            ).status_code
            == 403
        )
    with app.state.store.tx(write=False) as db:
        assert db.execute(text("SELECT COUNT(*) FROM billing")).scalar() == 0


def test_owner_threshold_warnings_are_shared_and_deduplicated(ledger):
    run = access(ledger, "child")
    with ledger.tx() as db:
        db.execute(text("UPDATE billing SET allowance=1000000"))
    ledger.usage_policy["annual"]["budget"] = 1_000_000
    identifier, _ = ledger.reserve(run, "one", 950_000)
    ledger.settle(identifier, 950_000, b"ok")
    assert ledger.balance("root")["usage_alerts"] == [75, 90]
    assert ledger.balance("root")["usage_alerts"] == [75, 90]
    assert ledger.balance("other")["usage_alerts"] == []
    with ledger.tx(write=False) as db:
        assert db.execute(text("SELECT COUNT(*) FROM space_budget_alerts")).scalar() == 2
