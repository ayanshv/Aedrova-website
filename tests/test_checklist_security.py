"""Adversarial SQL values and permission-scoped launch-email choices."""

import ast
import csv
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event, text
from test_waitlist import client  # noqa: F401

from aedrova_site.communications import unsubscribe_url
from scripts.export_waitlist import export


@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "'; DROP TABLE sessions; --", "x' UNION SELECT payload FROM sessions --"],
)
def test_user_values_never_become_sql(client, payload):  # noqa: F811
    store = client.app.state.store
    seen = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(store.engine, "before_cursor_execute", capture)
    try:
        store.session("victim", {"private": "unchanged"})
        store.session(payload, {"content": payload})
        store.rate_limit(payload, limit=5, seconds=60)
        assert store.session(payload)["content"] == payload
        with store.tx() as db:
            assert (
                db.execute(
                    text("SELECT count(*) FROM sessions WHERE id=:value"), {"value": payload}
                ).scalar()
                == 0
            )
            with pytest.raises(Exception, match="Choose a plan"):
                store.billing_lock(db, payload)
        assert store.session("victim") == {"private": "unchanged"}
        assert not any(payload in sql for sql in seen)
    finally:
        event.remove(store.engine, "before_cursor_execute", capture)


def test_no_interpolated_sql_literals():
    # Guard new direct interpolation at SQLAlchemy text sinks. Existing dynamic
    # schema/lease statements are reviewed constant allowlists, not user SQL.
    for path in Path("aedrova_site").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Name)
                or node.func.id != "text"
            ):
                continue
            for arg in node.args:
                assert not any(isinstance(n, ast.JoinedStr) for n in ast.walk(arg)), (
                    path,
                    node.lineno,
                )
                assert not any(
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "format"
                    for n in ast.walk(arg)
                ), (path, node.lineno)


def test_unsubscribe_requires_valid_purpose_and_confirmation(client, tmp_path):  # noqa: F811
    store = client.app.state.store
    store.session("signed-in", {"access_token": "untouched"})
    store.session(
        "registration-fixture",
        {"kind": "waitlist", "email": "person@example.com", "consent": "launch-updates-v1"},
    )
    url = unsubscribe_url(store, "person@example.com", "http://127.0.0.1:8090")
    token = parse_qs(urlsplit(url).query)["token"][0]
    assert client.get(url).status_code == 200  # GET must not suppress link scanners.
    assert export(store, tmp_path / "before.csv") == 1
    headers = {"origin": "http://127.0.0.1:8090"}
    assert (
        client.post(
            "/api/unsubscribe", json={"token": token}, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    wrong = store.cipher.encrypt(b'{"purpose":"login","registration":"waitlist:bad"}').decode()
    for value in [token[:-8] + "tampered", wrong]:
        assert (
            client.post("/api/unsubscribe", json={"token": value}, headers=headers).status_code
            == 403
        )
    for _ in range(2):
        assert client.post("/api/unsubscribe", json={"token": token}, headers=headers).json() == {
            "ok": True
        }
    assert export(store, tmp_path / "after.csv") == 0
    assert store.session("signed-in") == {"access_token": "untouched"}
    with (tmp_path / "before.csv").open() as file:
        row = next(csv.DictReader(file))
    assert row["unsubscribe_url"].startswith("https://aedrova.com/unsubscribe?token=")
    assert "person@example.com" not in row["unsubscribe_url"]


def test_waitlist_eligibility_and_consent_are_explicit(client):  # noqa: F811
    headers = {"origin": "http://127.0.0.1:8090"}
    for fields in [
        {"consent": True},
        {"consent": True, "age_confirmed": False},
        {"consent": "yes", "age_confirmed": True},
    ]:
        assert (
            client.post(
                "/api/waitlist", json={"email": "person@example.com", **fields}, headers=headers
            ).status_code
            == 422
        )
