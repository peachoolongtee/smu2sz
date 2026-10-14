# Handoff 17 (14 Oct 2026, evening): Slice B round three, to be built on the second machine

Read in this order: handoff 14 (protocol, gates, run commands), handoff 16 "overhaul plan" (the whole plan and the owner's
decisions not to re-open), then the brief this handoff executes: `docs/design/flow-mockup-2026-10-13/05_slice_b_round_three.md`
(with its §11, the deal tracker folded into Deals). Handoff 16 "slice D and tracker" is the second machine's own notes.

## Where dev is
- The accept-as-asked batch (the owner's accept and decline of a buyer's request; the queue expand cue) is merged into dev
  `--no-ff` on 14 Oct evening (see `git log --first-parent dev -3`). It passed an independent verifier (six claims on the busy
  books: authority, money, siblings, words, the cue, the 409 in place) and the full gates: tests/api 1359+, unit 152, whole mock
  435 / 0 failed, whole live 141 / 0 failed. Debt from it: #158 (executor), #159 (words). Do not reopen either in round three.
- The deal tracker (map #148) is on dev at its own route `/decisions/{id}/tracker`; nothing links to it yet. Round three §11 is
  where it enters Deals.
- Open with the owner, not blocking: the tracker cost switch Option A (today) or B (#155); the four FLAGs in the brief (ink
  not blue for the chart's primary; lighter selection weight; Business consequences inside the Cash impact tab; one funding
  mode until engine #147). Build as the brief says unless the owner answers.

## What to build: the brief, as two branches and one verifier
Start from dev AFTER the accept merge (check `git log --first-parent origin/dev -1` names it). Branch names are distinct from
anything this machine used: `feat/slice-b-r3-api` (services/api only) and `feat/slice-b-r3-web` (apps/web only). One worktree
each; one server implementer, one frontend owner; a verifier in a detached worktree with its own scratch folder.

### Server first (feat/slice-b-r3-api): the words batch of the brief
In the order the web needs them: (1) per-path short words and `terms[].scope` (§2, §3, §5); (2) `recommendation {mandate_text,
alternative_text, rule_text}` (§3; the browser's `deals.why.rule` dictionary string moves here); (3) `scenarios[]` on the picture
read composed from the exposure and compare reads (§4); (4) the per-point `comparison` map and `comparison_pairs` with
`cause_text` (§6); (5) §11: `lifecycle_stages[]` on the deal workspace read and the tracker read from ONE function; the queue's
closed rows and the `queue.deals` closed count; `buyer_history_text`; the Customer overview's `deals_history[]`; Activity's and
the Demo story's hrefs to Deals for agreed and ended deals. Every word en and zh; tests in `test_slice_b_round_three.py`
(golden day 0 with Option B; the busy books' Zhuhai deal with one reply; a state with no recommendation; the golden story walked
to its end for §11; zh). Nothing in the engine stability set (app/financial, verifier, funding, alerts, operations, clock,
books, mandate, covenants, domain/models.py); the picture read may call the exposure/compare functions, not re-derive them.
Hand the web the head after (1) and (2) so it can start; the rest follow on the same branch.

### Web (feat/slice-b-r3-web): the page, in vertical slices
Suggested order, each slice with its focused specs before the next: (a) the tabs, the address (`?view=`), the sticky header,
one scroll, the rail collapse (§7); (b) the Overview (§1, §3) and the terms-by-scope block (§2); (c) Compare responses (§1, §4,
§5, §7's Choose/Review buttons); (d) Cash impact: outcome table, headroom dot plot, the chart's chips, colours, markers, the
inspector's two blocks, "what caused the difference", Business consequences (§5, §6, §4); (e) Messages and the queue changes
(§9); (f) §11: the lifecycle strip, the tracker body shared with its route, the Terms tab, the Closed group, "Last time", the
Customer history rows and the entry points. Re-record the mocks after each server hand-back with the recorder (never
hand-edited; the recipe is in handoff 14 and in the accept-as-asked notes: the standard set with `--no-exposure` on an
exposure-off API, each other set on its matching API). Old addresses (`investigate=1`, `compare=1`, `chart=1`, `show=`) land on
`view=compare`; the round-two specs that pinned those sections are amended, not deleted, so the pins survive.

### Verifier (before the merge)
The six journeys in the brief's "Verifier" section, hand-checked against the API, not the implementers' tests; two passes are
normal for anything about money or authority (handoff 16: every pass so far found something 1,100 tests did not).

### Gates and the merge
Focused specs while building; at the merge: tests/api, typecheck/lint/unit, ONE whole mock and ONE whole live run, zero
retries, by the lead, on the merged tree; `--no-ff` into dev; plain one-line commits; no attribution lines; DESIGN.md's Deals
section rewritten to the three levels; close #152 and #154 with the counts, comment #153 (its display slot is built, the grade
is not); note the round on map #121 (#143) and #148.

## Coordination with this machine
- This machine will NOT touch Deals, Customer, Activity, the Demo story or the tracker while round three is open. It may take
  Slice C (Receivables and Cash: brief to be written) or the engine tickets; it will announce on the map before starting, and
  it will not merge into dev without pulling first.
- Before any push to dev: `git fetch`, merge `origin/dev` into the branch, re-run the focused specs. Before the merge: pull
  dev; if it moved, merge it in and re-run the whole pair.
- Distinct branch names (the `-r3-` names above); never ports 3000/8000; kill by own PIDs only; each agent its own scratch
  folder and only scripts it wrote.

## Run it
`scripts/dev.sh live` or `scripts/dev.sh mock` on this machine; on the PC start Next and uvicorn directly (handoff 16's note).
Busy books: Demo page → "Which books?" → Busy company → Load; owner header `X-Owner-Token: demo-owner-token`. The accept flow:
Deals → Zhuhai → "Review the request".
