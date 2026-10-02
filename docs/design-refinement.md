# Cinematic website refinement — September 30, 2026

The owner’s Lumora template is a design reference, not a request to change Aedrova’s product or backend framework. The website retains its Python server, Google entry, workspace and subscription controls, optional introduction, approved plan prices and release gates. This design-only pass preserved the desktop; the subsequent Milestone 9 managed access/settings changes are recorded separately.

## Visual implementation

Full-viewport scenic hero with four scenes from the provided reference, five-second automatic rotation, one-second crossfades, motion controls and lazy loading. The current scene remains visible until a replacement loads. Hidden/off-screen videos pause. Reduced-motion visitors see a still frame initially. A local fallback surface keeps content readable if the video host is unavailable.

Instrument Serif is self-hosted for display headings, with its OFL license bundled. Functional copy uses the existing system stack. Aedrova’s original mark is framed in CSS without altering the logo asset. Transparent glass navigation and a keyboard-accessible mobile overlay replace the old floating header. Product stories use alternating editorial layouts instead of a bento card grid.

Onboarding, plans, account, enterprise, download, payment return and legal pages all share the new design. Monthly remains visually prominent at $49/month, weekly stays $10/week, and enterprise remains a conversation. No false savings, fabricated customer counts or unshipped feature promises were added.

## Verification

- 24 Python regression checks pass: all nine public pages and their local assets; internal links and anchors; approved plan destinations and renewal text; visible form labels; Google sign-in entry; authenticated workspace/billing controls; closed-checkout and unreleased-download gates; narrow content-security policy.
- Changed Python files pass Ruff. Browser JavaScript passes Node syntax validation.
- In-app browser: four-step onboarding, selection persistence after Back, nickname input, plan handoff, monthly account handoff, theme toggle, scenery selection and pause checked.
- Mobile at 390 × 844: all nine public pages checked without horizontal overflow. Monthly is visually first. Mobile menu open, close and Escape dismissal verified; background content is inert while the menu is open.
- Desktop hero and supporting pages inspected. Screenshots saved in the current task’s outputs directory.

## Owner actions and remaining milestone work

No owner action is required to review the local design at http://127.0.0.1:8090. This change is not a deployment or a live billing acceptance test.

Before public publishing, approve the rights and production hosting for the reference scenery, or replace it with Aedrova-owned videos. The font license is already bundled. The later Milestone 9 implementation replaces UI mockups with actual desktop captures and implements allowances/managed access/billing code. Live Stripe/provider setup, production policies and a public signed release are still required; see milestone-9.md and owner-setup.md.


## October 1 correction: desktop palette and professional workspace

Replaced olive UI surfaces with the desktop’s #F5F5F7 / #FFFFFF light theme,
#000000 / #1C1C1E dark theme, and restrained #0066CC / #0A84FF accents.
Natural scenery retains its original colors, with neutral overlays and fallback.
Hero, product introduction and calls to action now emphasize team communication,
channels, project context and delivery rather than a group chat.

Five distinct actual Qt captures show dark workspace conversation, light threads,
light Files, dark agent activity and dark Projects. Images retain their own captured
theme in either website appearance. The capture script grabs the central app widget
so native OS menu/title bars are excluded. All content is local demonstration data;
the activity capture does not claim a live provider run. Desktop UI is unchanged.

Verification: all 72 website tests and Ruff pass. Captures were regenerated successfully
without remote services. No new owner setup is required for these visual corrections.
Existing production setup and live acceptance gates remain in owner-setup.md.

Browser verification: neutral light/dark surfaces confirmed on desktop. Eight public pages checked at 390px in both themes without horizontal overflow. All five capture assets are distinct; actual app views were visually inspected without a native top bar.

## October 1 entry and hero resilience

The owner's existing tab retained the older page; refreshing reproduced working
header and footer onboarding links. Verified both again after the fix, plus the
onboarding-to-plans handoff. CSS/JavaScript URLs now carry a content version to
avoid mixing old cached assets with new templates.

Each reference video now has a locally served JPEG first-frame poster and an
independent still-image layer. Selecting a scene shows its local image immediately;
video errors, blocked autoplay and slow loading no longer leave an empty hero or
block scenery rotation. Decorative layers cannot intercept button clicks.

74 Python tests, Ruff, JavaScript syntax and the deterministic scenery behavior
check pass. The behavior check covers failed video loading, rejected autoplay,
five-second rotation and paused selection. Browser verified all four local images,
scene selection and both entry links. No new personal setup is needed for the local
fix. Existing scenery rights and production launch requirements remain unchanged.

## October 1 six-question introduction

Every onboarding visit now begins at question one. Saved answers/nicknames remain,
but the obsolete persisted step is discarded. The six optional questions cover team,
current work, daily friction, a first-week goal, agent nickname and referral source.
Answer-specific acknowledgments connect team needs to actual product capabilities;
the optional goal is a local personal note and never silently invokes an agent.
Navigation/progress derive from the number of fieldsets, with guarded Back, keyboard
focus and a final plans handoff. All answers remain in browser storage; the existing
workspace creation path transfers only the agent nickname.

75 Python tests, Ruff and JavaScript syntax pass. Browser verified old saved state
returns to question one, all six screens, Back, retained selections and final plans
navigation. All six mobile screens at 390px have no horizontal overflow. No owner
configuration or database migration is required.


## October 1 single cinematic city hero

Replaced all four nature scenes and the selector/rotation with one real aerial night
view of busy New York streets. Source: Yura Forrat, Pexels video 37898716,
https://www.pexels.com/video/nighttime-aerial-view-of-nyc-skyscrapers-37898716/ .
Pexels license https://www.pexels.com/license/ checked October 1 permits website,
promotional and modified use. No endorsement or stock redistribution is claimed.
Source/download URLs, author and original/derivative SHA-256 are recorded in
static/media-credits.json. The unused reference nature stills were removed.

Prepared H.264 1080p, muted, half-speed footage for a calmer single loop, fast-start
metadata and a local first-frame poster. Subtle generated monochrome film grain,
neutral desaturation and contrast, and dark overlays keep text readable. Pause stops
grain as well as video; reduced motion starts with the still. Background visibility
pauses playback. Media CSP now allows only same-origin video.

76 Python tests, Ruff, JavaScript syntax and one-video behavior checks pass. Browser
verified local video playback, single-source rendering, pause/resume and responsive
layout. No owner purchase, media license setup or API credentials are required.

### Daytime human connections hero — October 1

Supersedes the aerial scene with one real street-level video of people walking
together in daylight, by Felicity Tai on Pexels (7963127). The local muted loop
has a warm cinematic grade, temporal film noise, stronger animated grain and a
vignette. Playback, pause, reduced-motion and poster fallback remain supported.
Source, license and file hashes are recorded in static/media-credits.json.

### Overhead pedestrian loop and playback recovery

Replaced the street-level scene with licensed direct-overhead pedestrian footage
(Pexels 13852105). Removed baked temporal noise and reduced CSS grain from .24
to .045 with soft-light blending. Video generation is unavailable in this session;
this is edited real footage. Autoplay is explicitly muted and inline. Saved pause
state no longer suppresses motion on later visits. Rejected autoplay exposes a
play control, media errors can be retried, and reduced motion remains respected.
