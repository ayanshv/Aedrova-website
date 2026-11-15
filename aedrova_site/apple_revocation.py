import base64
import json
import os

import httpx
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

APPLE = "https://appleid.apple.com"


class RevocationBody(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096, pattern=r"^[-A-Za-z0-9._~+/=]+$")


def revoke(client, client_id, client_secret, refresh_token, subjects):
    credentials = {"client_id": client_id, "client_secret": client_secret}
    try:
        verified = client.post(
            APPLE + "/auth/token",
            data={**credentials, "grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        if verified.status_code == 400 and verified.json().get("error") == "invalid_grant":
            return False
        verified.raise_for_status()
        result = verified.json()
        # The token response is received directly from Apple over authenticated TLS.
        claims = result["id_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
        if (
            claims.get("iss") != APPLE
            or claims.get("aud") != client_id
            or claims.get("sub") not in subjects
        ):
            return False
        response = client.post(
            APPLE + "/auth/revoke",
            data={
                **credentials,
                "token": result.get("refresh_token") or refresh_token,
                "token_type_hint": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.status_code == 200
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, IndexError, KeyError):
        raise HTTPException(503, "Apple revocation is temporarily unavailable.") from None


def install(app, store, identity, auth):
    @app.post("/api/account/apple/revoke", status_code=204)
    def revoke_for_pending_deletion(body: RevocationBody, request: Request):
        if not request.headers.get("authorization", "").startswith("Bearer "):
            raise HTTPException(403, "Sign in again to continue.")
        token = auth(request, change=True)
        user = identity.user(token)
        store.rate_limit("apple-revocation:" + user["id"], limit=5)
        subjects = {
            item["identity_data"]["sub"]
            for item in user.get("identities", [])
            if item.get("provider") == "apple" and (item.get("identity_data") or {}).get("sub")
        }
        receipt = identity.request(
            "/rest/v1/rpc/get_account_deletion_request", token, method="POST", data={}
        )
        if not subjects or not receipt or receipt["completed"]:
            raise HTTPException(403, "Apple revocation requires a pending account deletion.")
        client_id = os.environ.get("AEDROVA_APPLE_REVOKE_CLIENT_ID")
        client_secret = os.environ.get("AEDROVA_APPLE_REVOKE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(503, "Apple revocation is temporarily unavailable.")
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            if not revoke(client, client_id, client_secret, body.refresh_token, subjects):
                raise HTTPException(409, "Sign in with Apple again to refresh your authorization.")
        return Response(status_code=204)
