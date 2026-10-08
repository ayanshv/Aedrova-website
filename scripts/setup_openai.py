"""Install a provider key privately; verify model access without running paid inference."""

import argparse
import getpass
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(key, model, *, client=None):
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,256}", key or ""):
        raise ValueError("Enter an OpenAI API key; never send it through chat.")
    owned = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
    try:
        response = client.get(
            "https://api.openai.com/v1/models/" + model,
            headers={"Authorization": "Bearer " + key},
        )
        data = response.json()
        if response.status_code != 200 or not isinstance(data, dict) or data.get("id") != model:
            raise ValueError("OpenAI key or configured model access could not be verified.")
    except (httpx.HTTPError, ValueError):
        # Provider response bodies, exceptions and request headers may contain secrets.
        raise ValueError(
            "OpenAI access check failed. Check the key and model permissions."
        ) from None
    finally:
        if owned:
            client.close()
    return {"credentials": "verified", "model": model, "paid_inference": "not run"}


def install(key, *, root=ROOT):
    path = root / ".env.openai"
    if path.is_symlink():
        raise ValueError("Use a regular private .env.openai file.")
    models = json.loads((root / "config/models.openai.json").read_text())
    report = verify(key, models["codex"]["id"])
    content = (
        "# Private server credential. Never copy into the desktop app or commit.\n"
        "AEDROVA_OPENAI_KEY=" + key + "\n"
        "AEDROVA_MODELS_FILE=config/models.openai.json\n"
        "# Enable only through the explicit local launcher option or server secret store.\n"
        "AEDROVA_GATEWAY_ENABLED=false\n"
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", prefix=".env.openai-", dir=root, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check an injected server key only")
    args = parser.parse_args()
    if not args.check and not sys.stdin.isatty():
        raise SystemExit("Run setup directly in Terminal; a hidden key prompt requires a terminal.")
    try:
        if args.check:
            from aedrova_site.config import Config

            config = Config.load()
            if "codex" not in config.models:
                raise ValueError("Configure the OpenAI model first.")
            report = verify(config.openai_key, config.models["codex"]["id"])
        else:
            report = install(getpass.getpass("OpenAI API key (hidden): "))
    except Exception:
        raise SystemExit(
            "OpenAI setup failed. Check your key, model access and network. "
            "No key was printed and no paid inference was started."
        ) from None
    print(json.dumps(report))
    if not args.check:
        print(
            "Saved .env.openai privately. Gateway, entitlement and desktop activation are separate."
        )


if __name__ == "__main__":
    main()
