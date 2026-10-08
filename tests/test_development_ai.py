"""Local owner funding never grants public, unbounded or other-user access."""

import time

import pytest
from sqlalchemy import text

from aedrova_site.config import Config
from aedrova_site.store import Denied, Store


@pytest.mark.parametrize(
    "override",
    [
        {"production": True},
        {"origin": "https://aedrova.com"},
        {"database": "postgresql://localhost/app"},
        {"checkout_enabled": True},
        {"release_ready": True},
        {"waitlist_only": True},
    ],
)
def test_private_gate(override):
    with pytest.raises(ValueError):
        Config(development_ai=True, **override).validate()


def test_funding_scope_expiry_and_no_reset(tmp_path):
    url = f"sqlite:///{tmp_path / 'app.sqlite'}"
    store = Store(url, "", development_ai=True)
    first = store.grant_development("owner", "space", 2_000_000)
    with store.tx() as db:
        db.execute(text("UPDATE billing SET spent=1000 WHERE workspace='space'"))
    repeated = store.grant_development("owner", "space", 5_000_000, hours=168)
    assert repeated["allowance"] == 2_000_000
    assert repeated["spent"] == 1000
    assert repeated["period_end"] == first["period_end"]
    with pytest.raises(Denied):
        store.grant_development("owner", "other", 5_000_001)
    with pytest.raises(Denied):
        store.create_run("other-user", "space", "codex", "request-other-user")
    with pytest.raises(Denied):
        store.create_run("owner", "other", "codex", "request-other-space")
    assert store.create_run("owner", "space", "codex", "request-owner-001")
    with pytest.raises(Denied):
        store.create_run("owner", "space", "codex", "request-owner-002")
    with store.tx() as db:
        db.execute(
            text("UPDATE billing SET period_end=:end WHERE workspace='space'"),
            {"end": int(time.time()) - 1},
        )
    with pytest.raises(Denied):
        store.create_run("owner", "space", "codex", "request-owner-expired")
    production = Store(url, "")
    with pytest.raises(Denied):
        production.grant_development("owner", "space")
    with pytest.raises(Denied):
        production.create_run("owner", "space", "codex", "request-production")
    production.engine.dispose()
    store.engine.dispose()


def test_never_overwrite_billing(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'app.sqlite'}", "", development_ai=True)
    store.customer("space", "cus_real")
    with pytest.raises(Denied):
        store.grant_development("owner", "space")
    assert store.balance("space")["status"] != "development"
    store.engine.dispose()


def test_development_requires_fresh_owner_on_run_and_inference(tmp_path):
    from fastapi.testclient import TestClient

    from aedrova_site.app import create_app
    from tests.test_access_gateway import MODELS, Accounts

    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'app.sqlite'}",
            development_ai=True,
            gateway_enabled=True,
            models=MODELS,
            openai_key="test-only",
            anthropic_key="test-only",
        )
    )
    identity = Accounts()
    app.state.identity.user = identity.user
    app.state.identity.require = identity.require
    app.state.store.grant_development("user-a", "space-a")
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer access-a"}
        identity.role = "member"
        denied = client.post(
            "/api/runs",
            headers=headers,
            json={"workspace": "space-a", "provider": "codex", "request_id": "request-member-0001"},
        )
        assert denied.status_code == 403
        identity.role = "owner"
        response = client.post(
            "/api/runs",
            headers=headers,
            json={"workspace": "space-a", "provider": "codex", "request_id": "request-owner-0001"},
        )
        assert response.status_code == 200
        identity.role = "member"
        denied = client.post(
            "/gateway/codex/v1/responses",
            headers={"Authorization": "Bearer " + response.json()["token"]},
            json={"input": "must not reach provider"},
        )
        assert denied.status_code == 403
        assert app.state.store.balance("space-a")["reserved"] == 0
    app.state.store.engine.dispose()
