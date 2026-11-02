# Homepage pacing and scroll motion

November 3, 2026. Reference review: https://cluely.com and https://shotbase.com.
The review focused on staged product reveals, chapter pacing and subtle interface
depth. Aedrova retains its own type, colors, Buds, screenshots and copy. No reference
site assets, reviews, claims or code were copied.

The homepage now has 7 sections instead of 16. Repeated standalone screenshots
became a five-topic product tour: Workspace, Shared context, Build & review,
Buds & tools, and Meetings. Detailed meeting consent/device information remains
available in a native disclosure. Existing feature anchor links still select their
panel. The server renders all topics; without JavaScript, they remain readable.

Motion is limited to 620 ms entry reveals, a capped 65 ms stagger, 260 ms panel
transitions and a small desktop screenshot perspective settle. Scrolling stays
native. No scroll interception, pinned multi-viewport scenes, autoplay carousel,
text scrambling or decorative particle effects. Scroll work is passive,
requestAnimationFrame-coalesced, and limited to the visible product stage.

At 390 px, the selector uses balanced three/two rows, the Bud lineup uses three
columns, spacing/type adapt, and continuous perspective motion is disabled.
Prefers-reduced-motion disables the new animations and transforms, including when
the preference changes during the visit. Light/dark screenshots remain matched
to the selected theme. Tabs support Left/Right/Home/End and selected/focus states.

Verification: public page/navigation, discovery, release gates and translation
asset fingerprint checks; JavaScript syntax, Python style and tracked-secret checks.
Browser review covered desktop light/dark, 390 px mobile, tab switching, arrow-key
selection, and the Meetings anchor. Source and image captures are in
work/home-scroll/. Reduced-motion behavior was inspected in source; no physical
mobile device or OS reduced-motion preference change is claimed.

No owner payment, migration or private account setup is needed for this website
update. Public installer, provider and meeting readiness gates remain in force.
