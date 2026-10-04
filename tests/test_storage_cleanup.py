import json
from uuid import uuid4

import httpx
import pytest

from aedrova_site.storage_cleanup import StorageCleanup, headers, main

ORIGIN = "https://cpelagtufyocepnqcqqd.supabase.co"
KEY = "sb_secret_" + "synthetic" * 5


def row():
    return {"object_path": "/".join(str(uuid4()) for _ in range(3)), "lease": str(uuid4())}


def worker(rows, delete_status=200, finish=True):
    calls = []

    def provider(request):
        calls.append(request)
        if request.url.path.endswith("claim_storage_cleanup"):
            return httpx.Response(200, json=rows)
        if request.method == "DELETE":
            return httpx.Response(delete_status, json=[])
        return httpx.Response(200, json=finish)

    return StorageCleanup(ORIGIN, KEY, transport=httpx.MockTransport(provider)), calls


def test_claim_delete_then_independent_ack():
    item = row()
    instance, calls = worker([item])
    try:
        assert instance.run() == 1
        assert [r.method for r in calls] == ["POST", "DELETE", "POST"]
        assert json.loads(calls[1].content) == {"prefixes": [item["object_path"]]}
        assert calls[1].url.path == "/storage/v1/object/aedrova-files"
        assert "authorization" not in calls[0].headers
        assert calls[0].headers["apikey"] == KEY
    finally:
        instance.close()


@pytest.mark.parametrize(
    "rows",
    [
        [row(), {"object_path": "../other-bucket", "lease": str(uuid4())}],
        [row()] * 11,
        {"unexpected": True},
    ],
)
def test_validate_entire_batch_before_deleting(rows):
    instance, calls = worker(rows)
    try:
        with pytest.raises(RuntimeError):
            instance.run()
        assert len(calls) == 1
    finally:
        instance.close()


@pytest.mark.parametrize("status", [401, 429, 500, 302])
def test_failed_or_redirected_deletion_never_acknowledged(status):
    instance, calls = worker([row()], delete_status=status)
    try:
        with pytest.raises(RuntimeError):
            instance.run()
        assert len(calls) == 2
    finally:
        instance.close()


def test_lost_lease_keeps_accounting():
    instance, _ = worker([row()], finish=False)
    try:
        with pytest.raises(RuntimeError, match="lease"):
            instance.run()
    finally:
        instance.close()


def test_disabled_worker_needs_no_credentials(monkeypatch, capsys):
    monkeypatch.delenv("AEDROVA_STORAGE_CLEANUP_ENABLED", raising=False)
    main()
    assert capsys.readouterr().out == "Storage cleanup disabled.\n"


@pytest.mark.parametrize(
    "origin",
    [
        "http://cpelagtufyocepnqcqqd.supabase.co",
        "https://evil.test",
        ORIGIN + "/",
        ORIGIN + "@evil.test",
    ],
)
def test_credentials_never_sent_to_other_origin(origin):
    with pytest.raises(ValueError):
        StorageCleanup(origin, KEY)


def test_public_key_rejected_without_disclosure():
    secret = "sb_publishable_" + "synthetic" * 5
    with pytest.raises(ValueError) as error:
        headers(secret)
    assert secret not in str(error.value)
