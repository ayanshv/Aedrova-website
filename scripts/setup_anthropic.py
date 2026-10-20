"""Privately verify Anthropic model access without enabling or running inference."""

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
    if not re.fullmatch(r"sk-ant-[A-Za-z0-9_-]{20,256}", key or ""):
        raise ValueError("Enter an Anthropic API key privately in Terminal.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", model or ""):
        raise ValueError("Configure a valid Anthropic model identifier.")
    owned = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
    try:
        with client.stream(
            "GET",
            "https://api.anthropic.com/v1/models/" + model,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        ) as response:
            if response.status_code != 200:
                raise ValueError("Model access not verified.")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > 32768:
                    raise ValueError("Unexpected model response.")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("id") != model:
                raise ValueError("Configured model access not verified.")
    except (httpx.HTTPError, ValueError):
        raise ValueError(
            "Anthropic access check failed. Check the key and configured model permissions."
        ) from None
    finally:
        if owned:
            client.close()
    return {"credentials": "verified", "model": model, "paid_inference": "not run"}


def install(key, *, root=ROOT):
    path = root / ".env.anthropic"
    if path.is_symlink():
        raise ValueError("Use a regular private .env.anthropic file.")
    models = json.loads((root / "config/models.anthropic.json").read_text())
    report = verify(key, models["claude_code"]["id"])
    content = (
        "# Private server credential. Never bundle or commit.\n"
        "AEDROVA_ANTHROPIC_KEY=" + key + "\n"
        "AEDROVA_MODELS_FILE=config/models.anthropic.json\n"
        "AEDROVA_GATEWAY_ENABLED=false\n"
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", prefix=".env.anthropic-", dir=root, delete=False
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
        raise SystemExit("Run this directly in Terminal for the hidden key prompt.")
    try:
        if args.check:
            from aedrova_site.config import Config

            config = Config.load()
            if "claude_code" not in config.models:
                raise ValueError("Configure the Anthropic model first.")
            report = verify(config.anthropic_key, config.models["claude_code"]["id"])
        else:
            report = install(getpass.getpass("Anthropic API key (hidden): "))
    except Exception:
        raise SystemExit(
            "Anthropic setup failed. Check key, model access and network. "
            "No key was printed and no paid inference was started."
        ) from None
    print(json.dumps(report))
    if not args.check:
        print("Saved .env.anthropic privately. Gateway and entitlement activation are separate.")


if __name__ == "__main__":
    main()
