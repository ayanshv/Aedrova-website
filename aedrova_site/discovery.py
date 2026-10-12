"""Public, factual discovery metadata. Crawling never grants access to private data."""

from xml.sax.saxutils import escape

CANONICAL = "https://aedrova.com"
DESCRIPTION = (
    "Aedrova is a collaborative AI workspace for startup teams, combining team chat, "
    "configurable AI teammates called Buds, and coding agents that build from shared context."
)
PUBLIC_PAGES = {
    "/": ("Aedrova — Your team, plus AI", DESCRIPTION),
    "/product": ("What is Aedrova? AI workspace, Buds and team building", DESCRIPTION),
    "/plans": (
        "Aedrova plans — One subscription for your team",
        (
            "Explore Aedrova's intended Free, Pro, Team and Enterprise workspace plans. One "
            "paid subscription covers the team; current availability is shown on the page."
        ),
    ),
    "/waitlist": (
        "Join the Aedrova waitlist",
        (
            "Register for Aedrova launch updates: team collaboration, configurable Buds and "
            "AI-assisted software building."
        ),
    ),
    "/enterprise": (
        "Aedrova for your team — Enterprise inquiries",
        (
            "Discuss your team's workflows, scope and requirements with Aedrova. An inquiry "
            "does not create a subscription."
        ),
    ),
    "/support": (
        "Aedrova customer support",
        (
            "Contact Aedrova and find account, connector, billing and privacy troubleshooting "
            "guidance."
        ),
    ),
    "/privacy": (
        "Aedrova Privacy policy",
        (
            "How Aedrova handles workspace content, AI context, connected accounts, voice and "
            "meeting data, and privacy requests."
        ),
    ),
    "/terms": (
        "Aedrova Terms of service",
        (
            "Aedrova's service terms: team workspaces, AI responsibilities, software "
            "licensing, billing and liability."
        ),
    ),
    "/data-controls": (
        "Aedrova data and AI controls",
        (
            "Understand context permissions, disconnect connections and request access, "
            "export or deletion of Aedrova data."
        ),
    ),
    "/subprocessors": (
        "Aedrova service providers",
        (
            "Infrastructure, AI providers and optional connected services used by enabled "
            "Aedrova features."
        ),
    ),
    "/cookies": (
        "Aedrova cookies and browser storage",
        "Aedrova's functional browser storage, preferences and session information.",
    ),
    "/acceptable-use": (
        "Aedrova Acceptable Use policy",
        "Authorized, responsible use of Aedrova, Buds and connected tools.",
    ),
    "/security": (
        "Aedrova security and Beta availability",
        "Aedrova's access controls, vulnerability reporting and actual Beta availability.",
    ),
}
PRIVATE_PATHS = (
    "/api/",
    "/dots/",
    "/auth/",
    "/account",
    "/welcome",
    "/onboarding",
    "/download",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def public_deployment(config):
    return (
        config.origin.rstrip("/") in {CANONICAL, "https://www.aedrova.com"}
        and getattr(config, "deployment_environment", "") != "staging"
    )


def metadata(config, path, fallback):
    title, description = PUBLIC_PAGES.get(path, (fallback + " · Aedrova", DESCRIPTION))
    indexable = public_deployment(config) and path in PUBLIC_PAGES
    graph = None
    if indexable and path in {"/", "/product"}:
        graph = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "@id": CANONICAL + "/#brand",
                    "name": "Aedrova",
                    "url": CANONICAL + "/",
                    "logo": CANONICAL + "/static/brand.png",
                    "email": "contact@aedrova.com",
                },
                {
                    "@type": "WebSite",
                    "@id": CANONICAL + "/#website",
                    "name": "Aedrova",
                    "url": CANONICAL + "/",
                    "publisher": {"@id": CANONICAL + "/#brand"},
                },
                {
                    "@type": "SoftwareApplication",
                    "@id": CANONICAL + "/#application",
                    "name": "Aedrova",
                    "url": CANONICAL + "/product",
                    "description": DESCRIPTION,
                    "applicationCategory": "BusinessApplication",
                    "publisher": {"@id": CANONICAL + "/#brand"},
                },
            ],
        }
    return {
        "title": title,
        "description": description,
        "canonical": CANONICAL + path,
        "robots": "index, follow, max-image-preview:large" if indexable else "noindex, follow",
        "graph": graph,
    }


def robots(config):
    if not public_deployment(config):
        return "User-agent: *\nDisallow: /\n"
    # Search access is distinct from training. Google-Extended also controls Gemini
    # grounding; allow public pages under this mixed-purpose token for this goal.
    groups = ["User-agent: *\n" + "\n".join("Disallow: " + p for p in PRIVATE_PATHS)]
    for agent in (
        "OAI-SearchBot",
        "ChatGPT-User",
        "Claude-SearchBot",
        "Claude-User",
        "Google-Extended",
    ):
        groups.append(
            "User-agent: " + agent + "\n" + "\n".join("Disallow: " + p for p in PRIVATE_PATHS)
        )
    groups.extend(
        [
            "User-agent: GPTBot\nDisallow: /",
            "User-agent: ClaudeBot\nDisallow: /",
            "Sitemap: " + CANONICAL + "/sitemap.xml",
        ]
    )
    return "\n\n".join(groups) + "\n"


def sitemap(config):
    pages = PUBLIC_PAGES if public_deployment(config) else {}
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join("<url><loc>" + escape(CANONICAL + p) + "</loc></url>" for p in pages)
        + "</urlset>"
    )
