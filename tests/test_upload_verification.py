import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from aedrova_site.store import Denied
from aedrova_site.uploads import UploadVerifier


@pytest.mark.parametrize(
    "data,name,declared,allowed",
    [
        (b"notes", "brief.md", None, True),
        (b"MZ\0bad", "brief.txt", None, False),
        (b"notes", "brief.png", None, False),
        (b"notes", "brief.md", 3, False),
    ],
)
def test_server_inspects_actual_immutable_bytes_before_publication(data, name, declared, allowed):
    user, identifier = str(uuid4()), uuid4()
    row = {
        "id": str(identifier),
        "uploader_id": user,
        "byte_size": declared or len(data),
        "filename": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "object_path": "/".join(str(uuid4()) for _ in range(3)),
    }
    identity, store = MagicMock(), MagicMock()
    identity.user.return_value = {"id": user}
    identity.request.return_value = [row]
    identity.config = SimpleNamespace(supabase_key="public", supabase_url="https://stage.test")
    identity.client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=data))
    )
    verifier = UploadVerifier(identity, store)
    if allowed:
        result = verifier.verify("jwt", identifier)
        assert result["verified_type"] == "text/plain"
        store.engine.begin.assert_called_once()
    else:
        with pytest.raises(Denied):
            verifier.verify("jwt", identifier)
        store.engine.begin.assert_not_called()
    identity.client.close()


def test_other_uploader_never_downloaded_or_published():
    identity, store = MagicMock(), MagicMock()
    identity.user.return_value = {"id": str(uuid4())}
    identity.request.return_value = [{"uploader_id": str(uuid4())}]
    with pytest.raises(Denied):
        UploadVerifier(identity, store).verify("jwt", uuid4())
    identity.client.stream.assert_not_called()
    store.engine.begin.assert_not_called()
