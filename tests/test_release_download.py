"""Release handoff stays closed for previews; public metadata never leaks local paths."""

import hashlib
import json

from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config


def test_release_endpoint_stays_closed_before_notarized_release():
    with TestClient(create_app(Config())) as client:
        assert client.get("/api/release").status_code == 503
        assert client.get("/api/download").status_code == 503


def test_verified_manifest_drives_update_and_download_handoff(tmp_path):
    # A manifest fixture tests wiring only; it is not signing/notarization acceptance.
    artifact = tmp_path / "Aedrova.dmg"
    artifact.write_bytes(b"release endpoint fixture")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(".manifest.json").write_text(
        json.dumps(
            {
                "path": str(artifact),
                "sha256": digest,
                "public_release": True,
                "version": "0.1.0",
                "architecture": "arm64",
                "minimum_macos": "14.0",
            }
        )
    )
    config = Config(release_ready=True, download_path=str(artifact), download_sha256=digest)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/release")
        assert response.status_code == 200
        assert response.json()["sha256"] == digest
        assert response.json()["architecture"] == "arm64"
        assert str(tmp_path) not in response.text
        assert "path" not in response.json()
        page = client.get("/download")
        assert "Explore Aedrova" in page.text
        assert "Check for updates" in page.text
        download = client.get("/api/download")
        assert download.content == artifact.read_bytes()
        assert "Aedrova.dmg" in download.headers["content-disposition"]


def test_release_files_removed_after_startup_fail_closed(tmp_path):
    artifact = tmp_path / "Aedrova.dmg"
    artifact.write_bytes(b"fixture")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = artifact.with_suffix(".manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "sha256": digest,
                "public_release": True,
                "version": "0.1.0",
                "architecture": "arm64",
                "minimum_macos": "14.0",
            }
        )
    )
    with TestClient(
        create_app(
            Config(
                release_ready=True,
                download_path=str(artifact),
                download_sha256=digest,
            )
        )
    ) as client:
        manifest.unlink()
        assert client.get("/api/release").status_code == 503
        artifact.unlink()
        assert client.get("/api/download").status_code == 503
