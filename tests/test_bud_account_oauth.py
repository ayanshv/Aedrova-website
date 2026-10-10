# ruff: noqa: F811
"""New account flows: fixed destinations, automatic identities and managed cost gates."""

import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import text
from test_bud_oauth import started, system  # noqa: F401
from test_dots import system as dot_system  # noqa: F401

from aedrova_site.bud_providers import ReadProvider
from aedrova_site.store import Denied, RateLimited


def configured(system, provider, handler):
    oauth, dot, user, _ = system
    oauth.config.origin = "https://aedrova-connectors.onrender.com"
    setattr(oauth.config, provider + "_bud_client_id", "test-client")
    setattr(oauth.config, provider + "_bud_client_secret", "test-secret")
    oauth.config.vercel_bud_slug = "aedrova-buds"
    oauth.client.close()
    oauth.transport = httpx.MockTransport(handler)
    oauth.client = httpx.Client(transport=oauth.transport, follow_redirects=False)
    return oauth, dot, user


@pytest.mark.parametrize(
    "provider,actor", [("stripe", "acct_Aedrova123"), ("instagram", "123456789")]
)
def test_account_login_resolves_identity_without_ids_and_binds_grant(system, provider, actor):
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path.endswith("/me"):
            return httpx.Response(200, json={"user_id": actor})
        if provider == "stripe":
            assert req.headers["authorization"].startswith("Basic ")
            return httpx.Response(
                200,
                json={
                    "access_token": "private-access-token",
                    "refresh_token": "private-refresh-token",
                    "stripe_user_id": actor,
                    "scope": "stripe_apps",
                },
            )
        return httpx.Response(
            200, json={"access_token": "private-access-token", "expires_in": 5184000}
        )

    oauth, dot, user = configured(system, provider, handler)
    oauth.connections.providers[provider].execute = MagicMock(return_value={"records": {}})
    state, payload, target = started(system, provider, "")
    query = parse_qs(urlparse(target).query)
    assert query["state"] == [state] and "code_challenge" not in query
    if provider == "instagram":
        assert query["scope"] == ["instagram_business_basic"]
    result = oauth.callback(provider, state, payload["proof"], "code")
    assert oauth.status("session", state)["status"] == "connected"
    row = next(r for r in oauth.connections.rows(dot, user) if r["id"] == result["id"])
    assert row["resource"] == actor
    assert "private-access-token" not in json.dumps(oauth.connections.listing(dot, user))
    with oauth.store.tx() as db:
        assert "private-access-token" not in str(
            db.execute(text("SELECT payload FROM bud_oauth")).all()
        )
    assert all(r.url.scheme == "https" for r in seen)


def test_stripe_different_account_or_scope_cannot_connect(system):
    oauth, _, _ = configured(
        system,
        "stripe",
        lambda req: httpx.Response(
            200,
            json={
                "access_token": "private-access-token",
                "stripe_user_id": "acct_Other123",
                "scope": "read_write",
            },
        ),
    )
    with pytest.raises(Denied, match="Stripe app"):
        oauth.token("stripe", code="code")
    oauth.token = lambda *a, **kw: {"actor": "acct_Other123", "access": "private-access-token"}
    state, payload, _ = started(system, "stripe", "acct_Expected123")
    with pytest.raises(Denied, match="different account"):
        oauth.callback("stripe", state, payload["proof"], "code")
    assert oauth.status("session", state)["status"] == "failed"


def test_vercel_discovery_and_reads_keep_team_context_and_named_selection(system):
    def handler(req):
        if req.url.path == "/v2/oauth/access_token":
            assert parse_qs(req.content.decode())["client_secret"] == ["test-secret"]
            return httpx.Response(
                200, json={"access_token": "private-vercel-token", "team_id": "team_123abc"}
            )
        assert req.url.params["teamId"] == "team_123abc"
        return httpx.Response(200, json={"projects": [{"id": "prj_123abc", "name": "Website"}]})

    oauth, dot, user = configured(system, "vercel", handler)
    reader = oauth.connections.providers["vercel"]
    reader.execute = MagicMock(return_value={"records": {}})
    state, payload, target = started(system, "vercel", "")
    assert target.startswith("https://vercel.com/integrations/aedrova-buds/new?")
    oauth.callback("vercel", state, payload["proof"], "code")
    assert oauth.status("session", state)["resources"] == [{"id": "prj_123abc", "name": "Website"}]
    with pytest.raises(Denied, match="Choose a resource"):
        oauth.select("session", state, "prj_other123")
    result = oauth.select("session", state, "prj_123abc")
    envelope = reader.execute.call_args.kwargs["oauth"]
    assert envelope["team"] == "team_123abc"
    oauth.connections.execute("session", dot["workspace_id"], dot["id"], result["id"] + ".project")
    assert reader.execute.call_args.kwargs["oauth"]["team"] == "team_123abc"


def test_vercel_actual_reads_append_team_id():
    seen = []

    def handler(req):
        seen.append(req)
        assert req.url.params["teamId"] == "team_123abc"
        return httpx.Response(200, json={"id": "prj_123abc", "name": "Website", "deployments": []})

    reader = ReadProvider("vercel", transport=httpx.MockTransport(handler))
    try:
        for tool in ("project", "deployments"):
            reader.execute(
                "private-vercel-token", "prj_123abc", tool, oauth={"team": "team_123abc"}
            )
        assert len(seen) == 2
        with pytest.raises(Denied):
            reader.execute(
                "private-vercel-token", "prj_123abc", "project", oauth={"team": "../../bad"}
            )
    finally:
        reader.close()


def test_managed_search_needs_key_and_caps_all_reads_without_exposing_key(system):
    oauth, dot, user, _ = system
    service = oauth.connections
    with pytest.raises(Denied, match="owner setup"):
        service.managed_search("session", dot["workspace_id"], dot["id"], "startup research", 24)
    oauth.config.search_bud_key = "private-server-search-key"
    oauth.config.search_bud_workspace_daily_limit = 2
    service.providers["search"].execute = MagicMock(return_value={"records": []})
    result = service.managed_search(
        "session", dot["workspace_id"], dot["id"], "startup research", 24
    )
    row = service.rows(dot, user)[0]
    payload = json.loads(service.store.cipher.decrypt(row["secret"].encode()))
    assert "access" not in payload and "private-server-search-key" not in str(payload)
    tool = result["id"] + ".search"
    service.execute("session", dot["workspace_id"], dot["id"], tool)
    with pytest.raises(RateLimited):
        service.execute("session", dot["workspace_id"], dot["id"], tool)
    assert service.providers["search"].execute.call_count == 2
    assert "private-server-search-key" not in json.dumps(service.listing(dot, user))


@pytest.mark.parametrize("provider", ["stripe", "instagram", "vercel"])
def test_missing_registration_and_https_never_claim_login_available(system, provider):
    oauth, _, _, _ = system
    assert not oauth.available(provider)
    setattr(oauth.config, provider + "_bud_client_id", "client")
    setattr(oauth.config, provider + "_bud_client_secret", "secret")
    oauth.config.vercel_bud_slug = "aedrova-buds"
    assert not oauth.available(provider)
    oauth.config.origin = "https://connections.example.test"
    assert oauth.available(provider)


@pytest.mark.parametrize(
    "provider,actor", [("stripe", "acct_Aedrova123"), ("instagram", "123456789")]
)
def test_refresh_cannot_replace_authorized_account(system, provider, actor):
    oauth, dot, user = configured(system, provider, lambda req: httpx.Response(200, json={}))
    oauth.token = MagicMock(
        return_value={
            "kind": "oauth",
            "actor": actor,
            "access": "private-access-token",
            "refresh": "private-refresh-token",
            "token_expires": 1,
        }
    )
    reader = oauth.connections.providers[provider]
    reader.execute = MagicMock(return_value={"records": {}})
    state, payload, _ = started(system, provider, "")
    result = oauth.callback(provider, state, payload["proof"], "code")
    original = oauth.connections.rows(dot, user)[0]["secret"]
    oauth.token.return_value["actor"] = "acct_Different123" if provider == "stripe" else "999999999"
    with pytest.raises(Denied, match="Needs authorization"):
        oauth.connections.execute(
            "session",
            dot["workspace_id"],
            dot["id"],
            result["id"] + (".balance" if provider == "stripe" else ".profile"),
        )
    assert oauth.connections.rows(dot, user)[0]["secret"] == original


def test_instagram_exchange_query_secrets_are_redacted_from_http_logs(system, caplog):
    import logging

    oauth, _, _ = configured(
        system,
        "instagram",
        lambda req: httpx.Response(
            200, json={"access_token": "private-access-token", "user_id": "123456789"}
        ),
    )
    with caplog.at_level(logging.INFO, logger="httpx"):
        oauth.token("instagram", code="code")
    assert "private-access-token" not in caplog.text and "test-secret" not in caplog.text
    assert "[redacted]" in caplog.text


def test_managed_search_global_cap_survives_different_workspace_and_key_rotation(system):
    oauth, _, _, _ = system
    service = oauth.connections
    oauth.config.search_bud_key = "private-server-search-key"
    oauth.config.search_bud_daily_limit = 1
    service.providers["search"].execute = MagicMock(return_value={"records": []})
    service.read(
        "search",
        oauth.config.search_bud_key,
        "startup research",
        "search",
        oauth={"kind": "managed_search", "workspace": "one"},
    )
    oauth.config.search_bud_key = "rotated-server-search-key"
    with pytest.raises(RateLimited):
        service.read(
            "search",
            oauth.config.search_bud_key,
            "startup research",
            "search",
            oauth={"kind": "managed_search", "workspace": "two"},
        )
    assert service.providers["search"].execute.call_count == 1


@pytest.mark.parametrize("failure", [None, "account", "balance"])
def test_stripe_customer_account_selection_verifies_reads_before_connected(system, failure):
    """Exercise the actual Stripe reader after OAuth, without customer IDs or keys."""
    seen = []
    actor = "acct_Customer123"

    def handler(req):
        seen.append(req.url.path)
        if req.url.path == "/v1/oauth/token":
            assert req.method == "POST"
            assert parse_qs(req.content.decode())["code"] == ["stripe-code"]
            return httpx.Response(
                200,
                json={
                    "access_token": "customer-access-private",
                    "refresh_token": "customer-refresh-private",
                    "stripe_user_id": actor,
                    "scope": "stripe_apps",
                    "expires_in": 3600,
                },
            )
        assert req.headers["authorization"] == "Bearer customer-access-private"
        if req.url.path == "/v1/account":
            return httpx.Response(
                200,
                json={
                    "id": "acct_Wrong123" if failure == "account" else actor,
                },
            )
        assert req.url.path == "/v1/balance"
        return httpx.Response(
            403 if failure == "balance" else 200,
            json={
                "livemode": False,
                "available": [{"amount": 1234, "currency": "usd"}],
                "pending": [],
            },
        )

    oauth, dot, user = configured(system, "stripe", handler)
    oauth.connections.providers["stripe"].close()
    oauth.connections.providers["stripe"] = ReadProvider(
        "stripe", transport=httpx.MockTransport(handler)
    )
    oauth.config.stripe_bud_authorize_url = (
        "https://marketplace.stripe.com/oauth/v2/authorize?test_parameter=provider-issued"
    )
    state, payload, target = started(system, "stripe", "")
    query = parse_qs(urlparse(target).query)
    assert query["test_parameter"] == ["provider-issued"]
    assert query["state"] == [state]
    assert query["redirect_uri"] == [oauth.redirect("stripe")]
    if failure:
        with pytest.raises(Denied):
            oauth.callback("stripe", state, payload["proof"], "stripe-code")
        assert oauth.status("session", state)["status"] == "failed"
        assert not oauth.connections.rows(dot, user)
        if failure == "account":
            assert "/v1/balance" not in seen
    else:
        result = oauth.callback("stripe", state, payload["proof"], "stripe-code")
        assert oauth.status("session", state) == {"status": "connected", "connection": result["id"]}
        assert oauth.connections.rows(dot, user)[0]["resource"] == actor
        assert seen == ["/v1/oauth/token", "/v1/account", "/v1/balance"]
    assert "customer-access-private" not in json.dumps(oauth.connections.listing(dot, user))
