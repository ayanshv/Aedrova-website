"""Check genuine capture inventory and owner-confirmed public team details."""

import hashlib
import json
import re
import struct
from pathlib import Path

from test_public_pages import client  # noqa: F401

from aedrova_site.team import TEAM_MEMBERS

STATIC = Path(__file__).parents[1] / "aedrova_site/static"


def test_team_is_server_rendered_on_dedicated_page(client):  # noqa: F811
    for path in ("/team",):
        response = client.get(path)
        assert response.status_code == 200
        markup = response.text.split("<main", 1)[1]
        assert 'id="meet-the-team"' in markup
        for person in TEAM_MEMBERS:
            assert person["name"] in markup
            assert person["role"].replace("&", "&amp;") in markup
            assert person["bio"] in markup
        assert markup.count('class="team-member"') == 4
        assert markup.count('class="team-photo"') == 3
        assert TEAM_MEMBERS[0]["role"] == "Co-Founder & CEO / CTO"
        for person in TEAM_MEMBERS[:3]:
            assert f'src="{person["photo"]}"' in markup
            assert f'alt="{person["name"]},' in markup
            image = client.get(person["photo"])
            assert image.status_code == 200
            assert image.content.startswith(b"\xff\xd8")
            assert b"Exif\x00\x00" not in image.content

        founders = markup.index('id="team-tier-founders"')
        communications = markup.index('id="team-tier-communications"')
        for person in TEAM_MEMBERS[:3]:
            assert founders < markup.index(person["name"]) < communications
        assert communications < markup.index("Joash Thomas")
        assert "Bio coming soon" not in markup
        assert 'href="/team"' in markup
        assert '/static/team/ayansh-varma.jpg' in markup
    for path in ("/", "/about"):
        markup = client.get(path).text
        assert 'href="/team"' in markup
        assert 'class="team-member"' not in markup


def test_capture_inventory_matches_actual_files_and_all_home_ui_images(client):  # noqa: F811
    inventory = json.loads((STATIC / "product-captures.json").read_text())
    assert inventory["captured_at"] == "2026-10-26"
    captures = {item["file"]: item for item in inventory["captures"]}
    assert len(captures) == 24
    for name, item in captures.items():
        data = (STATIC / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert struct.unpack(">II", data[16:24]) == (item["width"], item["height"])
    markup = client.get("/").text
    images = re.findall(r'<img\b[^>]*src="/static/([\w-]+\.png)([^\"]*)"', markup)
    ui_images = [(name, query) for name, query in images if name in captures]
    # The two teammate-editor assets are refreshed for direct/legacy links; the
    # eleven current homepage stories each display both appearances.
    assert {name for name, _ in ui_images} == {
        name for name in captures if not name.startswith("teammate-")
    }
    assert all(query == "?v=20261026" for _, query in ui_images)
    for name, _ in ui_images:
        assert client.get("/static/" + name).status_code == 200
