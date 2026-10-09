"""Shared verified-connection presentation for every Bud provider."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from aedrova_site.bud_providers import CATALOG

COPY = {
    "github": "can now read your repository, issues, pull requests and deployments.",
    "supabase": (
        "can now check your project’s health and region. Database rows and keys stay private."
    ),
    "figma": "can now explore the structure and labels in your selected design file.",
    "notion": "can now read the page you shared and its content.",
    "stripe": "can now check your account’s available and pending balance.",
    "instagram": "can now review your professional profile and recent posts.",
    "tiktok": "can now review your authorized profile and recent public videos.",
    "search": "can now find web sources for your selected research topic.",
    "vercel": "can now check your project and recent deployments.",
    "linear": "can now read your selected team and recent issues.",
}
TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")


def confirmation(request, provider, bud):
    looks = ("builder", "designer", "marketing", "finance", "research", "product")
    look = bud.get("appearance", "auto")
    if look not in looks:
        role = str(bud.get("role", "builder")).lower().split(" · ")[0]
        look = role if role in looks else "builder"
    return TEMPLATES.TemplateResponse(
        request=request,
        name="bud-connected.html",
        context={
            "provider": CATALOG[provider][0],
            "bud_name": bud["name"],
            "look": look,
            "capability": COPY[provider],
        },
    )
