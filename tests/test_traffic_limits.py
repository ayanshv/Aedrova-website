import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.store import Store
from aedrova_site.traffic_limits import TrafficLimits


def test_login_limit_persists_across_workers_and_forwarded_header_is_not_a_bypass(tmp_path):
    database = f"sqlite:///{tmp_path}/limits.sqlite"

    def application():
        app = FastAPI()
        app.add_middleware(TrafficLimits, store=Store(database, Config().encryption_key))

        @app.get("/auth/google")
        def login():
            return {"ok": True}

        return app

    # Keep the test away from an actual fixed-window boundary.
    from unittest.mock import patch

    with patch.object(time, "time", return_value=1800000001):
        with TestClient(application()) as a, TestClient(application()) as b:
            for i in range(10):
                assert a.get("/auth/google", headers={"x-forwarded-for": str(i)}).status_code == 200
            rejected = b.get("/auth/google", headers={"x-forwarded-for": "another-ip"})
            assert rejected.status_code == 429
            assert 1 <= int(rejected.headers["retry-after"]) <= 300


def test_unknown_routes_and_metadata_are_bounded(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/web.sqlite"))
    with TestClient(app) as client:
        oversized = client.get("/missing?value=" + "x" * 8200)
        assert oversized.status_code == 431
        ambiguous = client.get(
            "/missing", headers=[("authorization", "one"), ("authorization", "two")]
        )
        assert ambiguous.status_code == 400
        # Unmatched paths share the same bucket; random URLs cannot grow keys.
        calls = []
        original = app.state.store.rate_limit

        def observe(key, **kwargs):
            calls.append(key)
            return original(key, **kwargs)

        app.state.store.rate_limit = observe
        client.get("/missing-one")
        client.get("/missing-two")
        assert calls[0] == calls[1]


def test_malformed_and_control_character_json_is_rejected_without_echo(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/web.sqlite"))
    with TestClient(app) as client:
        for body in (
            b'{"email":',
            b'{"email":"private\\u0000value"}',
            b'"\xff"',
            b'{"number":NaN}',
            b'{"number":1e999}',
        ):
            result = client.post(
                "/api/waitlist", content=body, headers={"content-type": "application/json"}
            )
            assert result.status_code == 422
            assert "private" not in result.text
