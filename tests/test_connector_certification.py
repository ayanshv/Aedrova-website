"""Catalog-wide grant lifecycle checks, with synthetic provider responses only."""

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_bud_connections import connections as _connections
from test_bud_connections import system as _system
from test_dots import system as _dot_system

from aedrova_site.bud_providers import CATALOG
from aedrova_site.store import Denied

connections = _connections
system = _system
dot_system = _dot_system
RESOURCES = {
    "github": "owner/repository",
    "supabase": "a" * 20,
    "figma": "fileKey123",
    "notion": "11111111-1111-1111-1111-111111111111",
    "stripe": "acct_Test123",
    "instagram": "123456789",
    "tiktok": "actor_test_123",
    "vercel": "prj_Project123",
    "search": "startup competitor research",
}


@pytest.mark.parametrize("provider", sorted(CATALOG))
def test_every_catalog_grant_is_private_versioned_reconnectable_and_revocable(
    connections, provider
):
    service, dot, owner = connections
    reader = service.providers[provider]
    reader.execute = MagicMock(return_value={"records": [], "untrusted": True})
    args = (
        "session",
        dot["workspace_id"],
        dot["id"],
        provider,
        RESOURCES[provider],
        "synthetic-private-access",
        24,
    )
    saved = service.connect(*args)
    assert reader.execute.call_count == len(CATALOG[provider][4])
    tool = next(iter(CATALOG[provider][4]))
    result = service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + "." + tool)
    assert result["provider"] == provider and result["untrusted"]
    assert "synthetic-private-access" not in json.dumps(service.listing(dot, owner))
    with service.store.tx() as db:
        assert (
            "synthetic-private-access"
            not in db.execute(text("SELECT secret FROM bud_connections")).scalar()
        )
    service.dots.identity.require.return_value = {"id": str(uuid4())}
    assert service.listing(dot, service.dots.identity.require.return_value["id"]) == []
    with pytest.raises(Denied):
        service.execute("other", dot["workspace_id"], dot["id"], saved["id"] + "." + tool)
    with pytest.raises(Denied):
        service.disconnect("other", dot["workspace_id"], dot["id"], saved["id"])
    service.dots.identity.require.return_value = {"id": owner}
    dot["version"] += 1
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + "." + tool)
    dot["version"] -= 1
    replacement = service.connect(*args)
    assert replacement["id"] != saved["id"] and len(service.listing(dot, owner)) == 1
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], saved["id"] + "." + tool)
    service.disconnect("session", dot["workspace_id"], dot["id"], replacement["id"])
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], replacement["id"] + "." + tool)
    expiring = service.connect(*args)
    with service.store.tx() as db:
        db.execute(text("UPDATE bud_connections SET expires=0"))
    with pytest.raises(Denied):
        service.execute("session", dot["workspace_id"], dot["id"], expiring["id"] + "." + tool)
