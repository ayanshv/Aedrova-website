import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.error_pages import error_response


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Config(
            database="sqlite:///" + str(tmp_path / "site.db"),
            encryption_key=Fernet.generate_key().decode(),
        )
    )

    @app.get("/failure/{code}")
    def failure(code: int):
        return JSONResponse(
            {"error": "private implementation detail"},
            status_code=code,
            headers={"Retry-After": "17"},
        )

    @app.get("/crash")
    def crash():
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(
    "status",
    [
        400,
        401,
        403,
        404,
        405,
        408,
        410,
        413,
        422,
        429,
        500,
        501,
        502,
        503,
        504,
        520,
        521,
        522,
        523,
        524,
        525,
        526,
    ],
)
def test_browser_errors_are_branded_keep_status_and_do_not_leak(client, status):
    response = client.get(f"/failure/{status}", headers={"Accept": "text/html"})
    assert response.status_code == status
    assert response.headers["retry-after"] == "17"
    assert "Aedrova" in response.text and "data:image/png;base64," in response.text
    assert "private implementation detail" not in response.text
    assert "style-src 'sha256-" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_browser_not_found_and_unexpected_failure(client):
    assert "A little off course." in client.get("/missing", headers={"Accept": "text/html"}).text
    response = client.get("/crash", headers={"Accept": "text/html"})
    assert response.status_code == 500
    assert "We’ll be right back." in response.text
    assert "secret internal detail" not in response.text


def test_machine_api_contracts_remain_json(client):
    response = client.get("/api/missing", headers={"Accept": "text/html"})
    assert response.status_code == 404 and response.json() == {"detail": "Not Found"}
    assert client.get("/failure/503").json() == {"error": "private implementation detail"}


def test_error_response_has_no_external_asset_requests():
    response = error_response(502)
    assert b"/static/" not in response.body
    assert b"<script" not in response.body
