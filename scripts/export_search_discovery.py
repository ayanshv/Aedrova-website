"""Export public crawler policy for an origin-independent, exact-path edge route."""

import json
from pathlib import Path

from aedrova_site.config import Config
from aedrova_site.discovery import CANONICAL, robots, sitemap


def main():
    target = Path(__file__).resolve().parents[1] / "deploy/search-discovery/robots.mjs"
    config = Config(origin=CANONICAL)
    target.write_text(
        "export const ROBOTS = " + json.dumps(robots(config)) + ";\n"
        + "export const SITEMAP = " + json.dumps(sitemap(config)) + ";\n"
    )


if __name__ == "__main__":
    main()
