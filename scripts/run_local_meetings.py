"""Run the internal loopback meeting service; public release flags stay disabled."""

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def launch_configuration(desktop, *, openai=False):
    files = [desktop / ".env.meetings", ROOT / ".env.meeting-server"]
    if not all(path.is_file() for path in files):
        raise ValueError("The existing private local meeting configuration files are required.")
    if (ROOT / ".env.dots").is_file():
        files.append(ROOT / ".env.dots")
    if openai:
        files.append(ROOT / ".env.openai")
        if not files[-1].is_file():
            raise ValueError("Run scripts/setup_openai.py before enabling local OpenAI.")
    command = ["uv", "run"]
    for path in files:
        command.extend(["--env-file", str(path)])
    command.extend(
        [
            "uvicorn",
            "aedrova_site.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8090",
            "--no-access-log",
        ]
    )
    environment = dict(os.environ)
    environment.update(
        {
            "AEDROVA_ORIGIN": "http://127.0.0.1:8090",
            "AEDROVA_PRODUCTION": "false",
            "AEDROVA_WAITLIST_ONLY": "false",
            "AEDROVA_MEETINGS_ENABLED": "true",
            "AEDROVA_DOTS_ENABLED": "true",
            "AEDROVA_MEETING_CONTEXT_ENABLED": "false",
            "AEDROVA_SPEECH_ENABLED": "false",
            "AEDROVA_CHECKOUT_ENABLED": "false",
            "AEDROVA_GATEWAY_ENABLED": "false",
            "AEDROVA_DEVELOPMENT_AI": "false",
            "AEDROVA_RELEASE_READY": "false",
            "AEDROVA_LEGAL_READY": "false",
            "AEDROVA_STRIPE_TEST_MODE": "false",
        }
    )
    if openai:
        environment["AEDROVA_GATEWAY_ENABLED"] = "true"
        environment["AEDROVA_DEVELOPMENT_AI"] = "true"
        environment["AEDROVA_MODELS_FILE"] = str(ROOT / "config/models.openai.json")
    return command, environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-openai", action="store_true")
    args = parser.parse_args()
    # Adjacent desktop checkout is the established local development layout.
    command, environment = launch_configuration(ROOT.parent / "Aedrova", openai=args.with_openai)
    print("Local meeting service on port 8090. Keep this terminal open; Ctrl+C stops it.")
    try:
        result = subprocess.run(command, env=environment, cwd=ROOT, check=False)
    except KeyboardInterrupt:
        return
    if result.returncode:
        raise SystemExit("Local service stopped. Check configuration or port 8090 availability.")


if __name__ == "__main__":
    main()
