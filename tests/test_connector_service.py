"""HTTPS connector deployment isolation and budgets."""

from dataclasses import replace

import pytest
from cryptography.fernet import Fernet

from aedrova_site.config import Config
from aedrova_site.connector_service import allowed, validate


def config():
    return Config(
        origin="https://aedrova-connectors.onrender.com",
        production=True,
        database="postgresql+psycopg://aedrova_website.cpelagtufyocepnqcqqd:fixture@"
        "aws-0-us-west-1.pooler.supabase.com:5432/postgres?sslmode=require",
        encryption_key=Fernet.generate_key().decode(),
        supabase_database=True,
        dots_enabled=True,
        db_pool_size=1,
        db_max_overflow=0,
    )


def test_private_service_gates_and_connection_budget():
    validate(config())
    for field in (
        "checkout_enabled",
        "gateway_enabled",
        "meetings_enabled",
        "release_ready",
        "development_ai",
        "speech_enabled",
        "legal_ready",
    ):
        with pytest.raises(ValueError):
            validate(replace(config(), **{field: True}))
    with pytest.raises(ValueError, match="pooled"):
        validate(replace(config(), db_pool_size=2))


@pytest.mark.parametrize(
    "path",
    [
        "/api/runs",
        "/api/checkout",
        "/api/waitlist",
        "/api/meetings/join",
        "/account",
        "/plans",
        "/download",
        "/auth/logout",
        "/dots/github/events",
    ],
)
def test_other_product_routes_are_not_exposed(path):
    assert not allowed("GET", path)
    assert not allowed("POST", path)


def test_oauth_static_and_native_authenticated_routes_are_preserved():
    assert allowed("GET", "/api/buds/connectors")
    assert allowed("GET", "/buds/authorize/" + "a" * 43)
    assert allowed("GET", "/buds/oauth/supabase/callback")
    assert allowed("GET", "/static/bud-connected.css")
    assert allowed("POST", "/api/buds/oauth/start")
    assert allowed("POST", "/api/dots/tools")
    assert allowed("POST", "/api/buds/connections/search")
    assert not allowed("GET", "/api/buds/connections/search")
    for provider in ("stripe", "instagram", "vercel"):
        assert allowed("GET", "/buds/oauth/" + provider + "/callback")
        assert not allowed("POST", "/buds/oauth/" + provider + "/callback")
    assert not allowed("POST", "/static/site.css")
    assert not allowed("GET", "/buds/oauth/unknown/callback")


def test_http_boundary_blocks_product_routes_without_calling_them(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aedrova_site import connector_service

    calls = []
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    def downstream(path):
        calls.append(path)
        return {"downstream": path}

    monkeypatch.setattr(connector_service, "create_app", lambda config: app)
    with TestClient(connector_service.create_connector_app(config())) as client:
        assert client.get("/").json()["service"] == "Aedrova Bud connections"
        assert client.post("/api/checkout").status_code == 404
        assert client.post("/api/runs").status_code == 404
        assert not calls
        assert client.get("/api/buds/connectors").status_code == 200
        assert calls == ["api/buds/connectors"]
