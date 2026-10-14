"""One bounded, read-only operator probe. No tokens, payloads or identifiers in output.

Run in the existing private host environment. Exit 1 means a scheduler should alert
the operator. This does not install a scheduler or send data to an alert provider.
"""

import json
import time

import httpx
from sqlalchemy import create_engine, text

from aedrova_site import budgets
from aedrova_site.config import Config


def database_checks(db, config):
    if db.dialect.name == "postgresql":
        db.exec_driver_sql("SET TRANSACTION READ ONLY")
        db.exec_driver_sql("SET LOCAL search_path TO aedrova_billing")
        db.exec_driver_sql("SET LOCAL statement_timeout TO '5s'")
    else:
        db.exec_driver_sql("PRAGMA query_only=ON")
    start, _ = budgets.month()
    used = budgets.totals(db, "company", start)["used"]
    free_used = budgets.totals(db, "free-pool", start)["used"]
    expired = db.scalar(text("""SELECT count(*) FROM inference i JOIN runs r
        ON r.id=i.run_id WHERE i.state='pending' AND r.expires<:now"""),
                        {"now": int(time.time())})
    return {
        "database": "passed",
        "company_budget_below_90_percent": used * 100 < config.company_budget_microusd * 90,
        "free_pool_below_90_percent": free_used * 100 < config.free_pool_microusd * 90,
        "expired_pending_requests": expired,
    }


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
        # Connection errors may include database URLs, tokens or private hostnames.
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
