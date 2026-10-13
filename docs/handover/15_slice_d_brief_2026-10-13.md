# Slice D brief: Activity and Demo (map #121, ticket #145), to start in parallel on a second machine

Slice D touches pages no other running branch touches (Activity, Demo, the trust views, the Demo tour), so it can start
now. Branch from `origin/feat/slice-b-web` (b4cb713a), NOT from dev: that branch carries the current kit (CommitmentReceipt,
StatusPill, `.flow-f`, PageHeader rules) and the Slice B pages; when Slice B merges, merge dev into this branch (small
conflicts in globals.css / DESIGN.md at most). Branches: `feat/slice-d-api` (services/api only) and `feat/slice-d-web`
(apps/web only), one worktree each, one frontend owner, one server implementer, a verifier before merge. Read handoff 14
first for the protocol, gates and run commands.

## The decisions (tickets #135 and #136, resolved 13 Oct; the owner's reconciliation on #136)

**Activity (#135).** A stable title ("Activity") with the state as the subheading (UX15); business events first (what
changed, why it matters, what remains, with "Open this decision" visible beside an outcome, UX24); benign authentication
failures summarised in one line apart from real security alerts, full evidence under disclosure, no audit event deleted
(UX10); a search box and a category filter; the ledger, security and evidence views hang off Activity as evidence links,
reached from the event that produced them.

**Demo (#136).** One current scene and one next control (UX18); the optional scene is "Load alternate scenario" with its
scope and a LOSS PREVIEW (what the main books lose, in words), a confirmation, and a one-click "Restore the main books"
afterwards (owner's reconciliation: no isolated per-session books now; revisit isolation only if the judge path needs it)
(UX19); clock, reset and the engine destinations behind an "Operator tools" disclosure; the manual owner boundary kept
(the approval scene is still the owner's click); a proof appendix linking the engine views (ledger, evidence, security,
the hash chain) from the scene that produced them. The busy company scenario (`POST /demo/reset?scenario=busy`) is the
data for the judge's path; the golden story stays the six-scene walk.

## What to salvage from Dylan's `ui-ux-testing` branch (27c0e95a; base 3ae6cf8f), and only this

- `apps/web/components/trust/evidence-view.tsx`, `security-view.tsx`, `app/trust/page.tsx`, `app/trust/layout.tsx`: the
  trust views (evidence, security) as one place; re-point `app/evidence` and `app/security` at them (his diff shrinks those
  pages to wrappers). Restyle to the kit (no hand-rolled cards or pills); keep every record and hash visible.
- `apps/web/components/business/tour.tsx`: the tour placement fix (the step popover no longer covers its target).
- `apps/web/components/business/reconciliation-section.tsx`: NOT this slice (Slice C, Receivables), leave it.
- Everything else on that branch (the other 28 files) is dropped; tell Dylan in the PR what was kept and why.
  `git diff 3ae6cf8f origin/ui-ux-testing -- <path>` shows each file.

## Server (feat/slice-d-api)

- GET /activity (app/api/activity.py or wherever the read lives): every row carries `kind` (business | security |
  benign_auth | system), `title_text`, `why_text`, `remaining_text`, `decision_id` + `href` when an outcome has a
  decision to open, `evidence_href` for the ledger/evidence/security view that proves it, `when` (relative word, en/zh),
  `category` for the filter; a `summary` block with `benign_auth_text` ("3 failed sign-in attempts today, all refused;
  nothing was reached") counted apart from `security_alerts`. No audit event is removed or merged; the summary is a
  sentence beside the rows, not a replacement.
- GET /demo/story (or the Demo's read): `scenes[]` with `state` (done | current | next | locked), one `next` control
  {label, href|action}, `alternate` {label "Load alternate scenario", scope_text, loss_preview_text, confirm_text,
  restore_text}, `operator_tools[]` (clock, reset, engine views) and `proof[]` (per scene: the evidence links it
  produced). `POST /demo/reset?scenario=busy` and `?scenario=golden_sme` already exist; `restore` = reset to the main
  scenario and is logged as an operation.
- Every word en and zh; tests in tests/api (one per read, both languages; the busy books and the golden story).

## Web (feat/slice-d-web)

- Activity: PageHeader "Activity" + state subheading; the business rows first (title, why, remaining, "Open this decision"
  as a quiet link beside the outcome), then "Security" with the one-line benign summary and the real alerts, evidence
  under `Disclosure`; search (client filter over the words already read) and the category SegmentedTabs; evidence links
  go to the trust views with `?from=activity` and the view shows "Back to Activity".
- Demo: the six scenes as a vertical list with ONE filled "Next" (the current scene's control, named: "Read the offer",
  "Approve the cure" …); the approval scene stays the owner's click; "Load alternate scenario" as an outline button that
  opens the loss preview + confirm, then "Restore the main books" visible until used; "Operator tools" as a Disclosure
  holding clock advance, reset and the engine destinations; the proof appendix under the scenes.
- Phone: the Next control inside the first viewport; the tour's steps point at the right targets at 390.
- Specs: activity (rows, summary, filter, evidence link + back), demo (one next, the alternate flow with restore, operator
  tools folded, proof links), the tour placement; both under mock (record the new reads with the recorder) and live.
- Verifier before merge: the main books cannot be silently replaced by the alternate scene (the preview says what is
  lost, the confirm is required, restore brings the same day-0 counts back); no audit event disappears from Activity
  under any filter; every evidence link lands on the record it names.

## Done means

API suite green; typecheck/lint/unit green; the Activity, Demo, trust and tour specs green under mock and live; the full
pair at the merge; DESIGN.md gets an "Activity and Demo" section; ticket #145 closed with the counts; the ui-ux-testing
PR comment to Dylan.
