"""Real metering and deterministic HTTP: no live credentials or provider spend."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from test_dots import system  # noqa: F401

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.store import Denied
from aedrova_site.translations import Translations, mask, restore


def translator(system, *, transform=None):  # noqa: F811
    dots, dot, user = system
    config = dots.config
    config.gateway_enabled, config.openai_key = True, "translation-fixture-key"
    dots.store.free_enabled = True
    dots.store.activate_free(user, dot["workspace_id"])
    dots.identity.billing_context.return_value = {"billing_workspace": dot["workspace_id"]}
    seen = []

    def handler(request):
        seen.append(request)
        data = json.loads(request.content)
        texts = json.loads(data["input"])
        result = [t.replace("Hello", "नमस्ते") for t in texts]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 100},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {"texts": transform(result) if transform else result}
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    service = Translations(
        config, dots.store, dots.identity, transport=httpx.MockTransport(handler)
    )
    return service, dot["workspace_id"], user, seen


def test_translation_preserves_code_mentions_links_and_caches_by_reader(system):  # noqa: F811
    service, workspace, user, seen = translator(system)
    source = 'Hello @Aedrova `print("Hello")` https://example.com [message:abc]'
    first = service.translate("session", workspace, user, "hi", [source])
    assert first["texts"] == [source.replace("Hello", "नमस्ते", 1)]
    assert len(seen) == 1
    assert json.loads(seen[0].content)["store"] is False
    assert seen[0].headers["idempotency-key"]
    assert service.store.balance(workspace)["spent"] > 0
    assert service.store.balance(workspace)["reserved"] == 0
    assert service.translate("session", workspace, user, "hi", [source])["cached"]
    assert len(seen) == 1
    service.translate("session", workspace, "other-reader", "hi", [source])
    assert len(seen) == 2
    service.close()


def test_cached_translation_is_not_returned_after_membership_revocation(system):  # noqa: F811
    service, workspace, user, seen = translator(system)
    service.translate("session", workspace, user, "hi", ["Hello"])
    service.identity.billing_context.side_effect = Denied("Revoked")
    with pytest.raises(Denied):
        service.translate("session", workspace, user, "hi", ["Hello"])
    assert len(seen) == 1
    service.close()


@pytest.mark.parametrize(
    "transform", [lambda _: [], lambda _: [""], lambda _: ["invalid protected tokens"]]
)
def test_invalid_model_result_is_never_presented_as_a_translation(system, transform):  # noqa: F811
    service, workspace, user, _ = translator(system, transform=transform)
    with pytest.raises(Denied):
        service.translate("session", workspace, user, "hi", ["Hello `code`"])
    assert not service.cache and not service.inflight
    assert service.store.balance(workspace)["reserved"] == 0
    service.close()


@pytest.mark.parametrize(
    "language,texts",
    [
        ("xx", ["Hello"]),
        ("hi", []),
        ("hi", ["x" * 12001]),
        ("hi", ["a\x00b"]),
        ("hi", ["ह" * 10000]),
    ],
)
def test_bounds_before_model_call(system, language, texts):  # noqa: F811
    service, workspace, user, seen = translator(system)
    with pytest.raises(Denied):
        service.translate("session", workspace, user, language, texts)
    assert not seen
    service.close()


def test_translation_route_requires_real_membership_and_cookie_csrf(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'app.db'}"))
    with TestClient(app) as client:
        app.state.identity.require = MagicMock(side_effect=Denied("No workspace access"))
        body = {
            "workspace": "00000000-0000-0000-0000-000000000001",
            "language": "hi",
            "texts": ["Hello"],
        }
        assert client.post("/api/translations", json=body).status_code == 403
        assert (
            client.post(
                "/api/translations", json=body, headers={"Authorization": "Bearer fixture"}
            ).status_code
            == 403
        )
        assert app.state.identity.require.call_count == 1


def test_mask_roundtrip_opaque_and_loss_fails_closed():
    source = 'नमस्ते ```print("hi")``` @Aedrova https://example.com'
    text, values = mask(source)
    assert "print" not in text and "https://" not in text
    assert restore(text, values) == source
    with pytest.raises(ValueError):
        restore(text.replace(next(iter(values)), ""), values)


def test_language_preference_is_private_and_cannot_modify_authority(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path / 'languages.db'}"))
    with TestClient(app) as client:
        identity = app.state.identity
        identity.user = MagicMock(
            return_value={"id": "reader", "user_metadata": {"aedrova_language": "hi"}}
        )
        identity.request = MagicMock(return_value={"id": "reader"})
        headers = {"Authorization": "Bearer reader-session"}
        assert client.get("/api/language").status_code == 403
        assert client.get("/api/language", headers=headers).json() == {
            "language": "hi",
            "translate": True,
        }
        result = client.post(
            "/api/language", headers=headers, json={"language": "ar", "translate": False}
        )
        assert result.status_code == 200
        identity.request.assert_called_once_with(
            "/auth/v1/user",
            "reader-session",
            method="PUT",
            data={"data": {"aedrova_language": "ar", "aedrova_translate": False}},
        )
        assert (
            client.post(
                "/api/language", headers=headers, json={"language": "hi", "role": "owner"}
            ).status_code
            == 422
        )
        identity.user.return_value = {"id": "reader", "user_metadata": {"aedrova_language": []}}
        assert client.get("/api/language", headers=headers).json()["language"] == "en"


def test_locale_updates_and_new_catalogs_invalidate_browser_assets(tmp_path):
    from aedrova_site.app import asset_fingerprint

    static = tmp_path / "static"
    (static / "locales").mkdir(parents=True)
    for name in ("site.css", "site.js", "preparation.js", "localization.js"):
        (static / name).write_text("fixture")
    (static / "locales/hi.json").write_text('{"Continue":"initial"}')
    first = asset_fingerprint(tmp_path)
    (static / "localization.js").write_text("updated logic")
    second = asset_fingerprint(tmp_path)
    assert second != first
    (static / "locales/hi.json").write_text('{"Continue":"updated"}')
    third = asset_fingerprint(tmp_path)
    assert third != second
    (static / "locales/es.json").write_text('{"Continue":"Continuar"}')
    assert asset_fingerprint(tmp_path) != third


def test_every_navigation_choice_has_a_complete_static_catalog():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "aedrova_site"
    script = (root / "static/localization.js").read_text()
    language_object = re.search(r"const languages=(\{.*?\});", script).group(1)
    languages = json.loads(language_object)
    assert len(languages) >= 50
    keys = set(json.loads((root / "static/locales/es.json").read_text()))
    for code in languages:
        if code == "en":
            continue
        catalog = json.loads((root / "static/locales" / (code + ".json")).read_text())
        assert keys <= set(catalog)
        assert all(isinstance(catalog[k], str) and catalog[k].strip() for k in keys)
        assert all("Aedrova" in catalog[k] for k in keys if "Aedrova" in k)
