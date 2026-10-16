# Handoff 19 (16 Oct 2026): dev reconciled after the Deals redesign, the security fixes and Dylan's UI

Written on the lead's machine after pulling `origin/dev` at **1fe0f764** (63 commits since this machine's last push,
e8e270f8 on 14 Oct). It records what landed, what it supersedes in the plan documents, what it left dangling, and what is
next. Read it before handoffs 16 and 17, which it amends.

## 1. What is on dev now (first-parent, oldest first)
| Merge | What |
|---|---|
| 4294a01f … 0ba8e4c1, 081541d1 (15 Oct) | Security Lead fixes SEC-01..05, 09, 10, 12, 13, 16..18 (intake hardening, one agreement per request, authority boundaries, the attack harness runs again, headers). Certified on `0ba8e4c1` and `a6de32a2` (`docs/security/CERTIFICATIONS.md`); S = GO, S-net = CONDITIONAL, P = NO-GO (`RELEASE_GATE.md`). |
| 31058785 (15 Oct) | **Slice B round three and the Deals redesign (#160, closed).** The owner reviewed round three's tabbed pane on 15 Oct (buggy, not intuitive: the rail, the charts, the breadcrumb, no Option B on the busy books) and it was redesigned: a deal opens as its own page with "All deals" and a prev/next walk, the recommendation first, one choices table, Cash impact as thin bars and two lines, scenarios on their own route, "Accept their request", why a reply is withheld, what happens if the buyer refuses, the Agreements grouped by money owed (Payment late / Awaiting payment / Closed), one row per agreed deal, the tracker as the agreed deal's Overview. DESIGN.md's Deals subsection now describes it (this handoff's commit). |
| e65c2378 | ADR-0006 amended: only the owner moves the clock (SEC-09). |
| a6de32a2 (16 Oct) | **Dylan's redesign of Home, Cash, Receivables, What-if, Activity, the trust pages and the shell**, on dev's Deals, with the owner's decisions (the alarm card keeps its risk tint, no glow or gradient anywhere; deal tools and step guide omitted; agreements folded inside the money groups; Home's deal rows open Deals, the in-place deal view removed; the funding ring hidden on a phone's Home). Mocks re-recorded; GitHub checks on every push (`.github/workflows/checks.yml`); **the branching rules** `docs/agents/integration.md`; `docs/NEGOTIATION_COMMUNICATION_HANDOFF.md`. |
| 8e80b8bc | Dylan's landing page (`/welcome`, "Access FLOW", `lib/account*.ts`); no empty review card after a send. |
| bbbfb7ce, 76933885, 1fe0f764 | Security Lead: the red-team d test re-pointed; `docs/security/*` (findings register, certifications, release gate, attack surface, evidence) and the route inventory script; the self-assessment updated. |

What Dylan's UI changed, page by page (read by the lead on 16 Oct):
- **Home** is still Home V2 (`HomeV2Page`): the cash card gained the funding ring (`lib/funding-mix.ts`, server strings, fen
  only size the arcs); the recommendation card runs nothing any more (its primary "Check funding plan" goes to `/cash`, the
  plan runs on Cash); the in-place deal view (`deal-focus.tsx`) is gone and a worklist row opens Deals with `from=home`;
  `/?decision=` redirects to Deals; the worklist table, upcoming movements and the owed-by-customer donut stay.
- **Cash**: the plan is first at every width, then the chart, then "Try other terms" and "More funding" cards, the options
  fold, "Your funding" (facilities and a buyer's agreed early payment in one list), readings. Still `CashPicture`; no scenario
  control; `?stress=` only.
- **Receivables** is a customer list first (`ListCard`s), the invoices on `?customer=`/`?buyer=` with "Back to list"; the
  three summary cards on the list page; `from` is still dropped.
- **Activity** gained a Reconciliation tab (Dylan's tile section, `#reconciliation`).
- **Shell**: eight rail entries (adds Documents, Sandbox, Loans), six on the phone bar, `/trust` in the account menu, a
  section hue and an animated line backdrop per page, frosted header and rail, `home-f` on every page's `main`,
  `--color-brand-700` now purple-ink (links read purple).

## 2. What this supersedes
- **Brief 05 (round three) and handoff 17** are history: round three was built, audited and redesigned under #160 (see the
  checkpoint, handoff 18, and the audit `docs/research/deals-flow-audit-2026-10-15.md`). Their header notes say so.
- **Brief 06 (Slice C)** stands in substance and is amended by its new §0: Receivables and Cash are Dylan's pages now, and
  the brief is applied to them, not to the pages it was written against.
- **Handoff 16 §5/§6** (what is in flight / what is left): accept-as-asked, round three (as redesigned) and the tracker fold
  are done; Slice C is not started; Slice E stands; round four (multi-deal comparison, proposing sandbox) stands as recorded.
- **The design language of record** is now dev as it stands: the Home V2 mockup language plus Dylan's redesign as the owner
  merged it (`00_design_language_of_record.md` for the words and rules; DESIGN.md's Home and Deals sections for the pages; the
  No Rail Rule with the alarm-card exception). A new page follows dev, not the 13 Oct mockup alone.

## 3. Left dangling by the merges (filed as #163)
1. **`#cash-options` no longer exists** on Cash (the options card became a `FoldCard` without an id), but three links still
   point at it: Home's recommendation secondary (the server's `secondary.href`, `home_v2.py`), `next-action.tsx:197` and
   `deals/flow/decision-pane.tsx:134`. Home's `links` to `#where-the-cash-goes` and `#facility-headroom` never existed.
2. `e2e/slice-b-round-three.spec.ts` is an empty file (0 bytes, created in 31058785): fill or remove.
3. Receivables drops `from` (Home's `?from=home` lands with no way back; no `context.back`).
4. `recommendation.rule_text` is sent and never rendered; the doc comment in `deals-page.tsx` still names `compare, chart`;
   the comment at `cash/page.tsx:268` describes the old desktop order.
5. DESIGN.md: the Receivables ("three layers") and Cash sections predate Dylan's pages; the Deals subsection is rewritten in
   this commit; the others are the Slice C work's to rewrite.

## 4. Open with the owner (decisions, not blockers)
- **#161**: zh buyer names: `tests/api/conftest.py` keeps a buyer's own name as written while `tests/deals/test_lang.py`
  forbids Latin in the zh read; one rule must give. Also the `tests/books` digest pin and the redteam-d test (fixed by
  bbbfb7ce).
- **#162**: the eight-customer busy books are parked (EX01 evaluates in 22 s there; a funding-planner profile in the
  stability set is needed).
- **#155**: the tracker's cost switch, Option A (today) or B.
- **The negotiation communication evaluation** (`docs/NEGOTIATION_COMMUNICATION_HANDOFF.md` §9): the lead's prior is
  draft-and-copy; no building until the owner picks an approach. `feat/buyer-message` / `-web` (16 Oct, unmerged) already
  build a "message to the buyer" in the send review with copy / mark sent, the buyer's yes and reply, and NO_SIMULATED_BUYER:
  review them against that handoff before anything else is designed.
- **The buy side** (`feat/capex-buy-side`, 31 ahead) waits for the Security Lead's certification of the merge commit
  (CAPEX-1 was merge-blocking; 2..4 fixed). `feat/setup-books` is inside it.

## 5. Branches not on dev (16 Oct)
`feat/buyer-message` (+2), `feat/buyer-message-web` (+3), `feat/capex-buy-side` (+31, held), `int/busy-five` (+19, parked),
`fix/busy-live-specs` (+20), `feat/setup-books` (+2), `fix/live-walk-readiness` (tracker.spec:216 on live),
`ci/linux-green` (the Linux runner), `perf/busy-tests` (the test snapshot, being moved onto dev on its own). Everything merged
is listed in §1; this machine's 101 merged worktrees were removed on 16 Oct (nine remain: seven research branches and one
dirty `w7c-web`).

## 6. Known test state on dev
Mock 427 passed / 0 failed at a6de32a2 and 8e80b8bc; live 136–138 passed with the known failures #157 (×2),
`demo.spec.ts:378`, `tracker.spec.ts:216` (fix on `fix/live-walk-readiness`), `accept-as-asked.spec.ts:186/228` and
`slice-b.spec.ts:318` (order-dependent in the full run, green alone); unit 163; tsc and eslint clean. API: the four of #161.

## 7. Rules now in force (owner, 15 Oct; `docs/agents/integration.md`)
Branch from the latest `origin/dev`, never from another feature branch; dev into the branch daily and before hand-in; one
task per branch; the FULL mock suite, typecheck, lint and unit before hand-in, exact counts; a failing spec is a defect or a
stale description, never skipped or deleted; mocks only from the recorder; report `POST /demo/reset` timing for any seed
change; only the lead merges into dev, `--no-ff`, after the full gate (API, mock desktop and phone, live, unit, typecheck,
lint); the GitHub checks must be green on the branch before a large hand-in. Plus the standing ones: never ports 3000/8000,
kill only by own PIDs, no `git stash`, no attribution lines.

## 8. Next on this machine
1. Fix #163 (small, web only, on `fix/cash-options-anchor` from dev; the full mock run before hand-in).
2. Slice C as amended (brief 06 §0): Receivables first (the lifecycle pill, the net bar, the reminder with its receipt, `from`
   honoured, the stress aside's `scenario=` link), then Cash (the position, the three-statement review on the run, Compare
   this scenario, sources apart), each a small branch per the rules; the Financial Timeline last.
3. Round four (multi-deal comparison, the proposing sandbox) after Slice C, if the owner still wants it.
