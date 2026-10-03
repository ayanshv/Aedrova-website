import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aedrova_site.app import create_app
from aedrova_site.config import Config


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Config(database=f"sqlite:///{tmp_path / 'waitlist.sqlite3'}", waitlist_only=True)
    )
    with TestClient(app) as instance:
        yield instance
    app.state.store.engine.dispose()


def test_waitlist_replaces_entry_points_and_blocks_signup(client):
    for path in ("/", "/plans", "/waitlist"):
        page = client.get(path)
        assert page.status_code == 200
        assert "Join waitlist today" in page.text
        assert 'href="/account?plan=' not in page.text
        assert 'href="/onboarding"' not in page.text
    for path in ("/onboarding", "/account", "/auth/google"):
        assert client.get(path, follow_redirects=False).headers["location"] == "/waitlist"


def test_saved_email_encrypted_and_duplicate_private(client):
    payload = {"email": "  PERSON@example.com ", "consent": True}
    headers = {"origin": "http://127.0.0.1:8090"}
    for _ in range(2):
        assert client.post("/api/waitlist", json=payload, headers=headers).json() == {"ok": True}
    store = client.app.state.store
    token = "waitlist:" + hashlib.sha256(b"person@example.com").hexdigest()
    assert store.session(token)["email"] == "person@example.com"
    with store.tx(write=False) as db:
        rows = db.execute(text("SELECT payload FROM sessions")).scalars().all()
    assert len(rows) == 1
    assert "person@example.com" not in rows[0]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "bad-email", "consent": True},
        {"email": "person@example.com", "consent": False},
        {"email": "person@example.com"},
        {"email": "a" * 260, "consent": True},
    ],
)
def test_invalid_signups_rejected(client, payload):
    assert (
        client.post(
            "/api/waitlist", json=payload, headers={"origin": "http://127.0.0.1:8090"}
        ).status_code
        == 422
    )


def test_foreign_origin_and_abuse_rejected(client):
    payload = {"email": "person@example.com", "consent": True}
    assert (
        client.post(
            "/api/waitlist", json=payload, headers={"origin": "https://other.example"}
        ).status_code
        == 403
    )
    for _ in range(5):
        assert (
            client.post(
                "/api/waitlist", json=payload, headers={"origin": "http://127.0.0.1:8090"}
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/waitlist", json=payload, headers={"origin": "http://127.0.0.1:8090"}
        ).status_code
        == 429
    )


def test_waitlist_cannot_enable_commercial_gates():
    for gate in ("checkout_enabled", "gateway_enabled", "meetings_enabled"):
        with pytest.raises(ValueError, match="Waitlist launch"):
            Config(waitlist_only=True, **{gate: True}).validate()


def test_operator_export_is_private_and_excludes_auth_sessions(client, tmp_path):
    from scripts.export_waitlist import export

    store = client.app.state.store
    store.session("signed-in-user", {"access_token": "private-auth-token"})
    client.post(
        "/api/waitlist",
        json={"email": "person@example.com", "consent": True},
        headers={"origin": "http://127.0.0.1:8090"},
    )
    path = tmp_path / "contacts.csv"
    assert export(store, path) == 1
    assert "person@example.com" in path.read_text()
    assert "private-auth-token" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        export(store, path)


def test_export_neutralizes_spreadsheet_formulas(client, tmp_path):
    from scripts.export_waitlist import export

    store = client.app.state.store
    store.session(
        "formula-fixture",
        {"kind": "waitlist", "email": "=2+2@example.com", "consent": "launch-updates-v1"},
    )
    path = tmp_path / "formula.csv"
    assert export(store, path) == 1
    assert "'=2+2@example.com" in path.read_text()


def test_waitlist_publishes_owner_contact_and_deletion_instructions(client):
    for path in ("/", "/privacy", "/terms"):
        page = client.get(path)
        assert 'href="mailto:aedrovaai@gmail.com"' in page.text
    privacy = client.get("/privacy").text
    assert "requests to remove your waitlist registration" in privacy
    assert "not used as AI build context" in privacy
    assert "Accounts, payments and app downloads are not open" in privacy
