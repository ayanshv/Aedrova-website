"""The invited-beta password gate on the plans and download pages."""

import pytest
from fastapi.testclient import TestClient

from aedrova_site import beta_gate
from aedrova_site.app import create_app
from aedrova_site.config import Config

PASSWORD = "a-long-test-beta-password"
ORIGIN = "http://testserver"


def client(tmp_path, password=PASSWORD):
    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'beta.sqlite'}",
            beta_password=password,
            origin=ORIGIN,
        )
    )
    return TestClient(app, follow_redirects=False)


def unlock(c, password):
    return c.post(
        "/beta/unlock",
        content=f"password={password}",
        headers={"origin": ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )


def test_plans_page_shows_the_gate_only_when_configured(tmp_path):
    with client(tmp_path) as c:
        page = c.get("/plans").text
        assert "Part of the Beta?" in page
        assert PASSWORD not in page
    with client(tmp_path, password="") as c:
        assert "Part of the Beta?" not in c.get("/plans").text


def test_download_is_closed_until_the_password_is_right(tmp_path):
    with client(tmp_path) as c:
        assert c.get("/download").headers["location"] == "/plans#beta"
        assert c.get("/api/download").status_code == 403
        wrong = unlock(c, "not-the-password")
        assert wrong.status_code == 303
        assert wrong.headers["location"] == "/plans?beta=wrong#beta"
        assert "set-cookie" not in wrong.headers
        assert "did not match" in c.get("/plans?beta=wrong").text
        assert c.get("/download").status_code == 303


def test_the_right_password_opens_the_download_with_a_signed_cookie(tmp_path):
    with client(tmp_path) as c:
        right = unlock(c, PASSWORD)
        assert right.status_code == 303 and right.headers["location"] == "/download"
        cookie = right.headers["set-cookie"]
        assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
        assert PASSWORD not in cookie
        assert c.get("/download").status_code == 200
        assert "Go to the download" in c.get("/plans").text
        assert c.get("/api/download").status_code == 503  # unlocked; no verified installer yet


def test_browsers_that_send_a_null_origin_can_still_unlock(tmp_path):
    with client(tmp_path) as c:
        for origin in ("null", None):
            headers = {"content-type": "application/x-www-form-urlencoded"}
            if origin:
                headers["origin"] = origin
            right = c.post("/beta/unlock", content=f"password={PASSWORD}", headers=headers)
            assert right.status_code == 303 and right.headers["location"] == "/download"


def test_forged_expired_and_cross_site_attempts_fail(tmp_path):
    with client(tmp_path) as c:
        c.cookies.set(beta_gate.COOKIE, "9999999999.deadbeef")
        assert c.get("/download").status_code == 303
        c.cookies.set(beta_gate.COOKIE, beta_gate.issue(PASSWORD, now=0))
        assert c.get("/download").status_code == 303
        c.cookies.clear()
        other = c.post(
            "/beta/unlock",
            content=f"password={PASSWORD}",
            headers={"origin": "https://evil.example"},
        )
        assert other.status_code == 403


def test_changing_the_password_signs_everyone_out():
    token = beta_gate.issue("first-password-here")
    assert beta_gate.valid("first-password-here", token)
    assert not beta_gate.valid("second-password-here", token)
    assert not beta_gate.valid("", token)


def test_a_short_password_is_refused():
    with pytest.raises(ValueError, match="at least 12"):
        Config(beta_password="short").validate()


def test_the_gate_works_while_the_site_is_in_waitlist_mode(tmp_path):
    app = create_app(
        Config(
            database=f"sqlite:///{tmp_path / 'wait.sqlite'}",
            beta_password=PASSWORD,
            origin=ORIGIN,
            waitlist_only=True,
        )
    )
    with TestClient(app, follow_redirects=False) as c:
        assert "Part of the Beta?" in c.get("/plans").text
        assert c.get("/download").headers["location"] == "/plans#beta"
        assert unlock(c, PASSWORD).headers["location"] == "/download"
        assert c.get("/download").status_code == 200
