"""Real Dot-service cache, normalization and Pulse authorization boundaries."""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_dots import authorize
from test_dots import system as dot_system

from aedrova_site.pulse import PERIODS, PulseService, github_projection
from aedrova_site.store import Denied


@pytest.fixture
def pulse_system(tmp_path):
    yield from dot_system.__wrapped__(tmp_path)


def read(pulse_system):
    service, dot, user = authorize(pulse_system)
    now = datetime.now(UTC).isoformat()
    calls = []

    def execute(token, resource, tool):
        calls.append(tool)
        records = {
            "changes": [
                {
                    "kind": "CodeChange",
                    "id": "change-1",
                    "summary": "Improve onboarding",
                    "date": now,
                }
            ],
            "issues": [
                {
                    "kind": "PullRequest",
                    "number": 4,
                    "title": "Review onboarding",
                    "updated_at": now,
                }
            ],
            "deployments": [
                {"kind": "Deployment", "id": 7, "environment": "preview", "created_at": now}
            ],
        }
        return {
            "records": records[tool],
            "untrusted": True,
            "source": "https://github.com/owner/repo",
            "coverage": "Most recent 10 records",
        }

    service.providers["github"].execute = execute
    pulse = PulseService(service)
    return pulse, dot, user, calls


def test_empty_overview_has_no_fake_metrics_or_provider_reads(pulse_system):
    service, dot, _ = pulse_system
    service.identity.request.return_value = []
    service.providers["github"].execute = MagicMock()
    assert PulseService(service).snapshot("session", dot["workspace_id"])["metrics"] == []
    service.providers["github"].execute.assert_not_called()


def test_snapshot_never_queries_providers_and_refresh_uses_same_agent_evidence(pulse_system):
    pulse, dot, user, calls = read(pulse_system)
    result = pulse.snapshot("session", dot["workspace_id"])
    assert not result["metrics"] and not calls
    result = pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    assert len(result["metrics"]) == 3 and len(result["signals"]) == 2
    assert all(m["value"] == 1 and m["change_percent"] is None for m in result["metrics"])
    assert calls == ["changes", "issues", "deployments"]
    calls.clear()
    agent = pulse.dots.execute(
        "session", dot["workspace_id"], [{"dot": dot["id"], "tool": "changes"}]
    )[0]
    assert agent["citation"] == result["metrics"][0]["citation"] and not calls
    assert agent["fetched_at"] == result["metrics"][0]["updated_at"]
    with pulse.dots.store.tx() as db:
        raw = db.execute(text("SELECT payload FROM dot_evidence_cache")).scalars().all()
    assert all(
        "Improve onboarding" not in value and "test-secret-fixture" not in value for value in raw
    )
    assert pulse.dots.grant(dot, user)


@pytest.mark.parametrize("period", list(PERIODS))
def test_time_ranges_use_observed_dates_without_inventing_comparison(period):
    now = int(time.time())

    def iso(t):
        return datetime.fromtimestamp(t, UTC).isoformat()

    evidence = dict(
        dot=str(uuid4()),
        name="GitHub",
        provider="github",
        tool="changes",
        citation="dot:fixture:changes",
        fetched_at=now,
        records=[
            {"kind": "CodeChange", "date": iso(now - 60), "summary": "Recent"},
            {"kind": "CodeChange", "date": iso(now - 400 * 86400), "summary": "Old"},
            {"kind": "CodeChange", "date": "unknown", "summary": "No date"},
        ],
    )
    metric = github_projection(evidence, period, now)
    assert metric["value"] == 1 and metric["unknown_dates"] == 1
    assert sum(metric["trend"]) == 1 and metric["change_percent"] is None


def test_stale_evidence_is_labeled_and_expiry_withholds_it(pulse_system):
    pulse, dot, _, _ = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    with pulse.dots.store.tx() as db:
        db.execute(text("UPDATE dot_grants SET synced=0"))
    assert all(m["stale"] for m in pulse.snapshot("session", dot["workspace_id"])["metrics"])
    with pulse.dots.store.tx() as db:
        db.execute(text("UPDATE dot_grants SET expires=0"))
    assert not pulse.snapshot("session", dot["workspace_id"])["metrics"]


def test_partial_failure_retains_only_authorized_evidence(pulse_system):
    pulse, dot, _, calls = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    good = pulse.dots.providers["github"].execute

    def execute(*args):
        if args[-1] == "issues":
            raise Denied("Temporary provider failure")
        return good(*args)

    pulse.dots.providers["github"].execute = execute
    result = pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    assert result["failed_tools"] == ["issues"] and len(result["metrics"]) == 3
    assert next(m for m in result["metrics"] if m["metric"] == "issues")["stale"]
    assert len(calls) == 5
    fresh = pulse.snapshot("session", dot["workspace_id"])
    assert next(m for m in fresh["metrics"] if m["metric"] == "issues")["stale"]


def test_disconnect_and_user_workspace_permissions_never_return_cached_metrics(pulse_system):
    pulse, dot, user, _ = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    pulse.dots.identity.require.return_value = {"id": str(uuid4())}
    assert not pulse.snapshot("another-user", dot["workspace_id"])["metrics"]
    pulse.dots.identity.require.return_value = {"id": user}
    pulse.dots.identity.require.side_effect = Denied("No membership")
    with pytest.raises(Denied):
        pulse.snapshot("session", str(uuid4()))
    pulse.dots.identity.require.side_effect = None
    pulse.dots.disconnect("session", dot["workspace_id"], dot["id"])
    assert not pulse.snapshot("session", dot["workspace_id"])["metrics"]
    with pulse.dots.store.tx() as db:
        assert db.execute(text("SELECT count(*) FROM dot_evidence_cache")).scalar() == 0


def test_invalid_range_never_reads_provider(pulse_system):
    pulse, dot, _, calls = read(pulse_system)
    with pytest.raises(Denied):
        pulse.refresh("session", dot["workspace_id"], dot["id"], "arbitrary")
    assert not calls


def test_grant_replacement_does_not_reuse_old_evidence(pulse_system):
    pulse, dot, _, _ = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    with pulse.dots.store.tx() as db:
        replacement = pulse.dots.store.cipher.encrypt(b"new-secret").decode()
        db.execute(text("UPDATE dot_grants SET secret=:s"), {"s": replacement})
    assert not pulse.snapshot("session", dot["workspace_id"])["metrics"]


def test_revocation_while_assembling_snapshot_withholds_response(pulse_system, monkeypatch):
    pulse, dot, _, _ = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    original = pulse.dots.cached

    def cached(*args, **kwargs):
        result = original(*args, **kwargs)
        with pulse.dots.store.tx() as db:
            db.execute(text("DELETE FROM dot_grants"))
        return result

    monkeypatch.setattr(pulse.dots, "cached", cached)
    with pytest.raises(Denied, match="access changed"):
        pulse.snapshot("session", dot["workspace_id"])


def test_cached_evidence_expires_without_provider_polling(pulse_system):
    pulse, dot, _, calls = read(pulse_system)
    pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    calls.clear()
    with pulse.dots.store.tx() as db:
        db.execute(text("UPDATE dot_evidence_cache SET expires=0"))
    assert not pulse.snapshot("session", dot["workspace_id"])["metrics"] and not calls


def test_multiple_sources_are_progressive_and_never_eagerly_refreshed(pulse_system):
    from urllib.parse import parse_qs, urlsplit

    pulse, dot, user, calls = read(pulse_system)
    second = {**dot, "id": str(uuid4()), "name": "GitHub service", "resource": "owner/service"}

    def rows(path, token, **kwargs):
        query = parse_qs(urlsplit(path).query)
        identifier = query.get("id", [None])[0]
        return [
            row.copy()
            for row in (dot, second)
            if identifier is None or identifier == "eq." + row["id"]
        ]

    pulse.dots.identity.request.side_effect = rows
    grant = pulse.dots.grant(dot, user)
    with pulse.dots.store.tx() as db:
        db.execute(
            text("""INSERT INTO dot_grants VALUES(:d,:u,:w,:v,:r,:s,:e,:a,0)"""),
            {
                "d": second["id"],
                "u": user,
                "w": dot["workspace_id"],
                "v": 1,
                "r": second["resource"],
                "s": grant["secret"],
                "e": grant["expires"],
                "a": "Connected",
            },
        )
    first = pulse.refresh("session", dot["workspace_id"], dot["id"], "7d")
    assert len(first["sources"]) == 2 and len(first["metrics"]) == 3
    assert all(m["dot"] == dot["id"] for m in first["metrics"]) and len(calls) == 3
    both = pulse.refresh("session", dot["workspace_id"], second["id"], "7d")
    assert len(both["metrics"]) == 6
    assert {m["dot"] for m in both["metrics"]} == {dot["id"], second["id"]}
    pulse.dots.disconnect("session", dot["workspace_id"], second["id"])
    assert len(pulse.snapshot("session", dot["workspace_id"])["metrics"]) == 3


def test_api_rejects_unconfigured_unauthenticated_and_extra_inputs(tmp_path):
    from fastapi.testclient import TestClient

    from aedrova_site.app import create_app
    from aedrova_site.config import Config

    app = create_app(Config(database=f"sqlite:///{tmp_path / 'api.db'}"))
    workspace = str(uuid4())
    with TestClient(app) as client:
        assert client.get("/api/pulse", params={"workspace": workspace}).status_code in (401, 403)
        headers = {"authorization": "Bearer fixture"}
        assert (
            client.get("/api/pulse", params={"workspace": workspace}, headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                "/api/pulse/refresh",
                json={"workspace": workspace, "dot": str(uuid4()), "url": "https://attacker.test"},
                headers=headers,
            ).status_code
            == 422
        )
