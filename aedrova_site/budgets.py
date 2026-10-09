"""Atomic cross-workspace cost limits. Called inside the existing ledger transaction."""

from datetime import UTC, datetime

from sqlalchemy import text

from aedrova_site.policy import USAGE_POLICY
from aedrova_site.store_errors import BudgetDenied


def policies(overrides):
    result = {name: dict(policy) for name, policy in USAGE_POLICY.items()}
    for name, changes in overrides.items():
        if name not in result or not isinstance(changes, dict):
            raise ValueError("Unknown usage policy.")
        for key, value in changes.items():
            if key not in result[name] or type(value) is not int or not 0 < value <= 1_000_000_000:
                raise ValueError("Usage limits must be positive bounded integers.")
            result[name][key] = value
    if any(result["annual"][key] < value for key, value in result["monthly"].items()):
        raise ValueError("Team limits must be at least as generous as Pro limits.")
    return result


def month():
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    end = datetime(now.year + (now.month == 12), now.month % 12 + 1, 1, tzinfo=UTC)
    return int(start.timestamp()), int(end.timestamp())


def lock(db):
    # Always before the workspace lock: consistent ordering avoids cross-workspace deadlocks.
    if db.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(73114012)"))


def totals(db, scope, period):
    row = (
        db.execute(
            text("""SELECT COALESCE(SUM(CASE WHEN actual IS NULL THEN amount
        ELSE actual END),0) AS used, COUNT(*) AS requests
        FROM budget_reservations WHERE scope=:scope AND period=:period"""),
            {"scope": scope, "period": period},
        )
        .mappings()
        .one()
    )
    return dict(row)


def scopes(store, row):
    result = [("company", store.company_budget, None)]
    if row["plan"] in store.usage_policy:
        policy = store.usage_policy[row["plan"]]
        result.append(("workspace:" + row["workspace"], policy["budget"], policy["requests"]))
        if row["plan"] == "free":
            result += [
                ("free-pool", store.free_pool, None),
                ("owner:" + row["budget_owner"], policy["budget"], policy["requests"]),
            ]
    return result


def reserve(store, db, row, identifier, amount, base):
    period, _ = month()
    for scope, ceiling, requests in scopes(store, row):
        used = totals(db, scope, period)
        charge = amount if scope in {"company", "free-pool"} else base
        if used["used"] + charge > ceiling:
            raise BudgetDenied(
                "Monthly AI budget reached. Wait for reset or review your plan. "
                "No provider request or automatic charge was made."
            )
        if requests is not None and used["requests"] >= requests:
            raise BudgetDenied("Monthly AI request limit reached. Human chat remains available.")
        db.execute(
            text("""INSERT INTO budget_reservations
            (id,scope,period,amount) VALUES(:id,:scope,:period,:amount)"""),
            {"id": identifier, "scope": scope, "period": period, "amount": charge},
        )


def settle(db, identifier, charge, base_charge):
    db.execute(
        text("""UPDATE budget_reservations SET actual=CASE
        WHEN scope IN ('company','free-pool') THEN :charge ELSE :base END
        WHERE id=:id AND actual IS NULL"""),
        {"id": identifier, "charge": charge, "base": base_charge},
    )
