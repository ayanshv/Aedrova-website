import asyncio
import time

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from aedrova_site.meeting_leases import MeetingLeases
from aedrova_site.store import Denied, Store


@pytest.fixture
def leases(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/leases.sqlite3", Fernet.generate_key().decode())
    value = MeetingLeases(store)
    yield value
    store.engine.dispose()


def scope():
    return {"room_name": "aedrova-w-c-m", "user_id": "u", "meeting_id": "m"}


class Identity:
    snapshot = {"ended": False, "participants": [{"user_id": "u"}]}
    error = False

    def request(self, path, token, *, method, data):
        assert path == "/rest/v1/rpc/meeting_consent_snapshot"
        assert token == "private-user-token" and data == {"p_meeting": "m"}
        if self.error:
            raise Denied("Membership revoked")
        return self.snapshot


class Media:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.room = self

    async def remove_participant(self, request):
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("Offline")


def test_encrypted_lease_and_no_duplicate_connection(leases):
    leases.put(scope(), "private-user-token")
    assert "private-user-token" not in str(leases.rows())
    with pytest.raises(Denied):
        leases.put(scope(), "private-user-token")


def test_valid_participant_is_retained(leases):
    leases.put(scope(), "private-user-token")
    media = Media()
    asyncio.run(leases.sweep(Identity(), media))
    assert not media.calls and leases.ready()


@pytest.mark.parametrize("failure", ["membership", "ended", "roster", "expired", "logout"])
def test_revocation_removes_real_media_identity_with_explicit_cutoff(leases, failure):
    leases.put(scope(), "private-user-token")
    identity = Identity()
    if failure == "membership":
        identity.error = True
    elif failure == "ended":
        identity.snapshot = {"ended": True, "participants": [{"user_id": "u"}]}
    elif failure == "roster":
        identity.snapshot = {"ended": False, "participants": []}
    elif failure == "logout":
        leases.revoke("m", "u")
    else:
        with leases.store.tx() as db:
            db.execute(text("UPDATE meeting_leases SET expires=0"))
    media = Media()
    asyncio.run(leases.sweep(identity, media))
    assert len(media.calls) == 1
    assert media.calls[0].room == "aedrova-w-c-m" and media.calls[0].identity == "u"
    assert media.calls[0].revoke_token_ts >= int(time.time())
    assert not leases.rows()
    with leases.store.tx() as db:
        assert db.execute(text("SELECT token FROM meeting_leases")).scalar() == ""


def test_failed_removal_is_retried_and_blocks_new_join(leases):
    leases.put(scope(), "private-user-token")
    leases.revoke("m", "u")
    media = Media(fail=True)
    asyncio.run(leases.sweep(Identity(), media))
    assert leases.rows()[0]["state"] == "revoking" and not leases.ready()
    media.fail = False
    asyncio.run(leases.sweep(Identity(), media))
    assert len(media.calls) == 2 and not leases.rows() and leases.ready()


def test_expired_or_revoking_lease_cannot_be_renewed(leases):
    leases.put(scope(), "private-user-token")
    leases.pulse("m", "u", "private-user-token")
    with pytest.raises(Denied):
        leases.pulse("m", "other", "private-user-token")
    leases.revoke("m", "u")
    with pytest.raises(Denied):
        leases.pulse("m", "u", "private-user-token")


def test_leases_survive_server_restart_and_key_loss_fails_closed(leases):
    leases.put(scope(), "private-user-token")
    leases.store.cipher = Fernet(Fernet.generate_key())
    restarted = MeetingLeases(leases.store)
    media = Media()
    asyncio.run(restarted.sweep(Identity(), media))
    assert media.calls and not restarted.rows()


def test_stale_scan_cannot_revoke_a_renewed_lease(leases):
    leases.put(scope(), "private-user-token")
    row = leases.rows()[0]
    with leases.store.tx() as db:
        db.execute(text("UPDATE meeting_leases SET expires=expires+1"))
    assert leases.revoke_current(row) is False
    assert leases.rows()[0]["state"] == "active"


def test_guard_scans_multiple_bounded_batches_with_bounded_fanout(leases):
    for index in range(205):
        leases.put(
            {"room_name": f"room-{index:04}", "user_id": "u", "meeting_id": "m"},
            "private-user-token",
        )
    assert len(leases.rows()) == 100
    calls, active, maximum = [], 0, 0

    async def check(row, *_):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        calls.append(row["room"])
        await asyncio.sleep(0.001)
        active -= 1
        return True

    leases.check = check
    asyncio.run(leases.sweep(Identity(), Media()))
    assert len(set(calls)) == 205 and maximum <= 10
    assert leases.ready()
