"""Resource choices come from consented provider APIs; no client hosts or secrets."""

import httpx
import pytest

from aedrova_site.bud_discovery import resources
from aedrova_site.store import Denied


@pytest.mark.parametrize(
    "provider,expected",
    [
        ("github", "owner/repo"),
        ("supabase", "a" * 20),
        ("notion", "11111111-1111-1111-1111-111111111111"),
    ],
)
def test_discovery_uses_fixed_hosts_and_named_authorized_choices(provider, expected):
    seen = []

    def request(req):
        seen.append(req)
        assert req.headers["authorization"] == "Bearer private-token"
        if req.url.path == "/user/installations":
            data = {"installations": [{"id": 23}]}
        elif req.url.path == "/user/installations/23/repositories":
            data = {"repositories": [{"full_name": expected}]}
        elif req.url.path == "/v1/projects":
            data = [{"id": expected, "name": "My app"}]
        else:
            assert str(req.url) == "https://api.notion.com/v1/search"
            data = {
                "results": [
                    {
                        "id": expected,
                        "properties": {
                            "title": {"type": "title", "title": [{"plain_text": "Team notes"}]}
                        },
                    }
                ]
            }
        return httpx.Response(200, json=data)

    choices = resources(provider, "private-token", httpx.MockTransport(request))
    assert choices[0]["id"] == expected and choices[0]["name"]
    assert "private-token" not in str(choices)
    assert all(req.url.scheme == "https" for req in seen)


def test_discovery_does_not_follow_redirects_or_expose_provider_errors():
    with pytest.raises(Denied):
        resources(
            "github",
            "private",
            httpx.MockTransport(
                lambda req: httpx.Response(302, headers={"Location": "https://evil.test"})
            ),
        )
