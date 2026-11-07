from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config


def test_apple_login_is_hidden_and_closed_until_configured(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'closed.sqlite'}"))
    with TestClient(app) as client:
        assert "/auth/apple" not in client.get("/account").text
        assert client.get("/auth/apple", follow_redirects=False).status_code == 404
    app.state.store.engine.dispose()


def test_apple_uses_existing_pkce_state_cookie_and_limit(tmp_path):
    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'open.sqlite'}",
            apple_login_enabled=True,
        )
    )
    with TestClient(app) as client:
        page = client.get("/account?plan=annual")
        assert "Sign in with Apple" in page.text
        response = client.get("/auth/apple?plan=annual", follow_redirects=False)
        assert response.status_code == 303
        query = parse_qs(urlsplit(response.headers["location"]).query)
        assert query["provider"] == ["apple"]
        assert query["scopes"] == ["email name"]
        assert query["code_challenge_method"] == ["s256"]
        assert "code_verifier" not in query
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        state = app.state.store.session(client.cookies["aedrova_oauth"])
        assert state["plan"] == "annual"
        for _ in range(9):
            assert client.get("/auth/google", follow_redirects=False).status_code == 303
        assert client.get("/auth/apple", follow_redirects=False).status_code == 429
    app.state.store.engine.dispose()
