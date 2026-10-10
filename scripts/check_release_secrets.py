"""Scan Git-tracked source for recognizable credentials; never print secret values."""

import subprocess
from pathlib import Path

from aedrova_site.credential_patterns import credential_rules

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    findings = []
    for name in filter(None, names):
        path = ROOT / name
        if "node_modules" in path.parts:
            findings.append((name, "tracked-vendor-directory"))
        if not path.is_file():
            continue
        if path.name.startswith(".env") and not path.name.endswith(".example"):
            findings.append((name, "tracked-environment-file"))
        findings.extend((name, rule) for rule in credential_rules(path.read_bytes()))
    for name, rule in findings:
        print(f"FAIL {rule}: {name}")
    if findings:
        raise SystemExit(1)
    print("PASS tracked-file credential patterns and environment/vendor exclusions")


if __name__ == "__main__":
    main()
