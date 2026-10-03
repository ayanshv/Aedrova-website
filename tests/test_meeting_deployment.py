import httpx
import pytest
from cryptography.fernet import Fernet

from aedrova_site.config import Config
from scripts.check_meeting_setup import check
from scripts.serve import main


def staging():
    return Config(
        production=True,
        origin="https://meeting-staging.example",
        database="postgresql+psycopg://unused-in-preflight",
        encryption_key=Fernet.generate_key().decode(),
        meetings_enabled=True,
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="fixture-key",
        livekit_api_secret="fixture-only-" * 4,
    )


def test_offline_preflight_does_not_claim_media_or_https_acceptance():
    assert check(staging()) == {
        "configuration": "passed",
        "https_readiness": "not tested",
        "two_mac_media": "not tested",
        "transcription": "not enabled",
    }


def test_probe_checks_api_and_independent_guard_without_credentials():
    calls = []

    def respond(request):
        calls.append(request.url.path)
        assert not request.headers.get("authorization")
        return httpx.Response(
            200, json={"status": "ready" if request.url.path.endswith("meetings") else "ok"}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert check(staging(), probe=True, client=client)["https_readiness"] == "passed"
    assert calls == ["/health", "/health/meetings"]


@pytest.mark.parametrize(
    "status,body",
    [
        (503, {"status": "unavailable"}),
        (200, {"status": "unavailable"}),
        (302, {"status": "ready"}),
    ],
)
def test_unhealthy_guard_or_redirect_is_rejected(status, body):
    def respond(request):
        guard = request.url.path.endswith("meetings")
        return httpx.Response(status if guard else 200, json=body if guard else {"status": "ok"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises((ValueError, httpx.HTTPError)):
            check(staging(), probe=True, client=client)


def test_staging_cannot_silently_enable_ai_or_checkout():
    config = staging()
    config.release_ready = True
    with pytest.raises(ValueError):
        check(config)


def test_http_entrypoint_disables_access_logs_and_untrusted_forwarded_headers(monkeypatch):
    calls = []
    monkeypatch.delenv("AEDROVA_TRUSTED_PROXY_IPS", raising=False)
    monkeypatch.setenv("PORT", "8091")
    monkeypatch.setattr("scripts.serve.uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
    main()
    assert calls[0]["port"] == 8091 and not calls[0]["access_log"]
    assert not calls[0]["proxy_headers"]
    assert calls[0]["limit_concurrency"] == 128
    assert calls[0]["timeout_graceful_shutdown"] > 240
    monkeypatch.setenv("AEDROVA_TRUSTED_PROXY_IPS", "10.0.0.0/24")
    main()
    assert calls[1]["proxy_headers"] and calls[1]["forwarded_allow_ips"] == "10.0.0.0/24"
    monkeypatch.setenv("AEDROVA_TRUSTED_PROXY_IPS", "*")
    with pytest.raises(SystemExit, match="wildcard"):
        main()
