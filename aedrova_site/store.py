"""Shared SQL ledger; production transactions serialize allowance reservations."""

import hashlib
import json
import secrets
import time
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, inspect, text

from aedrova_site import budgets
from aedrova_site.store_errors import BudgetDenied

SCHEMA = [
    (
        "CREATE TABLE IF NOT EXISTS credit_reversals (payment "
        "TEXT PRIMARY KEY, numerator BIGINT NOT NULL, "
        "denominator BIGINT NOT NULL)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS wallets (workspace TEXT "
        "PRIMARY KEY, balance BIGINT NOT NULL DEFAULT 0, "
        "reserved BIGINT NOT NULL DEFAULT 0)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS credits (id TEXT PRIMARY "
        "KEY, workspace TEXT NOT NULL, payment TEXT NOT NULL "
        "UNIQUE, amount BIGINT NOT NULL, reversed BIGINT NOT "
        "NULL DEFAULT 0)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS billing (\n        workspace "
        "TEXT PRIMARY KEY, customer TEXT NOT NULL "
        "UNIQUE,\nsubscription TEXT NOT NULL DEFAULT '',\n        "
        "plan TEXT NOT NULL DEFAULT '', status TEXT NOT NULL "
        "DEFAULT\n'pending', period_start BIGINT NOT NULL DEFAULT "
        "0,\n        period_end BIGINT NOT NULL DEFAULT 0, "
        "allowance BIGINT NOT NULL\nDEFAULT 0, spent BIGINT NOT "
        "NULL DEFAULT 0,\n        reserved BIGINT NOT NULL "
        "DEFAULT 0, concurrency INTEGER NOT NULL\nDEFAULT 1)"
    ),
    """CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, created BIGINT NOT NULL)""",
    (
        "CREATE TABLE IF NOT EXISTS runs (\n        id TEXT "
        "PRIMARY KEY, user_id TEXT NOT NULL, workspace TEXT NOT "
        "NULL,\nprovider TEXT NOT NULL,\n        token_hash TEXT "
        "NOT NULL UNIQUE, expires BIGINT NOT NULL, state "
        "TEXT\nNOT NULL DEFAULT 'active',\n        request_key "
        "TEXT NOT NULL UNIQUE)"
    ),
    """CREATE TABLE IF NOT EXISTS inference (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, period_start BIGINT NOT NULL,
        amount BIGINT NOT NULL, actual BIGINT, state TEXT NOT NULL DEFAULT 'pending', response TEXT,
        created BIGINT NOT NULL, input_tokens BIGINT, output_tokens BIGINT,
        base_reserved BIGINT NOT NULL DEFAULT 0, credit_reserved BIGINT NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS checkout (
        id TEXT PRIMARY KEY, workspace TEXT NOT NULL, plan TEXT NOT NULL,
        url TEXT, expires BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS limits (
        id TEXT PRIMARY KEY, count INTEGER NOT NULL, expires BIGINT NOT NULL)""",
]


SCHEMA += [
    "CREATE INDEX IF NOT EXISTS runs_workspace_active ON runs(workspace,state,expires)",
    "CREATE INDEX IF NOT EXISTS runs_user_active ON runs(user_id,state,expires)",
    "CREATE INDEX IF NOT EXISTS inference_run_state ON inference(run_id,state)",
    "CREATE INDEX IF NOT EXISTS inference_state_created ON inference(state,created)",
    "CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires)",
    "CREATE INDEX IF NOT EXISTS limits_expiry ON limits(expires)",
    "CREATE INDEX IF NOT EXISTS checkout_workspace_expiry ON checkout(workspace,expires)",
]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Denied(ValueError):
    pass


class RateLimited(Denied):
    def __init__(self, retry_after=60):
        super().__init__("Too many requests. Wait a minute and try again.")
        self.retry_after = retry_after


class Store:
    def __init__(
        self,
        url,
        encryption_key="",
        *,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        development_ai=False,
        usage_limits=None,
        company_budget=100_000_000,
        free_pool=25_000_000,
        free_enabled=False,
    ):
        if development_ai and not url.startswith("sqlite:///"):
            raise ValueError("Development allowances require a private SQLite database.")
        self.usage_policy = budgets.policies(usage_limits or {})
        self.company_budget, self.free_pool = company_budget, free_pool
        self.free_enabled = free_enabled
        self.development_ai = development_ai
        if url.startswith("sqlite:///"):
            path = Path(url.removeprefix("sqlite:///"))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            url,
            connect_args={"timeout": 10} if url.startswith("sqlite") else {},
            pool_pre_ping=True,
            pool_recycle=300,
            **(
                {"pool_size": pool_size, "max_overflow": max_overflow, "pool_timeout": pool_timeout}
                if url.startswith("postgresql")
                else {}
            ),
        )
        if self.engine.dialect.name == "postgresql":
            # Keep billing/auth tables outside Supabase's exposed public schema.
            with self.engine.begin() as db:
                db.execute(text("SELECT pg_advisory_xact_lock(73114011)"))
                # A restricted Supabase login owns the pre-created private schema,
                # but deliberately cannot CREATE schemas in the shared database.
                missing = db.scalar(text("SELECT to_regnamespace('aedrova_billing') IS NULL"))
                if missing:
                    db.execute(text("CREATE SCHEMA aedrova_billing"))
                db.execute(text("REVOKE ALL ON SCHEMA aedrova_billing FROM PUBLIC"))
            self.engine.dispose()

            @event.listens_for(self.engine, "connect")
            def private_schema(connection, _record):
                with connection.cursor() as cursor:
                    cursor.execute("SET search_path TO aedrova_billing")
                    cursor.execute("SET statement_timeout TO '15s'")
                    cursor.execute("SET lock_timeout TO '5s'")
                connection.commit()

        self.cipher = Fernet(encryption_key.encode() if encryption_key else Fernet.generate_key())
        with self.tx() as db:
            if self.engine.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73114011)"))
            for statement in SCHEMA:
                db.execute(text(statement))
            billing_columns = {column["name"] for column in inspect(db).get_columns("billing")}
            if "budget_owner" not in billing_columns:
                db.execute(
                    text("ALTER TABLE billing ADD COLUMN budget_owner TEXT NOT NULL DEFAULT ''")
                )
            db.execute(
                text("""CREATE TABLE IF NOT EXISTS budget_reservations (
                id TEXT NOT NULL, scope TEXT NOT NULL, period BIGINT NOT NULL,
                amount BIGINT NOT NULL, actual BIGINT, PRIMARY KEY(id,scope))""")
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS budget_scope_period "
                    "ON budget_reservations(scope,period)"
                )
            )
            db.execute(
                text("""CREATE TABLE IF NOT EXISTS inference_details (
                id TEXT PRIMARY KEY, plan TEXT NOT NULL, model TEXT NOT NULL,
                rates TEXT NOT NULL, usage TEXT NOT NULL DEFAULT '{}')""")
            )
            db.execute(
                text("""CREATE TABLE IF NOT EXISTS budget_alerts (
                period BIGINT NOT NULL, threshold INTEGER NOT NULL,
                PRIMARY KEY(period,threshold))""")
            )
            db.execute(
                text("""CREATE TABLE IF NOT EXISTS billing_holds (
                workspace TEXT PRIMARY KEY, period BIGINT NOT NULL)""")
            )
            columns = {column["name"] for column in inspect(db).get_columns("inference")}
            if "base_reserved" not in columns:
                db.execute(
                    text("ALTER TABLE inference ADD COLUMN base_reserved BIGINT NOT NULL DEFAULT 0")
                )
                db.execute(
                    text(
                        "ALTER TABLE inference ADD COLUMN credit_reserved BIGINT NOT NULL DEFAULT 0"
                    )
                )
                db.execute(text("UPDATE inference SET base_reserved=amount"))
        # Backfill existing money without resetting it. Legacy owner identity remains unknown.
        with self.tx() as db:
            budgets.lock(db)
            marker = "migration:monthly-budget-v2"
            if not db.execute(text("SELECT id FROM events WHERE id=:id"), {"id": marker}).first():
                from datetime import UTC, datetime

                rows = (
                    db.execute(
                        text("""SELECT i.*,r.workspace FROM inference i
                    JOIN runs r ON r.id=i.run_id""")
                    )
                    .mappings()
                    .all()
                )
                for entry in rows:
                    stamp = datetime.fromtimestamp(entry["created"], UTC)
                    period = int(datetime(stamp.year, stamp.month, 1, tzinfo=UTC).timestamp())
                    for scope, amount in [
                        ("company", entry["amount"]),
                        ("workspace:" + entry["workspace"], entry["base_reserved"]),
                    ]:
                        charge = entry["actual"]
                        if charge is not None and scope != "company":
                            charge = min(charge, entry["base_reserved"])
                        db.execute(
                            text("""INSERT INTO budget_reservations
                            (id,scope,period,amount,actual) VALUES(:id,:scope,:p,:amount,:actual)
                            ON CONFLICT DO NOTHING"""),
                            {
                                "id": entry["id"],
                                "scope": scope,
                                "p": period,
                                "amount": amount,
                                "actual": charge,
                            },
                        )
                db.execute(
                    text("INSERT INTO events(id,created) VALUES(:id,:now)"),
                    {"id": marker, "now": int(time.time())},
                )
        if url.startswith("sqlite:///"):
            path.chmod(0o600)

    @contextmanager
    def tx(self, *, write=True):
        with self.engine.connect() as db:
            if self.engine.dialect.name == "sqlite" and write:
                db.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                db.begin()
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def billing_lock(self, db, workspace):
        suffix = " FOR UPDATE" if self.engine.dialect.name == "postgresql" else ""
        row = (
            db.execute(text("SELECT * FROM billing WHERE workspace=:w" + suffix), {"w": workspace})
            .mappings()
            .first()
        )
        if not row:
            raise Denied("Choose a plan on the website before using included AI.")
        return row

    def customer(self, workspace, customer):
        with self.tx() as db:
            db.execute(
                text(
                    "INSERT INTO billing(workspace,customer) VALUES(:w,:c) "
                    "ON CONFLICT(workspace) DO NOTHING"
                ),
                {"w": workspace, "c": customer},
            )
            return dict(self.billing_lock(db, workspace))

    def wallet(self, db, workspace):
        # Caller holds the workspace billing lock; this also serializes credit grants.
        db.execute(
            text("INSERT INTO wallets(workspace) VALUES(:w) ON CONFLICT(workspace) DO NOTHING"),
            {"w": workspace},
        )
        return (
            db.execute(text("SELECT * FROM wallets WHERE workspace=:w"), {"w": workspace})
            .mappings()
            .one()
        )

    def payment_lock(self, db, payment):
        if self.engine.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:p,0))"), {"p": payment})

    def grant_credit(self, identifier, workspace, payment, amount):
        if type(amount) is not int or amount <= 0 or not payment:
            raise Denied("Invalid AI credit grant.")
        with self.tx() as db:
            self.payment_lock(db, payment)
            self.billing_lock(db, workspace)
            self.wallet(db, workspace)
            if db.execute(
                text("SELECT id FROM credits WHERE id=:id OR payment=:p"),
                {"id": identifier, "p": payment},
            ).first():
                return False
            reversal = (
                db.execute(text("SELECT * FROM credit_reversals WHERE payment=:p"), {"p": payment})
                .mappings()
                .first()
            )
            reversed_amount = (
                min(
                    amount,
                    (amount * reversal["numerator"] + reversal["denominator"] - 1)
                    // reversal["denominator"],
                )
                if reversal
                else 0
            )
            db.execute(
                text(
                    "INSERT INTO "
                    "credits(id,workspace,payment,amount,reversed) "
                    "VALUES(:id,:w,:p,:n,:r)"
                ),
                {"id": identifier, "w": workspace, "p": payment, "n": amount, "r": reversed_amount},
            )
            db.execute(
                text("UPDATE wallets SET balance=balance+:n WHERE workspace=:w"),
                {"n": amount - reversed_amount, "w": workspace},
            )
            return True

    def reverse_credit(self, payment, numerator, denominator):
        if (
            type(numerator) is not int
            or type(denominator) is not int
            or numerator < 0
            or denominator <= 0
        ):
            raise Denied("Invalid AI credit reversal.")
        if not payment:
            return
        with self.tx() as db:
            self.payment_lock(db, payment)
            prior = (
                db.execute(text("SELECT * FROM credit_reversals WHERE payment=:p"), {"p": payment})
                .mappings()
                .first()
            )
            if prior and prior["numerator"] * denominator > numerator * prior["denominator"]:
                numerator, denominator = prior["numerator"], prior["denominator"]
            db.execute(
                text(
                    "INSERT INTO credit_reversals VALUES(:p,:n,:d) ON "
                    "CONFLICT(payment) DO UPDATE SET "
                    "numerator=:n,denominator=:d"
                ),
                {"p": payment, "n": numerator, "d": denominator},
            )
            entry = (
                db.execute(text("SELECT * FROM credits WHERE payment=:p"), {"p": payment})
                .mappings()
                .first()
            )
            if not entry:
                return
            self.billing_lock(db, entry["workspace"])
            entry = (
                db.execute(text("SELECT * FROM credits WHERE payment=:p"), {"p": payment})
                .mappings()
                .one()
            )
            amount = min(
                entry["amount"], (entry["amount"] * numerator + denominator - 1) // denominator
            )
            if amount <= entry["reversed"]:
                return
            db.execute(
                text("UPDATE wallets SET balance=balance-:n WHERE workspace=:w"),
                {"n": amount - entry["reversed"], "w": entry["workspace"]},
            )
            db.execute(
                text("UPDATE credits SET reversed=:n WHERE payment=:p"), {"n": amount, "p": payment}
            )

    def budget_health(self):
        from aedrova_site.observability import emit

        period, reset = budgets.month()
        alerts = []
        with self.tx() as db:
            budgets.lock(db)
            used = budgets.totals(db, "company", period)["used"]
            for threshold in (50, 75, 90):
                if used * 100 >= self.company_budget * threshold:
                    created = db.execute(
                        text("""INSERT INTO budget_alerts(period,threshold)
                        VALUES(:period,:threshold) ON CONFLICT DO NOTHING"""),
                        {"period": period, "threshold": threshold},
                    ).rowcount
                    if created:
                        alerts.append(threshold)
        for threshold in alerts:
            emit(
                "ai_budget_threshold",
                threshold=threshold,
                estimated_microusd=used,
                ceiling_microusd=self.company_budget,
            )
        return {
            "estimated_microusd": used,
            "ceiling_microusd": self.company_budget,
            "reset_at": reset,
            "alerts": alerts,
        }

    def activate_free(self, user, workspace):
        """Called only after fresh owner/admin authorization and the explicit launch gate."""
        start, end = budgets.month()
        with self.tx() as db:
            budgets.lock(db)
            db.execute(
                text("""INSERT INTO billing(workspace,customer,plan,status,period_start,
                period_end,allowance,concurrency,budget_owner)
                VALUES(:w,:c,'free','active',:start,:end,:amount,1,:owner)
                ON CONFLICT(workspace) DO NOTHING"""),
                {
                    "w": workspace,
                    "c": "free:" + workspace,
                    "owner": user,
                    "start": start,
                    "end": end,
                    "amount": self.usage_policy["free"]["budget"],
                },
            )
            row = self.billing_lock(db, workspace)
            if row["plan"] != "free" or row["budget_owner"] != user:
                raise Denied("This workspace already has another plan or funding owner.")
            self.refresh_free(db, row)
        return self.balance(workspace)

    def refresh_free(self, db, row):
        if (
            self.free_enabled
            and row["budget_owner"]
            and row["plan"] in self.usage_policy
            and row["plan"] != "free"
            and (row["status"] == "inactive" or row["period_end"] <= int(time.time()))
        ):
            start, end = budgets.month()
            db.execute(
                text("""UPDATE billing SET plan='free',status='active',period_start=:start,
                period_end=:end,spent=0,reserved=0,allowance=:amount WHERE workspace=:w"""),
                {
                    "start": start,
                    "end": end,
                    "w": row["workspace"],
                    "amount": self.usage_policy["free"]["budget"],
                },
            )
            row = self.billing_lock(db, row["workspace"])
        if row["plan"] == "free" and row["period_end"] <= int(time.time()):
            start, end = budgets.month()
            db.execute(
                text("""UPDATE billing SET period_start=:start,period_end=:end,
                spent=0,reserved=0,allowance=:amount WHERE workspace=:w"""),
                {
                    "start": start,
                    "end": end,
                    "w": row["workspace"],
                    "amount": self.usage_policy["free"]["budget"],
                },
            )
            return self.billing_lock(db, row["workspace"])
        return row

    def run_limits(self, run):
        with self.tx(write=False) as db:
            plan = db.execute(
                text("SELECT plan FROM billing WHERE workspace=:w"), {"w": run["workspace"]}
            ).scalar()
        return self.usage_policy.get(
            plan,
            {
                "input_tokens": 200_000,
                "output_tokens": 16384,
                "run_seconds": 7200,
                "run_calls": 120,
                "tools": 64,
            },
        )

    def balance(self, workspace):
        with self.tx() as db:
            row = dict(self.refresh_free(db, self.billing_lock(db, workspace)))
            wallet = self.wallet(db, workspace)
            row["credit_balance"], row["credit_reserved"] = wallet["balance"], wallet["reserved"]
            row["available"] = max(0, row["allowance"] - row["spent"] - row["reserved"]) + max(
                0, wallet["balance"] - wallet["reserved"]
            )
            if row["plan"] == "free":
                row["available"] = max(0, row["allowance"] - row["spent"] - row["reserved"])
            if wallet["balance"] < 0:
                row["available"] = 0
            period, reset = budgets.month()
            if row["plan"] in self.usage_policy:
                limits = budgets.scopes(self, row)
                remaining = [
                    max(0, cap - budgets.totals(db, scope, period)["used"])
                    for scope, cap, _ in limits
                ]
                row["available"] = max(0, remaining[1]) + (
                    max(0, wallet["balance"] - wallet["reserved"]) if row["plan"] != "free" else 0
                )
                row["available"] = min(
                    row["available"],
                    *remaining[:1],
                    remaining[1] + max(0, wallet["balance"] - wallet["reserved"]),
                )
                if row["plan"] == "free":
                    row["available"] = min(row["available"], *remaining[2:])
                row["monthly_budget"] = self.usage_policy[row["plan"]]["budget"]
                row["monthly_spent"] = budgets.totals(db, "workspace:" + workspace, period)["used"]
                row["monthly_requests"] = budgets.totals(db, "workspace:" + workspace, period)[
                    "requests"
                ]
                row["monthly_request_limit"] = self.usage_policy[row["plan"]]["requests"]
            else:
                row.update(
                    monthly_budget=row["allowance"],
                    monthly_spent=row["spent"],
                    monthly_requests=0,
                    monthly_request_limit=120,
                )
            row["reset_at"] = reset
            row["has_billing"] = row["customer"].startswith("cus_")
            return {
                k: row[k]
                for k in (
                    "has_billing",
                    "reset_at",
                    "monthly_budget",
                    "monthly_spent",
                    "monthly_requests",
                    "monthly_request_limit",
                    "plan",
                    "status",
                    "period_end",
                    "allowance",
                    "spent",
                    "reserved",
                    "available",
                    "concurrency",
                    "credit_balance",
                    "credit_reserved",
                )
            }

    def subscription(
        self, event_id, customer, subscription, plan, status, start, end, approved, *, recheck=None
    ):
        with self.tx() as db:
            if db.execute(text("SELECT id FROM events WHERE id=:id"), {"id": event_id}).first():
                return False
            row = db.execute(
                text("SELECT workspace FROM billing WHERE customer=:c"), {"c": customer}
            ).first()
            if not row:
                raise Denied("Subscription customer is not linked to a workspace.")
            current = self.billing_lock(db, row[0])
            if db.execute(text("SELECT id FROM events WHERE id=:id"), {"id": event_id}).first():
                return False
            if recheck:
                recheck()
            if type(start) is not int or type(end) is not int or start < 0 or end <= start:
                raise Denied("Invalid subscription period.")
            if start < current["period_start"] and current["plan"] != "free":
                raise Denied("Subscription period moved backwards.")
            if (
                current["subscription"]
                and current["subscription"] != subscription
                and current["status"] == "active"
            ):
                raise Denied("A different workspace subscription is already active.")
            hold = db.execute(
                text("SELECT period FROM billing_holds WHERE workspace=:w"), {"w": row[0]}
            ).scalar()
            if hold is not None and start <= hold:
                status = "inactive"
            reset = start > current["period_start"]
            db.execute(
                text("""UPDATE billing SET subscription=:sub, plan=:p, status=:status,
                period_start=:start,period_end=:end,allowance=:allowance,concurrency=:concurrency,
                spent=CASE WHEN :reset=1 THEN 0 ELSE spent END,
                reserved=CASE WHEN :reset=1 THEN 0 ELSE reserved END WHERE customer=:c"""),
                {
                    "sub": subscription,
                    "p": plan,
                    "status": status,
                    "start": start,
                    "end": end,
                    "allowance": approved["allowance_microusd"],
                    "concurrency": approved["concurrency"],
                    "reset": int(reset),
                    "c": customer,
                },
            )
            db.execute(
                text("INSERT INTO events VALUES(:id,:now)"),
                {"id": event_id, "now": int(time.time())},
            )
            return True

    def grant_development(self, user, workspace, amount=2_000_000, *, hours=24):
        """Trusted local operator grant; never a subscription or a public endpoint."""
        if not self.development_ai or type(amount) is not int or not 0 < amount <= 5_000_000:
            raise Denied("Development funding is disabled or exceeds the $5 hard cap.")
        if type(hours) is not int or not 1 <= hours <= 168 or not user or not workspace:
            raise Denied("Invalid development grant.")
        now = int(time.time())
        customer = "development:" + user + ":" + workspace
        with self.tx() as db:
            db.execute(
                text(
                    "INSERT INTO billing(workspace,customer,plan,status,period_start,"
                    "period_end,allowance,concurrency) VALUES(:w,:c,'development',"
                    "'development',:start,:end,:amount,1) "
                    "ON CONFLICT(workspace) DO NOTHING"
                ),
                {
                    "w": workspace,
                    "c": customer,
                    "start": now,
                    "end": now + hours * 3600,
                    "amount": amount,
                },
            )
            row = self.billing_lock(db, workspace)
            if row["customer"] != customer or row["status"] != "development":
                raise Denied("This workspace already has another billing or funding record.")
            # Reruns must not reset spending, renew expiry or replenish a hard cap.
        return self.balance(workspace)

    def development_workspace(self, workspace):
        if not self.development_ai:
            return False
        with self.tx(write=False) as db:
            return (
                db.execute(
                    text(
                        "SELECT workspace FROM billing WHERE workspace=:w "
                        "AND status='development' AND plan='development'"
                    ),
                    {"w": workspace},
                ).first()
                is not None
            )

    def usable_allowance(self, row, user):
        if row["period_end"] <= int(time.time()):
            return False
        if row["status"] in {"active", "trialing"}:
            return True
        return bool(
            self.development_ai
            and row["status"] == "development"
            and row["plan"] == "development"
            and not row["subscription"]
            and row["customer"] == "development:" + user + ":" + row["workspace"]
        )

    def create_run(self, user, workspace, provider, request_key):
        now = int(time.time())
        run_id, token = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        with self.tx() as db:
            if self.engine.dialect.name == "postgresql":
                db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:u,1))"), {"u": user}
                )
            active = db.execute(
                text(
                    "SELECT count(*) FROM runs WHERE user_id=:u AND state='active' AND expires>:now"
                ),
                {"u": user, "now": now},
            ).scalar()
            if active >= 2:
                raise Denied(
                    "Your account already has two active builds. Finish or close one first."
                )
            row = self.refresh_free(db, self.billing_lock(db, workspace))
            if not self.usable_allowance(row, user):
                raise Denied("An active Aedrova plan is required.")
            wallet = self.wallet(db, workspace)
            if wallet["balance"] < 0:
                raise Denied("AI credits require billing review after a refund or dispute.")
            if row["plan"] in self.usage_policy:
                period, _ = budgets.month()
                remaining = (
                    self.usage_policy[row["plan"]]["budget"]
                    - budgets.totals(db, "workspace:" + workspace, period)["used"]
                )
            else:
                remaining = row["allowance"] - row["spent"] - row["reserved"]
            if remaining + wallet["balance"] - wallet["reserved"] <= 0:
                raise Denied("Your workspace's included AI allowance has been used.")
            key = digest(user + workspace + request_key)
            if db.execute(text("SELECT id FROM runs WHERE request_key=:k"), {"k": key}).first():
                raise Denied("This request already has a run. It will not be started twice.")
            count = db.execute(
                text(
                    "SELECT count(*) FROM runs WHERE workspace=:w AND "
                    "state='active' AND expires>:now"
                ),
                {"w": workspace, "now": now},
            ).scalar()
            if count >= row["concurrency"]:
                raise Denied("This workspace is at its concurrent build limit.")
            db.execute(
                text(
                    "INSERT INTO "
                    "runs(id,user_id,workspace,provider,token_hash,expires,r"
                    "equest_key) VALUES(:id,:u,:w,:p,:t,:expires,:key)"
                ),
                {
                    "id": run_id,
                    "u": user,
                    "w": workspace,
                    "p": provider,
                    "t": digest(token),
                    "expires": now
                    + self.usage_policy.get(row["plan"], {}).get("run_seconds", 7200),
                    "key": key,
                },
            )
        return {"id": run_id, "token": token, "expires": now + 7200}

    def run(self, token):
        with self.tx(write=False) as db:
            row = (
                db.execute(
                    text(
                        "SELECT * FROM runs WHERE token_hash=:t AND state='active' AND expires>:now"
                    ),
                    {"t": digest(token), "now": int(time.time())},
                )
                .mappings()
                .first()
            )
            if not row:
                raise Denied("Build access expired. Start a fresh request from Aedrova.")
            return dict(row)

    def end_run(self, run_id, user):
        with self.tx() as db:
            entry = (
                db.execute(
                    text("SELECT workspace,token_hash FROM runs WHERE id=:id AND user_id=:u"),
                    {"id": run_id, "u": user},
                )
                .mappings()
                .first()
            )
            if not entry:
                return
            self.billing_lock(db, entry["workspace"])
            db.execute(text("DELETE FROM sessions WHERE id=:id"), {"id": entry["token_hash"]})
            db.execute(
                text("UPDATE runs SET state='closed' WHERE id=:id AND user_id=:u"),
                {"id": run_id, "u": user},
            )

    def reserve(self, run, request_hash, amount, metadata=None):
        identifier = digest(run["id"] + request_hash)
        with self.tx() as db:
            budgets.lock(db)
            row = self.refresh_free(db, self.billing_lock(db, run["workspace"]))
            fresh = (
                db.execute(text("SELECT state,expires FROM runs WHERE id=:id"), {"id": run["id"]})
                .mappings()
                .one()
            )
            if fresh["state"] != "active" or fresh["expires"] <= int(time.time()):
                raise Denied("Build access expired. Start a fresh request.")
            if not self.usable_allowance(row, run["user_id"]):
                raise Denied("Your subscription is not active.")
            prior = (
                db.execute(text("SELECT * FROM inference WHERE id=:id"), {"id": identifier})
                .mappings()
                .first()
            )
            if prior:
                if prior["state"] == "completed" and prior["response"]:
                    return identifier, self.cipher.decrypt(prior["response"].encode())
                raise Denied(
                    "This model request is already running or has an "
                    "uncertain result. No automatic replay."
                )
            if not self.usable_allowance(row, run["user_id"]):
                raise Denied("Your subscription is not active.")
            if db.execute(
                text("SELECT id FROM inference WHERE run_id=:run AND state='pending' LIMIT 1"),
                {"run": run["id"]},
            ).first():
                raise Denied(
                    "This build already has a model request running. Wait before retrying."
                )
            calls = db.execute(
                text("SELECT count(*) FROM inference WHERE run_id=:id"), {"id": run["id"]}
            ).scalar()
            cap = self.usage_policy.get(row["plan"], {}).get("run_calls", 120)
            if calls >= cap:
                raise Denied("This workflow reached its model-call limit. Start a smaller task.")
            wallet = self.wallet(db, run["workspace"])
            if wallet["balance"] < 0:
                raise Denied("AI credits require billing review after a refund or dispute.")
            base = min(amount, max(0, row["allowance"] - row["spent"] - row["reserved"]))
            if row["plan"] in self.usage_policy:
                period, _ = budgets.month()
                used = budgets.totals(db, "workspace:" + run["workspace"], period)["used"]
                base = min(amount, max(0, self.usage_policy[row["plan"]]["budget"] - used))
            credit = amount - base
            if row["plan"] == "free" and credit:
                raise Denied("Free AI allowance reached. Upgrade or wait for the monthly reset.")
            if credit > wallet["balance"] - wallet["reserved"]:
                raise Denied("Not enough included AI remains for this request. No overage charged.")
            try:
                budgets.reserve(self, db, row, identifier, amount, base)
            except BudgetDenied as error:
                raise Denied(str(error)) from error
            db.execute(
                text("UPDATE billing SET reserved=reserved+:n WHERE workspace=:w"),
                {"n": base, "w": run["workspace"]},
            )
            db.execute(
                text(
                    "INSERT INTO "
                    "inference(id,run_id,period_start,amount,created,base_re"
                    "served,credit_reserved) "
                    "VALUES(:id,:run,:period,:n,:now,:base,:credit)"
                ),
                {
                    "id": identifier,
                    "run": run["id"],
                    "period": row["period_start"],
                    "n": amount,
                    "base": base,
                    "credit": credit,
                    "now": int(time.time()),
                },
            )
            db.execute(
                text("""INSERT INTO inference_details(id,plan,model,rates)
                VALUES(:id,:plan,:model,:rates)"""),
                {
                    "id": identifier,
                    "plan": row["plan"],
                    "model": (metadata or {}).get("id", "unknown"),
                    "rates": json.dumps(
                        {
                            k: v
                            for k, v in (metadata or {}).items()
                            if k.endswith("_rate") and type(v) is int
                        }
                    ),
                },
            )
            db.execute(
                text("UPDATE wallets SET reserved=reserved+:n WHERE workspace=:w"),
                {"n": credit, "w": run["workspace"]},
            )
        self.budget_health()
        return identifier, None

    def settle(self, identifier, actual, response=None, usage=None):
        usage = usage or {}
        with self.tx() as db:
            budgets.lock(db)
            entry = (
                db.execute(
                    text(
                        "SELECT inference.*,runs.workspace FROM inference JOIN "
                        "runs ON runs.id=inference.run_id WHERE inference.id=:id"
                    ),
                    {"id": identifier},
                )
                .mappings()
                .one()
            )
            row = self.billing_lock(db, entry["workspace"])
            # Re-read after taking the workspace lock: concurrent settlement must see the
            # committed state instead of charging an entry twice on PostgreSQL.
            entry = (
                db.execute(text("SELECT * FROM inference WHERE id=:id"), {"id": identifier})
                .mappings()
                .one()
            )
            if entry["state"] != "pending":
                return
            charge = entry["amount"] if actual is None else max(0, actual)
            base_charge = min(charge, entry["base_reserved"])
            credit_charge = charge - base_charge
            budgets.settle(db, identifier, charge, base_charge)
            db.execute(
                text("UPDATE inference_details SET usage=:usage WHERE id=:id"),
                {"id": identifier, "usage": json.dumps(usage)},
            )
            self.wallet(db, row["workspace"])
            db.execute(
                text(
                    "UPDATE wallets SET "
                    "reserved=reserved-:reserved,balance=balance-:charge "
                    "WHERE workspace=:w"
                ),
                {
                    "reserved": entry["credit_reserved"],
                    "charge": credit_charge,
                    "w": row["workspace"],
                },
            )
            if row["period_start"] == entry["period_start"]:
                db.execute(
                    text(
                        "UPDATE billing SET reserved=reserved-:reserved, "
                        "spent=spent+:spent WHERE workspace=:w"
                    ),
                    {
                        "reserved": entry["base_reserved"],
                        "spent": base_charge,
                        "w": row["workspace"],
                    },
                )
            if actual is None:
                response = None
            encrypted = self.cipher.encrypt(response).decode() if response is not None else None
            db.execute(
                text(
                    "UPDATE inference SET "
                    "actual=:actual,state=:state,response=:response,input_to"
                    "kens=:input,output_tokens=:output WHERE id=:id"
                ),
                {
                    "actual": charge,
                    "state": "completed" if response is not None else "uncertain",
                    "response": encrypted,
                    "id": identifier,
                    "input": usage.get("input_tokens"),
                    "output": usage.get("output_tokens"),
                },
            )

    def reconcile_expired(self):
        with self.tx() as db:
            entries = db.execute(
                text(
                    "SELECT inference.id FROM inference JOIN runs ON "
                    "runs.id=inference.run_id WHERE "
                    "inference.state='pending' AND runs.expires<:now LIMIT 500"
                ),
                {"now": int(time.time())},
            ).all()
        for row in entries:
            self.settle(row[0], None)

    def rate_limit(self, key, limit=60, seconds=60):
        now = int(time.time())
        key = digest(key + str(now // seconds))
        with self.tx() as db:
            db.execute(
                text(
                    "INSERT INTO limits VALUES(:id,1,:expires) ON "
                    "CONFLICT(id) DO UPDATE SET count=limits.count+1"
                ),
                {"id": key, "expires": now + seconds},
            )
            count = db.execute(text("SELECT count FROM limits WHERE id=:id"), {"id": key}).scalar()
            if count > limit:
                raise RateLimited(seconds - now % seconds)

    def session(self, token, payload=None, lifetime=3600):
        identifier = digest(token)
        with self.tx(write=payload is not None) as db:
            if payload is not None:
                encrypted = self.cipher.encrypt(json.dumps(payload).encode()).decode()
                db.execute(
                    text(
                        "INSERT INTO sessions VALUES(:id,:payload,:expires) ON "
                        "CONFLICT(id) DO UPDATE SET "
                        "payload=:payload,expires=:expires"
                    ),
                    {
                        "id": identifier,
                        "payload": encrypted,
                        "expires": int(time.time()) + lifetime,
                    },
                )
                return
            row = db.execute(
                text("SELECT payload FROM sessions WHERE id=:id AND expires>:now"),
                {"id": identifier, "now": int(time.time())},
            ).first()
            if not row:
                raise Denied("Sign in with Google to continue.")
            try:
                return json.loads(self.cipher.decrypt(row[0].encode()))
            except Exception as exc:
                raise Denied("Your session expired. Sign in again.") from exc

    def delete_session(self, token):
        with self.tx() as db:
            db.execute(text("DELETE FROM sessions WHERE id=:id"), {"id": digest(token)})

    def maintain(self):
        """Run hourly. Retain monetary ledger; expire private content after 24 hours."""
        self.reconcile_expired()
        now = int(time.time())
        with self.tx() as db:
            db.execute(text("DELETE FROM sessions WHERE expires<=:now"), {"now": now})
            db.execute(text("DELETE FROM limits WHERE expires<=:now"), {"now": now})
            db.execute(
                text("UPDATE inference SET response=NULL WHERE created<:before"),
                {"before": now - 86400},
            )
            db.execute(
                text("UPDATE runs SET state='expired' WHERE state='active' AND expires<=:now"),
                {"now": now},
            )
