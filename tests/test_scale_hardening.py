"""Bounded overload, accounting races and content-free diagnostics."""

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.gateway import authorize_run
from aedrova_site.observability import LOG, Admission
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied, Store


@pytest.fixture
def store(tmp_path):
    value = Store(f"sqlite:///{tmp_path}/ledger.sqlite3")
    value.customer("workspace", "customer")
    value.subscription(
        "event",
        "customer",
        "subscription",
        "monthly",
        "active",
        1,
        int(time.time()) + 3600,
        PLAN_POLICY["monthly"],
    )
    yield value
    value.engine.dispose()


def test_parallel_reservations_allow_only_one_pending_request_per_run(store):
    access = store.create_run("user", "workspace", "codex", "unique-request")
    run = store.run(access["token"])

    def reserve(index):
        try:
            return store.reserve(run, str(index), 100)
        except Denied:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(32)))
    accepted = [result for result in results if result is not None]
    assert len(accepted) == 1
    assert store.balance("workspace")["reserved"] == 100
    store.settle(accepted[0][0], 30, b"fixture-response")
    assert store.balance("workspace")["spent"] == 30
    assert store.reserve(run, "next-request", 50)[1] is None


def test_authorization_database_operations_never_run_on_event_loop_thread():
    main = threading.get_ident()
    calls = []

    def worker(value):
        calls.append(threading.get_ident())
        time.sleep(0.01)
        return value

    store = SimpleNamespace(
        run=lambda token: worker(
            {"id": "run", "provider": "codex", "workspace": "w", "user_id": "u"}
        ),
        session=lambda token: worker({"access_token": "private-token"}),
        rate_limit=lambda *a, **kw: worker(None),
        development_workspace=lambda workspace: worker(False),
    )
    identity = SimpleNamespace(require=lambda *a, **kw: worker({"id": "u"}))
    request = SimpleNamespace(headers={"authorization": "Bearer build-token"})
    asyncio.run(
        authorize_run(
            request,
            "codex",
            SimpleNamespace(gateway_enabled=True, models={"codex": {}}),
            store,
            identity,
        )
    )
    assert len(calls) == 5 and all(identifier != main for identifier in calls)


def test_admission_bounds_burst_and_releases_slots_on_cancellation():
    async def scenario():
        entered = asyncio.Event()
        released = asyncio.Event()
        statuses = []

        async def slow(scope, receive, send):
            entered.set()
            await released.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        gate = Admission(slow, maximum=2)

        async def request():
            async def send(message):
                if message["type"] == "http.response.start":
                    statuses.append(message["status"])

            async def receive():
                return {"type": "http.request", "body": b""}

            await gate({"type": "http", "path": "/gateway/codex/v1/responses"}, receive, send)

        first = asyncio.create_task(request())
        await entered.wait()
        second = asyncio.create_task(request())
        await asyncio.sleep(0)
        await asyncio.gather(*(request() for _ in range(30)))
        assert gate.active == 2 and statuses == [503] * 30
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert gate.active == 1
        released.set()
        await second
        assert gate.active == 0

    asyncio.run(scenario())


def test_rate_limits_return_retry_after_and_json_without_secrets(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/web.sqlite3"))
    with TestClient(app) as client:
        for _ in range(10):
            assert client.get("/auth/google", follow_redirects=False).status_code == 303
        result = client.get("/auth/google", follow_redirects=False)
        assert result.status_code == 429
        assert 1 <= int(result.headers["retry-after"]) <= 60
        assert "Too many requests" in result.json()["error"]


def test_readiness_database_failure_is_recoverable_and_liveness_survives(tmp_path, monkeypatch):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/web.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200

        def unavailable(**kw):
            raise OperationalError("private SQL", {"token": "private-token"}, Exception("offline"))

        monkeypatch.setattr(app.state.store, "tx", unavailable)
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health").status_code == 200
        result = client.get("/api/session")
        assert result.status_code == 503
        assert "private" not in result.text


def test_structured_logs_exclude_query_credentials_and_dynamic_ids(tmp_path):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    app = create_app(Config(database=f"sqlite:///{tmp_path}/web.sqlite3"))
    handler = Capture()
    LOG.addHandler(handler)
    try:
        with TestClient(app) as client:
            result = client.get(
                "/api/balance/private-workspace?token=private-query",
                headers={"authorization": "Bearer private-bearer"},
            )
            assert len(result.headers["x-request-id"]) == 32
    finally:
        LOG.removeHandler(handler)
    serialized = json.dumps(records)
    assert "private-workspace" not in serialized
    assert "private-query" not in serialized and "private-bearer" not in serialized
    assert any(row.get("route") == "/api/balance/{workspace}" for row in records)


@pytest.mark.parametrize("value", [0, -1, 1000, True])
def test_invalid_concurrency_configuration_fails_at_startup(value):
    with pytest.raises(ValueError, match="bounded"):
        Config(gateway_max_concurrency=value).validate()


def test_indexes_match_ledger_queries(store):
    with store.tx(write=False) as db:
        indexes = {row[1] for row in db.execute(text("PRAGMA index_list('runs')"))}
        assert "runs_workspace_active" in indexes


def test_account_cannot_monopolize_runs_across_many_workspaces(store):
    for index in range(3):
        workspace, customer = f"w-{index}", f"c-{index}"
        store.customer(workspace, customer)
        store.subscription(
            f"e-{index}",
            customer,
            f"s-{index}",
            "monthly",
            "active",
            1,
            int(time.time()) + 3600,
            PLAN_POLICY["monthly"],
        )
    first = store.create_run("same-user", "w-0", "codex", "r-0")
    store.create_run("same-user", "w-1", "codex", "r-1")
    with pytest.raises(Denied, match="two active"):
        store.create_run("same-user", "w-2", "codex", "r-2")
    store.end_run(first["id"], "same-user")
    assert store.create_run("same-user", "w-2", "codex", "r-2")["id"]


def test_non_model_bodies_have_smaller_bounds_without_content_length(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/bodies.sqlite3"))
    with TestClient(app) as client:
        result = client.post("/api/inquiries", content=iter([b"x" * 32768] * 3))
        assert result.status_code == 413
