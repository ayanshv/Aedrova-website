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

If the local service stops after a reboot or terminal shutdown, run from the website checkout:

```sh
uv run python -m scripts.run_local_meetings
```

Keep that terminal open. It binds only 127.0.0.1:8090, loads the two existing private setup
files without printing keys, enables development meetings and keeps speech/context,
checkout, paid AI and public release disabled. Local development uses the embedded guard;
production still requires a separate supervised guard. Do not start a second copy while
port 8090 is occupied. No paid Render or additional Stripe setup is required for this retry.
This does not make meetings accessible from another computer.

Future local preview rebuilds must retain the local meeting origin and existing Apple
Development identity. Use separate output artifacts for public-origin release rehearsals;
never replace the user's active local preview with a public-waitlist configuration.
M14's isolated installation/update rehearsal remains unfinished.
