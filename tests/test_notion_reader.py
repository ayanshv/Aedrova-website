"""Notion reads: pagination, nested blocks, sub-pages and the shared-pages overview."""

import json
from uuid import uuid4

import httpx

from aedrova_site.bud_providers import CATALOG, ReadProvider

PAGE = str(uuid4())
TOGGLE = str(uuid4())
CHILD = str(uuid4())


def rich(text):
    return [{"plain_text": text}]


def block(kind, text="", **extra):
    return {"id": str(uuid4()), "type": kind, kind: {"rich_text": rich(text)}, **extra}


def notion(requests):
    def handler(request):
        requests.append(request)
        url = str(request.url)
        if url.endswith("/v1/search"):
            body = json.loads(request.content)
            assert body["filter"] == {"property": "object", "value": "page"}
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": PAGE,
                            "last_edited_time": "2026-11-20T10:00:00Z",
                            "properties": {"t": {"type": "title", "title": rich("Roadmap")}},
                        },
                        {"id": str(uuid4()), "archived": True, "properties": {}},
                    ]
                },
            )
        if "/pages/" in url:
            return httpx.Response(
                200,
                json={
                    "id": PAGE,
                    "properties": {"Name": {"type": "title", "title": rich("Launch plan")}},
                },
            )
        if f"/blocks/{PAGE}/children" in url:
            if "start_cursor=next" in url:
                return httpx.Response(
                    200, json={"results": [block("paragraph", "Second page of blocks")]}
                )
            return httpx.Response(
                200,
                json={
                    "results": [
                        block("heading_1", "Goals"),
                        block(
                            "to_do",
                            "Ship the beta",
                            **{"to_do": {"checked": True, "rich_text": rich("Ship the beta")}},
                        ),
                        {**block("toggle", "Details"), "id": TOGGLE, "has_children": True},
                        {"id": CHILD, "type": "child_page", "child_page": {"title": "Pricing"}},
                    ],
                    "has_more": True,
                    "next_cursor": "next",
                },
            )
        if f"/blocks/{TOGGLE}/children" in url:
            return httpx.Response(200, json={"results": [block("paragraph", "Nested detail")]})
        if f"/blocks/{CHILD}/children" in url:
            return httpx.Response(200, json={"results": [block("paragraph", "Pro is $20")]})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


def test_page_read_follows_pagination_nesting_and_sub_pages():
    seen = []
    adapter = ReadProvider("notion", transport=notion(seen))
    result = adapter.execute("private-fixture-token", PAGE, "page")
    records = result["records"]
    assert records["title"] == ["Launch plan"]
    assert "# Goals" in records["text"] and "[x] Ship the beta" in records["text"]
    assert "Second page of blocks" in records["text"]
    assert "  Nested detail" in records["text"]  # indented under its toggle
    assert "[Page] Pricing" in records["text"]
    assert records["sub_pages"] == [{"title": "Pricing", "text": "Pro is $20"}]
    assert "sub-pages" in result["coverage"] and result["untrusted"]
    assert all(r.method == "GET" and r.url.scheme == "https" for r in seen)
    assert "private-fixture-token" not in json.dumps(result)
    adapter.close()


def test_request_budget_caps_a_runaway_page():
    seen = []

    def endless(request):
        seen.append(request)
        if "/pages/" in str(request.url):
            return httpx.Response(200, json={"id": PAGE, "properties": {}})
        return httpx.Response(
            200,
            json={"results": [block("paragraph", "x")], "has_more": True, "next_cursor": "again"},
        )

    adapter = ReadProvider("notion", transport=httpx.MockTransport(endless))
    result = adapter.execute("private-fixture-token", PAGE, "page")
    assert len(seen) <= 20 and result["records"]["truncated"] in {True, False}
    adapter.close()


def test_shared_pages_overview_lists_titles_only_and_skips_archived():
    seen = []
    adapter = ReadProvider("notion", transport=notion(seen))
    result = adapter.execute("private-fixture-token", PAGE, "workspace")
    assert [p["title"] for p in result["records"]["pages"]] == ["Roadmap"]
    assert result["coverage"].startswith("The 25 most recently edited")
    assert [r.method for r in seen] == ["POST"]  # a read-only search, nothing written
    adapter.close()


def test_notion_offers_two_read_only_tools():
    assert set(CATALOG["notion"][4]) == {"page", "workspace"}


def test_credentials_in_page_text_are_withheld():
    secret = "ntn_" + "A" * 30

    def leaky(request):
        if "/pages/" in str(request.url):
            return httpx.Response(200, json={"id": PAGE, "properties": {}})
        return httpx.Response(200, json={"results": [block("paragraph", secret)]})

    adapter = ReadProvider("notion", transport=httpx.MockTransport(leaky))
    try:
        adapter.execute("private-fixture-token", PAGE, "page")
        raised = False
    except Exception as error:
        raised = "withheld" in str(error)
    assert raised
    adapter.close()
