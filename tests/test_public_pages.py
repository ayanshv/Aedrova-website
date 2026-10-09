"""Regression checks for public navigation, templates and safe preview gates."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config

PAGES = [
    "/",
    "/onboarding",
    "/waitlist",
    "/plans",
    "/account",
    "/welcome",
    "/download",
    "/enterprise",
    "/privacy",
    "/terms",
]


class Document(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.nodes = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


@pytest.fixture
def client(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'site.sqlite3'}"))
    with TestClient(app) as instance:
        yield instance
    app.state.store.engine.dispose()


@pytest.mark.parametrize("path", PAGES)
def test_public_pages_and_local_assets_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    document = Document(response.text)
    assert sum(tag == "h1" for tag, _ in document.nodes) == 1
    assert any(tag == "main" and attrs.get("id") == "main" for tag, attrs in document.nodes)
    for tag, attrs in document.nodes:
        if tag in {"img", "script", "link"}:
            target = attrs.get("src") or attrs.get("href", "")
            if target.startswith("/static/"):
                assert client.get(target).status_code == 200, target


@pytest.mark.parametrize("path", PAGES)
def test_public_navigation_keeps_destinations_and_anchors(client, path):
    response = client.get(path)
    document = Document(response.text)
    for tag, attrs in document.nodes:
        if tag != "a":
            continue
        target = urlsplit(attrs.get("href", ""))
        if target.scheme or target.path.startswith("/auth/") or target.path.startswith("/api/"):
            continue
        destination = client.get(target.path or path)
        assert destination.status_code == 200, target.geturl()
        if target.fragment:
            ids = {a.get("id") for _, a in Document(destination.text).nodes}
            assert target.fragment in ids, target.geturl()


def test_external_media_cannot_expand_script_or_connection_policy(client):
    policy = client.get("/").headers["content-security-policy"]
    assert "media-src 'self';" in policy
    assert "script-src 'self';" in policy
    assert "connect-src 'self';" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy
    assert "font-src 'self'" in policy


def test_plan_links_keep_approved_prices_and_billing_choice(client):
    response = client.get("/plans")
    assert "$200" in response.text and "$10" in response.text
    targets = {attrs.get("href") for tag, attrs in Document(response.text).nodes if tag == "a"}
    assert "/account?plan=annual" in targets
    assert "/account?plan=monthly" in targets
    assert "/enterprise" in targets
    assert "charged each year until cancelled" in response.text
    assert "charged each month until cancelled" in response.text


def test_signed_out_account_keeps_google_entry(client):
    response = client.get("/account?plan=monthly")
    assert "Continue with Google" in response.text
    assert 'href="/auth/google?plan=monthly"' in response.text
    assert 'id="checkout"' not in response.text


def test_unreleased_preview_cannot_download_or_charge(client):
    response = client.get("/download")
    assert 'href="/api/download"' not in response.text
    assert client.get("/api/download").status_code != 200
    response = client.post(
        "/api/checkout",
        json={"workspace": "test-workspace", "plan": "monthly", "request_id": "test-preview-00001"},
    )
    assert response.status_code == 403


def test_form_inputs_retain_visible_labels(client):
    for path in ["/enterprise", "/onboarding"]:
        nodes = Document(client.get(path).text).nodes
        labels = {attrs.get("for") for tag, attrs in nodes if tag == "label"}
        for tag, attrs in nodes:
            if tag in {"input", "textarea", "select"}:
                assert attrs.get("id") in labels


def test_signed_in_account_retains_all_workspace_and_billing_controls(client):
    client.app.state.store.session(
        "local-test-session", {"access_token": "test-only", "csrf": "test"}
    )
    client.cookies.set("aedrova_session", "local-test-session")
    response = client.get("/account")
    controls = {attrs.get("id") for _, attrs in Document(response.text).nodes}
    assert {
        "workspace",
        "new-workspace",
        "create-workspace",
        "checkout",
        "portal",
        "logout",
    } <= controls
    assert 'href="/download"' in response.text


def test_hero_keeps_local_scenery_when_remote_video_is_unavailable(client):
    nodes = Document(client.get("/").text).nodes
    posters = [
        attrs
        for tag, attrs in nodes
        if tag == "img" and "scene-poster" in attrs.get("class", "").split()
    ]
    videos = [attrs for tag, attrs in nodes if tag == "video"]
    assert len(posters) == len(videos) == 1
    assert len({poster["src"] for poster in posters}) == 1
    assert videos[0]["data-src"] == "/static/overhead-pedestrians.mp4"
    assert not any("data-scene" in attrs for _, attrs in nodes)
    for poster, video in zip(posters, videos, strict=True):
        assert video["poster"] == poster["src"]
        response = client.get(poster["src"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content.startswith(b"\xff\xd8")


def test_entry_buttons_navigate_without_javascript_and_assets_are_versioned(client):
    nodes = Document(client.get("/").text).nodes
    entry_links = [
        attrs for tag, attrs in nodes if tag == "a" and attrs.get("href") == "/onboarding"
    ]
    assert len(entry_links) >= 3
    assert client.get("/onboarding").status_code == 200
    assets = [
        attrs.get("src") or attrs.get("href", "")
        for tag, attrs in nodes
        if tag in {"script", "link"}
    ]
    assert any(asset.startswith("/static/site.js?v=") for asset in assets)
    assert any(asset.startswith("/static/site.css?v=") for asset in assets)


def test_introduction_has_six_optional_questions_and_personal_goal(client):
    document = Document(client.get("/onboarding").text)
    steps = [attrs for tag, attrs in document.nodes if tag == "fieldset"]
    assert [attrs["data-step"] for attrs in steps] == [str(i) for i in range(6)]
    assert "hidden" not in steps[0]
    assert all("hidden" in step for step in steps[1:])
    goals = [attrs for tag, attrs in document.nodes if tag == "textarea"]
    assert goals[0]["id"] == "first-win"
    assert goals[0]["maxlength"] == "280"
    assert all(
        "required" not in attrs
        for tag, attrs in document.nodes
        if tag in {"input", "textarea", "select"}
    )
    acknowledgments = [attrs for tag, attrs in document.nodes if "data-response" in attrs]
    assert len(acknowledgments) == 12


def test_city_video_supports_browser_range_loading(client):
    response = client.get("/static/overhead-pedestrians.mp4", headers={"Range": "bytes=0-1023"})
    assert response.status_code == 206
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-range"].startswith("bytes 0-1023/")
    assert len(response.content) == 1024
    assert b"ftyp" in response.content[:32]


def test_meeting_showcase_uses_real_captures_and_honest_availability(client):
    page = client.get("/").text
    assert 'id="meetings"' in page
    assert "Implemented in the desktop preview" in page
    assert "Public rollout pending" in page
    assert "audio transcription requires current consent from every participant" in page
    assert "AI reuse is a separate choice" in page
    assert "does not give the agent automatic visual understanding" in page
    for asset in (
        "meetings-light.png",
        "meetings-dark.png",
        "devices-light.png",
        "devices-dark.png",
    ):
        assert asset in page
        response = client.get("/static/" + asset)
        assert response.status_code == 200
        assert response.content.startswith(b"\x89PNG")
    assert "Planned video calls" not in page


def test_meeting_links_and_plan_disclosures_preserve_release_gate(client):
    assert "/#meetings" in client.get("/").text
    assert "public availability and any meeting limits will be confirmed" in (
        client.get("/plans").text
    )
