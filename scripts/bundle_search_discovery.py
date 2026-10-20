"""Prepare the existing Worker dashboard's single-file public robots upload."""

from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1] / "deploy/search-discovery"
    policy = (root / "robots.mjs").read_text().replace("export const", "const", 1)
    handler = (
        (root / "worker.mjs").read_text().replace("import { ROBOTS } from './robots.mjs';", "")
    )
    (root / "worker-bundled.js").write_text(policy + "\n" + handler)


if __name__ == "__main__":
    main()
