"""M13 private-input validation and gateway parser limits."""

import json

from test_access_gateway import begin
from test_access_gateway import client as gateway_client  # noqa: F401


def test_validation_does_not_echo_private_input(request):
    client = request.getfixturevalue("gateway_client")
    secret = "synthetic-private-content"
    response = client.post(
        "/api/runs",
        headers={"x-csrf-token": "csrf-a"},
        json={"workspace": [secret], "provider": "codex", "request_id": "build-request-00001"},
    )
    assert response.status_code == 422
    assert secret not in response.text
    assert response.json() == {"error": "Some request fields are invalid. Check your input."}


def test_deep_model_request_rejected_before_spending(request):
    client = request.getfixturevalue("gateway_client")
    run = begin(client)
    nested = "synthetic"
    for _ in range(120):
        nested = [nested]
    response = client.post(
        "/gateway/codex/v1/responses",
        headers={"Authorization": "Bearer " + run["token"]},
        content=json.dumps({"input": nested, "tools": []}),
    )
    assert response.status_code == 403
    assert "nesting" in response.text
