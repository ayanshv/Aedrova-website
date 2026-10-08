"""Pulse projections over the same authorized, encrypted Dot evidence used by agents."""

import hashlib
import time
from datetime import datetime
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict

from aedrova_site.store import Denied

PERIODS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "12m": 365}
TTL = 300


def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return int(dt.timestamp())
    except (ValueError, TypeError, OverflowError):
        return None


def github_projection(evidence, period, now):
    """Observed activity only. A bounded feed cannot establish total volume or causality."""
    tool = evidence["tool"]
    specs = {
        "changes": ("Commits observed", "CodeChange", "date"),
        "issues": ("Open pull requests", "PullRequest", "updated_at"),
        "deployments": ("Deployments observed", "Deployment", "created_at"),
    }
    if tool not in specs:
        return None
    title, kind, date_key = specs[tool]
    records = evidence.get("records", [])
    if not isinstance(records, list):
        return None
    start = now - PERIODS[period] * 86400
    items, trend = [], [0] * min(PERIODS[period], 30)
    unknown = 0
    for row in records:
        if not isinstance(row, dict) or row.get("kind") != kind:
            continue
        date = timestamp(row.get(date_key))
        if tool != "issues" and date is None:
            unknown += 1
            continue
        if tool != "issues" and not start <= date <= now:
            continue
        item = {
            "id": str(row.get("id") or row.get("number") or ""),
            "title": str(
                row.get("title") or row.get("summary") or row.get("environment") or "Activity"
            )[:500],
            "detail": str(row.get("summary") or row.get("ref") or "")[:1200],
            "timestamp": date,
            "citation": evidence["citation"],
        }
        items.append(item)
        if date is not None and start <= date <= now:
            index = min(len(trend) - 1, int((date - start) * len(trend) / (now - start)))
            trend[index] += 1
    items.sort(key=lambda item: item["timestamp"] or 0, reverse=True)
    return {
        "id": evidence["dot"] + ":" + tool,
        "metric": tool,
        "category": "Engineering",
        "label": title,
        "value": len(items),
        "unit": "observed" if tool != "issues" else "in sample",
        "period": "current" if tool == "issues" else period,
        "change_percent": None,
        "comparison": "Unavailable: bounded source history",
        "source": evidence["provider"],
        "dot": evidence["dot"],
        "dot_name": evidence["name"],
        "source_url": evidence.get("source", ""),
        "citation": evidence["citation"],
        "updated_at": evidence["fetched_at"],
        "coverage": evidence.get("coverage", "Bounded source history"),
        "unknown_dates": unknown,
        "trend": trend if tool != "issues" else [],
        "items": items,
    }


# Provider modules register projections and bounded overview capabilities here;
# desktop and model use the original Dot tool registry, never separate credentials.
PROJECTORS = {"github": github_projection}
OVERVIEW_TOOLS = {"github": ("changes", "issues", "deployments")}


class PulseService:
    def __init__(self, dots):
        self.dots = dots

    def snapshot(self, token, workspace, period="7d"):
        if period not in PERIODS:
            raise Denied("Choose a supported time range.")
        rows = self.dots.list(token, workspace)
        user = self.dots.identity.require(token, workspace)["id"]
        metrics, sources, signals = [], [], []
        now = int(time.time())
        grants = {}
        for row in rows:
            source = {
                k: row[k] for k in ("id", "name", "provider", "status", "last_sync", "version")
            }
            source["cached"] = 0
            if row["status"] in {"Connected", "Error", "Syncing"}:
                dot = row
                grant = self.dots.grant(dot, user)
                grants[row["id"]] = (user, grant["secret"] if grant else None)
                for tool in OVERVIEW_TOOLS.get(row["provider"], ()):
                    evidence = self.dots.cached(dot, user, grant, tool, stale=True)
                    if not evidence:
                        continue
                    metric = PROJECTORS[row["provider"]](evidence, period, now)
                    if metric:
                        metric["stale"] = (
                            now - metric["updated_at"] >= TTL
                            or not grant["synced"]
                            or bool(evidence.get("read_failed_at"))
                        )
                        metrics.append(metric)
                        source["cached"] += 1
                        if tool != "issues" and metric["items"]:
                            item = metric["items"][0]
                            signals.append(
                                {
                                    "metric_id": metric["id"],
                                    "title": item["title"],
                                    "timestamp": item["timestamp"],
                                    "source": row["name"],
                                    "citation": metric["citation"],
                                    "stale": metric["stale"],
                                }
                            )
            sources.append(source)
        # Recheck membership and every grant before releasing any cached evidence.
        live = {r["id"]: r for r in self.dots.list(token, workspace)}
        for row in rows:
            fresh = live.get(row["id"])
            if not fresh or fresh["version"] != row["version"] or fresh["status"] != row["status"]:
                raise Denied("Source access changed. Refresh Pulse.")
            if row["id"] in grants:
                user, secret = grants[row["id"]]
                grant = self.dots.grant(fresh, user)
                if not grant or grant["secret"] != secret or grant["expires"] <= time.time():
                    raise Denied("Source access changed. Refresh Pulse.")
        return {
            "workspace": workspace,
            "period": period,
            "metrics": metrics,
            "sources": sources,
            "signals": sorted(signals, key=lambda s: s["timestamp"], reverse=True)[:8],
            "generated_at": now,
        }

    def refresh(self, token, workspace, dot_id, period):
        if period not in PERIODS:
            raise Denied("Choose a supported time range.")
        dot, _ = self.dots.dot(token, workspace, dot_id)
        tools = OVERVIEW_TOOLS.get(dot["provider"], ())
        if not tools:
            raise Denied("This provider has no Pulse capabilities yet.")
        errors = []
        for tool in tools:
            try:
                self.dots.execute(token, workspace, [{"dot": dot_id, "tool": tool}], refresh=True)
            except Denied:
                # Do not leak provider payloads or abort other sources on transient failure.
                errors.append(tool)
        snapshot = self.snapshot(token, workspace, period)
        snapshot["failed_tools"] = errors
        for metric in snapshot["metrics"]:
            if metric["dot"] == dot_id and metric["metric"] in errors:
                metric["stale"] = True
        return snapshot


class RefreshBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: UUID
    dot: UUID
    period: str = "7d"


def install(app, dots, auth):
    service = PulseService(dots)
    app.state.pulse = service

    @app.get("/api/pulse")
    def snapshot(request: Request, workspace: UUID, period: str = "7d"):
        return service.snapshot(auth(request), str(workspace), period)

    @app.post("/api/pulse/refresh")
    def refresh(request: Request, body: RefreshBody):
        token = auth(request, change=True)
        if body.period not in PERIODS:
            raise Denied("Choose a supported time range.")
        dots.store.rate_limit("pulse:" + hashlib.sha256(token.encode()).hexdigest(), limit=12)
        return service.refresh(token, str(body.workspace), str(body.dot), body.period)
