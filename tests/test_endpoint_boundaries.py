"""Adversarial boundary regression checks; isolated DB, no external provider calls."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.store import RateLimited


@pytest.fixture
def app(tmp_path):
    value = create_app(Config(database=f"sqlite:///{tmp_path}/audit.sqlite"))
    yield value
    value.state.identity.close()
    value.state.store.engine.dispose()


@pytest.mark.parametrize(
    "media",
    [
        "application/json",
        "Application/JSON; charset=utf-8",
        "application/problem+json",
        "application/vnd.aedrova+json",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        b'{"x":NaN}',
        b'{"x":1e999}',
        b'{"x":"private\\u0000payload"}',
        ("[" * 70 + "0" + "]" * 70).encode(),
    ],
)
def test_json_media_variants_cannot_bypass_input_bounds(app, media, body):
    with TestClient(app) as client:
        result = client.post("/api/waitlist", content=body, headers={"content-type": media})
    assert result.status_code == 422
    assert "Malformed request" in result.json()["error"]
    assert "private" not in result.text


def test_gateway_bounds_json_even_with_no_or_wrong_content_type(app):
    with TestClient(app) as client:
        for headers in [{}, {"content-type": "text/plain"}]:
            result = client.post(
                "/gateway/codex/v1/responses", content=b'{"n":NaN}', headers=headers
            )
            assert result.status_code == 403
            assert "Malformed request" in result.json()["error"]


def require_headers(response):
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex"


def test_early_body_metadata_origin_and_throttle_errors_keep_headers(app):
    with TestClient(app) as client:
        cases = [
            client.post("/api/waitlist", content=b"x" * 65537),
            client.get("/missing?data=" + "x" * 8200),
            client.get("/", headers={"origin": "https://untrusted.example"}),
            client.get("/api/missing"),
        ]
        assert [r.status_code for r in cases] == [413, 431, 403, 404]
        for result in cases:
            require_headers(result)

        def limited(*args, **kwargs):
            raise RateLimited(17)

        app.state.store.rate_limit = limited
        result = client.get("/api/session")
        assert result.status_code == 429 and result.headers["retry-after"] == "17"
        require_headers(result)


def test_unexpected_api_errors_do_not_leak_details_and_keep_headers(app):
    @app.get("/api/audit-crash")
    def crash():
        raise RuntimeError("private synthetic secret")

    with TestClient(app) as client:
        result = client.get("/api/audit-crash")
    assert result.status_code == 500
    assert "private" not in result.text and "secret" not in result.text
    assert result.headers["content-type"].startswith("application/json")
    require_headers(result)


def test_scanner_runs_outside_project_without_pythonpath(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_release_secrets.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS tracked-file credential patterns" in result.stdout
