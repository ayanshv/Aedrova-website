"""Report OAuth readiness and callbacks without printing credentials."""

import json
import os

PROVIDERS = ("github", "figma", "notion", "supabase", "tiktok", "stripe", "instagram", "vercel")


def main():
    origin = os.environ.get("AEDROVA_ORIGIN", "http://127.0.0.1:8090").rstrip("/")
    result = {}
    for provider in PROVIDERS:
        prefix = "GITHUB_DOT" if provider == "github" else provider.upper() + "_BUD"
        client_id = os.environ.get("AEDROVA_" + prefix + "_CLIENT_ID", "")
        secret = os.environ.get("AEDROVA_" + prefix + "_CLIENT_SECRET", "")
        result[provider] = {
            "credentials_configured": bool(client_id and secret),
            "partial_configuration": bool(client_id) != bool(secret),
            "https_required": provider in {"supabase", "tiktok", "stripe", "instagram", "vercel"},
            "callback_ready": provider
            not in {"supabase", "tiktok", "stripe", "instagram", "vercel"}
            or origin.startswith("https://"),
            "callback": origin + "/buds/oauth/" + provider + "/callback",
        }
    result["search"] = {
        "managed_key_configured": bool(os.environ.get("AEDROVA_SEARCH_BUD_KEY")),
        "customer_key_required": False,
    }
    result["vercel"]["slug_configured"] = bool(os.environ.get("AEDROVA_VERCEL_BUD_SLUG"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
