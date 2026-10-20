import csv
import hashlib
import json
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.discovery import robots
from scripts.export_waitlist import export


@pytest.fixture
def public_client(tmp_path):
    app = create_app(
        Config(
            origin="https://aedrova.com",
            database=f"sqlite:///{tmp_path / 'discovery.db'}",
            waitlist_only=True,
        )
    )
    with TestClient(app) as client:
        yield client
    app.state.store.engine.dispose()


class Schema(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.reading = False
        self.parts = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.reading = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.reading = False

    def handle_data(self, text):
        if self.reading:
            self.parts.append(text)


def test_public_crawl_rules_allow_discovery_not_private_routes(public_client):
    response = public_client.get("/robots.txt")
    assert "x-robots-tag" not in response.headers
    assert "x-robots-tag" not in public_client.get("/sitemap.xml").headers
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    for agent in [
        "Googlebot",
        "bingbot",
        "OAI-SearchBot",
        "Claude-SearchBot",
        "ChatGPT-User",
        "Claude-User",
        "Google-Extended",
    ]:
        assert parser.can_fetch(agent, "https://aedrova.com/product")
        for path in [
            "/api/session",
            "/account",
            "/auth/callback?code=secret",
            "/dots/authorize/token",
            "/onboarding",
        ]:
            assert not parser.can_fetch(agent, "https://aedrova.com" + path)
    for agent in ["GPTBot", "ClaudeBot"]:
        assert not parser.can_fetch(agent, "https://aedrova.com/product")
    assert parser.site_maps() == ["https://aedrova.com/sitemap.xml"]
    root = ElementTree.fromstring(public_client.get("/sitemap.xml").text)
    urls = [element.text for element in root.findall("{*}url/{*}loc")]
    assert "https://aedrova.com/product" in urls
    assert all("?" not in url and "onboarding" not in url and "/account" not in url for url in urls)
    for url in urls:
        assert public_client.get(url).status_code == 200


def test_schema_is_factual_and_canonical_has_no_session_query(public_client):
    page = public_client.get("/product?token=never-publish-this")
    graph = json.loads("".join(Schema(page.text).parts))["@graph"]
    assert {item["@type"] for item in graph} == {"Organization", "WebSite", "SoftwareApplication"}
    assert not any(
        "offers" in item or "aggregateRating" in item or "downloadUrl" in item for item in graph
    )
    assert 'href="https://aedrova.com/product"' in page.text
    assert "never-publish-this" not in page.text
    assert 'name="robots" content="index, follow' in page.text
    assert 'href="/onboarding"' in public_client.get("/").text
    assert public_client.get("/onboarding").headers["x-robots-tag"] == "noindex"
    assert public_client.get("/api/session").status_code in {401, 403}


def test_staging_and_preview_do_not_advertise_indexing(tmp_path):
    config = Config(
        origin="https://preview.example", database=f"sqlite:///{tmp_path / 'preview.db'}"
    )
    app = create_app(config)
    with TestClient(app) as client:
        assert client.get("/robots.txt").text == "User-agent: *\nDisallow: /\n"
        assert client.get("/product").headers["x-robots-tag"] == "noindex"
        assert "SoftwareApplication" not in client.get("/product").text
        assert not ElementTree.fromstring(client.get("/sitemap.xml").text).findall("{*}url")
    app.state.store.engine.dispose()
    config.origin = "https://aedrova.com"
    config.deployment_environment = "staging"
    assert robots(config) == "User-agent: *\nDisallow: /\n"


def test_referral_is_optional_validated_encrypted_and_exported(public_client, tmp_path):
    headers = {"origin": "https://aedrova.com"}
    payload = {
        "email": "referral@example.com",
        "consent": True,
        "age_confirmed": True,
        "referral_source": "chatgpt",
        "referral_detail": "=danger()",
    }
    assert public_client.post("/api/waitlist", json=payload, headers=headers).status_code == 200
    store = public_client.app.state.store
    token = "waitlist:" + hashlib.sha256(b"referral@example.com").hexdigest()
    assert store.session(token)["referral_source"] == "chatgpt"
    path = tmp_path / "private.csv"
    assert export(store, path) == 1
    with path.open() as file:
        row = list(csv.DictReader(file))[0]
    assert row["referral_source"] == "chatgpt"
    assert row["referral_detail"] == "'=danger()"
    for invalid in [{"referral_source": "unknown"}, {"referral_detail": "a" * 161}]:
        assert (
            public_client.post(
                "/api/waitlist", json={**payload, **invalid}, headers=headers
            ).status_code
            == 422
        )
    assert (
        public_client.post(
            "/api/waitlist", json={**payload, "referral_source": "prefer_not"}, headers=headers
        ).status_code
        == 200
    )
    assert store.session(token)["referral_detail"] == ""
    assert (
        public_client.post(
            "/api/waitlist",
            json={"email": "optional@example.com", "consent": True, "age_confirmed": True},
            headers=headers,
        ).status_code
        == 200
    )
    page = public_client.get("/onboarding").text
    for label in ["ChatGPT", "Claude", "Gemini", "Perplexity", "Prefer not to say"]:
        assert label in page
    assert 'id="wizard-next"' in page
    assert public_client.get("/account", follow_redirects=False).headers["location"] == "/waitlist"
