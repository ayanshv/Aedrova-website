"""Owner-approved fixed early-access window. Never derived from browser/signup time."""

import time
from datetime import UTC, datetime

DAYS = 60
STARTS_AT = int(datetime(2026, 10, 22, 4, 58, 40, tzinfo=UTC).timestamp())
# Owner extended the final day through 11:59 p.m. Pacific; never move the start.
ENDS_AT = int(datetime(2026, 12, 21, 7, 59, 59, tzinfo=UTC).timestamp())
ENDS_ISO = datetime.fromtimestamp(ENDS_AT, UTC).isoformat()
ENDS_LABEL = "December 20, 2026 at 11:59 p.m. Pacific"


def status(now=None):
    now = time.time() if now is None else now
    return {
        "active": STARTS_AT <= now < ENDS_AT,
        "ended": now >= ENDS_AT,
        "days": DAYS,
        "starts_at": STARTS_AT,
        "ends_at": ENDS_AT,
        "ends_iso": ENDS_ISO,
        "ends_label": ENDS_LABEL,
        "remaining_seconds": max(0, int(ENDS_AT - now)),
    }


def is_grant(row):
    return (
        row["customer"].startswith("free:early-access:")
        and not row["subscription"]
        and row["plan"] in {"monthly", "annual"}
    )
