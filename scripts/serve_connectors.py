"""Render entry point for the isolated Bud connection service."""

from scripts.serve import main

if __name__ == "__main__":
    main("aedrova_site.connector_service:create_connector_app")
