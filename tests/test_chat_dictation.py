from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from test_speech import audio

from aedrova_site.app import DictationBody, create_app
from aedrova_site.config import Config
from aedrova_site.speech import DictationService
from aedrova_site.store import Denied


def test_draft_speech_reserves_budget_and_never_persists_audio_or_text():
    store = MagicMock()
    store.create_run.return_value = {"token": "run-token", "id": "run-id"}
    store.reserve.return_value = ("reservation", False)
    sent = []

    def provider(request):
        sent.append(request)
        return httpx.Response(200, json={"text": "A draft, not a sent message"})

    config = SimpleNamespace(
        chat_speech_enabled=True, speech_key="secret", speech_rate_microusd_per_minute=6000
    )
    instance = DictationService(config, store, transport=httpx.MockTransport(provider))
    body = DictationBody(channel=uuid4(), identifier=uuid4(), audio=audio(30))
    result = instance.transcribe_draft(
        str(uuid4()), body, workspace="origin", billing_workspace="verified-root"
    )
    assert result == {"text": "A draft, not a sent message"}
    assert len(sent) == 1 and store.reserve.call_args.args[2] == 3000
    assert store.create_run.call_args.kwargs["billing_workspace"] == "verified-root"
    store.settle.assert_called_once_with("reservation", 3000, b"completed")
    store.end_run.assert_called_once()
    instance.close()


def test_allowance_denial_never_calls_provider():
    store = MagicMock()
    store.create_run.side_effect = Denied("no plan")
    sent = []
    instance = DictationService(
        SimpleNamespace(chat_speech_enabled=True),
        store,
        transport=httpx.MockTransport(lambda request: sent.append(request)),
    )
    with pytest.raises(Denied):
        instance.transcribe_draft(
            str(uuid4()),
            DictationBody(channel=uuid4(), identifier=uuid4(), audio=audio()),
            workspace="origin",
            billing_workspace="root",
        )
    assert not sent
    store.reserve.assert_not_called()
    instance.close()


def test_model_rejects_impersonation_and_oversized_audio():
    for update in [{"user": str(uuid4())}, {"workspace": str(uuid4())}, {"audio": "a" * 1280101}]:
        with pytest.raises(ValueError):
            DictationBody(
                **({"channel": uuid4(), "identifier": uuid4(), "audio": audio()} | update)
            )


def test_disabled_and_inaccessible_channel_never_send_audio(tmp_path):
    config = Config(database=f"sqlite:///{tmp_path / 'chat.db'}")
    app = create_app(config)
    app.state.dictation.transcribe_draft = MagicMock()
    with TestClient(app) as client:
        payload = {"channel": str(uuid4()), "identifier": str(uuid4()), "audio": audio()}
        assert client.post("/api/chat/speech", json=payload).status_code == 403
        config.chat_speech_enabled = True
        app.state.identity.user = MagicMock(return_value={"id": str(uuid4())})
        app.state.identity.request = MagicMock(return_value=[])
        assert (
            client.post(
                "/api/chat/speech", json=payload, headers={"Authorization": "Bearer fixture"}
            ).status_code
            == 403
        )
    app.state.dictation.transcribe_draft.assert_not_called()
    app.state.store.engine.dispose()


def test_full_duration_route_accepts_bounded_payload_and_uses_verified_scope(tmp_path):
    config = Config(database=f"sqlite:///{tmp_path / 'route.db'}")
    app = create_app(config)
    config.chat_speech_enabled = True
    user, workspace, root = str(uuid4()), str(uuid4()), str(uuid4())
    app.state.identity.user = MagicMock(return_value={"id": user})
    app.state.identity.request = MagicMock(return_value=[{"workspace_id": workspace}])
    app.state.identity.require = MagicMock()
    app.state.identity.billing_context = MagicMock(return_value={"billing_workspace": root})
    app.state.dictation.transcribe_draft = MagicMock(return_value={"text": "Editable"})
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/speech",
            headers={"Authorization": "Bearer fixture"},
            json={"channel": str(uuid4()), "identifier": str(uuid4()), "audio": audio(30)},
        )
        assert response.status_code == 200 and response.json() == {"text": "Editable"}
    app.state.identity.require.assert_called_once_with("fixture", workspace)
    assert app.state.dictation.transcribe_draft.call_args.kwargs == {
        "workspace": workspace,
        "billing_workspace": root,
    }
    app.state.store.engine.dispose()
