"""Provider-specific account authorization, with bounded server-only responses."""

import json
import logging
import re
import time

import httpx

from aedrova_site.bud_providers import validate_resource
from aedrova_site.store import Denied


class PrivateOAuthURLs(logging.Filter):
    """Meta requires token query parameters; redact them from HTTP client logs."""

    def filter(self, record):
        record.msg = re.sub(
            r"([?&](?:access_token|client_secret)=)[^&\s\"]+", r"\1[redacted]", record.getMessage()
        )
        record.args = ()
        return True


logging.getLogger("httpx").addFilter(PrivateOAuthURLs())


def response(client, method, url, **kwargs):
    try:
        with client.stream(method, url, **kwargs) as result:
            if result.status_code != 200:
                raise Denied("Needs authorization")
            raw = bytearray()
            for block in result.iter_bytes():
                raw.extend(block)
                if len(raw) > 32768:
                    raise Denied("Unsupported authorization response.")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("error"):
                raise Denied("Needs authorization")
            return data
    except (httpx.HTTPError, ValueError):
        raise Denied("Authorization provider unavailable. Retry shortly.") from None


def exchange(oauth, provider, *, code=None, refresh=None):
    client_id, secret = oauth.credentials(provider)
    if not client_id or not secret:
        raise Denied("Needs authorization")
    redirect = oauth.redirect(provider)
    actor, team = "", ""
    if provider == "stripe":
        data = response(
            oauth.client,
            "POST",
            "https://api.stripe.com/v1/oauth/token",
            auth=(secret, ""),
            data={
                "grant_type": "refresh_token" if refresh else "authorization_code",
                "refresh_token" if refresh else "code": refresh or code,
            },
        )
        if data.get("scope") != "stripe_apps":
            raise Denied("Authorize the Aedrova Stripe app only.")
        actor = validate_resource(provider, str(data.get("stripe_user_id", "")))
    elif provider == "vercel":
        if refresh:
            raise Denied("Needs authorization")
        data = response(
            oauth.client,
            "POST",
            "https://api.vercel.com/v2/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": secret,
                "code": code,
                "redirect_uri": redirect,
            },
        )
        team = data.get("team_id") or ""
        if not isinstance(team, str) or (
            team and not re.fullmatch(r"team_[A-Za-z0-9]{1,100}", team)
        ):
            raise Denied("Unsupported authorization account.")
        # Long-lived integration tokens are revoked by uninstalling the integration.
        data["expires_in"] = 31536000
    elif provider == "instagram":
        if refresh:
            data = response(
                oauth.client,
                "GET",
                "https://graph.instagram.com/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": refresh},
            )
        else:
            short = response(
                oauth.client,
                "POST",
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": client_id,
                    "client_secret": secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect,
                    "code": code,
                },
            )
            access = short.get("access_token", "")
            if not valid_token(access):
                raise Denied("Unsupported authorization response.")
            data = response(
                oauth.client,
                "GET",
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": secret,
                    "access_token": access,
                },
            )
        if not valid_token(data.get("access_token")):
            raise Denied("Unsupported authorization response.")
        profile = response(
            oauth.client,
            "GET",
            "https://graph.instagram.com/v25.0/me",
            headers={"Authorization": "Bearer " + data["access_token"]},
            params={"fields": "id,user_id,username"},
        )
        actor = validate_resource(provider, str(profile.get("user_id") or profile.get("id", "")))
        # Instagram renews its long-lived access token, rather than issuing a refresh token.
        data["refresh_token"] = data["access_token"]
    else:
        raise Denied("Unsupported authorization provider.")
    access = data.get("access_token")
    renewal = data.get("refresh_token", "")
    seconds = data.get("expires_in", 3600)
    if (
        not valid_token(access)
        or (not isinstance(renewal, str) or (renewal and not valid_token(renewal)))
        or type(seconds) is not int
        or not 1 <= seconds <= 31536000
    ):
        raise Denied("Unsupported authorization response.")
    if str(data.get("token_type", "bearer")).lower() != "bearer":
        raise Denied("Unsupported authorization response.")
    return dict(
        kind="oauth",
        access=access,
        refresh=renewal,
        actor=actor,
        team=team,
        token_expires=int(time.time()) + seconds,
    )


def valid_token(value):
    return (
        isinstance(value, str) and 8 <= len(value) <= 4096 and not any(c.isspace() for c in value)
    )
