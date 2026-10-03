"""Real response decoding; a void RPC is successful, malformed JSON is not."""

from types import SimpleNamespace

import httpx
import pytest

from aedrova_site.services import Identity
from aedrova_site.store import Denied


@pytest.mark.parametrize(
    "status,content,expected",
    [(204, b"", None), (200, b"null", None), (200, b'{"ok":true}', {"ok": True})],
)
def test_successful_rpc_responses(monkeypatch, status, content, expected):
    response = httpx.Response(
        status,
        content=content,
        request=httpx.Request("POST", "https://example.supabase.co/rest/v1/rpc/meeting_presence"),
    )
    identity = Identity(
        SimpleNamespace(supabase_url="https://example.supabase.co", supabase_key="public"),
        transport=httpx.MockTransport(lambda request: response),
    )
    assert identity.request("/rest/v1/rpc/meeting_presence", "session", method="POST") == expected


@pytest.mark.parametrize("status", [200, 401, 403, 500])
def test_invalid_or_failed_responses_still_fail_closed(monkeypatch, status):
    response = httpx.Response(
        status,
        content=b"",
        request=httpx.Request("POST", "https://example.supabase.co/rest/v1/rpc/meeting_presence"),
    )
    identity = Identity(
        SimpleNamespace(supabase_url="https://example.supabase.co", supabase_key="public"),
        transport=httpx.MockTransport(lambda request: response),
    )
    with pytest.raises(Denied):
        identity.request("/rest/v1/rpc/meeting_presence", "session", method="POST")
