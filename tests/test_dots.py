import hashlib
import json
import time
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.dots import DotService, GitHubProvider
from aedrova_site.store import Denied, Store


@pytest.fixture
def system(tmp_path):
    config = Config(
        database=f"sqlite:///{tmp_path / 'dots.db'}",
        encryption_key=Fernet.generate_key().decode(),
        dots_enabled=True,
        github_dot_client_id="fixture",
        github_dot_client_secret="fixture-secret",
    )
    store = Store(config.database, config.encryption_key)
    identity = MagicMock()
    workspace, user, dot_id = map(str, (uuid4(), uuid4(), uuid4()))
    dot = dict(
        id=dot_id,
        workspace_id=workspace,
        provider="github",
        resource="owner/repo",
        name="GitHub",
        version=1,
    )
    identity.require.return_value = {"id": user}
    identity.request.return_value = [dot]

    def transport(request):
        if request.url.host == "github.com":
            return httpx.Response(
                200,
                json={
                    "access_token": "test-secret-fixture",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        if request.method == "DELETE":
            return httpx.Response(204)
        if "/commits" in request.url.path:
            return httpx.Response(
                200,
                json=[{"sha": "a", "commit": {"message": "Ship", "committer": {"date": "today"}}}],
            )
        return httpx.Response(200, json={"full_name": "owner/repo", "private": True})

    service = DotService(config, store, identity, transport=httpx.MockTransport(transport))
    yield service, dot, user
    service.providers["github"].close()
    store.engine.dispose()


def authorize(system):
    service, dot, user = system
    url = service.start("session", dot["workspace_id"], dot["id"])
    state = url.rsplit("/", 1)[-1]
    payload = service.state(state)
    service.callback(state, payload["proof"], "code")
    return service, dot, user


def test_oauth_encrypts_secrets_and_normalizes_only_selected_tools(system):
    service, dot, user = authorize(system)
    result = service.execute(
        "session", dot["workspace_id"], [{"dot": dot["id"], "tool": "changes"}]
    )
    assert result[0]["records"][0]["kind"] == "CodeChange"
    assert result[0]["untrusted"] and result[0]["citation"].startswith("dot:")
    assert "test-secret-fixture" not in json.dumps(service.list("session", dot["workspace_id"]))
    assert "test-secret-fixture" not in service.grant(dot, user)["secret"]
    with service.store.tx() as db:
        assert db.execute(text("SELECT count(*) FROM dot_audit")).scalar() == 3


def test_state_is_single_use_browser_bound_and_expires(system):
    service, dot, _ = system
    state = service.start("session", dot["workspace_id"], dot["id"]).rsplit("/", 1)[-1]
    service.state(state)
    with pytest.raises(Denied, match="browser changed"):
        service.callback(state, "wrong-browser", "code")
    with pytest.raises(Denied, match="expired"):
        service.callback(state, "wrong-browser", "code")
    state = service.start("session", dot["workspace_id"], dot["id"]).rsplit("/", 1)[-1]
    with service.store.tx() as db:
        db.execute(text("UPDATE dot_oauth SET expires=0"))
    with pytest.raises(Denied):
        service.state(state)


def test_user_and_workspace_isolation_and_expired_grant(system):
    service, dot, user = authorize(system)
    service.identity.require.return_value = {"id": str(uuid4())}
    with pytest.raises(Denied, match="authorization"):
        service.execute(
            "other-session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}]
        )
    service.identity.require.return_value = {"id": user}
    with service.store.tx() as db:
        db.execute(text("UPDATE dot_grants SET expires=:t"), {"t": int(time.time()) - 1})
    assert service.list("session", dot["workspace_id"])[0]["status"] == "Needs authorization"
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}])
    service.identity.require.side_effect = Denied("No membership")
    with pytest.raises(Denied):
        service.list("session", str(uuid4()))


def test_permission_failure_and_disconnection_revoke(system):
    service, dot, user = authorize(system)
    service.providers["github"].client.close()
    service.providers["github"].client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(403))
    )
    with pytest.raises(Denied, match="Permission issue"):
        service.execute("session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}])
    assert service.grant(dot, user)["status"] == "Permission issue"
    assert (
        service.disconnect("session", dot["workspace_id"], dot["id"])["provider_revoked"] is False
    )
    assert service.grant(dot, user) is None


def test_disconnect_during_external_read_withholds_result(system):
    service, dot, user = authorize(system)

    def read(*_args):
        with service.store.tx() as db:
            db.execute(text("DELETE FROM dot_grants"))
        return {"records": []}

    service.providers["github"].execute = read
    with pytest.raises(Denied, match="disconnected"):
        service.execute("session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}])


@pytest.mark.parametrize("tool", ["https://attacker.test", "write", "delete", "../../secrets"])
def test_model_cannot_expand_capabilities(system, tool):
    service, dot, _ = authorize(system)
    service.providers["github"].execute = MagicMock()
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], [{"dot": dot["id"], "tool": tool}])
    service.providers["github"].execute.assert_not_called()


def test_provider_does_not_follow_redirects_or_return_secrets():
    provider = GitHubProvider(
        Config(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "https://attacker.test"})
        ),
    )
    with pytest.raises(Denied):
        provider.execute("secret", "owner/repo", "repository")
    provider.close()
    provider = GitHubProvider(
        Config(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"description": "ghp_" + "a" * 30})
        ),
    )
    with pytest.raises(Denied, match="sensitive"):
        provider.execute("secret", "owner/repo", "repository")
    provider.close()


def test_disabled_and_invalid_api_inputs_do_not_read_provider(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'api.db'}"))
    app.state.identity.user = MagicMock(return_value={"id": "u"})
    with TestClient(app) as client:
        headers = {"authorization": "Bearer fixture"}
        assert (
            client.get("/api/dots", params={"workspace": str(uuid4())}, headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                "/api/dots/tools",
                json={"workspace": str(uuid4()), "calls": [], "token": "secret"},
                headers=headers,
            ).status_code
            == 422
        )
        providers = client.get("/api/dots/providers", headers=headers).json()["providers"]
        assert all(not p["available"] for p in providers)
    assert (
        "secret"
        not in client.post("/api/dots/tools", json={"token": "secret"}, headers=headers).text
    )


def test_signed_events_dedupe_and_ignore_unconfigured_webhooks(tmp_path):
    import hmac

    config = Config(
        database=f"sqlite:///{tmp_path / 'events.db'}",
        dots_enabled=True,
        encryption_key=Fernet.generate_key().decode(),
        github_dot_webhook_secret="webhook-fixture",
    )
    app = create_app(config)
    payload = b'{"repository":{"full_name":"owner/repo"}}'
    signature = "sha256=" + hmac.new(b"webhook-fixture", payload, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        assert client.post("/dots/github/events", content=payload).status_code == 403
        headers = {"x-hub-signature-256": signature, "x-github-delivery": "fixture-1"}
        for _ in range(2):
            assert (
                client.post("/dots/github/events", content=payload, headers=headers).status_code
                == 200
            )
        with app.state.store.tx() as db:
            assert (
                db.execute(
                    text("SELECT count(*) FROM events WHERE id='dot-github:fixture-1'")
                ).scalar()
                == 1
            )


def test_browser_authorization_requires_matching_aedrova_identity(tmp_path):
    config = Config(
        database=f"sqlite:///{tmp_path / 'browser.db'}",
        dots_enabled=True,
        encryption_key=Fernet.generate_key().decode(),
        github_dot_client_id="fixture",
        github_dot_client_secret="fixture-secret",
    )
    app = create_app(config)
    dot = dict(
        id=str(uuid4()),
        workspace_id=str(uuid4()),
        provider="github",
        resource="owner/repo",
        name="GitHub",
        version=1,
    )
    app.state.identity.require = MagicMock(return_value={"id": "owner"})
    app.state.identity.request = MagicMock(return_value=[dot])
    app.state.identity.user = MagicMock(return_value={"id": "owner"})
    with TestClient(app) as client:
        url = app.state.dots.start("native-session", dot["workspace_id"], dot["id"])
        state = url.rsplit("/", 1)[-1]
        response = client.get("/dots/authorize/" + state, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"].startswith(
            "/auth/google?dot="
        )
        app.state.store.session("web-cookie", {"access_token": "web-session", "csrf": "csrf"})
        client.cookies.set("aedrova_session", "web-cookie")
        app.state.identity.user.return_value = {"id": "other-user"}
        assert client.get("/dots/authorize/" + state, follow_redirects=False).status_code == 403
        app.state.identity.user.return_value = {"id": "owner"}
        response = client.get("/dots/authorize/" + state, follow_redirects=False)
        assert response.status_code == 307
        assert "code_challenge_method=S256" in response.headers["location"]
        assert "fixture-secret" not in response.text + response.headers["location"]
        assert "HttpOnly" in response.headers["set-cookie"]


def test_removing_dot_purges_all_user_grants_and_requires_admin(system):
    service, dot, user = authorize(system)
    service.identity.require.side_effect = lambda token, workspace, **kwargs: (
        (_ for _ in ()).throw(Denied("admin required")) if kwargs.get("billing") else {"id": user}
    )
    with pytest.raises(Denied, match="admin required"):
        service.remove("session", dot["workspace_id"], dot["id"], 1)
    assert service.grant(dot, user)
    service.identity.require.side_effect = None
    assert service.remove("session", dot["workspace_id"], dot["id"], 1)["provider_revoked"]
    assert service.grant(dot, user) is None


def test_transient_failure_can_be_retried_without_reauthorization(system):
    service, dot, user = authorize(system)
    real = service.providers["github"].execute

    def fail(*_args):
        raise Denied("Temporary failure")

    service.providers["github"].execute = fail
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}])
    assert service.grant(dot, user)["status"] == "Error"
    service.providers["github"].execute = real
    assert service.execute(
        "session", dot["workspace_id"], [{"dot": dot["id"], "tool": "repository"}]
    )
    assert service.grant(dot, user)["status"] == "Connected"


def test_disconnect_revokes_stale_version_credentials_too(system):
    service, dot, user = authorize(system)
    dot["version"] = 2
    assert service.grant(dot, user) is None
    assert service.grant(dot, user, allow_stale=True)
    assert service.disconnect("session", dot["workspace_id"], dot["id"])["provider_revoked"]
    assert service.grant(dot, user, allow_stale=True) is None
