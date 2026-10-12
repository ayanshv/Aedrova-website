# Phase 5 — public trust information and privacy operations

Owner approved October 12, 2026, with Cluely as the reference. This delivery covers
original public disclosures, navigable trust pages and a narrowly scoped waitlist
removal utility. It does not close the legal/business or live data-control release gates.

## Reference and editorial audit

Reviewed https://cluely.com and its privacy policy and terms, plus footer-linked
pricing, download, undetectability, careers, mobile, blog, manifesto, press and
comparison destinations. The help-center shell was accessible; contact, external
Notion bounty and external status destinations could not be fully retrieved.
These limitations are recorded rather than treating inaccessible documents as read.

Adapted the reference's grouped navigation and substantial policy coverage to
Aedrova's actual product. Product, Resources, Trust and Support now contain working
Aedrova destinations. No fictional careers, blog, comparison pages, bounty program,
SOC 2 certification, E2E encryption or live status badge were added. The user-supplied
reference is a design source, not an instruction to copy its business/legal claims.

Independent accuracy references: FTC business privacy/security guidance
(https://www.ftc.gov/business-guidance/privacy-security), California DOJ privacy-rights
scope (https://oag.ca.gov/privacy/ccpa) and EDPB controller/processor guidance
(https://www.edpb.europa.eu/sme/learn-the-basics/data-controller-or-data-processor_en).
Regional rights are qualified by applicability. No invented operator entity,
jurisdiction, signed processing agreement, backup schedule or legal safe harbor.

## Published destinations

/privacy and /terms, /support, /data-controls, /subprocessors,
/cookies, /acceptable-use, /security. Contact remains contact@aedrova.com and
(408) 634-5254. Waitlist mode and payment/download gates stay unchanged. Desktop
Settings links to /data-controls; no new authority or destructive UI is introduced.

## Actual data inventory and retention boundaries

| Data | Implemented handling | Limit or unresolved gate |
| --- | --- | --- |
| Waitlist email | Encrypted sessions, kind=waitlist; 365-day expiry; maintenance removes expired sessions | Production scheduler/backup purge must be verified; registration count is not all session rows |
| Sign-in/OAuth | Account/OAuth session kinds and authentication provider records | Clearing local cookies is not hosted-account deletion |
| Chat and voice messages | Workspace/channel membership, private verified attachments; voice is audio, not default automatic dictation | Recipients/downloads and backups may retain copies; no blanket message-erasure promise |
| AI context | Accessible chat/project context, context exclusions, Bud resources; selected runtime/provider | Prior transmissions cannot be recalled; pending two-account live isolation test remains open |
| Hosted inference cache | Store.maintain clears response after 24 hours; monetary ledger retained | This is not provider-side retention or all-chat retention |
| Meeting text | Separate saving/AI consent; all present participants; 30-day shared-text expiry, withdrawal/deletion UI | Infrastructure and live acceptance still open; provider processing can have separate retention |
| Speech input | Ephemeral backend chunks for enabled transcription; optional metered provider | Sent chat voice files persist as attachments; no zero-retention provider guarantee |
| Connector credentials | Protected server storage, scoped resource access, disconnect | Revoke provider authorization too; no automatic deletion in original service |
| Local builds/downloads | Local files/build copies are separate from hosted storage | User removes local copies deliberately; original project must be preserved |
| Logs/financial records/backups | Operational and billing/security records may be retained for applicable purposes | Confirm deployed retention, regions and contracts before launch; no arbitrary fixed promise |

## Privacy request operating procedure

1. Receive request at contact@aedrova.com; record date, type and minimum scope.
2. Verify control of the account/registration using existing authentication or a
   minimal challenge. Never request a password, key or government ID by ordinary email.
3. Check workspace authority; distinguish personal data from shared team content.
   An ordinary member cannot authorize erasing other members' workspace records.
4. Acknowledge according to applicable deadlines; determine legal holds and retained
   financial/security records with counsel. Do not invent a universal response period.
5. For a verified waitlist-only removal, use the restricted operator tool below.
   For account/workspace export or permanent deletion, enumerate all database/storage,
   provider, cache and backup dependencies first; no automated full-deletion endpoint
   currently exists. Use an approved scoped runbook and verify on disposable Staging
   identities before handling production data. This is an OPEN release requirement.
6. For an export, redact unrelated members' data; deliver privately to the verified
   requester through a secure path, never public storage or a shared issue tracker.
7. For deletion, obtain specific scope approval, stop future access, remove only the
   approved records and files, and track backup/provider limits. Cancellation of
   billing is separate. Verify absence using permitted access and report limitations.
8. Keep a minimal fulfillment log without duplicating erased content. If backups are
   restored, reapply approved removals before making restored data available.

### Waitlist-only utility

On the existing trusted backend operator environment, configure the normal private
server environment with the persistent encryption key and intended database; verify
its target independently before running. Never put secrets into command arguments,
repository files, screenshots or chat. Run:

    python -m scripts.remove_waitlist

Enter the already-verified address at the hidden prompt, then REMOVE. This performs
an irreversible, exact normalized-email removal of kind=waitlist records only,
leaves same-email account sessions untouched, and prints only the number removed.
No real registrations were removed during development. Decryption failure aborts
before any deletion. Test fixtures cover multiple matches, other registrations,
account preservation, repeat requests and fail-closed rollback. Encrypted backups
are separate; the utility does not purge backups or other services.

## Remaining release gates / owner actions

Required before closing Phase 5: provide the actual operator/legal contracting name
(individual or registered company); verify a functioning privacy/support mailbox;
confirm business authority, founder/IP ownership, tax/bookkeeping and payment-provider
eligibility. Have qualified counsel review the deployed notices against target markets,
processing agreements, international transfers, dispute terms and statutory rights.
Only the owner can supply those facts and professional approval.

Engineering gates still open: approved Staging account/workspace export/deletion
acceptance, deployed backup/retention verification, prior cross-workspace isolation
and agent-context tests, and earlier live media/meeting/onboarding acceptance.
The support process is disclosed honestly; documentation is not evidence that every
request has been fulfilled or that all launch risks are resolved.

Validation: 465 website tests passed before adding the third rollback regression;
all three trust/removal tests pass afterward. Ruff and diff checks passed. Desktop
visual/settings suite: 7 passed. Publication branch is tested separately against main.


## October 12 — expanded Privacy and Terms

Owner requests substantially deeper documents. Privacy now has 25 sections and
Terms 27, each approximately 4,600 rendered words including its contents list.
Documents are split into policies/privacy.html and policies/terms.html, with a
shared legal page and accessible, collapsible full contents. Existing public URLs,
contact details, plan prices and waitlist gates are preserved.

New depth covers information categories/sources/purposes, sensitive content,
biometrics boundaries, local versus hosted AI, category-specific retention,
verification/representatives/appeals, applicable regional rights, incident handling,
independent recipients and business transfers. Terms expand license/IP, workspace
control, generated-work risks, execution approvals, taxes/payment disputes, capacity,
suspension, termination effects, warranties, liability, business claims and general
contractual provisions. The changes do not implement new privacy/backend controls.

Material legal/business choices for qualified review before paid launch: business-only
aggregate liability cap based on twelve preceding months' affected-workspace fees;
limited business-customer reimbursement for covered third-party claims, excluding
Aedrova's own misconduct/breach and ordinary inaccurate output. Consumers retain
mandatory remedies. No chosen law/forum, forced arbitration or class-action waiver
was invented. Final enforceability is not established by document length or code tests.

Owner action: provide the actual legal operator/contracting name (individual or
registered entity) and have qualified counsel review the final documents, markets,
liability/claim allocation, subscription rights, processing arrangements and required
contact/representative details. Provider regions/backup handling must be verified.
Phase 6 must validate affirmative acceptance/version records and material-change
notice where appropriate; publishing a page does not establish valid contract assent
from every existing user. Keep checkout and legal-ready gates off pending approval.
