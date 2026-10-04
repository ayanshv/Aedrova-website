# Meeting website showcase

Captured the actual rebuilt Mac app's Meetings tab and local device-check sheet through
native UI automation, in light and dark mode. Disposable local preview settings and sample
workspace only; no people, live camera frames, private chat or credentials were published.
Only native title chrome was cropped from workspace captures; UI was not redrawn.
Screenshots switch with the website theme. Raw captures and responsive QA are ignored
under work/meeting-captures.

The homepage now describes channel calls, audio/video/screensharing, gallery/speaker
views, local device checks, join cards, participant photos/counts, shared announcement
channel configuration and private-channel scope. Optional audio transcripts and separate
AI reuse consent are described accurately. It explicitly distinguishes audio/text context
from visual screen understanding. Added a Meetings navigation anchor and updated FAQs
and plans disclosures. Public launch remains waitlist-only; no billing/provider/release
flag or price changed. Public calls and final multi-device acceptance remain pending.

Validation: 247 local website tests passed. An isolated copy of GitHub HEAD plus only
these publishable changes passed 192 tests. Ruff and diff whitespace checks passed.
Desktop/browser light and dark screenshots inspected; 390px mobile viewport has no
horizontal overflow. No Docker runtime was available locally; CI covers Docker startup.

Owner actions: none for this website content update. The desktop shared announcements
still require the separately provided 202610030004_meeting_activity.sql migration in
Supabase if it has not already been applied. Public meeting hosting, consented speech
provider setup and final two-device validation remain deferred release work.
