"""OAuth exchange, isolation, expiry, rotation and real-read boundaries (mock HTTP)."""

import base64
import hashlib
import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_dots import system as dot_system  # noqa: F401

from aedrova_site.app import create_app
from aedrova_site.bud_connections import BudConnections
from aedrova_site.bud_oauth import PROVIDERS, BudOAuth, state_key
from aedrova_site.bud_providers import ReadProvider
from aedrova_site.config import Config
from aedrova_site.store import Denied


@pytest.fixture
def system(dot_system):  # noqa: F811
    dots, dot, user = dot_system
    for key in ("figma", "notion", "supabase"):
        setattr(dots.config, key + "_bud_client_id", "app-id")
        setattr(dots.config, key + "_bud_client_secret", "app-secret")
    connections = BudConnections(dots)
    seen = []

    def transport(request):
        seen.append(request)
        return httpx.Response(
            200,
            json=dict(
                access_token="oauth-access-private",
                token_type="bearer",
                refresh_token="oauth-refresh-private",
                expires_in=3600,
            ),
        )

    oauth = BudOAuth(connections, transport=httpx.MockTransport(transport))
    connections.oauth = oauth
    dots.connections = connections
    connections.providers["figma"].execute = MagicMock(
        return_value={"records": {"title": "Design"}}
    )
    yield oauth, dot, user, seen
    connections.close()


def started(system, provider="figma", resource="fileKey123"):
    oauth, dot, user, _ = system
    result = oauth.start("session", dot["workspace_id"], dot["id"], provider, resource, 24)
    target, payload = oauth.authorize(result["state"], user)
    return result["state"], payload, target


def complete(system):
    oauth, dot, _, _ = system
    state, payload, _ = started(system)
    result = oauth.callback("figma", state, payload["proof"], "authorization-code")
    return result, state


def test_real_read_required_encrypted_credentials_and_poll_bound_to_account(system):
    oauth, dot, user, _ = system
    result, state = complete(system)
    oauth.connections.providers["figma"].execute.assert_called_once_with(
        "oauth-access-private", "fileKey123", "design", oauth=True
    )
    assert oauth.status("session", state) == {"status": "connected", "connection": result["id"]}
    with oauth.store.tx() as db:
        raw = str(db.execute(text("SELECT secret FROM bud_connections")).all())
        raw += str(db.execute(text("SELECT payload FROM bud_oauth")).all())
        assert "oauth-access-private" not in raw and "oauth-refresh-private" not in raw
    listing = oauth.connections.listing(dot, user)
    assert "oauth-access-private" not in json.dumps(listing)
    _, payload = oauth.state(state)
    assert "session" not in payload and "proof" not in payload and "verifier" not in payload
    oauth.dots.identity.require.return_value = {"id": str(uuid4())}
    with pytest.raises(Denied):
        oauth.status("other-account", state)
    with pytest.raises(Denied):
        oauth.connections.execute(
            "other-account", dot["workspace_id"], dot["id"], result["id"] + ".design"
        )


@pytest.mark.parametrize(
    "provider,resource",
    [
        ("github", "owner/repo"),
        ("figma", "fileKey123"),
        ("notion", str(uuid4())),
        ("supabase", "a" * 20),
    ],
)
def test_fixed_endpoints_provider_scopes_pkce_and_confidential_exchange(system, provider, resource):
    oauth, _, _, seen = system
    if provider == "supabase":
        oauth.config.origin = "https://connections.example.test"
    state, payload, target = started(system, provider, resource)
    parsed = urlparse(target)
    assert parsed.hostname == urlparse(PROVIDERS[provider][0]).hostname
    params = parse_qs(parsed.query)
    assert params["state"] == [state] and params["redirect_uri"] == [oauth.redirect(provider)]
    if provider == "notion":
        assert "code_challenge" not in params and params["owner"] == ["user"]
    else:
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(payload["verifier"].encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert params["code_challenge"] == [challenge]
    oauth.token(provider, code="code", verifier=payload["verifier"])
    request = seen[-1]
    assert str(request.url) == PROVIDERS[provider][1] and request.method == "POST"
    body = (
        json.loads(request.content)
        if provider == "notion"
        else {key: value[0] for key, value in parse_qs(request.content.decode()).items()}
    )
    assert body["grant_type"] == "authorization_code"
    assert body["redirect_uri"] == oauth.redirect(provider)
    if provider != "github":
        assert request.headers["authorization"].startswith("Basic ")
    if provider == "supabase":
        assert "scope" not in params  # Dashboard-configured Projects Read, never deprecated 'all'.


def test_wrong_browser_provider_replay_and_expiry_are_blocked(system):
    oauth, _, user, _ = system
    state, payload, _ = started(system)
    for provider, proof in (("notion", payload["proof"]), ("figma", "wrong-browser")):
        with pytest.raises(Denied, match="browser"):
            oauth.callback(provider, state, proof, "code")
    oauth.callback("figma", state, payload["proof"], "code")
    with pytest.raises(Denied):
        oauth.callback("figma", state, payload["proof"], "code")
    state, _, _ = started(system)
    with oauth.store.tx() as db:
        db.execute(text("UPDATE bud_oauth SET expires=0 WHERE id=:i"), {"i": state_key(state)})
    with pytest.raises(Denied, match="expired"):
        oauth.authorize(state, user)


def test_wrong_aedrova_account_never_opens_provider(system):
    oauth, dot, _, _ = system
    result = oauth.start("session", dot["workspace_id"], dot["id"], "figma", "fileKey123", 24)
    with pytest.raises(Denied, match="same Google"):
        oauth.authorize(result["state"], str(uuid4()))
    assert oauth.state(result["state"])[0]["status"] == "pending"


@pytest.mark.parametrize("cause", ["version", "cancel", "provider", "membership", "during-read"])
def test_failed_or_changed_authorization_never_creates_connection(system, cause):
    oauth, dot, _, _ = system
    state, payload, _ = started(system)
    if cause == "version":
        dot["version"] += 1
    if cause == "provider":
        oauth.connections.providers["figma"].execute.side_effect = Denied("Permission issue")
    if cause == "membership":
        oauth.dots.identity.require.side_effect = Denied("No membership")
    if cause == "during-read":

        def changed(*args, **kwargs):
            dot["version"] += 1
            return {"records": []}

        oauth.connections.providers["figma"].execute.side_effect = changed
    with pytest.raises(Denied):
        oauth.callback("figma", state, payload["proof"], "code", denied=cause == "cancel")
    with oauth.store.tx() as db:
        assert db.execute(text("SELECT count(*) FROM bud_connections")).scalar() == 0
    assert oauth.state(state)[0]["status"] == "failed"


def expire_access(oauth, connection):
    with oauth.store.tx() as db:
        encrypted = db.execute(
            text("SELECT secret FROM bud_connections WHERE id=:i"), {"i": connection}
        ).scalar()
        envelope = json.loads(oauth.store.cipher.decrypt(encrypted.encode()))
        envelope["token_expires"] = 1
        db.execute(
            text("UPDATE bud_connections SET secret=:s WHERE id=:i"),
            dict(
                i=connection, s=oauth.store.cipher.encrypt(json.dumps(envelope).encode()).decode()
            ),
        )


def test_refresh_rotates_tokens_without_extending_grant_or_resurrecting_disconnect(system):
    oauth, dot, user, seen = system
    result, _ = complete(system)
    before = oauth.connections.rows(dot, user)[0]
    expire_access(oauth, result["id"])
    evidence = oauth.connections.execute(
        "session", dot["workspace_id"], dot["id"], result["id"] + ".design"
    )
    assert evidence["records"]["title"] == "Design"
    assert parse_qs(seen[-1].content.decode())["grant_type"] == ["refresh_token"]
    after = oauth.connections.rows(dot, user)[0]
    assert before["expires"] == after["expires"] and before["id"] == after["id"]
    oauth.connections.disconnect("session", dot["workspace_id"], dot["id"], result["id"])
    with pytest.raises(Denied):
        oauth.connections.access(after, force=True)
    assert oauth.connections.rows(dot, user) == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401),
        httpx.Response(302, headers={"location": "https://evil.test"}),
        httpx.Response(200, json={"access_token": "bad token"}),
        httpx.Response(200, json={"access_token": "private-token", "expires_in": -1}),
        httpx.Response(200, json={"access_token": "private-token", "scope": "read write"}),
        httpx.Response(200, content=b"x" * 33000),
    ],
)
def test_bad_token_responses_fail_closed_without_leaking_secrets(system, response):
    oauth, _, _, _ = system
    oauth.client.close()
    oauth.client = httpx.Client(
        transport=httpx.MockTransport(lambda _: response), follow_redirects=False
    )
    with pytest.raises(Denied) as error:
        oauth.token("supabase", code="code", verifier="verifier")
    assert "private-token" not in str(error.value)


def test_refresh_token_is_withheld_if_provider_echoes_it(system):
    oauth, dot, _, _ = system
    result, _ = complete(system)
    oauth.connections.providers["figma"].execute.return_value = {"records": "oauth-refresh-private"}
    with pytest.raises(Denied, match="sensitive"):
        oauth.connections.execute(
            "session", dot["workspace_id"], dot["id"], result["id"] + ".design"
        )


@pytest.mark.parametrize("provider", ["figma"])
def test_oauth_reader_uses_bearer_instead_of_personal_token_headers(provider):
    def transport(request):
        assert request.headers["Authorization"] == "Bearer oauth-access-private"
        assert "X-Figma-Token" not in request.headers
        if provider == "figma":
            return httpx.Response(200, json={"name": "Design", "document": {"children": []}})
        return httpx.Response(
            200, json={"data": {"team": {"id": resource, "name": "Team", "key": "TEAM"}}}
        )

    resource = "fileKey123" if provider == "figma" else str(uuid4())
    tool = "design" if provider == "figma" else "team"
    reader = ReadProvider(provider, transport=httpx.MockTransport(transport))
    try:
        assert reader.execute("oauth-access-private", resource, tool, oauth=True)["records"]
    finally:
        reader.close()


def test_http_routes_google_handoff_cookie_proof_csrf_and_real_callback(tmp_path):
    config = Config(
        database=f"sqlite:///{tmp_path / 'http.db'}",
        encryption_key=Fernet.generate_key().decode(),
        dots_enabled=True,
        figma_bud_client_id="app",
        figma_bud_client_secret="secret",
    )
    app = create_app(config)
    dot = dict(
        id=str(uuid4()),
        workspace_id=str(uuid4()),
        provider="github",
        resource="owner/repo",
        version=1,
        name="Bud",
    )
    identity = app.state.identity
    identity.require = MagicMock(return_value={"id": "owner"})
    identity.request = MagicMock(return_value=[dot])
    identity.user = MagicMock(return_value={"id": "owner"})
    oauth = app.state.dots.connections.oauth
    oauth.client.close()
    oauth.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=dict(access_token="private-oauth-access", expires_in=3600)
            )
        )
    )
    app.state.dots.connections.providers["figma"].execute = MagicMock(return_value={"records": []})
    body = dict(
        workspace=dot["workspace_id"], dot=dot["id"], provider="figma", resource="fileKey123"
    )
    with TestClient(app, base_url=config.origin) as client:
        assert client.post("/api/buds/oauth/start", json=body).status_code == 403
        app.state.store.session("cookie", {"access_token": "session", "csrf": "proof"})
        client.cookies.set("aedrova_session", "cookie")
        assert client.post("/api/buds/oauth/start", json=body).status_code == 403
        result = client.post(
            "/api/buds/oauth/start", json=body, headers={"x-csrf-token": "proof"}
        ).json()
        redirected = client.get(result["url"], follow_redirects=False)
        assert redirected.status_code == 303
        cookie = redirected.headers["set-cookie"]
        assert (
            "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/buds/oauth/figma" in cookie
        )
        callback = client.get(
            "/buds/oauth/figma/callback", params={"state": result["state"], "code": "code"}
        )
        assert callback.status_code == 200 and "Figma is connected" in callback.text
        assert "private-oauth-access" not in callback.text
        assert "connected-bud look-builder" in callback.text
        assert "@Bud" in callback.text
        assert client.get("/static/bud-connected.css").status_code == 200
        assert client.get("/static/buds-atlas.png").status_code == 200
        assert (
            client.get("/api/buds/oauth/status", params={"state": result["state"]}).json()["status"]
            == "connected"
        )
        assert (
            client.get(
                "/buds/oauth/figma/callback", params={"state": result["state"], "code": "code"}
            ).status_code
            == 403
        )
        client.cookies.clear()
        result = oauth.start("session", dot["workspace_id"], dot["id"], "figma", "fileKey123", 24)
        identity.user.side_effect = Denied("Sign in")
        redirect = client.get(result["url"], follow_redirects=False)
        assert redirect.status_code == 303 and redirect.headers["location"].startswith(
            "/auth/google?bud="
        )
        google = client.get(redirect.headers["location"], follow_redirects=False)
        assert google.status_code == 303
        saved = app.state.store.session(client.cookies.get("aedrova_oauth"))
        assert saved["bud"] == result["state"]
        identity.user.side_effect = None
        identity.request.return_value = {"access_token": "web-access"}
        redirect = client.get("/auth/callback?code=google-code", follow_redirects=False)
        assert redirect.headers["location"] == "/buds/authorize/" + result["state"]


def test_concurrent_refresh_uses_one_rotating_refresh_token(system):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    oauth, dot, user, seen = system
    result, _ = complete(system)
    expire_access(oauth, result["id"])
    grant = oauth.connections.rows(dot, user)[0]
    barrier = Barrier(4)

    def read(_):
        barrier.wait(timeout=5)
        return oauth.connections.access(dict(grant))[1]

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(read, range(4)))
    assert values == ["oauth-access-private"] * 4
    assert len(seen) == 2  # Initial exchange plus a single refresh.


def test_expired_grant_does_not_refresh_and_removal_during_read_withholds_evidence(system):
    oauth, dot, _, seen = system
    result, _ = complete(system)

    def removed(*args, **kwargs):
        oauth.connections.disconnect("session", dot["workspace_id"], dot["id"], result["id"])
        return {"records": []}

    oauth.connections.providers["figma"].execute.side_effect = removed
    with pytest.raises(Denied, match="disconnected"):
        oauth.connections.execute(
            "session", dot["workspace_id"], dot["id"], result["id"] + ".design"
        )
    oauth.connections.providers["figma"].execute.side_effect = None
    result, _ = complete(system)
    expire_access(oauth, result["id"])
    with oauth.store.tx() as db:
        db.execute(text("UPDATE bud_connections SET expires=0"))
    before = len(seen)
    with pytest.raises(Denied):
        oauth.connections.execute(
            "session", dot["workspace_id"], dot["id"], result["id"] + ".design"
        )
    assert len(seen) == before


@pytest.mark.parametrize("provider", ["figma", "notion", "supabase"])
def test_oauth_configuration_rejects_partial_credentials_and_hides_secrets(provider):
    with pytest.raises(ValueError, match="both"):
        Config(**{provider + "_bud_client_id": "app"}).validate()
    config = Config(
        **{provider + "_bud_client_id": "app", provider + "_bud_client_secret": "hidden-value"}
    )
    config.validate()
    assert "hidden-value" not in repr(config)


@pytest.mark.parametrize(
    "provider", list(__import__("aedrova_site.bud_providers", fromlist=["CATALOG"]).CATALOG)
)
def test_every_provider_uses_shared_confirmation_and_escapes_bud_name(provider):
    from starlette.requests import Request

    from aedrova_site.bud_providers import CATALOG
    from aedrova_site.connection_confirmation import COPY, confirmation

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = confirmation(
        request, provider, {"name": "<script>bad</script>", "appearance": "finance"}
    )
    html = response.body.decode()
    assert CATALOG[provider][0] + " is connected." in html
    assert COPY[provider] in html
    assert "connected-bud look-finance" in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html
    assert "<script>bad</script>" not in html


def test_supabase_http_callback_is_blocked_before_creating_authorization(system):
    oauth, dot, _, seen = system
    assert not oauth.available("supabase")
    with pytest.raises(Denied, match="HTTPS callback"):
        oauth.start("session", dot["workspace_id"], dot["id"], "supabase", "a" * 20, 24)
    with oauth.store.tx() as db:
        assert db.execute(text("SELECT count(*) FROM bud_oauth")).scalar() == 0
    assert not seen
    oauth.config.origin = "https://connections.example.test"
    assert oauth.available("supabase")
    assert oauth.redirect("supabase").startswith("https://")


def test_tiktok_oauth_uses_client_key_and_resolves_authorized_account(system):
    oauth, dot, user, _ = system
    oauth.config.origin = "https://connections.example.com"
    oauth.config.tiktok_bud_client_id = "tiktok-app"
    oauth.config.tiktok_bud_client_secret = "tiktok-secret"
    requests = []

    def exchange(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "tiktok-access-private",
                "refresh_token": "tiktok-refresh-private",
                "expires_in": 86400,
                "token_type": "Bearer",
                "open_id": "account12345",
                "scope": "user.info.basic,video.list",
            },
        )

    oauth.client.close()
    oauth.client = httpx.Client(transport=httpx.MockTransport(exchange))
    oauth.connections.providers["tiktok"].execute = MagicMock(return_value={"records": {}})
    state, payload, target = started(system, "tiktok", "me")
    params = parse_qs(urlparse(target).query)
    assert params["client_key"] == ["tiktok-app"]
    assert "client_id" not in params
    assert params["scope"] == ["user.info.basic,video.list"]
    oauth.callback("tiktok", state, payload["proof"], "code")
    body = parse_qs(requests[0].content.decode())
    assert body["client_key"] == ["tiktok-app"]
    assert body["client_secret"] == ["tiktok-secret"]
    assert "authorization" not in requests[0].headers
    assert oauth.connections.providers["tiktok"].execute.call_args.args[1] == "account12345"


def test_tiktok_oauth_requires_https_and_rejects_broad_grants(system):
    oauth, _, _, _ = system
    oauth.config.tiktok_bud_client_id = "app"
    oauth.config.tiktok_bud_client_secret = "secret"
    oauth.config.origin = "http://localhost:8090"
    assert "HTTPS" in oauth.setup_hint("tiktok")
    oauth.client.close()
    oauth.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "access_token": "private-token",
                    "open_id": "account12345",
                    "scope": "user.info.basic,video.list,video.publish",
                },
            )
        )
    )
    with pytest.raises(Denied, match="excessive permissions"):
        oauth.token("tiktok", code="code", verifier="verifier")
