"""One bounded, read-only operator probe. No tokens, payloads or identifiers in output.

Run in the existing private host environment. Exit 1 means a scheduler should alert
the operator. This does not install a scheduler or send data to an alert provider.
"""

import json

import httpx
from sqlalchemy import create_engine

from aedrova_site.config import Config
from aedrova_site.operations import database_checks as database_checks


def readiness(config, client):
    with client.stream("GET", config.origin.rstrip("/") + "/health/ready") as response:
        if response.status_code != 200:
            return False
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > 16384:
                return False
        return json.loads(body) == {"status": "ready"}


def healthy(report):
    return (
        report.get("database") == "passed"
        and report.get("http_ready") is True
        and report.get("company_budget_below_90_percent") is True
        and report.get("free_pool_below_90_percent") is True
        and report.get("expired_pending_requests") == 0
    )


def main():
    engine = None
    report = {}
    try:
        config = Config.load()
        engine = create_engine(
            config.database, pool_pre_ping=True,
            connect_args={"connect_timeout": 5} if config.database.startswith("postgresql")
            else {"timeout": 5},
        )
        with engine.connect() as db, db.begin():
            report.update(database_checks(db, config))
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            report["http_ready"] = readiness(config, client)
    except Exception:

        report["probe"] = "failed; inspect private host configuration/logs"
    finally:
        if engine is not None:
            engine.dispose()
    report["status"] = "healthy" if healthy(report) else "attention_required"
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "healthy":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
