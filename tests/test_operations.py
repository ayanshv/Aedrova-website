"""Operational probes reject unavailable services and never repair/mutate the ledger."""

import json
import time

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from aedrova_site.budgets import month
from aedrova_site.config import Config
from aedrova_site.store import Store
from scripts.check_operations import database_checks, healthy, main, readiness


def test_private_monitor_detects_budget_and_stale_work_without_mutation(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'monitor.sqlite'}")
    config = Config(company_budget_microusd=1000, free_pool_microusd=100)
    period, _ = month()
    with store.tx() as db:
        db.execute(text("INSERT INTO budget_reservations VALUES('x','company',:p,900,NULL)"),
                   {"p": period})
        db.execute(text("INSERT INTO budget_reservations VALUES('x','free-pool',:p,90,NULL)"),
                   {"p": period})
        db.execute(text("""INSERT INTO runs(id,user_id,workspace,provider,token_hash,expires,
            state,request_key)
            VALUES('r','u','w','codex','hash',:t,
            'active','request')"""), {"t": int(time.time()) - 1})
        db.execute(text("""INSERT INTO inference(id,run_id,period_start,amount,state,created)
            VALUES('i','r',:p,10,'pending',:p)"""), {"p": period})
    with store.engine.connect() as db, db.begin():
        report = database_checks(db, config)
        assert report["expired_pending_requests"] == 1
        assert report["company_budget_below_90_percent"] is False
        assert report["free_pool_below_90_percent"] is False
        with pytest.raises(OperationalError, match="readonly"):
            db.execute(text("DELETE FROM runs"))
    assert not healthy({**report, "http_ready": True})
    with store.tx(write=False) as db:
        assert db.scalar(text("SELECT count(*) FROM runs")) == 1
    store.engine.dispose()


@pytest.mark.parametrize("status,body", [
    (503, '{"status":"unavailable"}'), (302, '{}'), (200, '{"status":"ok"}'),
    (200, 'x' * 16385), (200, '{"status":"ready"}'),
])
def test_readiness_requires_bounded_exact_ready_response(status, body):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert readiness(Config(origin="https://staging.example"), client) is (
            status == 200 and body == '{"status":"ready"}'
        )
    assert len(calls) == 1 and calls[0].url.path == "/health/ready"
    assert "authorization" not in calls[0].headers


def test_failure_report_never_exposes_credentials(monkeypatch, capsys):
    secret = "private-database-credential"
    monkeypatch.setattr(Config, "load", lambda: (_ for _ in ()).throw(ValueError(secret)))
    with pytest.raises(SystemExit, match="1"):
        main()
    output = capsys.readouterr().out
    assert secret not in output
    assert json.loads(output)["status"] == "attention_required"
