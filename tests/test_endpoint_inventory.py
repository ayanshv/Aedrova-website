"""Every current private route must reject an anonymous, schema-valid request."""

from urllib.parse import quote

from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from scripts.audit_endpoints import inventory


def sample(schema, components, key=""):
    if "$ref" in schema:
        return sample(components[schema["$ref"].rsplit("/", 1)[1]], components, key)
    if "anyOf" in schema:
        return sample(next(v for v in schema["anyOf"] if v.get("type") != "null"), components, key)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind = schema.get("type")
    if kind == "object":
        return {
            k: sample(v, components, k)
            for k, v in schema.get("properties", {}).items()
            if k in schema.get("required", [])
        }
    if kind == "array":
        return [
            sample(schema["items"], components) for _ in range(max(1, schema.get("minItems", 0)))
        ]
    if kind == "boolean":
        return True
    if kind in {"integer", "number"}:
        return max(1, schema.get("minimum", 0))
    if schema.get("format") == "uuid":
        return "11111111-1111-4111-8111-111111111111"
    if key == "session_id":
        return "cs_audit_reference_00001"
    if key == "provider":
        return "codex"
    if key == "action":
        return "publish"
    if key == "kind":
        return "image"
    if key == "plan":
        return "monthly"
    return "a" * max(20, schema.get("minLength", 0))


def test_all_private_routes_reject_anonymous_schema_valid_requests(tmp_path):
    app = create_app(Config(database=f"sqlite:///{tmp_path}/inventory.sqlite"))
    rows = inventory(app)
    assert len(rows) >= 70
    assert all(row["boundary"] != "UNCLASSIFIED" for row in rows)
    schema = app.openapi()
    components = schema["components"]["schemas"]
    checked = []
    with TestClient(app) as client:
        for row in rows:
            if row["boundary"] not in {
                "user-session-or-bearer-and-resource-authorization",
                "scoped-build-token-and-entitlement",
            }:
                continue
            for method in row["methods"]:
                spec = schema["paths"][row["path"]][method.lower()]
                path = row["path"]
                params = {}
                for param in spec.get("parameters", []):
                    if not param.get("required"):
                        continue
                    value = sample(param["schema"], components, param["name"])
                    if param["in"] == "path":
                        path = path.replace("{" + param["name"] + "}", quote(str(value)))
                    if param["in"] == "query":
                        params[param["name"]] = value
                body_schema = (
                    spec.get("requestBody", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                kwargs = {"params": params}
                if body_schema:
                    kwargs["json"] = sample(body_schema, components)
                response = client.request(method, path, **kwargs)
                assert response.status_code == 403, (
                    method,
                    path,
                    response.status_code,
                    response.text,
                )
                assert response.headers["cache-control"] == "no-store"
                checked.append((method, path))
    assert len(checked) >= 40
    app.state.identity.close()
    app.state.store.engine.dispose()
