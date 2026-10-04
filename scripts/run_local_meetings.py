"""Run the internal loopback meeting service; public release flags stay disabled."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def launch_configuration(desktop):
    files = [desktop / ".env.meetings", ROOT / ".env.meeting-server"]
    if not all(path.is_file() for path in files):
        raise ValueError("The existing private local meeting configuration files are required.")
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
            "AEDROVA_MEETING_CONTEXT_ENABLED": "false",
            "AEDROVA_SPEECH_ENABLED": "false",
            "AEDROVA_CHECKOUT_ENABLED": "false",
            "AEDROVA_GATEWAY_ENABLED": "false",
            "AEDROVA_RELEASE_READY": "false",
            "AEDROVA_LEGAL_READY": "false",
            "AEDROVA_STRIPE_TEST_MODE": "false",
        }
    )
    return command, environment


def main():
    # Adjacent desktop checkout is the established local development layout.
    command, environment = launch_configuration(ROOT.parent / "Aedrova")
    print("Local meeting service on port 8090. Keep this terminal open; Ctrl+C stops it.")
    try:
        result = subprocess.run(command, env=environment, cwd=ROOT, check=False)
    except KeyboardInterrupt:
        return
    if result.returncode:
        raise SystemExit("Local service stopped. Check configuration or port 8090 availability.")


if __name__ == "__main__":
    main()
