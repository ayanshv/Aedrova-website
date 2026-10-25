# ruff: noqa: F811
"""Actual ledger boundaries with deterministic HTTP, never live provider spend."""

import json

import httpx
import pytest
from test_bud_oauth import system  # noqa: F401
from test_dots import system as dot_system  # noqa: F401

from aedrova_site.research import RESERVATION, public_url
from aedrova_site.store import Denied


def answer():
    return {
        "status": "completed",
        "usage": {"input_tokens": 2000, "output_tokens": 100},
        "output": [
            {"type": "web_search_call", "status": "completed"},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Verified result.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://example.com/report",
                                "title": "Report",
                            }
                        ],
                    }
                ],
            },
        ],
    }


def setup(system, handler=None):
    oauth, dot, user, _ = system
    config, service = oauth.config, oauth.connections
    config.gateway_enabled, config.openai_key = True, "fixture-openai-private-key"
    service.store.free_enabled = True
    service.store.activate_free(user, dot["workspace_id"])
    service.dots.identity.billing_context.return_value = {"billing_workspace": dot["workspace_id"]}
    seen = []

    def transport(request):
        seen.append(request)
        return handler(request) if handler else httpx.Response(200, json=answer())

    service.research.client.close()
    service.research.client = httpx.Client(transport=httpx.MockTransport(transport))
    grant = service.managed_search(
        "session", dot["workspace_id"], dot["id"], "Startup research", 24
    )
    return service, dot, user, grant["id"] + ".search", seen


def test_research_enable_is_free_and_real_read_is_metered_and_cited(system):
    service, dot, user, tool, seen = setup(system)
    assert not seen  # Connecting alone must never spend AI credit.
    row = service.rows(dot, user)[0]
    assert "fixture-openai" not in service.store.cipher.decrypt(row["secret"].encode()).decode()
    result = service.execute("session", dot["workspace_id"], dot["id"], tool)
    assert result["records"]["sources"][0]["url"] == "https://example.com/report"
    assert len(seen) == 1 and seen[0].url == "https://api.openai.com/v1/responses"
    body = json.loads(seen[0].content)
    assert body["tools"][0]["external_web_access"] is True
    assert body["max_tool_calls"] == 1 and body["store"] is False
    assert seen[0].headers["idempotency-key"]
    assert service.store.balance(dot["workspace_id"])["spent"] == 11950
    assert "fixture-openai" not in json.dumps(result)
    service.disconnect("session", dot["workspace_id"], dot["id"], row["id"])
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], tool)
    assert len(seen) == 1


def test_borrowed_run_preserves_free_concurrency_and_rejects_foreign_scope(system):
    service, dot, user, tool, seen = setup(system)
    run = service.store.create_run(user, dot["workspace_id"], "codex", "parent")
    service.execute("session", dot["workspace_id"], dot["id"], tool, run_token=run["token"])
    assert service.store.run(run["token"])["id"] == run["id"]
    other = service.store.run(run["token"])
    original = service.store.run
    service.store.run = lambda token: {**other, "user_id": "another-user"}
    with pytest.raises(Denied, match="another account"):
        service.execute("session", dot["workspace_id"], dot["id"], tool, run_token=run["token"])
    service.store.run = original
    assert len(seen) == 1


def test_budget_denial_happens_before_network(system):
    service, dot, user, tool, seen = setup(system)
    service.store.company_budget = 1
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], tool)
    assert not seen


@pytest.mark.parametrize("mode", ["timeout", "invalid", "uncited", "rejected"])
def test_failures_never_invent_results_or_retry_and_account_for_uncertainty(system, mode):
    def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("private provider error", request=request)
        if mode == "invalid":
            return httpx.Response(200, content=b"not json")
        if mode == "rejected":
            return httpx.Response(401, json={"secret": "do not echo"})
        result = answer()
        result["output"][1]["content"][0]["annotations"] = []
        return httpx.Response(200, json=result)

    service, dot, _, tool, seen = setup(system, handler)
    with pytest.raises(Denied) as error:
        service.execute("session", dot["workspace_id"], dot["id"], tool)
    assert "private provider" not in str(error.value) and "do not echo" not in str(error.value)
    assert len(seen) == 1
    spent = service.store.balance(dot["workspace_id"])["spent"]
    assert spent == (0 if mode == "rejected" else 11950 if mode == "uncited" else RESERVATION)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:pass@example.com",
        "https://example.com/\nfoo",
    ],
)
def test_unsafe_citations_rejected(url):
    assert not public_url(url)
