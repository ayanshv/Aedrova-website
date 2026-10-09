"""Real service boundaries with deterministic provider HTTP responses; no live tokens."""

import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from test_dots import system as dot_system  # noqa: F401

from aedrova_site.bud_connections import BudConnections
from aedrova_site.bud_providers import ReadProvider, validate_resource
from aedrova_site.store import Denied


@pytest.fixture
def system(dot_system):  # noqa: F811
    return dot_system


@pytest.fixture
def connections(system):
    dots, dot, user = system

    def transport(request):
        assert request.url.host == "api.figma.com"
        assert request.method == "GET"
        assert request.headers["X-Figma-Token"] == "private-fixture-token"
        return httpx.Response(200, json={"name": "Product", "document": {"children": []}})

    service = BudConnections(dots, transport=httpx.MockTransport(transport))
    dots.connections = service
    yield service, dot, user
    service.close()


def connect(service, dot):
    return service.connect(
        "session",
        dot["workspace_id"],
        dot["id"],
        "figma",
        "fileKey123",
        "private-fixture-token",
        24,
    )


def test_multiple_resources_encrypted_and_private_by_user(connections):
    service, dot, user = connections
    first = connect(service, dot)
    service.connect(
        "session",
        dot["workspace_id"],
        dot["id"],
        "figma",
        "secondFile",
        "private-fixture-token",
        24,
    )
    rows = service.listing(dot, user)
    assert len(rows) == 2
    assert "private-fixture-token" not in json.dumps(rows)
    with service.store.tx() as db:
        assert "private-fixture-token" not in str(
            db.execute(text("SELECT secret FROM bud_connections")).scalars().all()
        )
    catalog = service.dots.list("session", dot["workspace_id"])
    tool = first["id"] + ".design"
    assert tool in catalog[0]["tools"]
    assert "repository" not in catalog[0]["tools"]  # OAuth was never authorized
    result = service.dots.execute(
        "session", dot["workspace_id"], [{"dot": dot["id"], "tool": tool}]
    )[0]
    assert result["provider"] == "figma" and result["untrusted"]
    assert result["records"]["name"] == "Product"
    service.dots.identity.require.return_value = {"id": str(uuid4())}
    assert service.listing(dot, service.dots.identity.require.return_value["id"]) == []
    with pytest.raises(Denied, match="authorization"):
        service.execute("other", dot["workspace_id"], dot["id"], tool)
    with pytest.raises(Denied):
        service.disconnect("other", dot["workspace_id"], dot["id"], first["id"])


def test_revocation_rotation_expiry_and_version_withhold_evidence(connections):
    service, dot, user = connections
    first = connect(service, dot)
    second = connect(service, dot)
    assert first["id"] != second["id"]
    assert len(service.listing(dot, user)) == 1
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], first["id"] + ".design")
    dot["version"] += 1
    assert service.listing(dot, user)[0]["status"] == "Needs authorization"
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], second["id"] + ".design")
    dot["version"] -= 1
    with service.store.tx() as db:
        db.execute(text("UPDATE bud_connections SET expires=0"))
    assert service.listing(dot, user) == []


def test_disconnect_during_read_and_failed_auth_never_connect(connections):
    service, dot, user = connections
    saved = connect(service, dot)

    def revoked(*args):
        service.disconnect("session", dot["workspace_id"], dot["id"], saved["id"])
        return {"records": []}

    service.providers["figma"].execute = revoked
    with pytest.raises(Denied, match="disconnected"):
        service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + ".design")
    service.providers["figma"].execute = lambda *_: (_ for _ in ()).throw(
        Denied("Permission issue")
    )
    with pytest.raises(Denied):
        connect(service, dot)
    assert service.listing(dot, user) == []


@pytest.mark.parametrize(
    "provider,resource",
    [
        ("figma", "https://evil.test"),
        ("notion", "../secret"),
        ("supabase", "a?keys"),
        ("stripe", "https://api.stripe.com"),
        ("github", "a/../b"),
        ("unknown", "anything"),
    ],
)
def test_resources_fail_closed(provider, resource):
    with pytest.raises(Denied):
        validate_resource(provider, resource)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 302])
def test_provider_failures_do_not_leak_secrets_or_follow_redirect(status):
    seen = []

    def transport(request):
        seen.append(request.url.host)
        return httpx.Response(
            status,
            headers={"Location": "https://evil.test"},
            json={"error": "private-fixture-token"},
        )

    provider = ReadProvider("figma", transport=httpx.MockTransport(transport))
    with pytest.raises(Denied) as error:
        provider.execute("private-fixture-token", "fileKey123", "design")
    assert "private-fixture-token" not in str(error.value)
    assert seen == ["api.figma.com"]
    provider.close()


@pytest.mark.parametrize(
    "provider,resource,payload,tool",
    [
        ("figma", "fileKey123", {"name": "Design", "document": {"children": []}}, "design"),
        ("notion", str(uuid4()), {"properties": {}, "results": []}, "page"),
        (
            "supabase",
            "abcdefghijklmnopqrst",
            {"id": "abcdefghijklmnopqrst", "name": "Project", "api_keys": ["must-not-return"]},
            "project",
        ),
        (
            "stripe",
            "acct_example123",
            {
                "id": "acct_example123",
                "email": "must-not-return",
                "available": [{"amount": 100, "currency": "usd"}],
                "pending": [],
            },
            "balance",
        ),
        ("instagram", "123456789", {"id": "123456789", "username": "brand"}, "profile"),
        (
            "tiktok",
            "openid123",
            {
                "data": {"user": {"open_id": "openid123", "display_name": "Brand"}},
                "error": {"code": "ok"},
            },
            "profile",
        ),
        (
            "search",
            "AI workspaces",
            {
                "web": {
                    "results": [
                        {
                            "title": "Research",
                            "url": "https://example.com",
                            "description": "Evidence",
                        }
                    ]
                }
            },
            "search",
        ),
        (
            "vercel",
            "prj_example123",
            {"id": "prj_example123", "name": "App", "env": ["must-not-return"]},
            "project",
        ),
    ],
)
def test_each_adapter_reads_actual_endpoint_and_normalizes(provider, resource, payload, tool):
    seen = []

    def transport(request):
        seen.append(request)
        return httpx.Response(
            200, json={**payload, "id": resource} if provider == "notion" else payload
        )

    adapter = ReadProvider(provider, transport=httpx.MockTransport(transport))
    result = adapter.execute(
        "rk_test_fixturetoken" if provider == "stripe" else "private-fixture-token", resource, tool
    )
    assert result["untrusted"] and result["coverage"] and result["source"].startswith("https://")
    assert "must-not-return" not in json.dumps(result)
    assert all(r.url.scheme == "https" for r in seen)
    assert all(r.method == "GET" for r in seen)
    adapter.close()


def test_oversized_and_malformed_response_and_credential_content_fail_closed():
    for payload in [
        {"document": "bad"},
        {"name": "private-fixture-token"},
        {"name": "a" * (513 * 1024)},
    ]:
        adapter = ReadProvider(
            "figma",
            transport=httpx.MockTransport(lambda request, p=payload: httpx.Response(200, json=p)),
        )
        with pytest.raises(Denied):
            adapter.execute("private-fixture-token", "fileKey123", "design")
        adapter.close()


def test_failed_read_updates_status_and_reconnect_recovers(connections):
    service, dot, user = connections
    saved = connect(service, dot)
    original = service.providers["figma"].execute
    service.providers["figma"].execute = lambda *_: (_ for _ in ()).throw(
        Denied("Needs authorization")
    )
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + ".design")
    assert service.listing(dot, user)[0]["status"] == "Needs authorization"
    service.providers["figma"].execute = original
    replacement = connect(service, dot)
    assert replacement["id"] != saved["id"]
    assert service.listing(dot, user)[0]["status"] == "Connected"


def test_membership_revocation_before_read_never_contacts_provider(connections):
    service, dot, _ = connections
    saved = connect(service, dot)
    from unittest.mock import MagicMock

    service.providers["figma"].execute = MagicMock()
    service.dots.identity.require.side_effect = Denied("No membership")
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + ".design")
    service.providers["figma"].execute.assert_not_called()


def test_connector_routes_auth_csrf_and_validation_never_echo_password(tmp_path):
    from unittest.mock import MagicMock

    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient

    from aedrova_site.app import create_app
    from aedrova_site.config import Config

    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'routes.db'}",
            encryption_key=Fernet.generate_key().decode(),
            dots_enabled=True,
        )
    )
    dot = dict(
        id=str(uuid4()),
        workspace_id=str(uuid4()),
        version=1,
        provider="github",
        resource="owner/repo",
        name="Builder",
    )
    app.state.identity.user = MagicMock(return_value={"id": "owner"})
    app.state.identity.require = MagicMock(return_value={"id": "owner"})
    app.state.identity.request = MagicMock(return_value=[dot])
    app.state.dots.connections.providers["figma"].execute = MagicMock(return_value={"records": []})
    secret = "private-fixture-token"
    body = {
        "workspace": dot["workspace_id"],
        "dot": dot["id"],
        "provider": "figma",
        "resource": "fileKey123",
        "credential": secret,
    }
    with TestClient(app) as client:
        assert client.post("/api/buds/connections", json=body).status_code == 403
        bearer = {"authorization": "Bearer fixture"}
        invalid = client.post("/api/buds/connections", json={**body, "hours": 0}, headers=bearer)
        assert invalid.status_code == 422 and secret not in invalid.text
        assert client.get("/api/buds/connectors", headers=bearer).status_code == 200
        app.state.store.session("cookie", {"access_token": "web-session", "csrf": "proof"})
        client.cookies.set("aedrova_session", "cookie")
        assert client.post("/api/buds/connections", json=body).status_code == 403
        connected = client.post(
            "/api/buds/connections", json=body, headers={"x-csrf-token": "proof"}
        )
        assert connected.status_code == 200 and secret not in connected.text
        listing = client.get(
            "/api/buds/connections", params={"workspace": dot["workspace_id"], "dot": dot["id"]}
        )
        assert listing.status_code == 200 and secret not in listing.text
        assert "Connected" in listing.text
        rejected = client.post(
            "/api/buds/connections",
            json=body,
            headers={"origin": "https://evil.test", "x-csrf-token": "proof"},
        )
        assert rejected.status_code == 403
