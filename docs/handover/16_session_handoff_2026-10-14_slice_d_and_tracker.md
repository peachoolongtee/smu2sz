# Handoff 16 (14 Oct 2026, small hours): Slice D and the deal tracker, paused before their merges

Read handoffs 14 (protocol, gates, run commands) and 15 (the Slice D brief) first. This session ran on the second machine
(Windows, Git Bash). It was paused at the owner's request with every branch pushed and nothing merged into dev. Nothing here is
on dev except this file.

## What the owner asked for in this session, in order
1. Pull dev and read brief 15; mock up Activity and Demo; "go with the dialog and start slice D".
2. Reconcile `feat/agent-optimiser` (haoencheo2025's buyer reliability score); "go with your recommendation" (one measure with
   payment behaviour), then: what he actually wants is a deal lifecycle tracker; "build this" (Slice B is working on Deals in
   parallel, stay clear of it); "chart this as a map".
3. For the tracker's funding figure he chose **Option A** (funding after a late payment counted in the deal's total). The lead
   has since recommended B twice on the verifier's evidence; **he has not answered**. The switch is on A.
4. Asked how to break the product down for the pitch; the lead offered to update `docs/deliverables/deck_outline.md`; **no answer yet**.

## Where each piece stands

### Slice D: Activity and Demo (map #121, ticket #145)
- Branches (pushed): `feat/slice-d-api` 832e41d0 (services/api only) and `feat/slice-d-web` 9b18524e (apps/web, with the API
  branch merged in). Both cut from `feat/slice-b-web` b4cb713a. **Neither has dev merged in yet; Slice B landed on dev
  (866b52d5) during this session, so that merge is the next step.**
- Built: `GET /activity` (every operation and security event once, classified business / security / benign_auth / system, the
  ledger's own words, the actor from the approval record); `GET /demo/story` (where the six scenes stand, derived from the
  books; one `next`; the alternate scenario with a loss preview; operator tools; proof links; a `books` block and a
  `loss_token`); `POST /demo/restore`; `from_scenario` / `confirm_loss=<token>` on reset and restore with 409 BOOKS_CHANGED /
  LOSS_NOT_CONFIRMED / LOSS_CHANGED; `/audit` events gained words. Web: Activity on the new read; Demo as one scene with one
  filled next; the strip on other pages follows the server's story; one guarded dialog for every reset or replacement of the
  books (`lib/books-guard.ts`); `/trust?view=evidence|security&entry=|&event=&from=` (no menu row); the tour fix.
- Last runs by the web owner at 9b18524e (zero retries): unit 132; **whole mock 365 passed, 41 skipped, 0 failed; whole live
  111 passed, 30 skipped, 0 failed**. The lead's own gate last ran one round earlier (68497b0f: static green, mock 364 / 40 / 0,
  live 94 / 30 / **15 failed**, API 1136 / 2): the 15 were the sign-in dialog opening by itself on every live page (the shell
  read the owner-only story for visitors) and one stale Activity spec; both are reported fixed, **not yet re-run by the lead**.
- Independent verifier, two passes. Holding: no audit event disappears; nothing presses the owner's approval; the reads change
  nothing and leak no ids; restore equals a fresh reset field by field; failed sign-in evidence links land on their event.
  Second pass still broke "the books cannot be silently replaced" three ways (a double click at widths up to 768 px lands on
  the dialog's confirm; a stale page on the same scenario confirmed a stale list; documents and customer inputs were not
  counted as loss). All three are reported fixed in 832e41d0 / 9b18524e (the token, the fingerprint against a fresh reset, the
  armed confirm that ignores `event.detail > 1`). **A third verifier pass has not been run.**
- Decided by the lead and to be confirmed by the owner if he cares: the restore cannot be "logged as an operation" (a reset
  wipes the log and the executor is in the stability set), so the swap history is in memory and is not shown; the old "Your
  agreements" and set-aside blocks left Activity (agreements are rows with "Open this decision"; refusals sit under Security).
- Known and left: "the cash would land 2 days ago" on a decided request row (older shared ledger wording, a words follow-up);
  the strip's own forward button is brand blue (outside the `.flow-f` scope: Slice E); an offer submitted but never evaluated
  is not in the loss count (the store cannot list such offers); books this process did not reset count as "something to lose".
- To finish: merge `origin/dev` into `feat/slice-d-web` (expect conflicts in globals.css, DESIGN.md, dictionary, mock handlers,
  e2e helpers; Slice B's side for its own files), re-record `--slice-d`, whole mock + whole live + tests/api by the lead, a
  third verifier pass on claim 1 only, `--no-ff` into dev, close #145 with the counts, write Dylan's PR comment (kept from
  ui-ux-testing: the two trust views rebuilt on the kit as one `/trust` page by address, and the tour placement fix; dropped:
  the rest, including the menu row and `lib/mode.ts`).

### The deal tracker (map #148; tickets #149 read, #150 page, #151 verification, #152–#155 later)
- Branches (pushed): `feat/deal-tracker-api` 8c2f0017 (one new module `app/api/deal_tracker.py`, its test, one line in
  main.py) and `feat/deal-tracker-web` (the page on its own route `/decisions/[id]/tracker`, new files plus small marked edits
  to shared files). Both cut from `feat/slice-b-web` b4cb713a.
- **In flight when this was written:** the web owner was merging 8c2f0017 and `origin/dev` into `feat/deal-tracker-web`,
  re-recording `--tracker` and running the whole mock suite. See the addendum at the foot for its result.
- The read, as verified on the golden story (fen): expected 302,777 = terms 218,620 (0.85% of ¥257,200.00, booked from cash)
  + funding planned at agreement 84,157 (the gap plan's draw ran at agreement); after the owner approves the day-34 cure,
  funding "after this buyer's late payment" 178,219. Switch A (today): actual 480,996, on top 178,219. Switch B: actual
  302,777, related 178,219 shown beside. `COUNT_RELATED_FUNDING` in `app/api/deal_tracker.py` is the switch; the page renders
  either from the data (uncounted related lines go in an "outside this deal's cost" block, covered by a unit test only).
- Rules it now follows: no new pricing (every figure a stored value or an integer sum or difference); a discount is booked only
  from cash; only executed receipts count; later funding is a line with `relation` and `counted`, counted only when this buyer
  was the only late buyer and this deal its only late deal when the cure was quoted (by log order), never in two trackers;
  funding secured on the deal's invoice is shown, never counted; a deal is ended only when every invoice is paid; a promise
  paid after its day is "paid late", not kept.
- Independent verifier (#151), two passes: the golden figures match the records to the fen at seven moments; pass one found a
  phantom discount, a refused receipt changing money, a cure counted in two trackers and wrong ended / kept verdicts; pass two
  confirmed nine of ten fixed and found three more (lateness judged by day not log order; the terms component derived from
  the plan that ran; a receipt at face before the agreement booking a discount). All reported fixed in 8c2f0017 (37 tracker
  tests; tests/api 1146 passed, 2 skipped, the implementer's run). **A third verifier pass and the lead's gate have not been run.**
- Evidence for the owner's A-or-B decision: with the buyer fully on time the same shortfall still needs ¥331.49 of funding, so
  counting the whole ¥1,782.19 in the deal's total overstates what the lateness cost. Under B the story ends "closed as
  expected", ¥3,027.77 against ¥3,027.77.
- To finish: the third verifier pass (give it `tracker-verify`, moved to the new head), the lead's gate (whole mock, live
  tracker + record, tests/api), `--no-ff` into dev after Slice D, close #149 to #151 with the counts.

### The optimiser branch (#153)
`int/agent-optimiser` (pushed) = dev eb16ef20 + the branch's server commit and decision record (renumbered ADR-0013). Its 12
tests and tests/api + tests/strategy (1599 passed, 8 skipped) pass. Held out of dev: on day 0 it grades Foshan 90 (Reliable) and
Dongguan 39 (Risky) from an imported history while payment behaviour says nothing can be said yet. The owner's decision: one
measure (the grade reads payment behaviour's rule and history), after Slice B; the web commit (72efa4d8) needs a port.

## Open with the owner
1. Tracker Option A or B (the lead recommends B).
2. #155: physical deliverables (out of version one); the grade as a word or only its evidence.
3. Whether the restore should be in the hash chain (needs a small engine change).
4. Update the deck outline now, or after the merges.

## How this session worked, and what to keep
- Lead specifies, reviews screenshots, gates and merges; sonnet implementers (`backend`, `frontend` agent types on this machine)
  in their own worktrees from spec files at the worktree roots (`SPEC_*.md`, `REF_*.html`, never committed); independent
  verifiers (general-purpose) in their own detached worktrees with a scratch folder each.
- **Two things the focused runs missed and the lead's gate caught:** six mock failures outside the slice's own 15 files (a
  dropped customer link among them) and fifteen live failures (a real regression). An implementer reports only after ONE whole
  mock run and ONE whole live run are green.
- **Every verifier pass found money or safety defects that 1,100 passing tests did not.** Budget two or three passes for
  anything about money, authority or the books.
- An agent ran another agent's leftover script from the shared scratchpad and edited a file in the other's worktree
  (uncommitted; the file was found clean afterwards; a `git checkout` it then attempted was denied and was not run for it).
  Give each agent its own scratch folder and tell it to run only scripts it wrote.
- This machine: `scripts/dev.sh` and `pnpm dev:mock` / `dev:live` set variables inline and default to ports 3000 / 8000, which
  are not to be used here; start Next and uvicorn directly. Ports used: slice D web 3221 to 3223 / 8221 / 8223, tracker web
  3241 to 3243 / 8241 / 8243, API agents 8211 / 8231, verifiers 3262 / 8262 and 3272 / 8272, the lead's gate 3252 / 3253 / 8253.
- Worktrees under `.claude/worktrees/`: slice-d-api, slice-d-web, slice-d-verify (+ -scratch), deal-tracker-api,
  deal-tracker-web, tracker-verify (+ -scratch), int-optimiser. Gate logs sit beside them (`slice_d_gate2_*.log`,
  `tracker_api_gate.log`). Mockups: the owner's private canvas "FLOW Slice D Mockups" (seven Slice D boards, the tracker board,
  Option A and B side by side).
- Subagent ids do not survive a new session: resume from the specs, the branches and this file.

## Kickoff for the next session
Pull dev; read this file; check whether dev moved (Slice B round two was designed on the other machine). Then, in order:
Slice D (merge dev in, re-record, the lead's whole gate, the verifier's third pass on claim 1, merge, #145, Dylan's comment);
the tracker (its integration result below, the verifier's third pass, the lead's gate, merge after Slice D, #149 to #151);
then #152 (entry points), #153 (one measure) and #154 (close-out carry-over) as the map orders them.

## Addendum: the tracker's integration round (reported after the pause was asked for)
`feat/deal-tracker-web` is at 893a5ac2 (pushed) and now CONTAINS dev (Slice B, 866b52d5) and `feat/deal-tracker-api` 8c2f0017.
The only conflict was `playwright.config.ts` (dev's live `testMatch` kept, `tracker` added); the one link on the decision
record, the one mock route, the dictionary block, DESIGN.md and package.json merged by themselves. `--tracker` re-recorded on
the merged tree (stable on a second run). The web owner's runs, zero retries: unit 133; **whole mock suite 394 passed, 47
skipped, 0 failed**; live `tracker.spec.ts` 1 passed (`record.spec.ts` is not in the live project). The eyebrow prints the
server's `agreed_text`. Still to do, unchanged: the verifier's third pass, the lead's own gate (whole mock, the whole live
project, tests/api on the merged tree), the merge after Slice D. Because this branch already holds dev, Slice D should merge
dev first and land first; then merge dev into this branch once more before its gate.

## Update, 14 Oct midday
- Slice D was finished and merged into dev by the other session (4804370d), with the owner's "Which books?" addendum. Nothing of Slice D remains on this machine's list.
- The deal tracker is merged into dev (86e8a9bb): #149, #150 and #151 closed with their counts; the map (#148) frontier is now #152 (entry points, unblocked), #153 (one measure), #154 (close-out and carry-over, unblocked) and #155 (owner decisions). The switch stays on Option A.
- The gate on dev + the tracker found dev's own failures, filed as #157 (demo.spec.ts:527 and live.spec.ts:329 broken by Slice D's last commits; three flaky) and an update on #156.
