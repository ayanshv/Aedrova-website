import base64
import json
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from aedrova_site.apple_revocation import APPLE, install, revoke


def test_apple_revoke_checks_subject_and_cannot_forward_another_accounts_token():
    events = []

    def handle(request):
        events.append((str(request.url), parse_qs(request.content.decode())))
        if request.url.path == "/auth/token":
            claims = {"sub": "apple-user", "iss": APPLE, "aud": "com.example.login"}
            payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
            return httpx.Response(200, json={"id_token": f"header.{payload}.signature"})
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert not revoke(client, "com.example.login", "secret", "test-token", {"other-user"})
        assert [event[0] for event in events] == [APPLE + "/auth/token"]
        assert revoke(client, "com.example.login", "secret", "test-token", {"apple-user"})

    assert events[-1] == (
        APPLE + "/auth/revoke",
        {
            "client_id": ["com.example.login"],
            "client_secret": ["secret"],
            "token": ["test-token"],
            "token_type_hint": ["refresh_token"],
        },
    )


@pytest.mark.parametrize(("status", "error"), [(400, "invalid_grant"), (503, "server_error")])
def test_apple_invalid_grant_and_outage_are_distinct(status, error):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"error": error}))
    ) as client:
        if status == 400:
            assert not revoke(client, "client", "secret", "token", {"apple-user"})
        else:
            with pytest.raises(HTTPException) as failure:
                revoke(client, "client", "secret", "token", {"apple-user"})
            assert failure.value.status_code == 503


def test_revocation_requires_own_pending_request(monkeypatch):
    class Store:
        def rate_limit(self, key, limit):
            assert (key, limit) == ("apple-revocation:account", 5)

    class Identity:
        receipt = None

        def user(self, token):
            assert token == "session"
            return {
                "id": "account",
                "identities": [{"provider": "apple", "identity_data": {"sub": "id"}}],
            }

        def request(self, path, token, *, method, data):
            assert (path, token, method, data) == (
                "/rest/v1/rpc/get_account_deletion_request",
                "session",
                "POST",
                {},
            )
            return self.receipt

    app = FastAPI()
    identity = Identity()
    install(app, Store(), identity, lambda request, change: request.headers["authorization"][7:])
    client = TestClient(app)
    monkeypatch.setenv("AEDROVA_APPLE_REVOKE_CLIENT_ID", "")
    assert (
        client.post("/api/account/apple/revoke", json={"refresh_token": "test"}).status_code == 403
    )
    headers = {"Authorization": "Bearer session"}
    for receipt, expected in [(None, 403), ({"completed": True}, 403), ({"completed": False}, 503)]:
        identity.receipt = receipt
        assert (
            client.post(
                "/api/account/apple/revoke", headers=headers, json={"refresh_token": "test"}
            ).status_code
            == expected
        )
