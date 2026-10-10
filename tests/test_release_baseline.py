"""Deferred Pulse cannot be reached, even when Buds are enabled."""

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config


def test_pulse_routes_removed_without_removing_meeting_heartbeats(tmp_path):
    app = create_app(
        Config(
            database="sqlite:///" + str(tmp_path / "site.sqlite3"),
            encryption_key=Fernet.generate_key().decode(),
            dots_enabled=True,
        )
    )
    with TestClient(app) as client:
        assert client.get("/api/pulse").status_code == 404
        assert client.post("/api/pulse/refresh", json={}).status_code == 404
    paths = {route.path for route in app.routes}
    assert "/api/meetings/pulse" in paths
    assert "/api/buds/connectors" in paths
