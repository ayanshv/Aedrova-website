import base64
import io
import json
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from test_meeting_context_api import config

from aedrova_site.app import MeetingReviewBody, MeetingSpeechBody, create_app
from aedrova_site.speech import SpeechService, decode_audio
from aedrova_site.store import Denied


def audio(seconds=1, channels=1, rate=16000):
    result = io.BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\0\0" * int(rate * seconds) * channels)
    return base64.b64encode(result.getvalue()).decode()


def body(**updates):
    return MeetingSpeechBody(
        **(
            dict(
                meeting=uuid4(),
                identifier=uuid4(),
                revision=1,
                roster=[uuid4()],
                offset_ms=0,
                audio=audio(),
            )
            | updates
        )
    )


def service(response=None):
    sent = []

    def provider(request):
        sent.append(request)
        return response or httpx.Response(200, json={"text": "Reviewed words"})

    instance = SpeechService(
        SimpleNamespace(speech_enabled=True, speech_key="fixture-secret"),
        None,
        transport=httpx.MockTransport(provider),
    )
    instance.database = MagicMock(side_effect=["pending", uuid4()])
    return instance, sent


def test_decode_removes_extraneous_payload():
    raw = base64.b64decode(audio()) + b"PRIVATE_METADATA"
    clean, duration = decode_audio(base64.b64encode(raw).decode())
    assert duration == 1000 and b"PRIVATE_METADATA" not in clean


@pytest.mark.parametrize(
    "encoded",
    ["!!!", audio(0.5), audio(11), audio(channels=2), audio(rate=8000)],
    ids=["invalid", "short", "oversized", "stereo", "wrong-rate"],
)
def test_malformed_audio_never_reserved_or_sent(encoded):
    instance, sent = service()
    with pytest.raises(Denied):
        instance.transcribe(
            str(uuid4()), SimpleNamespace(**(body().model_dump() | {"audio": encoded}))
        )
    instance.database.assert_not_called()
    assert not sent
    instance.close()


def test_authorized_provider_request_and_review_gate():
    instance, sent = service()
    user = str(uuid4())
    result = instance.transcribe(user, body())
    assert result["review_required"] and len(sent) == 1
    request = sent[0]
    assert request.url == "https://api.openai.com/v1/audio/transcriptions"
    assert b"whisper-1" in request.content and b"microphone.wav" in request.content
    assert instance.database.call_args_list[0].args[1]["user"] == user
    assert instance.database.call_args_list[1].args[1]["body"] == "Reviewed words"
    instance.close()


def test_consent_denial_and_completed_replay_never_call_provider():
    instance, sent = service()
    instance.database.side_effect = Denied("consent")
    with pytest.raises(Denied):
        instance.transcribe(str(uuid4()), body())
    assert not sent
    instance.database.side_effect = None
    instance.database.return_value = "completed"
    assert instance.transcribe(str(uuid4()), body())["replayed"]
    assert not sent
    instance.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="fixture-secret"),
        httpx.Response(200, json={"text": "x" * 2001}),
        httpx.Response(200, text="x" * 17000),
        httpx.Response(200, json={"text": None}),
        httpx.Response(200, json=["wrong-shape"]),
    ],
)
def test_provider_failure_sanitized_and_no_retry(response):
    instance, sent = service(response)
    with pytest.raises(Denied) as error:
        instance.transcribe(str(uuid4()), body())
    assert "fixture-secret" not in str(error.value) and len(sent) == 1
    assert instance.database.call_args_list[-1].args[1]["body"] is None
    instance.close()


def test_changed_consent_after_provider_discards_result():
    instance, sent = service()
    instance.database.side_effect = ["pending", Denied("withdrawn"), Denied("withdrawn")]
    with pytest.raises(Denied):
        instance.transcribe(str(uuid4()), body())
    assert len(sent) == 1
    instance.close()


def test_busy_and_disabled_never_send():
    instance, sent = service()
    for _ in range(4):
        instance.slots.acquire()
    with pytest.raises(Denied, match="busy"):
        instance.transcribe(str(uuid4()), body())
    instance.config.speech_enabled = False
    with pytest.raises(Denied, match="not enabled"):
        instance.transcribe(str(uuid4()), body())
    assert not sent
    instance.database.assert_not_called()
    instance.close()


def test_models_reject_speaker_and_invalid_review():
    good = body().model_dump()
    # Every meeting input forbids extra fields; trusted identity owns the speaker.
    with pytest.raises(ValueError):
        MeetingSpeechBody(**good, speaker_id=str(uuid4()))
    for values in [dict(version=-1), dict(body="x" * 2001), dict(decision="yes")]:
        with pytest.raises(ValueError):
            MeetingReviewBody(
                **(dict(identifier=uuid4(), version=0, body="Text", decision=False) | values)
            )


def test_api_disabled_and_scoped_review_history(tmp_path):
    app = create_app(config(tmp_path, enabled=True))
    app.state.identity.request = MagicMock(return_value=[])
    app.state.identity.user = MagicMock()
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/meetings/speech", json=json.loads(body().model_dump_json())
            ).status_code
            == 403
        )
        app.state.identity.user.assert_not_called()
        headers = {"authorization": "Bearer account-session"}
        meeting, channel = str(uuid4()), str(uuid4())
        assert (
            client.get(
                "/api/meetings/transcript/" + meeting + "?page=2", headers=headers
            ).status_code
            == 200
        )
        call = app.state.identity.request.call_args.args
        assert call[1] == "account-session" and "offset=100" in call[0]
        assert (
            client.get(
                "/api/meetings/transcript/" + meeting + "?page=200", headers=headers
            ).status_code
            == 403
        )
        assert client.get("/api/meetings/history/" + channel, headers=headers).status_code == 200
        assert "started_at.desc" in app.state.identity.request.call_args.args[0]
        assert (
            client.post(
                "/api/meetings/transcript/review",
                headers=headers,
                json=dict(identifier=str(uuid4()), version=2, body="Corrected", decision=True),
            ).status_code
            == 200
        )
        args = app.state.identity.request.call_args
        assert args.args[1] == "account-session" and args.kwargs["data"]["p_version"] == 2
    app.state.store.engine.dispose()


def test_speech_gate_requires_private_database_key_and_meeting_context():
    from aedrova_site.config import Config

    for values in [
        dict(speech_enabled=True),
        dict(speech_enabled=True, meetings_enabled=True, meeting_context_enabled=True),
    ]:
        with pytest.raises(ValueError):
            Config(**values).validate()
    config = Config(speech_key="fixture-hidden-secret")
    assert "fixture-hidden-secret" not in repr(config)


def test_empty_and_timeout_results_do_not_persist_text():
    instance, _ = service(httpx.Response(200, json={"text": "  "}))
    instance.database.side_effect = ["pending", None]
    assert instance.transcribe(str(uuid4()), body())["id"] is None
    assert instance.database.call_args_list[-1].args[1]["body"] is None
    instance.close()


def test_trickling_provider_deadline_discards_text(monkeypatch):
    class Trickle(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"text":'
            yield b'"never saved"}'

    instance, sent = service(httpx.Response(200, stream=Trickle()))
    clock = iter([0, 1, 26])
    monkeypatch.setattr("aedrova_site.speech.time.monotonic", lambda: next(clock))
    with pytest.raises(Denied, match="No automatic retry"):
        instance.transcribe(str(uuid4()), body())
    assert len(sent) == 1
    assert instance.database.call_args_list[-1].args[1]["body"] is None
    assert instance.slots.acquire(blocking=False)
    instance.close()

    def timeout(request):
        raise httpx.ReadTimeout("fixture-hidden-secret", request=request)

    instance = SpeechService(
        SimpleNamespace(speech_enabled=True, speech_key="fixture-secret"),
        None,
        transport=httpx.MockTransport(timeout),
    )
    instance.database = MagicMock(side_effect=["pending", None])
    with pytest.raises(Denied) as error:
        instance.transcribe(str(uuid4()), body())
    assert "fixture-hidden-secret" not in str(error.value)
    assert instance.database.call_args_list[-1].args[1]["body"] is None
    instance.close()


def test_transcription_reserves_shared_budget_before_provider(tmp_path):
    from aedrova_site.store import Store

    instance, sent = service()
    store = Store(f"sqlite:///{tmp_path / 'speech-budget.sqlite'}")
    user = str(uuid4())
    store.activate_free(user, "workspace")
    instance.store = store
    instance.config.speech_rate_microusd_per_minute = 6000
    try:
        instance.transcribe(user, body(), workspace="workspace")
        assert len(sent) == 1
        assert store.balance("workspace")["monthly_spent"] == 100
        assert store.balance("workspace")["monthly_requests"] == 1
        instance.database.side_effect = ["pending", uuid4()]
        store.company_budget = 100
        with pytest.raises(Denied):
            instance.transcribe(user, body(), workspace="workspace")
        assert len(sent) == 1
    finally:
        store.engine.dispose()
        instance.close()
