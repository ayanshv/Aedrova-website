"""Disposable ledger restore drill; no hosted backup or customer data is touched."""

import sqlite3
import time

import pytest
from cryptography.fernet import Fernet

from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied, Store


def test_restored_ledger_preserves_money_replay_private_sessions_and_pending_work(tmp_path):
    key = Fernet.generate_key().decode()
    source = tmp_path / "source.sqlite"
    restored = tmp_path / "restored.sqlite"
    store = Store(f"sqlite:///{source}", encryption_key=key)
    store.customer("workspace", "customer")
    now = int(time.time())
    store.subscription("evt_paid", "customer", "subscription", "monthly", "active",
                       now - 10, now + 86400, PLAN_POLICY["monthly"])
    store.session("private-session", {"access_token": "synthetic-private-value"})
    token = store.create_run("member", "workspace", "codex", "request-0001")["token"]
    run = store.run(token)
    completed, _ = store.reserve(run, "completed", 100)
    store.settle(completed, 80, b"private-result")
    pending, _ = store.reserve(run, "pending", 200)
    before = store.balance("workspace")
    # SQLite's backup API provides a consistent committed snapshot, including WAL.
    with sqlite3.connect(source) as original, sqlite3.connect(restored) as target:
        original.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    store.engine.dispose()
    recovered = Store(f"sqlite:///{restored}", encryption_key=key)
    assert recovered.balance("workspace") == before
    assert recovered.session("private-session")["access_token"] == "synthetic-private-value"
    assert recovered.run(token)["id"] == run["id"]
    assert recovered.reserve(run, "completed", 100)[1] == b"private-result"
    recovered.settle(completed, 80, b"private-result")
    assert recovered.balance("workspace") == before
    assert recovered.subscription("evt_paid", "customer", "subscription", "monthly", "active",
                                  now - 10, now + 86400, PLAN_POLICY["monthly"]) is False
    # Uncertain in-flight requests remain reserved; restore never refunds them silently.
    recovered.settle(pending, None)
    assert recovered.balance("workspace")["spent"] == 280
    recovered.engine.dispose()
    wrong_key = Store(f"sqlite:///{restored}", encryption_key=Fernet.generate_key().decode())
    with pytest.raises(Denied, match="expired"):
        wrong_key.session("private-session")
    wrong_key.engine.dispose()
