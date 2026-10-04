from pathlib import Path

import pytest

from scripts.run_local_meetings import launch_configuration


def test_private_setup_required(tmp_path):
    with pytest.raises(ValueError):
        launch_configuration(tmp_path)


def test_loopback_launcher_does_not_enable_public_features(tmp_path, monkeypatch):
    root = tmp_path / "site"
    desktop = tmp_path / "desktop"
    root.mkdir()
    desktop.mkdir()
    (root / ".env.meeting-server").write_text("")
    (desktop / ".env.meetings").write_text("")
    monkeypatch.setattr("scripts.run_local_meetings.ROOT", root)
    monkeypatch.setenv("AEDROVA_SPEECH_ENABLED", "true")
    monkeypatch.setenv("AEDROVA_GATEWAY_ENABLED", "true")
    command, environment = launch_configuration(desktop)
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert environment["AEDROVA_MEETINGS_ENABLED"] == "true"
    for name in ("SPEECH_ENABLED", "GATEWAY_ENABLED", "CHECKOUT_ENABLED", "RELEASE_READY"):
        assert environment["AEDROVA_" + name] == "false"
    assert all(
        Path(command[i + 1]).is_file() for i, arg in enumerate(command) if arg == "--env-file"
    )
