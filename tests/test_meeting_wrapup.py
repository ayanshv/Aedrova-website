from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from test_meeting_context_api import config

from aedrova_site.app import create_app


def test_wrapup_forwards_user_scope_and_atomic_review_without_changing_consent(tmp_path):
    app = create_app(config(tmp_path, enabled=True))
    app.state.identity.request = MagicMock(return_value=2)
    meeting = str(uuid4())
    segments = [dict(identifier=str(uuid4()), version=i, body="Corrected text") for i in range(2)]
    headers = {"authorization": "Bearer test-session"}
    with TestClient(app) as client:
        result = client.post("/api/meetings/transcript/confirm", headers=headers,
                             json=dict(meeting=meeting, segments=segments))
        assert result.status_code == 200 and result.json() == {"confirmed": 2}
        args = app.state.identity.request.call_args
        assert args.args == ("/rest/v1/rpc/confirm_meeting_transcript", "test-session")
        assert args.kwargs["data"] == {"p_meeting": meeting, "p_segments": segments}
        app.state.identity.request.return_value = dict(meeting=meeting, ready=False)
        result = client.get("/api/meetings/wrapup/" + meeting, headers=headers)
        assert result.json()["ready"] is False
        assert app.state.identity.request.call_args.args[0] == "/rest/v1/rpc/meeting_wrapup_status"
    app.state.store.engine.dispose()


def test_disabled_or_invalid_confirmation_never_reaches_rpc(tmp_path):
    app = create_app(config(tmp_path))
    app.state.identity.request = MagicMock()
    with TestClient(app) as client:
        assert client.get("/api/meetings/wrapup/" + str(uuid4())).status_code == 403
        assert client.post("/api/meetings/transcript/confirm",
                           json=dict(meeting=str(uuid4()), segments=[])).status_code == 422
        assert client.post("/api/meetings/transcript/confirm",
                           json=dict(meeting=str(uuid4()), segments=[dict(
                               identifier=str(uuid4()), version=0, body="x", ai_allowed=True)]
                           )).status_code == 422
    app.state.identity.request.assert_not_called()
    app.state.store.engine.dispose()
