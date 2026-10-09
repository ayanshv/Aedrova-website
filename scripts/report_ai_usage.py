"""Private operator report. No public route and no prompts, secrets or email addresses."""

import json

from sqlalchemy import text

from aedrova_site.app import create_app
from aedrova_site.budgets import month


def report(store):
    period, reset = month()
    with store.tx(write=False) as db:
        rows = (
            db.execute(
                text("""SELECT r.workspace,r.user_id,r.provider,
            COALESCE(d.plan,'legacy') AS plan,COALESCE(d.model,'unknown') AS model,
            COUNT(*) AS requests,COALESCE(SUM(i.input_tokens),0) AS input_tokens,
            COALESCE(SUM(i.output_tokens),0) AS output_tokens,
            COALESCE(SUM(COALESCE(i.actual,i.amount)),0) AS estimated_microusd
            FROM inference i JOIN runs r ON r.id=i.run_id
            LEFT JOIN inference_details d ON d.id=i.id
            WHERE i.created>=:start AND i.created<:end
            GROUP BY r.workspace,r.user_id,r.provider,d.plan,d.model"""),
                {"start": period, "end": reset},
            )
            .mappings()
            .all()
        )
        conversions = (
            db.execute(
                text("""SELECT plan,COUNT(*) AS workspaces
            FROM billing GROUP BY plan""")
            )
            .mappings()
            .all()
        )
    return {
        "period_start": period,
        "reset_at": reset,
        "usage": [dict(r) for r in rows],
        "current_plan_distribution": [dict(r) for r in conversions],
        "budget": store.budget_health(),
    }


def main():
    app = create_app()
    try:
        print(json.dumps(report(app.state.store), indent=2))
    finally:
        app.state.store.engine.dispose()


if __name__ == "__main__":
    main()
