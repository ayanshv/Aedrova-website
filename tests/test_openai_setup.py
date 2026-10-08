import json
import stat

import httpx
import pytest

from scripts.setup_openai import install, verify

KEY = "sk-" + "x" * 40
MODEL = "gpt-5.3-codex"


def test_verify_is_read_only_and_does_not_follow_redirects():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": MODEL})

    with httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=False) as client:
        assert verify(KEY, MODEL, client=client)["paid_inference"] == "not run"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api.openai.com/v1/models/" + MODEL
    assert requests[0].headers["authorization"] == "Bearer " + KEY


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_provider_errors_do_not_expose_key(status):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"error": KEY}))
    ) as client:
        with pytest.raises(ValueError) as error:
            verify(KEY, MODEL, client=client)
    assert KEY not in str(error.value)


def test_private_install_leaves_activation_explicit(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/models.openai.json").write_text(json.dumps({"codex": {"id": MODEL}}))
    monkeypatch.setattr("scripts.setup_openai.verify", lambda *args: {"credentials": "verified"})
    install(KEY, root=tmp_path)
    path = tmp_path / ".env.openai"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "AEDROVA_GATEWAY_ENABLED=false" in path.read_text()
    assert not list(tmp_path.glob("tmp*"))


def test_failed_validation_does_not_write_credentials(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/models.openai.json").write_text(json.dumps({"codex": {"id": MODEL}}))

    def fail(*args):
        raise ValueError("Rejected")

    monkeypatch.setattr("scripts.setup_openai.verify", fail)
    with pytest.raises(ValueError):
        install(KEY, root=tmp_path)
    assert not (tmp_path / ".env.openai").exists()


def test_openai_only_configuration_does_not_require_claude_key():
    from pathlib import Path

    from aedrova_site.config import Config

    models = json.loads((Path(__file__).parents[1] / "config/models.openai.json").read_text())
    assert set(models) == {"codex"}
    Config(gateway_enabled=True, models=models, openai_key=KEY).validate()
