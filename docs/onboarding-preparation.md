# Onboarding and checkout preparation · 19 October 2026

Implemented locally. Not pushed, deployed, or activated in production by this task.

After finishing (or skipping) the website introduction, a small branded dialog shows the Builder Bud and three spinner/checkmark steps. It brings the saved choices together and fetches the real plan page before navigating. Optional answers stay in the browser; this screen does not send them to a model, invent a personalized subscription, or create a workspace/build. The normal fast path is about 1.3 seconds; “Continue to plans” can bypass it immediately. Page-load failure/timeout provides a direct exit, with no endless loader. JavaScript-disabled users keep their existing plans links.

The same dialog covers confirmed workspace checkout while the actual session request runs, then validates the HTTPS Stripe destination before showing the handoff. An interrupted or failed request returns to the order review with an error. Requests abort after 20 seconds; existing idempotency keys and server billing permissions remain. Prices, release gates, waitlist mode, and payment enablement are unchanged. The billing portal and purchased-credit routes retain their direct, validated redirects.

Desktop Settings → Team plan & billing already opens this website account flow. It receives the same preparation screen at checkout; no separate native billing or compulsory payment step was added to app onboarding.

Accessibility: native modal focus containment, named steps, polite live status, restored focus after cancellation/failure, one optional plans action, small-screen scrolling, light/charcoal surfaces, and reduced-motion spinner/entrance behavior. Browser back/forward restoration closes a stale dialog.

Validation: 68 focused tests passed, including eight Chromium browser cases against isolated FastAPI/Stripe fixtures. Coverage includes full introduction, skipping, mobile/reduced motion, preload error, monthly and annual checkout, checkout service failure, unsafe URL rejection and timeout recovery. Existing public-page, waitlist and backend checkout checks pass. No live charge or real provider call was made. UI captures are in ignored `work/preparation-preview/`.

Owner actions: no account, credential, SQL or payment action is required for this source change. A normal authorized source push and website deployment are still needed before users can see it. This task has not changed hosted services or the packaged desktop app.
