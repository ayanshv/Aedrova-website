"""Contract and isolation checks with fixture HTTP; never publish to a live account."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from test_dots import system as dot_system  # noqa: F401

from aedrova_site.bud_connections import BudConnections
from aedrova_site.bud_oauth import BudOAuth
from aedrova_site.social.providers import BufferAdapter
from aedrova_site.social.service import (
    ChannelSelection,
    Draft,
    PostAction,
    SocialService,
    media_url,
)
from aedrova_site.store import Denied


@pytest.fixture
def social(request):
    dots, dot, user = request.getfixturevalue("dot_system")
    dots.config.origin = "https://staging.example.com"
    dots.config.social_publishing_enabled = True
    dots.config.buffer_bud_client_id = "fixture-app"
    dots.config.buffer_bud_client_secret = "fixture-client-secret"
    seen, options = [], {}

    def transport(request):
        seen.append(request)
        if request.url.host == "auth.buffer.com":
            if options.get("refresh_timeout"):
                raise httpx.ReadTimeout("fixture timeout")
            return httpx.Response(
                200,
                json=dict(
                    access_token="renewed-access-fixture",
                    refresh_token="rotated-refresh-fixture",
                    token_type="bearer",
                    expires_in=3600,
                    scope=BufferAdapter.SCOPES,
                ),
            )
        payload = json.loads(request.content)
        query = payload["query"]
        if "organizations" in query:
            return httpx.Response(
                200,
                json={
                    "data": {"account": {"organizations": [{"id": "org-1", "name": "Test team"}]}}
                },
            )
        if "channels(" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "channels": [
                            dict(
                                id="channel-1",
                                name="Test profile",
                                service="linkedin",
                                organizationId="org-1",
                                allowedActions=["scheduleUpdates"],
                                isDisconnected=options.get("disconnected", False),
                                isLocked=False,
                                isQueuePaused=options.get("paused", False),
                            )
                        ]
                    }
                },
            )
        if "createPost" in query:
            if options.get("publish_timeout"):
                raise httpx.ReadTimeout("fixture timeout")
            if options.get("rate_limit"):
                return httpx.Response(429, headers={"Retry-After": "60"})
            return httpx.Response(
                200,
                json={
                    "data": {
                        "createPost": {
                            "post": {
                                "id": "provider-post-1",
                                "channelId": "channel-1",
                                "status": "buffer",
                                "dueAt": payload["variables"]["input"].get("dueAt"),
                            }
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "post": {"id": "provider-post-1", "channelId": "channel-1", "status": "sent"}
                }
            },
        )

    transport = httpx.MockTransport(transport)
    connections = BudConnections(dots, transport=transport)
    oauth = BudOAuth(connections, transport=transport)
    connections.oauth = oauth
    service = SocialService(connections, adapter=BufferAdapter(transport=transport))
    grant = connections.connect(
        "session",
        dot["workspace_id"],
        dot["id"],
        "buffer",
        "org-1",
        "initial-access-fixture",
        24,
        oauth=dict(
            kind="oauth",
            access="initial-access-fixture",
            refresh="initial-refresh-fixture",
            token_expires=int(time.time()) + 3600,
        ),
    )
    yield service, dot, user, grant["id"], seen, options
    service.close()
    connections.close()


def select(social):
    service, dot, _, connection, _, _ = social
    service.select(
        "session",
        ChannelSelection(
            workspace=dot["workspace_id"],
            dot=dot["id"],
            connection=connection,
            channels=["channel-1"],
        ),
    )


def draft(social, **changes):
    service, dot, _, connection, _, _ = social
    value = dict(
        id=uuid4(),
        workspace=dot["workspace_id"],
        dot=dot["id"],
        connection=connection,
        channel="channel-1",
        text="Our test team's reviewed draft.",
        action="publish",
    )
    return service.save("session", Draft(**(value | changes)))


def action(social, row):
    _, dot, _, _, _, _ = social
    return PostAction(
        workspace=dot["workspace_id"], dot=dot["id"], id=row["id"], revision=row["revision"]
    )


def writes(social):
    return [
        r
        for r in social[4]
        if r.url.host == "api.buffer.com" and "createPost" in json.loads(r.content)["query"]
    ]


def test_oauth_pkce_state_and_minimal_scopes(social):
    service, dot, user, _, _, _ = social
    oauth = service.connections.oauth
    started = oauth.start("session", dot["workspace_id"], dot["id"], "buffer", "", 24)
    with pytest.raises(Denied):
        oauth.authorize(started["state"], str(uuid4()))
    target, payload = oauth.authorize(started["state"], user)
    params = parse_qs(urlsplit(target).query)
    assert params["code_challenge_method"] == ["S256"]
    assert set(params["scope"][0].split()) == set(BufferAdapter.SCOPES.split())
    assert "account:write" not in target
    with pytest.raises(Denied):
        oauth.callback("buffer", started["state"], "wrong-proof", "fixture-code")
    result = oauth.callback("buffer", started["state"], payload["proof"], "fixture-code")
    assert result["status"] == "choose_resource"
    assert oauth.status("session", started["state"])["resources"] == [
        {"id": "org-1", "name": "Test team"}
    ]


def test_selection_required_and_post_approval_is_exact(social):
    service = social[0]
    with pytest.raises(Denied, match="Select"):
        draft(social)
    select(social)
    row = draft(social)
    with pytest.raises(Denied, match="Approve"):
        service.dispatch("session", action(social, row))
    service.decide("session", action(social, row), approve=True)
    edited = draft(social, id=row["id"], revision=1, text="An edited draft.")
    assert edited["state"] == "draft" and edited["revision"] == 2
    with pytest.raises(Denied):
        service.dispatch("session", action(social, edited))
    assert not writes(social)


def test_scheduling_approval_status_and_retries(social):
    service = social[0]
    select(social)
    row = draft(social, action="schedule", due_at=datetime.now(UTC) + timedelta(hours=2))
    service.decide("session", action(social, row), approve=True)
    result = service.dispatch("session", action(social, row))
    assert result["state"] == "submitted" and result["provider_status"] == "buffer"
    assert service.dispatch("session", action(social, row))["id"] == row["id"]
    assert len(writes(social)) == 1
    sent = json.loads(writes(social)[0].content)["variables"]["input"]
    assert sent["mode"] == "customScheduled" and sent["dueAt"]
    assert sent["assets"] == [] and sent["needsApproval"] is False
    assert service.status("session", action(social, row))["provider_status"] == "sent"
    with pytest.raises(Denied):
        draft(social, id=row["id"], revision=1, text="Change a scheduled post")


def test_timeout_does_not_republish_or_allow_reapproval(social):
    service = social[0]
    select(social)
    row = draft(social)
    service.decide("session", action(social, row), approve=True)
    social[5]["publish_timeout"] = True
    assert service.dispatch("session", action(social, row))["state"] == "unknown"
    assert service.dispatch("session", action(social, row))["state"] == "unknown"
    with pytest.raises(Denied):
        service.decide("session", action(social, row), approve=True)
    assert len(writes(social)) == 1


def test_concurrent_dispatch_only_one_external_write(social):
    service = social[0]
    select(social)
    row = draft(social)
    service.decide("session", action(social, row), approve=True)

    def attempt(_):
        try:
            return service.dispatch("session", action(social, row))["state"]
        except Denied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert "submitted" in results
    assert len(writes(social)) == 1


def test_reselection_and_revocation_cancel_authority(social):
    service, dot, _, connection, _, _ = social
    select(social)
    row = draft(social)
    service.decide("session", action(social, row), approve=True)
    select(social)
    with pytest.raises(Denied):
        service.dispatch("session", action(social, row))
    service.decide("session", action(social, row), approve=True)
    service.connections.disconnect("session", dot["workspace_id"], dot["id"], connection)
    with pytest.raises(Denied):
        service.dispatch("session", action(social, row))
    assert not writes(social)


def test_drafts_are_encrypted_and_foreign_users_denied(social):
    service, dot, _, _, _, _ = social
    select(social)
    row = draft(social)
    with service.store.tx() as db:
        assert "reviewed draft" not in str(db.execute(text("SELECT body FROM social_posts")).all())
    service.dots.identity.require.return_value = {"id": str(uuid4())}
    assert service.list_posts("foreign", dot["workspace_id"], dot["id"])["posts"] == []
    for op in (
        lambda: service.decide("foreign", action(social, row), approve=True),
        lambda: service.dispatch("foreign", action(social, row)),
        lambda: service.status("foreign", action(social, row)),
    ):
        with pytest.raises(Denied):
            op()


def test_single_use_refresh_never_replayed_after_timeout(social):
    service, dot, user, _, seen, options = social
    grant = service.connections.rows(dot, user)[0]
    options["refresh_timeout"] = True
    for _ in range(2):
        with pytest.raises(Denied):
            service.connections.access(grant, force=True)
    assert len([r for r in seen if r.url.host == "auth.buffer.com"]) == 1
    envelope = json.loads(
        service.store.cipher.decrypt(service.connections.rows(dot, user)[0]["secret"].encode())
    )
    assert envelope["refresh"] == ""


def test_rate_limit_and_disconnected_channel_do_not_claim_success(social):
    service = social[0]
    select(social)
    row = draft(social)
    service.decide("session", action(social, row), approve=True)
    social[5]["disconnected"] = True
    with pytest.raises(Denied):
        service.dispatch("session", action(social, row))
    assert not writes(social)
    social[5]["disconnected"] = False
    social[5]["rate_limit"] = True
    assert service.dispatch("session", action(social, row))["state"] == "rejected"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.png",
        "https://127.0.0.1/a",
        "https://localhost/a",
        "https://example.com/a?token=private",
        "https://user:pass@example.com/a",
        "https://10.0.0.1/a",
    ],
)
def test_private_or_expiring_media_not_accepted(url):
    with pytest.raises(Denied):
        media_url(url)


def test_analytics_never_substitutes_personal_keys(social):
    with pytest.raises(Denied, match="not available"):
        social[0].adapters["buffer"].get_post_analytics("fixture-access", "provider-post-1")
    service, dot, _, _, _, _ = social
    with pytest.raises(Denied, match="personal API keys"):
        service.connections.connect(
            "session",
            dot["workspace_id"],
            dot["id"],
            "buffer",
            "org-1",
            "personal-token-fixture",
            24,
        )


def test_refresh_rotates_once_and_uses_new_access(social):
    service, dot, user, _, seen, _ = social
    grant = service.connections.rows(dot, user)[0]
    _, token, _ = service.connections.access(grant, force=True)
    assert token == "renewed-access-fixture"
    envelope = json.loads(
        service.store.cipher.decrypt(service.connections.rows(dot, user)[0]["secret"].encode())
    )
    assert envelope["refresh"] == "rotated-refresh-fixture"
    service.connections.access(grant)
    assert len([r for r in seen if r.url.host == "auth.buffer.com"]) == 1


def test_revocation_during_refresh_cannot_resurrect_connection(social):
    service, dot, user, connection, _, _ = social
    grant = service.connections.rows(dot, user)[0]
    exchange = service.connections.oauth.token

    def revoke_then_return(*args, **kwargs):
        result = exchange(*args, **kwargs)
        service.connections.disconnect("session", dot["workspace_id"], dot["id"], connection)
        return result

    service.connections.oauth.token = revoke_then_return
    with pytest.raises(Denied):
        service.connections.access(grant, force=True)
    assert not service.connections.rows(dot, user)


@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.example.com:bad/test.jpg",
        "https://cdn.example.com/\nphoto.jpg",
        "https://[broken/a.jpg",
    ],
)
def test_malformed_media_urls_are_rejected(url):
    with pytest.raises(Denied):
        media_url(url)


@pytest.mark.parametrize(
    "data",
    [
        {"account": None},
        {"account": {"organizations": [None]}},
        {"account": {"organizations": [{"id": {}, "name": "Bad"}]}},
    ],
)
def test_malformed_organizations_fail_closed(data):
    adapter = BufferAdapter(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": data}))
    )
    try:
        with pytest.raises(Denied):
            adapter.organizations("fixture-access")
    finally:
        adapter.close()


def test_full_oauth_selection_and_callback_replay(social):
    service, dot, user, _, _, _ = social
    oauth = service.connections.oauth
    started = oauth.start("session", dot["workspace_id"], dot["id"], "buffer", "", 24)
    _, payload = oauth.authorize(started["state"], user)
    oauth.callback("buffer", started["state"], payload["proof"], "fixture-code")
    with pytest.raises(Denied):
        oauth.select("session", started["state"], "foreign-org")
    result = oauth.select("session", started["state"], "org-1")
    assert result["id"]
    with pytest.raises(Denied):
        oauth.callback("buffer", started["state"], payload["proof"], "fixture-code")
    with pytest.raises(Denied):
        oauth.select("session", started["state"], "org-1")


def test_feature_flag_blocks_existing_grant_dispatch(social):
    service = social[0]
    select(social)
    row = draft(social)
    service.decide("session", action(social, row), approve=True)
    service.dots.config.social_publishing_enabled = False
    with pytest.raises(Denied):
        service.dispatch("session", action(social, row))
    assert not writes(social)


@pytest.mark.parametrize("kind,expected", [("image", "post"), ("video", "reel")])
def test_instagram_has_required_format_and_feed_policy(kind, expected):
    seen = []

    def respond(request):
        seen.append(json.loads(request.content)["variables"]["input"])
        return httpx.Response(
            200,
            json={
                "data": {
                    "createPost": {
                        "post": {"id": "post-1", "channelId": "channel-1", "status": "buffer"}
                    }
                }
            },
        )

    adapter = BufferAdapter(transport=httpx.MockTransport(respond))
    try:
        adapter.schedule_post(
            "fixture-token",
            dict(
                channel="channel-1",
                platform="instagram",
                text="Reviewed",
                assets=[dict(kind=kind, url="https://cdn.example.com/media")],
                due_at="2026-11-30T09:11:54+00:00",
            ),
        )
        assert seen[0]["metadata"]["instagram"] == dict(type=expected, shouldShareToFeed=True)
    finally:
        adapter.close()


@pytest.mark.parametrize("status", ["scheduled", "published", "failed"])
def test_current_buffer_status_vocabulary_is_preserved(status):
    adapter = BufferAdapter(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": {"post": {"id": "post-1", "channelId": "channel-1", "status": status}}
                },
            )
        )
    )
    try:
        assert adapter.get_post_status("fixture-token", "post-1")["status"] == status
    finally:
        adapter.close()
