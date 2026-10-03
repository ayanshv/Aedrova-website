"""Channel-scoped meeting credentials. Disabled until media acceptance is complete."""

from datetime import timedelta
from uuid import UUID

import jwt
from livekit import api

from aedrova_site.store import Denied


def issue_meeting_access(config, identity, store, token, meeting, leases=None):
    if not config.meetings_enabled:
        raise Denied("Meetings are being prepared. No microphone or camera was started.")
    if leases is not None and not leases.ready():
        raise Denied("Call access monitoring is starting or unavailable. Retry shortly.")
    user = identity.user(token)
    store.rate_limit("meeting-join:" + user["id"], limit=8)
    scope = identity.request(
        "/rest/v1/rpc/join_meeting", token, method="POST", data={"p_meeting": str(meeting)}
    )
    try:
        identifiers = {
            key: str(UUID(scope[key]))
            for key in ("meeting_id", "workspace_id", "channel_id", "user_id")
        }
        room = "aedrova-" + "-".join(
            identifiers[key] for key in ("workspace_id", "channel_id", "meeting_id")
        )
        if identifiers["meeting_id"] != str(meeting) or identifiers["user_id"] != user["id"]:
            raise ValueError("scope")
        if scope["room_name"] != room:
            raise ValueError("room")
    except (KeyError, TypeError, ValueError) as error:
        raise Denied("Meeting access could not be verified.") from error
    if leases is not None:
        leases.put(scope, token)
    credential = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(user["id"])
        .with_name(str(user.get("user_metadata", {}).get("full_name", "Teammate"))[:80])
        .with_ttl(timedelta(minutes=5))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=False,
                can_update_own_metadata=False,
                can_publish_sources=["camera", "microphone", "screen_share", "screen_share_audio"],
            )
        )
    ).to_jwt()
    claims = jwt.decode(
        credential, config.livekit_api_secret, algorithms=["HS256"], issuer=config.livekit_api_key
    )
    return {
        **identifiers,
        "url": config.livekit_url,
        "token": credential,
        "expires_at": claims["exp"],
    }
