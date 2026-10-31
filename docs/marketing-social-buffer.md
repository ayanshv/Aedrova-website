# Marketing Bud social publishing — Buffer transition

Updated October 31, 2026. Implementation and staging setup are in progress. This
is not a claim of live publication acceptance or production availability.

## Product and connection flow

Marketing Bud remains the strategist: existing private Bud conversations generate
campaign ideas, audience questions, researched opportunities, platform-specific
captions, variations, hashtags, calls to action and content calendars. Existing
model entitlements and spending limits apply. The model has no publish tool.

Marketing Bud → Social → Connect Buffer → Buffer authorization → choose an
organization → select authorized social channels → save selection. Customers do
not supply keys or create Meta/TikTok developer apps. Users first connect their
actual social profiles in Buffer; the staging operator currently has zero
channels. Only channels for which Buffer reports scheduling authority can be
selected. Locked/disconnected channels cannot publish; paused queues block dispatch.

The Social workspace has Accounts and Drafts & posts tabs. Ask Bud uses the
existing private, metered conversation. Use latest reply copies text into an
editable local draft. It is not approval. Choose destination, text, optional
public media and local scheduling time, then Save draft → Approve draft → Publish
now / Schedule post. Reject does not call a provider. Changing content, destination,
time, media, channel selection or Bud version invalidates authority. Once handed
to Buffer, changes/cancellation must be managed in Buffer; no misleading local
edit can alter a provider-scheduled post.

## Official API findings

Sources inspected before implementation:

- [OAuth authentication](https://developers.buffer.com/guides/authentication.html)
- [Building apps and app clients](https://developers.buffer.com/guides/building-apps.html)
- [GraphQL reference](https://developers.buffer.com/reference.html)
- [Posts and scheduling](https://developers.buffer.com/guides/posts-and-scheduling.html)
- [Hosting media](https://developers.buffer.com/guides/hosting-media.html)
- [API limits](https://developers.buffer.com/guides/api-limits.html)

Buffer supports multi-user OAuth authorization-code flows with mandatory S256
PKCE. A confidential server client is appropriate. The requested scopes are
account:read, posts:read, posts:write and offline_access. App registration only
selects the three API permissions; offline_access is requested during OAuth.
Single-use refresh tokens rotate. Replay can revoke the grant; ambiguous refresh
failure requires reconnect, never resubmission of the consumed refresh token.

The API can list organizations/channels and submit immediate or UTC-scheduled
posts. Platform/format constraints still apply. Returned authorized channels are
the source of truth; availability in Buffer's website is not proof every format
is supported by this adapter. Initial media controls accept one image or video;
Instagram/Pinterest require media and TikTok/YouTube require a video. Platform
validation errors remain visible. Platform-specific extensions and every format
have not been live-certified.

Buffer OAuth apps cannot currently fetch the documented post analytics reserved
for personal API keys. Analytics are explicitly unavailable; no invented metrics
or customer-key workaround is offered. Performance suggestions can use context a
user deliberately supplies, with its provenance stated.

Media needs a stable, public, direct HTTPS URL until the provider publishes it.
Aedrova does not expose private workspace attachments or create public copies.
Signed/expiring/query-bearing URLs, credentials, private literal hosts and malformed
ports are rejected. Aedrova does not fetch that URL; Buffer fetches the approved
asset. Users are responsible for choosing appropriately public assets.

The signed-in Free account permits one App Client and shows 0/3 connected channels.
No upgrade was purchased. OAuth app quotas differ from personal-key quotas; do
not apply personal-key numbers to multi-user OAuth. Local authenticated social
routes are limited to 30 requests/minute/session plus existing account limits.
Provider 429 responses are explicit and are not retried automatically. No paid
hosting worker is needed: Buffer owns its accepted scheduled queue.

## Architecture and security

`social.providers.SocialProvider` defines connection, disconnection, account,
draft delivery, immediate/scheduled posting, status and analytics operations.
`BufferAdapter` owns endpoints, OAuth exchange, GraphQL and wire-format mapping.
The service uses neutral content/channel/time/asset fields. Adding another
adapter does not require rewriting Marketing Bud's creative conversation.

Existing `bud_connections` and `bud_oauth` hold encrypted credentials and short-lived
OAuth state. State is bound to authenticated user, workspace, Bud version, browser
proof and PKCE verifier. Callback and organization selection are single-use.
Credentials stay encrypted server-side; no keys are in desktop settings/storage.
Buffer rejects personal tokens at the connection boundary. Selected channel
permissions and posts are scoped to the grant, user, workspace and Bud; no shared
workspace member can use another member's grant or draft.

New private backend tables:

- `social_channels`: grant/channel identifiers, validated channel metadata and a
  permission nonce renewed on selection.
- `social_posts`: user/workspace/Bud/grant/channel, encrypted draft body, revision,
  approval fingerprint, provider ID/status, generic error and dispatch state.

Tables are created by the existing restricted backend schema owner on startup,
under the same private search path as existing connector tables. No public-table
migration or frontend SQL access is needed. Bud removal purges its social drafts
and orphan channel permissions. Disconnect stops future dispatch but does not
cancel posts already queued by Buffer. Account/workspace deletion procedures must
include the new tables (see operational deletion below); do not assume Supabase
Auth deletion cascades into the separate private backend database.

All routes authenticate and authorize the current user/resource. Writes reuse
CSRF checks. Unknown fields, malformed IDs, oversized text/assets and secret-like
post text are rejected. Provider requests use fixed HTTPS hosts, bounded JSON,
finite timeouts, no redirects or environment proxies, and generic errors that
exclude upstream payloads/tokens. Channel permissions and connection validity are
rechecked before external writes, under grant locks shared with disconnect.

Approval binds the exact encrypted draft content and revision. A durable Sending
claim commits before any write. Repeated or concurrent dispatch requests cannot
send that draft twice. Buffer createPost has no documented idempotency key;
therefore timeouts, uncertain provider results or worker crashes stay Unconfirmed.
They are never blindly retried or reapproved. Check Buffer and reconcile manually
before deliberately creating another post. This is at-most-once dispatch, not a
false exactly-once delivery guarantee. `buffer` means queued; `sent` means published.
The UI does not mark a request as published merely because it was accepted.

## Controlled transition and other providers

Legacy Instagram/TikTok read routes, OAuth grants and tested lifecycle controls
are preserved. They are no longer Marketing Bud's primary publishing dependency.
Their public approvals remain unverified; the old TikTok demo was blocked by
loss of access to the test account, and Meta business verification was not
submitted. No migration silently grants publishing access to an old read grant.
`AEDROVA_SOCIAL_PUBLISHING_ENABLED=false` defaults to off. When off, Buffer is
absent from connection catalogs and Social displays setup information rather
than a dead connect button. Enabling it does not imply other providers are live.

[LinkedIn member sharing](https://learn.microsoft.com/linkedin/consumer/integrations/self-serve/share-on-linkedin)
uses w_member_social. A separate adapter adds another registration/lifecycle
without a demonstrated initial advantage over Buffer; it is deferred. Ayrshare is
an extension point only; no Ayrshare integration or keys were created.

## Staging deployment and acceptance gates

1. Register confidential Aedrova Staging client (completed with owner approval).
   Callback: https://aedrova-beta-staging.onrender.com/buds/oauth/buffer/callback
   Privacy URL: https://aedrova.com/privacy. No production callback.
2. Generated credentials are saved in ignored `.env.buffer-bud-staging`, mode 0600.
   Set AEDROVA_BUFFER_BUD_CLIENT_ID and AEDROVA_BUFFER_BUD_CLIENT_SECRET only on
   Render aedrova-beta-staging. Set AEDROVA_SOCIAL_PUBLISHING_ENABLED=true there.
   Keep production disabled. Never put these values in Git or screenshots.
3. Run full app/backend checks and required hosted CI. Deploy reviewed backend
   commit to staging, keeping existing database/encryption key and identity setup.
4. Connect one real social profile through Buffer (owner sign-in/consent needed).
   Use Aedrova's fresh Connect Buffer and verify organization/channel retrieval,
   selection, local editing, approval invalidation and isolation.
5. Owner reviews exact test content, destination and time before any real post.
   Verify one accepted scheduled/immediate post and its actual provider status;
   verify duplicate dispatch is suppressed. Delete/manage any public test post
   only with appropriate owner authorization.
6. Verify refresh/expiry/disconnect and provider-side revocation on a disposable
   grant. Buffer Connected Apps removal is the provider-side revoke path; no
   undocumented revoke endpoint is invented. Reconnect when completed.
7. Record actual live evidence before closing Stage 1. OAuth client creation or
   fixture tests alone do not satisfy live publishing acceptance.

Operational deletion: after verifying a data-subject request and its scope, use
the existing private-backend operator procedure, selecting rows by bound UUIDs,
to remove `social_posts` for that user/workspace and `social_channels` for their
removed connection IDs. Revoke provider access and respect existing backup
retention. Never offer unrestricted public SQL or claim remote scheduled posts
are cancelled by this deletion. Extending automated whole-account deletion
across the private backend remains an operations launch gate.
