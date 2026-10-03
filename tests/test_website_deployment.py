"""The first public website must be ready without silently opening paid product access."""

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from scripts.check_website_deployment import check


def production():
    return Config(
        origin="https://aedrova.com",
        production=True,
        database="postgresql+psycopg://fixture-unused",
        encryption_key=Fernet.generate_key().decode(),
    )


def respond(request):
    assert not request.headers.get("authorization")
    assert not request.headers.get("apikey")
    assert not request.url.query
    if request.url.path == "/health":
        return httpx.Response(
            200, json={"status": "ok", "checkout_enabled": False, "managed_ai_enabled": False}
        )
    if request.url.path == "/health/ready":
        return httpx.Response(200, json={"status": "ready"})
    return httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8", "x-content-type-options": "nosniff"},
        text="<html></html>",
    )


def test_offline_check_never_claims_live_deployment():
    assert check(production())["https_pages_and_database"] == "not tested"


def test_probe_checks_pages_and_database_without_credentials():
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report = check(production(), probe=True, client=client)
    assert report["https_pages_and_database"] == "passed"
    assert report["google_sign_in"] == "manual acceptance required"


@pytest.mark.parametrize(
    "status,body",
    [
        (503, {"status": "unavailable"}),
        (302, {"status": "ready"}),
        (200, ["ready"]),
        (200, {"status": "unavailable"}),
    ],
)
def test_probe_rejects_database_outage_redirect_and_malformed_readiness(status, body):
    def handler(request):
        if request.url.path == "/health/ready":
            return httpx.Response(status, json=body)
        return respond(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            check(production(), probe=True, client=client)


def test_probe_rejects_accidentally_open_public_checkout():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(
                200, json={"status": "ok", "checkout_enabled": True, "managed_ai_enabled": False}
            )
        return respond(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            check(production(), probe=True, client=client)


def test_probe_rejects_wrong_page_and_oversized_health_response():
    for route in ("/plans", "/health"):

        def handler(request, route=route):
            if request.url.path == route:
                return httpx.Response(200, text="x" * 20000)
            return respond(request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError):
                check(production(), probe=True, client=client)


def test_local_config_is_not_public_acceptance():
    with pytest.raises(ValueError):
        check(Config())


def test_probe_matches_actual_application_response_contract(tmp_path):
    config = production()
    fixture = Config(
        origin=config.origin,
        encryption_key=config.encryption_key,
        database="sqlite:///" + str(tmp_path / "site.sqlite3"),
    )
    app = create_app(fixture)
    with TestClient(app, base_url=config.origin) as site:

        def handler(request):
            reply = site.get(request.url.path, follow_redirects=False)
            return httpx.Response(reply.status_code, headers=reply.headers, content=reply.content)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            assert check(config, probe=True, client=client)["https_pages_and_database"] == "passed"
