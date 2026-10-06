# Local preview meeting recovery — October 3, 2026

The running local meeting API was absent. The M14 rehearsal preview also accidentally
pointed at the public waitlist site, where meetings are intentionally disabled. Rebuilt
with `AEDROVA_MANAGED_ORIGIN=http://127.0.0.1:8090`, local AI mode and the existing Apple
Development identity. The app was reopened; ordinary Google sign-in is required before
retrying a channel call. No public flags or private configuration file values were changed.

The local service is running and /health/meetings reports ready. Synthetic LiveKit
camera/audio/screen frames passed; physical-device and signed-in call retry are still
owner acceptance, not proven by that synthetic check. 473 desktop and 245 website tests,
Ruff, 23 embedded SQL scripts, private ledger schema, runtime handshake/boundaries and
packaged signature/resource checks passed during this task.

On October 5 the absent local service was restored and registered as a user
LaunchAgent at `~/Library/LaunchAgents/com.aedrova.local-meetings.plist`. It starts
at login and restarts after an unexpected process exit; no terminal needs to stay
open. It runs `uv run python -m scripts.run_local_meetings` from this checkout.
The service binds only 127.0.0.1:8090 and loads the existing private setup files
without printing keys. Paid/public launch flags remain disabled.

Check its status with `launchctl print gui/$(id -u)/com.aedrova.local-meetings`.
Restart it with `launchctl kickstart -k gui/$(id -u)/com.aedrova.local-meetings`.
Do not start a duplicate terminal service while port 8090 is occupied.
Logs live in `~/Library/Logs/Aedrova/local-meetings.*.log` with private permissions.
Moving these checkouts or removing the local uv executable requires updating the
LaunchAgent paths. No paid Render or additional Stripe setup is needed locally.
This does not make meetings accessible from another computer.

Future local preview rebuilds must retain the local meeting origin and existing Apple
Development identity. Use separate output artifacts for public-origin release rehearsals;
never replace the user's active local preview with a public-waitlist configuration.
M14's isolated installation/update rehearsal remains unfinished.
