"""Fresh workspace authorization, CSRF/PKCE boundaries and billable failure accounting."""

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.gateway import cost
from aedrova_site.policy import PLAN_POLICY
from aedrova_site.store import Denied

MODELS = {
    "codex": {
        "id": "gpt-5.3-codex",
        "input_rate": 1_750_000,
        "output_rate": 14_000_000,
        "cache_read_rate": 175_000,
    },
    "claude_code": {
        "id": "claude-sonnet-5-5",
        "input_rate": 2_000_000,
        "output_rate": 10_000_000,
        "cache_read_rate": 200_000,
        "cache_write_rate": 2_500_000,
        "cache_long_write_rate": 4_000_000,
    },
}


class Accounts:
    revoked = False
    role = "owner"

    def user(self, token):
        if token != "access-a":
            raise Denied("Sign in again.")
        return {"id": "user-a"}

    def require(self, token, workspace, *, billing=False):
        user = self.user(token)
        if self.revoked or workspace != "space-a" or (billing and self.role != "owner"):
            raise Denied("Workspace access denied.")
        return user


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'app.sqlite'}",
            gateway_enabled=True,
            models=MODELS,
            openai_key="server-only-key",
            anthropic_key="server-only-claude",
        )
    )
    identity = Accounts()
    app.state.identity.user = identity.user
    app.state.identity.require = identity.require
    store = app.state.store
    store.customer("space-a", "cus_a")
    store.subscription(
        "evt",
        "cus_a",
        "sub_a",
        "monthly",
        "active",
        100,
        int(time.time()) + 1000,
        PLAN_POLICY["monthly"],
    )
    store.session("web-session", {"access_token": "access-a", "csrf": "csrf-a"})
    with TestClient(app) as value:
        value.cookies.set("aedrova_session", "web-session")
        value.accounts = identity
        yield value
    store.engine.dispose()


def begin(client, provider="codex"):
    response = client.post(
        "/api/runs",
        headers={"x-csrf-token": "csrf-a"},
        json={"workspace": "space-a", "provider": provider, "request_id": "build-request-00001"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "path,body",
    [
        (
            "/api/runs",
            {"workspace": "space-a", "provider": "codex", "request_id": "build-request-00001"},
        ),
        (
            "/api/checkout",
            {"workspace": "space-a", "plan": "monthly", "request_id": "checkout-request-01"},
        ),
        ("/api/portal/space-a", {}),
        ("/api/logout", {}),
    ],
)
def test_cookie_mutations_require_csrf(client, path, body):
    assert client.post(path, json=body).status_code == 403


def test_foreign_workspace_and_member_billing_denied_before_stripe(client, monkeypatch):
    monkeypatch.setattr("stripe.checkout.Session.create", lambda **kw: pytest.fail("No checkout"))
    assert client.get("/api/balance/space-b").status_code == 403
    client.accounts.role = "member"
    assert (
        client.post(
            "/api/checkout",
            headers={"x-csrf-token": "csrf-a"},
            json={"workspace": "space-a", "plan": "monthly", "request_id": "checkout-request-01"},
        ).status_code
        == 403
    )


def test_desktop_bearer_works_without_browser_csrf_and_no_shared_key_exposed(client):
    client.cookies.clear()
    response = client.post(
        "/api/runs",
        headers={"Authorization": "Bearer access-a"},
        json={"workspace": "space-a", "provider": "codex", "request_id": "desktop-request-01"},
    )
    assert response.status_code == 200
    assert "server-only" not in response.text and "access-a" not in response.text
    assert response.json()["base_url"] == "http://127.0.0.1:8090/gateway/codex/v1"


def test_inference_rechecks_revocation_and_provider_binding(client):
    access = begin(client)
    headers = {"Authorization": "Bearer " + access["token"]}
    assert (
        client.post("/gateway/claude_code/v1/messages", headers=headers, json={}).status_code == 403
    )
    client.accounts.revoked = True
    assert client.post("/gateway/codex/v1/responses", headers=headers, json={}).status_code == 403
    assert client.app.state.store.balance("space-a")["reserved"] == 0


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"tools": ["bad"]},
        {"tools": [{"type": "web_search"}]},
        {"input": [{"type": "input_image", "image_url": "https://example.invalid"}]},
        {"previous_response_id": "resp_external"},
        {"background": True},
        {"input": "x" * 200_000},
        {"max_output_tokens": "invalid"},
    ],
)
def test_unbounded_or_invalid_requests_rejected_before_reservation(client, body):
    access = begin(client)
    response = client.post(
        "/gateway/codex/v1/responses",
        json=body,
        headers={"Authorization": "Bearer " + access["token"]},
    )
    assert response.status_code == 403
    assert client.app.state.store.balance("space-a")["reserved"] == 0


def upstream(monkeypatch, data, *, status=200, fail=False):
    requests = []

    class Stream:
        status_code = status

        async def __aenter__(self):
            if fail:
                raise httpx.ConnectError("private diagnostic")
            return self

        async def __aexit__(self, *a):
            pass

        async def aiter_bytes(self):
            yield data

    class Provider:
        def __init__(self, **kw):
            assert not kw["follow_redirects"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        def stream(self, method, url, **kw):
            requests.append((url, kw))
            return Stream()

    monkeypatch.setattr("aedrova_site.gateway.httpx.AsyncClient", Provider)
    return requests


def test_successful_stream_charged_once_replayed_and_server_controls_model(client, monkeypatch):
    access = begin(client)
    data = (
        b"data: "
        b'{"type":"response.completed","response":{"usage":{"inpu'
        b't_tokens":100,"output_tokens":10}}}\n\n'
    )
    requests = upstream(monkeypatch, data)
    body = {"model": "expensive-unapproved-model", "stream": True, "input": "hello"}
    headers = {"Authorization": "Bearer " + access["token"]}
    first = client.post("/gateway/codex/v1/responses", json=body, headers=headers)
    assert first.content == data
    assert client.post("/gateway/codex/v1/responses", json=body, headers=headers).content == data
    assert len(requests) == 1
    forwarded = json.loads(requests[0][1]["content"])
    assert forwarded["model"] == MODELS["codex"]["id"]
    assert forwarded["store"] is False and forwarded["service_tier"] == "default"
    assert requests[0][0] == "https://api.openai.com/v1/responses"
    assert client.app.state.store.balance("space-a")["spent"] == 315
    assert client.app.state.store.balance("space-a")["reserved"] == 0


@pytest.mark.parametrize("failure", ["rejected", "connection", "incomplete"])
def test_provider_failures_have_no_silent_replay_or_secret_diagnostics(
    client, monkeypatch, failure
):
    access = begin(client)
    requests = upstream(
        monkeypatch,
        b'data: {"type":"response.created"}\n\n',
        status=401 if failure == "rejected" else 200,
        fail=failure == "connection",
    )
    body = {"stream": True, "input": "hello"}
    headers = {"Authorization": "Bearer " + access["token"]}
    response = client.post("/gateway/codex/v1/responses", json=body, headers=headers)
    assert "private diagnostic" not in response.text and "server-only-key" not in response.text
    assert client.post("/gateway/codex/v1/responses", json=body, headers=headers).status_code == 403
    assert len(requests) == 1
    balance = client.app.state.store.balance("space-a")
    assert balance["reserved"] == 0
    assert balance["spent"] == 0 if failure == "rejected" else balance["spent"] > 0


def test_claude_count_requires_fresh_membership_and_does_not_spend(client):
    access = begin(client, "claude_code")
    headers = {"x-api-key": access["token"]}
    assert (
        client.post(
            "/gateway/claude_code/v1/messages/count_tokens", headers=headers, json={}
        ).status_code
        == 200
    )
    client.accounts.revoked = True
    assert (
        client.post(
            "/gateway/claude_code/v1/messages/count_tokens", headers=headers, json={}
        ).status_code
        == 403
    )
    assert client.app.state.store.balance("space-a")["spent"] == 0


def test_cost_accounts_for_provider_specific_caches():
    assert (
        cost(
            {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 80},
                "output_tokens": 10,
            },
            MODELS["codex"],
        )
        == 189
    )
    assert (
        cost(
            {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 200,
                "cache_creation": {"ephemeral_1h_input_tokens": 100},
            },
            MODELS["claude_code"],
        )
        == 970
    )
    assert cost({"input_tokens": 1, "output_tokens": -1}, MODELS["codex"]) is None


def test_oauth_pkce_one_use_and_error_redirect(client, monkeypatch):
    response = client.get("/auth/google", follow_redirects=False)
    assert (
        response.status_code == 303 and "code_challenge_method=s256" in response.headers["location"]
    )
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "SameSite=lax" in response.headers["set-cookie"]
    )
    monkeypatch.setattr(
        client.app.state.identity, "request", lambda *a, **kw: {"access_token": "access-a"}
    )
    callback = client.get("/auth/callback?code=one-use", follow_redirects=False)
    assert callback.status_code == 303 and callback.headers["location"] == "/account"
    assert (
        client.get("/auth/callback?code=one-use", follow_redirects=False).headers["location"]
        == "/account?login_error=1"
    )


def test_wrong_origin_and_logout_session_revocation(client):
    assert (
        client.post(
            "/api/logout", headers={"Origin": "https://foreign.invalid", "x-csrf-token": "csrf-a"}
        ).status_code
        == 403
    )
    assert client.post("/api/logout", headers={"x-csrf-token": "csrf-a"}).status_code == 200
    assert client.get("/api/session").status_code == 403


def test_compaction_is_metered_and_preserves_stateless_budget_boundary(client, monkeypatch):
    access = begin(client)
    data = json.dumps(
        {
            "object": "response.compaction",
            "usage": {"input_tokens": 100, "output_tokens": 10},
            "output": [],
        }
    ).encode()
    requests = upstream(monkeypatch, data)
    response = client.post(
        "/gateway/codex/v1/responses/compact",
        json={"input": "hello"},
        headers={"Authorization": "Bearer " + access["token"]},
    )
    assert response.content == data
    assert requests[0][0].endswith("/responses/compact")
    assert "max_output_tokens" not in json.loads(requests[0][1]["content"])
    assert client.app.state.store.balance("space-a")["spent"] == 315


def test_claude_stream_with_caching_charges_actual_usage(client, monkeypatch):
    access = begin(client, "claude_code")
    data = (
        b"data: "
        b'{"type":"message_start","message":{"usage":{"input_toke'
        b'ns":100,"output_tokens":0,"cache_read_input_tokens":100'
        b"}}}\n\ndata: "
        b'{"type":"message_delta","usage":{"output_tokens":10}}\n\n'
        b'data: {"type":"message_stop"}\n\n'
    )
    requests = upstream(monkeypatch, data)
    response = client.post(
        "/gateway/claude_code/v1/messages",
        json={
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 100,
        },
        headers={"x-api-key": access["token"]},
    )
    assert response.content == data
    assert client.app.state.store.balance("space-a")["spent"] == 320
    assert requests[0][0] == "https://api.anthropic.com/v1/messages"
    assert json.loads(requests[0][1]["content"])["service_tier"] == "standard"


def test_workspace_creation_transfers_nickname_through_existing_onboarding_rpc(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client.app.state.identity,
        "request",
        lambda path, token, **kw: calls.append((path, kw)) or "space-new",
    )
    response = client.post(
        "/api/workspaces",
        json={"name": "New team", "nickname": "Atlas"},
        headers={"x-csrf-token": "csrf-a"},
    )
    assert response.status_code == 200 and response.json()["id"] == "space-new"
    assert calls[0][0] == "/rest/v1/rpc/onboard_workspace"
    assert calls[0][1]["data"] == {
        "p_name": "New team",
        "p_nickname": "Atlas",
        "p_provider": "codex",
    }


def test_total_deadline_stops_trickling_provider_and_keeps_uncertain_accounting(
    client, monkeypatch
):
    import asyncio

    access = begin(client)
    client.app.state.config.provider_deadline_seconds = 0.01

    class Stream:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def aiter_bytes(self):
            await asyncio.sleep(0.04)
            yield b"private-provider-output"

    class Provider:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        def stream(self, *a, **kw):
            return Stream()

    monkeypatch.setattr("aedrova_site.gateway.httpx.AsyncClient", Provider)
    result = client.post(
        "/gateway/codex/v1/responses",
        json={"stream": True, "input": "test"},
        headers={"Authorization": "Bearer " + access["token"]},
    )
    assert "interrupted" in result.text and "private-provider-output" not in result.text
    balance = client.app.state.store.balance("space-a")
    assert balance["reserved"] == 0 and balance["spent"] > 0


def test_closing_stream_mid_response_settles_once_without_replaying(client, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from aedrova_site.gateway import inference

    access = begin(client)
    upstream(monkeypatch, b'data: {"type":"response.created"}\n\n')

    async def body():
        return b'{"stream":true,"input":"test"}'

    async def disconnected():
        return False

    request = SimpleNamespace(
        headers={"authorization": "Bearer " + access["token"]},
        body=body,
        is_disconnected=disconnected,
    )

    async def close_after_first_chunk():
        response = await inference(
            request,
            "codex",
            client.app.state.config,
            client.app.state.store,
            client.app.state.identity,
        )
        assert await anext(response.body_iterator)
        await response.body_iterator.aclose()

    asyncio.run(close_after_first_chunk())
    balance = client.app.state.store.balance("space-a")
    assert balance["reserved"] == 0 and balance["spent"] > 0


@pytest.mark.parametrize(
    "data", [b"data: []\n\n", b'data: {"type":"response.completed","response":null}\n\n']
)
def test_malformed_provider_metadata_fails_without_exposing_diagnostics(client, monkeypatch, data):
    access = begin(client)
    upstream(monkeypatch, data)
    result = client.post(
        "/gateway/codex/v1/responses",
        json={"stream": True, "input": "test"},
        headers={"Authorization": "Bearer " + access["token"]},
    )
    assert "interrupted" in result.text
    assert client.app.state.store.balance("space-a")["reserved"] == 0
