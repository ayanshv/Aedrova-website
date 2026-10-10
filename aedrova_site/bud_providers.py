"""Resource-scoped read adapters. No model-controlled host, credential or write operation."""

import json
import re
from urllib.parse import urlencode
from uuid import UUID

import httpx

from aedrova_site.store import Denied

# Each entry declares the complete executable surface; everything else fails closed.
CATALOG = {
    "github": (
        "GitHub",
        "Code & delivery",
        "Repository changes, issues and deployments",
        "owner/repository",
        {
            "repository": "Repository",
            "changes": "Recent commits",
            "issues": "Open issues",
            "deployments": "Deployments",
        },
    ),
    "supabase": (
        "Supabase",
        "Code & delivery",
        "Project health and region; no rows, SQL or keys",
        "project reference",
        {"project": "Project health"},
    ),
    "figma": (
        "Figma",
        "Design & knowledge",
        "File structure and design labels",
        "file key",
        {"design": "Design file"},
    ),
    "notion": (
        "Notion",
        "Design & knowledge",
        "An explicitly shared page and its immediate blocks",
        "page UUID",
        {"page": "Page content"},
    ),
    "stripe": (
        "Stripe",
        "Finance",
        "Account balance; no customer personal data",
        "acct_ account ID",
        {"balance": "Available and pending balance"},
    ),
    "instagram": (
        "Instagram",
        "Marketing",
        "Professional account profile and recent posts",
        "Instagram user ID",
        {"profile": "Profile", "posts": "Recent posts"},
    ),
    "tiktok": (
        "TikTok",
        "Marketing",
        "Authorized profile and recent public videos",
        "TikTok open_id",
        {"profile": "Profile", "videos": "Recent videos"},
    ),
    "search": (
        "Web search",
        "Research",
        "Brave Search results for your saved research topic",
        "research topic",
        {"search": "Web search"},
    ),
    "vercel": (
        "Vercel",
        "Code & delivery",
        "Project metadata and recent deployments",
        "prj_ project ID",
        {"project": "Project", "deployments": "Deployments"},
    ),
}


def descriptor(key):
    name, group, description, hint, tools = CATALOG[key]
    return {
        "id": key,
        "name": name,
        "group": group,
        "description": description,
        "resource_hint": hint,
        "tools": tools,
        "auth": "Access token",
        "permissions": "Read-only: " + description,
        "configurable": True,
        "available": True,
    }


def validate_resource(provider, value):
    value = value.strip()
    if provider not in CATALOG or not value or len(value) > 200:
        raise Denied("Choose a supported tool and resource.")
    if provider == "search":
        if len(value) < 3 or any(ord(c) < 32 for c in value):
            raise Denied("Enter a research topic of 3–200 characters.")
        return value
    if provider in {"notion"}:
        try:
            return str(UUID(value))
        except ValueError:
            raise Denied("Use the page or team UUID, not its URL.") from None
    patterns = {
        "github": r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}",
        "supabase": r"[a-z]{20}",
        "figma": r"[A-Za-z0-9_-]{5,100}",
        "stripe": r"acct_[A-Za-z0-9]{5,100}",
        "instagram": r"[0-9]{5,40}",
        "tiktok": r"[A-Za-z0-9_-]{5,150}",
        "vercel": r"prj_[A-Za-z0-9]{5,100}",
    }
    if not re.fullmatch(patterns[provider], value) or ".." in value:
        raise Denied("Use the resource identifier shown for this tool, not a URL or credentials.")
    return value


class ReadProvider:
    def __init__(self, key, *, transport=None):
        self.key = key
        self.client = httpx.Client(
            timeout=httpx.Timeout(12, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def request(self, token, url, *, headers=None, body=None, list_response=False):
        try:
            # URLs below are constructed exclusively by these adapters, never provider payloads.
            with self.client.stream(
                "POST" if body is not None else "GET",
                url,
                headers=headers or {"Authorization": "Bearer " + token},
                json=body,
            ) as response:
                if response.status_code == 401:
                    raise Denied("Needs authorization")
                if response.status_code in {403, 404}:
                    raise Denied("Permission issue")
                if response.status_code == 429:
                    raise Denied("Provider rate limit reached. Try again later.")
                response.raise_for_status()
                payload = bytearray()
                for block in response.iter_bytes():
                    payload.extend(block)
                    if len(payload) > 512 * 1024:
                        raise Denied("Provider data is too large. Choose a smaller resource.")
                result = json.loads(payload)
                if not isinstance(result, list if list_response else dict):
                    raise Denied("Unsupported provider response.")
                return result
        except Denied:
            raise
        except (httpx.HTTPError, ValueError):
            raise Denied("The provider is temporarily unavailable. Retry shortly.") from None

    def execute(self, token, resource, tool, *, oauth=False):
        try:
            return self._execute(token, resource, tool, oauth=oauth)
        except (AttributeError, TypeError, KeyError, IndexError):
            raise Denied("Unsupported provider response. Retry shortly.") from None

    def _execute(self, token, resource, tool, *, oauth=False):
        resource = validate_resource(self.key, resource)
        if tool not in CATALOG[self.key][4]:
            raise Denied("This tool is not available.")
        get = lambda url, **kw: self.request(token, url, **kw)  # noqa: E731
        records = None
        source = ""
        coverage = "Bounded resource snapshot; no complete-history claim"
        if self.key == "notion":
            headers = {"Authorization": "Bearer " + token, "Notion-Version": "2026-03-11"}
            page = get("https://api.notion.com/v1/pages/" + resource, headers=headers)
            if page.get("id", "").replace("-", "") != resource.replace("-", ""):
                raise Denied("Notion returned a different page.")
            blocks = get(
                "https://api.notion.com/v1/blocks/" + resource + "/children?page_size=20",
                headers=headers,
            )

            def text(items):
                return "".join(str(t.get("plain_text", "")) for t in items if isinstance(t, dict))[
                    :2000
                ]

            records = {
                "title": [
                    text(v.get("title", []))
                    for v in page.get("properties", {}).values()
                    if isinstance(v, dict) and v.get("type") == "title"
                ],
                "blocks": [
                    {
                        "type": b.get("type"),
                        "text": text(b.get(b.get("type"), {}).get("rich_text", [])),
                    }
                    for b in blocks.get("results", [])[:20]
                ],
            }
            source = "https://www.notion.so/" + resource.replace("-", "")
            coverage = "Up to 20 immediate blocks; nested blocks and pagination not included"
        elif self.key == "figma":
            row = get(
                "https://api.figma.com/v1/files/" + resource + "?depth=2",
                headers={"Authorization": "Bearer " + token} if oauth else {"X-Figma-Token": token},
            )
            if not isinstance(row.get("name"), str) or not isinstance(row.get("document"), dict):
                raise Denied("Unsupported Figma response.")
            records = {
                "name": row.get("name"),
                "last_modified": row.get("lastModified"),
                "pages": [
                    {
                        "name": p.get("name"),
                        "frames": [
                            str(f.get("name", ""))[:300] for f in p.get("children", [])[:20]
                        ],
                    }
                    for p in row.get("document", {}).get("children", [])[:20]
                ],
            }
            source = "https://www.figma.com/design/" + resource
            coverage = "Top 20 pages and 20 top-level frames per page; no image analysis"
        elif self.key == "supabase":
            row = get("https://api.supabase.com/v1/projects/" + resource)
            if row.get("id") != resource:
                raise Denied("The project does not match the selected resource.")
            records = {k: row.get(k) for k in ("id", "name", "region", "status", "created_at")}
            source = "https://supabase.com/dashboard/project/" + resource
        elif self.key == "stripe":
            if not oauth and not token.startswith(("rk_live_", "rk_test_")):
                raise Denied(
                    "Use a restricted read-only Stripe key, not a secret or publishable key."
                )
            account = get("https://api.stripe.com/v1/account")
            if account.get("id") != resource:
                raise Denied("This key belongs to a different Stripe account.")
            row = get("https://api.stripe.com/v1/balance")
            records = {
                "livemode": row.get("livemode"),
                **{
                    k: [
                        {"amount": r.get("amount"), "currency": r.get("currency")}
                        for r in row.get(k, [])[:20]
                    ]
                    for k in ("available", "pending")
                },
            }
            source = "https://dashboard.stripe.com/balance"
            coverage = "Balance in minor currency units; not revenue, profit or accounting advice"
        elif self.key == "instagram":
            fields = (
                ("id,user_id,username,media_count" if oauth else "id,username,media_count")
                if tool == "profile"
                else "id,caption,media_type,permalink,timestamp"
            )
            path = resource if tool == "profile" else resource + "/media"
            row = get(
                "https://graph.instagram.com/v25.0/"
                + path
                + "?"
                + urlencode({"fields": fields, "limit": 10})
            )
            if (
                tool == "profile"
                and str((row.get("user_id") or row.get("id")) if oauth else row.get("id"))
                != resource
            ):
                raise Denied("Instagram returned a different account.")
            records = (
                {k: row.get(k) for k in ("id", "username", "media_count")}
                if tool == "profile"
                else [
                    {
                        k: str(r.get(k, ""))[:1500]
                        for k in ("id", "caption", "media_type", "permalink", "timestamp")
                    }
                    for r in row.get("data", [])[:10]
                ]
            )
            source = "https://www.instagram.com/"
            coverage = "Professional account only; up to 10 posts; no posting or messaging"
        elif self.key == "tiktok":
            profile = get("https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name")
            if profile.get("error", {}).get("code") != "ok":
                raise Denied("Needs authorization")
            user = profile.get("data", {}).get("user", {})
            if user.get("open_id") != resource:
                raise Denied("TikTok returned a different account.")
            records = {k: user.get(k) for k in ("open_id", "display_name")}
            if tool == "videos":
                row = get(
                    "https://open.tiktokapis.com/v2/video/list/?fields=id,title,create_time,share_url",
                    body={"max_count": 10},
                )
                if row.get("error", {}).get("code") != "ok":
                    raise Denied("Permission issue")
                records = [
                    {
                        k: str(r.get(k, ""))[:1500]
                        for k in ("id", "title", "create_time", "share_url")
                    }
                    for r in row.get("data", {}).get("videos", [])[:10]
                ]
            source = "https://www.tiktok.com/"
            coverage = "Up to 10 public videos; no posting or direct messages"
        elif self.key == "search":
            row = get(
                "https://api.search.brave.com/res/v1/web/search?"
                + urlencode({"q": resource, "count": 5}),
                headers={"X-Subscription-Token": token, "Accept": "application/json"},
            )
            records = [
                {k: str(r.get(k, ""))[:1500] for k in ("title", "url", "description")}
                for r in row.get("web", {}).get("results", [])[:5]
            ]
            source = "https://search.brave.com/search?" + urlencode({"q": resource})
            coverage = "Up to 5 search snippets; linked pages are not fetched"
        elif self.key == "vercel":
            team = oauth.get("team", "") if isinstance(oauth, dict) else ""
            if team and not re.fullmatch(r"team_[A-Za-z0-9]{1,100}", team):
                raise Denied("Unsupported Vercel account.")
            if tool == "project":
                row = get(
                    "https://api.vercel.com/v9/projects/"
                    + resource
                    + ("?" + urlencode({"teamId": team}) if team else "")
                )
                if row.get("id") != resource:
                    raise Denied("Vercel returned a different project.")
                records = {k: row.get(k) for k in ("id", "name", "framework", "updatedAt")}
            else:
                row = get(
                    "https://api.vercel.com/v6/deployments?"
                    + urlencode(
                        {"projectId": resource, "limit": 10, **({"teamId": team} if team else {})}
                    )
                )
                records = [
                    {k: r.get(k) for k in ("uid", "name", "state", "created", "target")}
                    for r in row.get("deployments", [])[:10]
                ]
            source = "https://vercel.com/dashboard"
        else:
            raise Denied("This provider has no adapter.")
        # Never return provider credentials, raw headers, or unbounded response objects.
        serialized = json.dumps(records, ensure_ascii=False)
        if len(serialized.encode()) > 64 * 1024:
            raise Denied("The selected evidence is too large.")
        if token in serialized or re.search(
            r"(?:gh[pousr]_[A-Za-z0-9]{20,}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]+|"
            r"sk-[A-Za-z0-9_-]{20,}|(?:sbp|ntn|figd)_[A-Za-z0-9_-]{20,}|"
            r"-----BEGIN .*PRIVATE KEY)",
            serialized,
        ):
            raise Denied("Sensitive provider content was withheld.")
        return {"records": records, "source": source, "coverage": coverage, "untrusted": True}
