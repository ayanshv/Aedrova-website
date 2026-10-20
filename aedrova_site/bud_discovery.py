"""Bounded, fixed-host resource discovery after customer OAuth consent."""

from urllib.parse import urlencode

from aedrova_site.bud_providers import ReadProvider, validate_resource
from aedrova_site.store import Denied

PICKERS = {"github", "supabase", "notion", "vercel"}


def resources(provider, token, transport=None, *, team=""):
    reader = ReadProvider(provider, transport=transport)
    choices = []

    def add(identifier, title):
        identifier = validate_resource(provider, str(identifier))
        if identifier not in {row["id"] for row in choices}:
            choices.append({"id": identifier, "name": str(title or identifier)[:160]})

    try:
        if provider == "vercel":
            params = {"limit": 100}
            if team:
                params["teamId"] = team
            data = reader.request(token, "https://api.vercel.com/v9/projects?" + urlencode(params))
            for project in data.get("projects", [])[:100]:
                add(project["id"], project.get("name"))
        elif provider == "github":
            data = reader.request(token, "https://api.github.com/user/installations?per_page=100")
            installations = data.get("installations", [])
            for installation in installations[:10]:
                identifier = installation.get("id")
                if type(identifier) is not int or identifier <= 0:
                    raise Denied("Could not list authorized repositories.")
                data = reader.request(
                    token,
                    f"https://api.github.com/user/installations/{identifier}/repositories?per_page=100",
                )
                for repo in data.get("repositories", [])[:100]:
                    add(repo["full_name"], repo["full_name"])
        elif provider == "supabase":
            for project in reader.request(
                token, "https://api.supabase.com/v1/projects", list_response=True
            )[:100]:
                add(project.get("ref") or project["id"], project.get("name"))
        elif provider == "notion":
            data = reader.request(
                token,
                "https://api.notion.com/v1/search",
                headers={"Authorization": "Bearer " + token, "Notion-Version": "2022-06-28"},
                body={"page_size": 100, "filter": {"property": "object", "value": "page"}},
            )
            for page in data.get("results", [])[:100]:
                if page.get("archived") or page.get("in_trash"):
                    continue
                title = next(
                    (
                        p.get("title", [])
                        for p in page.get("properties", {}).values()
                        if p.get("type") == "title"
                    ),
                    [],
                )
                add(
                    page["id"],
                    "".join(part.get("plain_text", "") for part in title) or "Untitled page",
                )
        return sorted(choices, key=lambda row: row["name"].casefold())
    except (KeyError, TypeError, AttributeError, ValueError):
        raise Denied("Could not list authorized resources. Reconnect and try again.") from None
    finally:
        reader.close()
