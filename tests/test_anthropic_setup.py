import json
import stat
from pathlib import Path

import httpx
import pytest

from scripts.setup_anthropic import install, verify

KEY = "sk-ant-" + "x" * 40
MODEL = "claude-sonnet-5-5"


def test_metadata_check_uses_only_fixed_read_endpoint():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": MODEL})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert verify(KEY, MODEL, client=client)["paid_inference"] == "not run"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api.anthropic.com/v1/models/" + MODEL
    assert requests[0].headers["x-api-key"] == KEY
    assert requests[0].headers["anthropic-version"] == "2023-06-01"


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_errors_never_print_credential_or_follow_redirects(status):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"location": "https://example.com"}, json={"error": KEY}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError) as error:
            verify(KEY, MODEL, client=client)
    assert len(requests) == 1
    assert KEY not in str(error.value)


@pytest.mark.parametrize(
    "payload", [{"id": "different-model"}, [], {"id": MODEL, "large": "x" * 32768}]
)
def test_wrong_model_or_unbounded_response_never_verifies(payload):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(ValueError):
            verify(KEY, MODEL, client=client)


def test_invalid_model_cannot_send_credential_to_another_path():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("must not send"))
    ) as client:
        with pytest.raises(ValueError):
            verify(KEY, "../messages?key=value", client=client)


def prepare(root):
    (root / "config").mkdir()
    (root / "config/models.anthropic.json").write_text(json.dumps({"claude_code": {"id": MODEL}}))


def test_private_install_does_not_activate_gateway(tmp_path, monkeypatch):
    prepare(tmp_path)
    monkeypatch.setattr("scripts.setup_anthropic.verify", lambda *args: {"credentials": "verified"})
    install(KEY, root=tmp_path)
    path = tmp_path / ".env.anthropic"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "AEDROVA_GATEWAY_ENABLED=false" in path.read_text()
    assert not list(tmp_path.glob(".env.anthropic-*"))


def test_failed_verification_preserves_existing_key(tmp_path, monkeypatch):
    prepare(tmp_path)
    path = tmp_path / ".env.anthropic"
    path.write_text("existing-private-file")

    def fail(*args):
        raise ValueError("Denied")

    monkeypatch.setattr("scripts.setup_anthropic.verify", fail)
    with pytest.raises(ValueError):
        install(KEY, root=tmp_path)
    assert path.read_text() == "existing-private-file"


def test_symlink_is_not_replaced_or_written(tmp_path):
    other = tmp_path / "private-target"
    other.write_text("preserve")
    (tmp_path / ".env.anthropic").symlink_to(other)
    with pytest.raises(ValueError):
        install(KEY, root=tmp_path)
    assert other.read_text() == "preserve"


def test_anthropic_only_configuration_needs_no_openai_key():
    from aedrova_site.config import Config

    models = json.loads((Path(__file__).parents[1] / "config/models.anthropic.json").read_text())
    assert set(models) == {"claude_code"}
    Config(gateway_enabled=True, models=models, anthropic_key=KEY).validate()
