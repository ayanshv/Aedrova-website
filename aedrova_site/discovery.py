"""Public, factual discovery metadata. Crawling never grants access to private data."""

from xml.sax.saxutils import escape

from aedrova_site.team import TEAM_MEMBERS, anchor

CANONICAL = "https://aedrova.com"
PUBLIC_ICONS = frozenset({"/favicon.ico", "/favicon.png", "/static/checkout-icon.png"})
DESCRIPTION = (
    "Aedrova is a collaborative AI workspace for startup teams, combining team chat, "
    "configurable AI teammates called Buds, and coding agents that build from shared context."
)
PUBLIC_PAGES = {
    "/team": (
        "Aedrova co-founders and team | Ayansh, Minh-Khoa, Abhinav and Joash",
        "Meet Aedrova’s co-founders Ayansh Varma, Minh-Khoa Nguyen and Abhinav "
        "Thirumala, and Director of Communication Joash Thomas.",
    ),
    "/faq": (
        "Aedrova FAQ | Buds, building, access and pricing",
        "Answers about workspaces, AI teammates, connectors, privacy and Beta availability.",
    ),
    "/about": (
        "About Aedrova",
        "Learn what Aedrova does, who its co-founders are, and how to contact the team.",
    ),
    "/research/crawlability": (
        "Aedrova crawlability study | October 22, 2026",
        "A reproducible audit of public page availability, crawler access and indexing signals.",
    ),
    "/refunds": (
        "Aedrova refund policy",
        "Cancellation, refund requests and preserved consumer rights.",
    ),
    "/": ("Aedrova | The workspace for your team and tools", DESCRIPTION),
    "/product": ("What is Aedrova? AI workspace, Buds and team building", DESCRIPTION),
    "/plans": (
        "Aedrova plans | One subscription for your team",
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
        "Aedrova for your team | Enterprise inquiries",
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
    "/buds/",
    "/gateway/",
    "/unsubscribe",
    "/auth/",
    "/account",
    "/welcome",
    "/onboarding",
    # Let crawlers see /download's waitlist redirect (or its noindex landing page).
    # Blocking the landing URL hides both signals and can leave a bare URL indexed.
    # Actual downloads remain protected by /api/ and the server release gate.
    "/download/",
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


def organization(*, include_founders=False):
    brand = {
        "@type": "Organization",
        "@id": CANONICAL + "/#brand",
        "name": "Aedrova",
        "url": CANONICAL + "/",
        "description": DESCRIPTION,
        "logo": CANONICAL + "/favicon.png",
        "email": "contact@aedrova.com",
    }
    if include_founders:
        brand["founder"] = [
            {
                "@type": "Person",
                "@id": CANONICAL + "/team#" + anchor(member),
                "name": member["name"],
                "url": CANONICAL + "/team#" + anchor(member),
            }
            for member in TEAM_MEMBERS
            if member["tier"] == "founders"
        ]
    return brand


def metadata(config, path, fallback):
    title, description = PUBLIC_PAGES.get(path, (fallback + " · Aedrova", DESCRIPTION))
    indexable = public_deployment(config) and path in PUBLIC_PAGES
    graph = None
    if indexable and path in {"/", "/product"}:
        graph = {
            "@context": "https://schema.org",
            "@graph": [
                organization(include_founders=path == "/"),
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
    if indexable and path in {"/faq", "/research/crawlability"}:
        graph = {
            "@context": "https://schema.org",
            "@type": "Article" if path == "/research/crawlability" else "WebPage",
            "headline": title,
            "name": title,
            "url": CANONICAL + path,
            "datePublished": "2026-10-22",
            "author": {
                "@type": "Organization",
                "name": "Aedrova team",
                "url": CANONICAL + "/about",
            },
            "publisher": {"@type": "Organization", "name": "Aedrova", "url": CANONICAL},
        }
    if indexable and path in {"/team", "/about"}:
        people = []
        for member in TEAM_MEMBERS:
            person = {
                "@type": "Person",
                "@id": CANONICAL + "/team#" + anchor(member),
                "url": CANONICAL + "/team#" + anchor(member),
                "name": member["name"],
                "jobTitle": member["role"],
                "worksFor": {"@id": CANONICAL + "/#brand"},
            }
            if path == "/team":
                person["description"] = member["bio"]
                if member.get("photo"):
                    person["image"] = CANONICAL + member["photo"]
            people.append(person)
        graph = {
            "@context": "https://schema.org",
            "@graph": [
                organization(include_founders=True),
                {
                    "@type": "AboutPage",
                    "@id": CANONICAL + path + "#webpage",
                    "url": CANONICAL + path,
                    "name": title,
                    "description": description,
                    "about": {"@id": CANONICAL + "/#brand"},
                    "mainEntity": [{"@id": person["@id"]} for person in people],
                    "publisher": {"@id": CANONICAL + "/#brand"},
                    "author": {
                        "@type": "Organization",
                        "name": "Aedrova team",
                        "url": CANONICAL + "/about",
                    },
                    "datePublished": "2026-10-22" if path == "/about" else "2026-10-27",
                    "dateModified": "2026-10-27",
                },
                *people,
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
        "GPTBot",
        "ClaudeBot",
    ):
        groups.append(
            "User-agent: " + agent + "\n" + "\n".join("Disallow: " + p for p in PRIVATE_PATHS)
        )
    groups.append("Sitemap: " + CANONICAL + "/sitemap.xml")
    return "\n\n".join(groups) + "\n"


def sitemap(config):
    pages = PUBLIC_PAGES if public_deployment(config) else {}
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join("<url><loc>" + escape(CANONICAL + p) + "</loc></url>" for p in pages)
        + "</urlset>"
    )
