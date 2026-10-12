from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from scripts.remove_waitlist import remove_registration


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Config(database=f"sqlite:///{tmp_path / 'privacy.sqlite3'}", waitlist_only=True)
    )
    with TestClient(app) as instance:
        yield instance
    app.state.store.engine.dispose()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if "id" in values:
            self.ids.add(values["id"])


def test_trust_destinations_and_local_anchors_work_without_opening_checkout(client):
    pages = [
        "/privacy",
        "/terms",
        "/support",
        "/data-controls",
        "/security",
        "/cookies",
        "/subprocessors",
        "/acceptable-use",
    ]
    parsed = {}
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200
        assert "contact@aedrova.com" in response.text
        assert "Footer navigation" in response.text
        parsed[path] = Links()
        parsed[path].feed(response.text)
        assert 'href="/onboarding"' not in response.text
    for path, parser in parsed.items():
        for href in parser.links:
            target, _, anchor = href.partition("#")
            target = target or path
            if target in parsed and anchor:
                assert anchor in parsed[target].ids, href
    assert "one-click automated erase/export" in client.get("/data-controls").text
    assert "not a live uptime monitor" in client.get("/security").text
    assert "(408) 634-5254" in client.get("/support").text


def test_verified_waitlist_removal_preserves_auth_and_other_registrations(client):
    store = client.app.state.store
    store.session("u1", {"kind": "account", "email": "person@example.com"})
    store.session("u2", {"kind": "waitlist", "email": "other@example.com"})
    store.session("u3", {"kind": "waitlist", "email": "person@example.com"})
    store.session("u4", {"kind": "waitlist", "email": "PERSON@example.com"})
    assert remove_registration(store, " Person@example.com ") == 2
    assert remove_registration(store, "person@example.com") == 0
    assert store.session("u1")["kind"] == "account"
    assert store.session("u2")["email"] == "other@example.com"
    with pytest.raises(ValueError):
        remove_registration(store, "")


def test_waitlist_removal_rolls_back_if_any_record_cannot_be_decrypted(client):
    from cryptography.fernet import InvalidToken
    from sqlalchemy import text

    store = client.app.state.store
    store.session("valid", {"kind": "waitlist", "email": "person@example.com"})
    store.session("damaged", {"kind": "waitlist", "email": "other@example.com"})
    from aedrova_site.store import digest

    with store.tx() as db:
        db.execute(
            text("UPDATE sessions SET payload='invalid' WHERE id=:id"), {"id": digest("damaged")}
        )
    with pytest.raises(InvalidToken):
        remove_registration(store, "person@example.com")
    assert store.session("valid")["email"] == "person@example.com"
