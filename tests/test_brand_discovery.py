"""Favicon discovery is public, while unrelated assets/private pages stay noindex."""

from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.discovery import CANONICAL, PUBLIC_ICONS


def test_favicons_crawlable_and_team_indexable(tmp_path):
    app = create_app(Config(origin=CANONICAL, database=f"sqlite:///{tmp_path / 'brand.db'}"))
    with TestClient(app) as client:
        for path in PUBLIC_ICONS:
            for method in ("GET", "HEAD"):
                response = client.request(method, path, headers={"User-Agent": "Googlebot-Image"})
                assert response.status_code == 200
                assert "noindex" not in response.headers.get("x-robots-tag", "")
                assert response.headers["content-type"].startswith("image/")
                if method == "HEAD":
                    assert not response.content
        for path in ("/account", "/static/site.js", "/favicon.ico/private"):
            assert client.get(path).headers["x-robots-tag"] == "noindex"
        assert "noindex" not in client.get("/team").headers.get("x-robots-tag", "")
        assert "https://aedrova.com/team" in client.get("/sitemap.xml").text
        home = client.get("/").text
        assert 'href="/favicon.png"' in home and 'href="/favicon.ico"' in home
    app.state.store.engine.dispose()


def test_staging_favicons_still_noindex(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'staging.db'}"))
    with TestClient(app) as client:
        assert client.get("/favicon.png").headers["x-robots-tag"] == "noindex"
    app.state.store.engine.dispose()
