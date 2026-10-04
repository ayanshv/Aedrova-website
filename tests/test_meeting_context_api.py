from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config


def config(tmp_path, enabled=False):
    return Config(
        database=f"sqlite:///{tmp_path / 'meeting-text.db'}",
        meetings_enabled=True,
        meeting_context_enabled=enabled,
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="fixture",
        livekit_api_secret="fixture-" * 8,
        encryption_key="cJCmi_jhk27DV-CuzWR2VSGvnqftlkXpKbDYRhDPuTg=",
    )


def test_disabled_meeting_text_does_not_call_identity_or_rpc(tmp_path):
    app = create_app(config(tmp_path))
    app.state.identity.request = MagicMock()
    with TestClient(app) as client:
        assert (
            client.post("/api/meetings/consent", json={"meeting": str(uuid4())}).status_code == 403
        )
        assert (
            client.post("/api/meetings/text/withdraw", json={"meeting": str(uuid4())}).status_code
            == 403
        )
    app.state.identity.request.assert_not_called()
    app.state.store.engine.dispose()


def test_context_requires_meetings_and_waitlist_cannot_enable_it():
    with pytest.raises(ValueError, match="enabled meeting service"):
        Config(meeting_context_enabled=True).validate()
    with pytest.raises(ValueError):
        Config(waitlist_only=True, meetings_enabled=True, meeting_context_enabled=True).validate()


def test_meeting_text_models_bound_inputs_and_do_not_accept_speaker_impersonation():
    from aedrova_site.app import MeetingTextBody

    meeting, user = uuid4(), uuid4()
    good = dict(meeting=meeting, identifier=uuid4(), revision=1, roster=[user], body="CSV export")
    parsed = MeetingTextBody(**good)
    assert not hasattr(parsed, "speaker_id")
    for changes in [dict(revision=0), dict(roster=[]), dict(body="x" * 2001), dict(offset_ms=-1)]:
        with pytest.raises(ValueError):
            MeetingTextBody(**{**good, **changes})


def test_enabled_consent_forwards_user_token_without_server_speaker_claim(tmp_path):
    app = create_app(config(tmp_path, enabled=True))
    app.state.identity.request = MagicMock(return_value={"id": "fixture"})
    meeting = str(uuid4())
    with TestClient(app) as client:
        response = client.post(
            "/api/meetings/consent",
            headers={"authorization": "Bearer user-session-fixture"},
            json={"meeting": meeting, "transcription": True, "ai_context": False},
        )
        assert response.status_code == 200
    calls = app.state.identity.request.call_args_list
    assert calls[0].args == ("/rest/v1/rpc/set_meeting_consent", "user-session-fixture")
    assert calls[0].kwargs["data"] == {"p_meeting": meeting, "p_transcription": True, "p_ai": False}
    assert calls[1].args[0] == "/rest/v1/rpc/meeting_consent_snapshot"
    app.state.store.engine.dispose()
