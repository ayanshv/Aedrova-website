# Service Phase 1 release baseline

October 10, 2026. Owner authorized Phase 1; later phases/public launch remain gated.
Full app/service inventory, hosted review and exact owner actions:
../Aedrova/docs/final-beta-phase-1.md (companion desktop repository).

Pulse service routes/module/tests removed; meeting heartbeat routes remain. No data
purged. Explicit staging configuration must use a separate Supabase project/HTTPS
origin, restricted database role and encryption key; production targets/live Stripe
keys/checkout/download flags/development bypass rejected. See deploy/staging.env.example.
No staging server credentials or new cloud deployment configured by this commit.

Service local evidence: 409 tests passed, Ruff/compile and tracked recognizable-secret
scan passed. Private PostgreSQL schema/access/atomic lease SQL checks passed in PGlite;
networked concurrency and hosted acceptance remain gates. CI expanded to run on branch
pushes, upload JUnit evidence, check tracked credentials/private PostgreSQL permissions
and keep container startup/readiness validation. Remote CI must pass before release.

Removed 3,937 tracked node_modules vendor files from the motion project index, kept
installed files on disk; ignore rules prevent re-adding, manifests/lockfile retained.
No first-party credential-pattern hit found; this does not certify historical Git data.
GitHub hosted review: public repo, 0 collaborators, Secret Protection/push protection on;
no classic branch protection/rulesets; Dependabot/CodeQL not yet configured.

Website remains waitlist; customer Stripe connector public review/business verification
still required. No billing activation, Pulse replacement or installer launch here.

Remote evidence: service baseline a2b1423, GitHub Actions run 38078223509 **passed**,
including tests, private PostgreSQL permissions/leases, Docker build and startup.
Desktop companion a7efded pushed; native PostgreSQL CI passed, Windows revealed
existing Unix-only fcntl imports, which remain a visible release blocker. Mac preview
rebuilt separately; no Windows installer or public service deployment claimed.
Owner installed the app's 23 staging migrations; hosted Table Editor verified tables.
Next owner action: run sql/supabase-website.sql ONLY in Aedrova Staging, creating the
restricted NOLOGIN role/private schema. Password remains a later private handoff.

Owner completed private role creation and LOGIN credential SQL in staging. Actual
restricted pooler login verified; public workspace read denied. Staging environment
validated and deploy/render-beta-staging.yaml prepared for a separate free service.
Sensitive values remain ignored locally; cloud installation still awaits approval.
Stripe sandbox mode is off because checkout is off and this server enforces HTTPS
production transport controls. Google staging OAuth remains a separate setup gate.
