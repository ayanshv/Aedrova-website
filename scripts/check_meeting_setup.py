"""Credential-safe meeting staging preflight; optional public HTTPS readiness probe.

Does not join rooms, capture media, transcribe, purchase, deploy or print configuration.
Run in the server environment, with private values injected by its secret store.
"""

import argparse
import json

import httpx

from aedrova_site.config import Config


def check(config, *, probe=False, client=None, speech=False, database=False):
    config.validate()
    if not config.production or not config.meetings_enabled:
        raise ValueError("Use enabled production-mode meeting staging configuration.")
    if config.checkout_enabled or config.gateway_enabled or config.release_ready:
        raise ValueError("Meeting staging must keep paid AI, checkout and releases disabled.")
    if speech and not (
        config.speech_enabled
        and config.meeting_context_enabled
        and config.supabase_database
        and config.speech_key
    ):
        raise ValueError(
            "Enable speech and meeting context with a server-only key and restricted database."
        )
    if database:
        if not speech:
            raise ValueError("Use speech mode for its restricted database grant check.")
        from sqlalchemy import create_engine, text

        engine = create_engine(
            config.database, pool_size=1, max_overflow=0, connect_args={"connect_timeout": 10}
        )
        try:
            with engine.connect() as connection:
                for function in (
                    "public.reserve_meeting_speech(uuid,uuid,uuid,bigint,uuid[],text,integer,integer)",
                    "public.finish_meeting_speech(uuid,uuid,text)",
                ):
                    row = connection.execute(
                        text(
                            "SELECT to_regprocedure(:f) IS NOT NULL, "
                            "has_function_privilege(current_user,:f,'EXECUTE')"
                        ),
                        {"f": function},
                    ).one()
                    if not all(row):
                        raise ValueError(
                            "Install speech migrations and grant "
                            "the restricted backend role execution."
                        )
        finally:
            engine.dispose()
    if probe:
        owned = client is None
        client = client or httpx.Client(timeout=10, follow_redirects=False)
        try:
            for path in ("/health", "/health/meetings"):
                with client.stream("GET", config.origin.rstrip("/") + path) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 16384:
                            raise ValueError("Unexpected readiness response.")
                    result = json.loads(body)
                expected = "ok" if path == "/health" else "ready"
                if result.get("status") != expected:
                    raise ValueError("The shared meeting service is not ready.")
        finally:
            if owned:
                client.close()
    return {
        "configuration": "passed",
        "https_readiness": "passed" if probe else "not tested",
        "two_mac_media": "not tested",
        "transcription": (
            "configured; provider capture not tested" if config.speech_enabled else "not enabled"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument(
        "--speech", action="store_true", help="Require enabled speech configuration."
    )
    parser.add_argument(
        "--database", action="store_true", help="Check speech function execution grants."
    )
    args = parser.parse_args()
    try:
        report = check(Config.load(), probe=args.probe, speech=args.speech, database=args.database)
    except Exception:
        # Config/HTTP/SQL error payloads can contain keys, origins or DSNs.
        raise SystemExit(
            "Meeting staging preflight failed. Check server configuration, "
            "HTTPS and the independent guard; credentials were not printed."
        ) from None
    print(json.dumps(report))


if __name__ == "__main__":
    main()
