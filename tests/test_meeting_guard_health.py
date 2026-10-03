import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.meeting_leases import MeetingLeases
from aedrova_site.store import Denied, Store


def test_external_guard_state_is_shared_expires_and_rejects_embedded(tmp_path):
    store = Store(f'sqlite:///{tmp_path}/shared.sqlite3', Fernet.generate_key().decode())
    api = MeetingLeases(store, require_external=True)
    guard = MeetingLeases(store)
    try:
        assert not api.ready()
        guard.publish_health('embedded', True)
        api.last_success = time.monotonic()
        assert not api.ready()
        guard.publish_health('external', True)
        assert api.ready()
        restarted = MeetingLeases(store, require_external=True)
        assert restarted.ready()
        guard.publish_health('external', False)
        assert not api.ready()
        for checked in (int(time.time()) - 11, int(time.time()) + 60):
            with store.tx() as db:
                db.execute(text("UPDATE meeting_guard_health SET checked=:t,healthy=1 "
                                "WHERE role='external'"), {'t': checked})
            assert not api.ready()
    finally:
        store.engine.dispose()


def test_database_failure_is_not_a_healthy_guard(tmp_path):
    store = Store(f'sqlite:///{tmp_path}/missing.sqlite3')
    leases = MeetingLeases(store, require_external=True)
    with store.tx() as db:
        db.execute(text('DROP TABLE meeting_guard_health'))
    assert not leases.ready()
    store.engine.dispose()


def test_simultaneous_joins_only_reserve_one_lease(tmp_path):
    store = Store(f'sqlite:///{tmp_path}/race.sqlite3')
    leases = MeetingLeases(store)
    scope = {'room_name': 'room', 'user_id': 'user', 'meeting_id': 'meeting'}

    def reserve(_):
        try:
            leases.put(scope, 'token')
            return True
        except Denied:
            return False

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            assert list(executor.map(reserve, range(4))).count(True) == 1
        assert len(leases.rows()) == 1
    finally:
        store.engine.dispose()


def test_production_lifespan_does_not_start_embedded_guard(tmp_path, monkeypatch):
    # Isolate deployment policy from PostgreSQL connection setup in this unit test.
    monkeypatch.setattr(Config, 'validate', lambda self: None)
    app = create_app(Config(production=True, meetings_enabled=True,
                            database=f'sqlite:///{tmp_path}/api.sqlite3'))
    calls = []

    async def unexpected_guard(*args, **kwargs):
        calls.append(True)

    monkeypatch.setattr(app.state.meeting_leases, 'run', unexpected_guard)
    try:
        with TestClient(app) as client:
            assert client.get('/health').status_code == 200
            assert client.get('/health/meetings').status_code == 503
            app.state.meeting_leases.publish_health('external', True)
            assert client.get('/health/meetings').json() == {'status': 'ready'}
            app.state.meeting_leases.publish_health('external', False)
            assert client.get('/health/meetings').status_code == 503
        assert not calls
    finally:
        app.state.store.engine.dispose()


def test_external_runner_marks_health_on_sweep_and_shutdown(tmp_path, monkeypatch):
    store = Store(f'sqlite:///{tmp_path}/guard.sqlite3')
    leases = MeetingLeases(store)

    class Service:
        closed = False

        def __init__(self, *args):
            pass

        async def aclose(self):
            self.closed = True

    async def sweep(*args):
        leases.last_success = time.monotonic()

    async def stop(_):
        assert leases.external_ready()
        raise asyncio.CancelledError

    monkeypatch.setattr('aedrova_site.meeting_leases.api.LiveKitAPI', Service)
    monkeypatch.setattr(leases, 'sweep', sweep)
    monkeypatch.setattr('aedrova_site.meeting_leases.asyncio.sleep', stop)
    try:
        try:
            asyncio.run(leases.run(Config(), None, role='external'))
        except asyncio.CancelledError:
            pass
        assert not leases.external_ready()
    finally:
        store.engine.dispose()
