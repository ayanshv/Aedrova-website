"""Atomic cross-workspace cost limits. Called inside the existing ledger transaction."""

from datetime import UTC, datetime

from sqlalchemy import text

from aedrova_site import promotion
from aedrova_site.policy import USAGE_POLICY
from aedrova_site.store_errors import BudgetDenied

FIVE_HOURS = 5 * 3600
WEEK = 7 * 24 * 3600


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

    if db.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(73114012)"))


def totals(db, scope, period):
    row = (
        db.execute(
            text("""SELECT COALESCE(SUM(CASE WHEN actual IS NULL THEN amount
        ELSE actual END),0) AS used, COALESCE(SUM(actual),0) AS settled,
        COUNT(*) AS requests
        FROM budget_reservations b WHERE scope=:scope AND
        (CASE WHEN :scope LIKE 'workspace:%' THEN EXISTS
        (SELECT 1 FROM inference i WHERE i.id=b.id AND i.created>=:period)
        ELSE period=:period END)"""),
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
        if row["plan"] == "free" or promotion.is_grant(row):
            result += [
                ("free-pool", store.free_pool, None),
                ("owner:" + row["budget_owner"], policy["budget"], policy["requests"]),
            ]
    return result


def inflight(db, workspace, seconds=FIVE_HOURS):
    """Requests in this billing space that are reserved but not yet settled."""
    import time

    return db.execute(
        text("""SELECT COUNT(*) FROM inference i
        JOIN inference_attribution a ON a.id=i.id
        WHERE a.billing_workspace=:w AND i.created>:since AND i.actual IS NULL"""),
        {"w": workspace, "since": int(time.time()) - seconds},
    ).scalar()


def window_blocked(db, workspace, seconds, budget, base):
    """True when a rolling window cannot take another request.

    A window pauses work when it is full, which is what the usage meter shows. A request's
    worst-case hold (its input bound, its full output and any hosted searches) can be larger
    than a small window by itself, so a lone request is judged on what has been used. Only when
    other requests are still in flight is the hold counted, so parallel work cannot overspend.
    """
    used = rolling(db, workspace, seconds)
    if used >= budget:
        return True
    return inflight(db, workspace, seconds) > 0 and used + base > budget


def reserve(store, db, row, identifier, amount, base):
    period, _ = month()
    policy = store.usage_policy.get(row["plan"])
    if policy and window_blocked(
        db, row["workspace"], FIVE_HOURS, policy.get("five_hour_budget", policy["budget"]), base
    ):
        raise BudgetDenied(
            "Shared five-hour AI capacity reached. Work pauses until capacity "
            "returns; human chat remains available."
        )
    weekly = policy.get("weekly_budget") if policy else None
    if weekly and window_blocked(db, row["workspace"], WEEK, weekly, base):
        raise BudgetDenied(
            "Weekly AI allowance reached. Work resumes as earlier usage ages out; "
            "human chat remains available. No provider request or automatic charge was made."
        )
    for scope, ceiling, requests in scopes(store, row):
        scope_period = billing_month(row)[0] if scope.startswith("workspace:") else period
        used = totals(db, scope, scope_period)
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
            {"id": identifier, "scope": scope, "period": scope_period, "amount": charge},
        )


def settle(db, identifier, charge, base_charge):
    db.execute(
        text("""UPDATE budget_reservations SET actual=CASE
        WHEN scope IN ('company','free-pool') THEN :charge ELSE :base END
        WHERE id=:id AND actual IS NULL"""),
        {"id": identifier, "charge": charge, "base": base_charge},
    )


def billing_month(row):
    """Monthly anniversary windows even when the subscription renews annually."""
    import calendar
    import time

    if row["plan"] == "free" or not row["period_start"]:
        return month()
    anchor = datetime.fromtimestamp(row["period_start"], UTC)
    now = datetime.fromtimestamp(time.time(), UTC)

    def boundary(offset):
        index = anchor.year * 12 + anchor.month - 1 + offset
        year, m = divmod(index, 12)
        return anchor.replace(
            year=year, month=m + 1, day=min(anchor.day, calendar.monthrange(year, m + 1)[1])
        )

    offset = max(0, (now.year - anchor.year) * 12 + now.month - anchor.month)
    if boundary(offset) > now and offset:
        offset -= 1
    return int(boundary(offset).timestamp()), min(
        int(boundary(offset + 1).timestamp()), row["period_end"]
    )


def rolling(db, workspace, seconds=FIVE_HOURS):
    """Provider cost used by one billing space within the last `seconds`."""
    import time

    used = db.execute(
        text("""SELECT COALESCE(SUM(CASE WHEN i.actual IS NULL THEN i.base_reserved
        WHEN i.actual<i.base_reserved THEN i.actual ELSE i.base_reserved END),0) FROM inference i
        JOIN inference_attribution a ON a.id=i.id
        WHERE a.billing_workspace=:w AND i.created>:since"""),
        {"w": workspace, "since": int(time.time()) - seconds},
    ).scalar()
    return used


def window_reset(db, workspace, seconds):
    """When the oldest usage in the window ages out, or 0 when the window is empty."""
    import time

    oldest = db.execute(
        text("""SELECT MIN(i.created) FROM inference i
        JOIN inference_attribution a ON a.id=i.id
        WHERE a.billing_workspace=:w AND i.created>:since"""),
        {"w": workspace, "since": int(time.time()) - seconds},
    ).scalar()
    return int(oldest) + seconds if oldest else 0
