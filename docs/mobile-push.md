# iPhone and Android push notifications

New chat activity can notify a person's iPhone. Apple only delivers a push to a build signed
with the app's push capability, so this stays off until the owner completes the steps below.

## How it works

1. The iPhone app asks permission, registers with Apple, and stores its device token in the
   shared database (`register_push_device`).
2. When a chat notification row is created, a database trigger posts its id to
   `POST /internal/push` on this service. It sends ids only, never message text.
3. This service looks up the notification, builds a short alert that names the person and
   place, and sends it to each registered device through Apple. Devices Apple reports as gone
   are removed.

The alert never contains the message. Examples: "Maya, Mentioned you in #launch", "Maya,
Sent you a message".

## Owner steps (nothing here can be done for you)

1. In Apple Developer → Certificates, Identifiers & Profiles → Identifiers, open the
   `com.aedrova.desktop` App ID and enable **Push Notifications**.
2. In Keys, create a key with **Apple Push Notifications service (APNs)**. Download the `.p8`
   once. Note its **Key ID** and your **Team ID**.
3. In Render for this service, set these environment variables (paste the `.p8` contents as
   the value of `AEDROVA_APNS_KEY`, including the BEGIN and END lines):
   - `AEDROVA_APNS_KEY`
   - `AEDROVA_APNS_KEY_ID`
   - `AEDROVA_APNS_TEAM_ID`
   - `AEDROVA_APNS_TOPIC` (defaults to `com.aedrova.desktop`)
   - `AEDROVA_PUSH_WEBHOOK_SECRET` (a random string of at least 32 characters)
4. Apply `supabase/migrations/202611240001_mobile_push.sql` to the project, staging first.
5. In the Supabase SQL editor, turn the sender on for that project (run it as the owner,
   replacing the URL host and secret). Skipping this leaves push off:

   ```sql
   create extension if not exists pg_net with schema extensions;
   insert into aedrova_private.push_config(key, value) values
     ('url', 'https://YOUR-SERVICE-HOST/internal/push'),
     ('secret', 'THE SAME VALUE AS AEDROVA_PUSH_WEBHOOK_SECRET')
   on conflict (key) do update set value = excluded.value;
   ```

   Never paste the secret or the key into chat, a commit, or a ticket.
6. Build the iPhone app with a profile that includes the push capability, install it on a real
   iPhone, and turn on **Settings → Notifications → Push notifications**.

## Android

Android phones use Firebase Cloud Messaging. The same alerts are sent, naming the person and
place and never the message. The app stays quiet until the owner completes these steps.

1. In the Firebase console, create a project (or use an existing one) and add an **Android
   app** with the package name `com.aedrova.mobile`. Copy its **project ID**, **project
   number**, **app ID** and **web API key** from Project settings. They are not secrets.
2. In Project settings → Service accounts, generate a new private key for the Firebase Admin
   service account. Download the JSON once. Never paste it into chat, a commit or a ticket.
3. In Render for this service, set `AEDROVA_FCM_SERVICE_ACCOUNT` to the whole JSON file (or the
   same file in base64).
4. Apply `supabase/migrations/202611260001_android_push.sql`, staging first. It adds a platform
   to each stored device and lets the sender tell phones apart. Run it after the iPhone migration.
5. In the Android project, put the four Firebase values in `firebase.properties` (see its
   README), then build. Without them the app does not ask for notification permission.

Phones Google reports as unregistered are removed, as with Apple.

## Turning it off

Delete the two rows in `aedrova_private.push_config`. The trigger then does nothing.
