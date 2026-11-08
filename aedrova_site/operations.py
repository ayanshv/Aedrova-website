"""Read-only spending and stale-work checks for the private operator logs."""

import asyncio
import time

from sqlalchemy import text

from aedrova_site import budgets
from aedrova_site.observability import emit


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
    expired = db.scalar(
        text("""SELECT count(*) FROM inference i JOIN runs r ON r.id=i.run_id
                WHERE i.state='pending' AND r.expires<:now"""),
        {"now": int(time.time())},
    )
    return {
        "database": "passed",
        "company_budget_below_90_percent": used * 100 < config.company_budget_microusd * 90,
        "free_pool_below_90_percent": free_used * 100 < config.free_pool_microusd * 90,
        "expired_pending_requests": expired,
    }


def spending_health(engine, config):
    try:
        with engine.connect() as db, db.begin():
            report = database_checks(db, config)
    except Exception:
        return {"status": "attention_required", "database": "failed"}
    alert = (
        not report["company_budget_below_90_percent"]
        or not report["free_pool_below_90_percent"]
        or report["expired_pending_requests"] > 0
    )
    return {"status": "attention_required" if alert else "healthy", **report}


async def monitor_spending(engine, config, stop):
    while not stop.is_set():
        report = await asyncio.to_thread(spending_health, engine, config)
        emit("operations_spending_probe", **report)
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
        except TimeoutError:
            pass
