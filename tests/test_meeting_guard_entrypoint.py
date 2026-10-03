from unittest.mock import MagicMock

import pytest

from aedrova_site.config import Config
from scripts import meeting_guard


def test_external_guard_honors_shared_database_budget_and_cleans_up(monkeypatch):
    config = Config(meetings_enabled=True, db_pool_size=1, db_max_overflow=0, db_pool_timeout=3)
    monkeypatch.setattr(meeting_guard.Config, "load", lambda: config)
    store = MagicMock()
    factory = MagicMock(return_value=store)
    identity = MagicMock()
    monkeypatch.setattr(meeting_guard, "Store", factory)
    monkeypatch.setattr(meeting_guard, "Identity", lambda _: identity)
    calls = []

    class Leases:
        def __init__(self, value):
            assert value is store

        async def run(self, value, auth, *, role):
            calls.append((value, auth, role))

    monkeypatch.setattr(meeting_guard, "MeetingLeases", Leases)
    meeting_guard.main()
    factory.assert_called_once_with(
        config.database, config.encryption_key, pool_size=1, max_overflow=0, pool_timeout=3
    )
    assert calls == [(config, identity, "external")]
    identity.close.assert_called_once()
    store.engine.dispose.assert_called_once()


def test_guard_refuses_disabled_meetings_before_connecting(monkeypatch):
    monkeypatch.setattr(meeting_guard.Config, "load", lambda: Config())
    factory = MagicMock()
    monkeypatch.setattr(meeting_guard, "Store", factory)
    with pytest.raises(SystemExit, match="Enable meeting"):
        meeting_guard.main()
    factory.assert_not_called()


def test_guard_startup_errors_do_not_print_private_configuration(monkeypatch, capsys):
    def fail():
        raise ValueError("postgresql://private-password@private-host")

    monkeypatch.setattr(meeting_guard.Config, "load", fail)
    with pytest.raises(SystemExit) as error:
        meeting_guard.main()
    assert "private-password" not in str(error.value)
    assert "private-password" not in "".join(capsys.readouterr())


def test_guard_disposes_database_if_identity_initialization_fails(monkeypatch):
    monkeypatch.setattr(meeting_guard.Config, "load", lambda: Config(meetings_enabled=True))
    store = MagicMock()
    monkeypatch.setattr(meeting_guard, "Store", lambda *args, **kwargs: store)

    def fail(_):
        raise RuntimeError("private-provider-secret")

    monkeypatch.setattr(meeting_guard, "Identity", fail)
    with pytest.raises(SystemExit, match="credentials were not printed"):
        meeting_guard.main()
    store.engine.dispose.assert_called_once()
