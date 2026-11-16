"""Release handoff stays closed for previews; public metadata never leaks local paths."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config


def test_release_endpoint_stays_closed_before_notarized_release():
    with TestClient(create_app(Config())) as client:
        assert client.get("/api/release").status_code == 503
        assert client.get("/api/download").status_code == 503
        assert client.get("/api/release?platform=windows").status_code == 503
        assert client.get("/api/download?platform=windows").status_code == 503


def test_windows_download_requires_a_verified_installer(tmp_path):
    mac = tmp_path / "Aedrova.dmg"
    windows = tmp_path / "Aedrova-Setup.exe"
    mac.write_bytes(b"mac release fixture")
    windows.write_bytes(b"windows release fixture")
    mac_digest = hashlib.sha256(mac.read_bytes()).hexdigest()
    windows_digest = hashlib.sha256(windows.read_bytes()).hexdigest()
    mac.with_suffix(".manifest.json").write_text(
        json.dumps(
            {
                "sha256": mac_digest,
                "public_release": True,
                "version": "0.1.0",
                "architecture": "arm64",
                "minimum_macos": "14.0",
            }
        )
    )
    manifest = {
        "sha256": windows_digest,
        "public_release": True,
        "version": "0.1.0",
        "architecture": "x86_64",
    }
    windows_manifest = windows.with_suffix(".manifest.json")
    windows_manifest.write_text(json.dumps(manifest))
    config = Config(
        release_ready=True,
        download_path=str(mac),
        download_sha256=mac_digest,
        windows_download_path=str(windows),
        windows_download_sha256=windows_digest,
    )
    with pytest.raises(ValueError, match="Windows installer does not match"):
        config.validate()
    windows_manifest.write_text(json.dumps({**manifest, "authenticode_verified": True}))
    with TestClient(create_app(config)) as client:
        assert "Download for Windows" in client.get("/download").text
        metadata = client.get("/api/release?platform=windows").json()
        assert metadata["platform"] == "windows"
        assert metadata["sha256"] == windows_digest
        assert "path" not in metadata
        response = client.get("/api/download?platform=windows")
        assert response.content == windows.read_bytes()
        assert "Aedrova-Setup.exe" in response.headers["content-disposition"]
        assert client.get("/api/download").content == mac.read_bytes()
        windows_manifest.unlink()
        assert client.get("/api/download?platform=windows").status_code == 503


def test_verified_manifest_drives_update_and_download_handoff(tmp_path):

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
