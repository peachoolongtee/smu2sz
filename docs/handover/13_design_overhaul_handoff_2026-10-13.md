# Handoff 13 (13 Oct 2026): the design overhaul: what is done, what is in motion, how the work runs now

Read docs/handover/08 (protocol, gates, environment quirks) and 12 (the connected pages that shipped on 12 Oct) first. This
document covers the design overhaul only: the design system (#112, merged) and Home V2 (#117, in motion), the owner's rules
that now govern UI work, and the measured cost of the last wave that caused the process change.

## The owner's rules, in force from 13 Oct

1. **Only the Home page changes.** Deals, Receivables, Customer, Cash, Activity, Approvals and the shared components as
   #112 built them are frozen until the owner's own overhaul brief for those pages. Shared-component changes are reported
   to the lead, not made. Parked: #118, #119, #113, #114, the port of the three connected pages onto the shared kit.
2. **Deliver vertical slices, not reviewed waves.** Home V2 (page, worklist, customer focus, deal focus) is one integrated
   feature with ONE frontend owner on one branch, `feat/home-v2-web`. Server support and independent validation run in
   parallel on their own branches and ports. The owner agent hands back after each slice; the lead resumes it onto the next.
3. **Focused tests during development; full gates only at checkpoints.** The owner agent runs typecheck, lint, unit, the
   feature's specs, a11y and the Home cases of responsive. The full mock suite, the whole live project and the API suite run
   at two checkpoints: integration (slices 1 and 2 together, before the dev merge) and release (the swap to default).
   Anything that touches money, authority, execution or settlement still gets rigorous independent verification.
4. **The Home V2 design and interaction architecture are frozen.** docs/design/home-v2-2026-10-12/00–02 and
   HomeV2Proto.dc.html are the record; no redesign or specification round without a demonstrated correctness problem. Where
   a document is silent the builder takes the simplest reading and notes it in the report.
5. **Fewer documents.** Keep the slice reports, one screenshot set at the integration checkpoint for the owner's five-second
   test, and the state matrix as tests. No more handoff documents unless the work changes hands.
6. The standing invariants hold unchanged: INVARIANT 13 (the browser computes no money or date words; every string from the
   server read or the dictionary, en and zh, 您 voice; no ids or day numbers in Business mode; 13 px floor), one filled
   primary and one DecisionCard per page, recorded mocks never hand-edited, worktree per agent, plain one-line commits, no
   attribution lines, no unscoped `pkill`, never port 3000, never a bare `git stash`.

## Done: the design system (#112), dev d8598f8d, closed

Spec: docs/design/design-system-2026-10-12/00_spec_112.md. The record as built: apps/web/DESIGN.md §"Design system
(map #88, ticket #112)" and its subsections (tokens, three card types, SegmentedTabs, StateWord, type scale, sidebar,
reduced motion, the banned list). Gate at merge: mock 384 pass / 42 skip / 0 fail, live project 117 / 14 / 0, unit 112.
Reviewed once (code: CHANGES REQUIRED; design: FIX FIRST), 21 items fixed in one round, then merged.

What exists now and how to use it:
- **Tokens** in apps/web/app/globals.css: motion `--dur-instant/fast/—/expanded/scenario/narrative` with `--ease-ui` and
  `--ease-select`; five radii; the type scale (headline 26 / 34 / 36 px dominates the major value 24 / 28 / 30 px;
  supporting line height 18 px; nothing under 13 px, chart text included). No new fonts (Lato / Inter body, Plus Jakarta
  Sans display), brand #0368e9, no new colours.
- **Three card types** in apps/web/components/business/kit.tsx: `Card` (a container), `DecisionCard` (the page's one decision:
  eyebrow, title, text, the one filled primary and a quiet secondary; one per page, the first approval only, no action
  slot), `SelectedCard` (the selected row or card: one selected style everywhere, a 3 px left rule on queue rows). The
  queue, the path columns and the document bar sit on these three; hand-rolled containers are gone.
- **SegmentedTabs** in apps/web/components/ui/segmented-tabs.tsx (+ `segmented-tabs-model.ts`, unit-tested): the one
  segmented control on the owner's pill reference. A `#eef1f5` track on a `line-ui` hairline, a white raised selected pill
  (1 px shadow, no overshoot, `--dur-fast` / `--ease-select`, none under reduced motion), per-option widths reserved by a
  weight-800 twin so choosing never resizes a tab, selected label weight 800 with its icon in brand blue, optional count
  badge (red only when the owner is needed), `stretch` and `scroll` modes (own `scrollLeft`, edge fade; never the window's
  scroll). A tablist: arrow keys, Home, End, one tab stop. The Cash window group and the Activity filter already use it.
- **StateWord** in apps/web/components/ui/state-word.tsx (+ `state-word-model.ts`, unit-tested): the one way a server-named
  state is drawn: glyph, tone and the server's word, no container. Twelve states with fixed glyphs and tones (planned,
  arranged, received, repaid, owed, scheduled, agreed, pending, current, due_soon, overdue, promise_missed) plus `tone` for
  any other server status (`state_tone` / `result_tone`). Three shapes: word, line, step. `StatePill` and the pill variant
  are retired (`OperationStatePill` in operation-result.tsx is a different thing, an operation's run status, and stays).
- **Sidebar**: collapsible, the toggle an icon button at the foot with a tooltip and a name; the stored value read in its own
  try before hydration (apps/web/lib/use-sidebar.ts, app-shell.tsx, pre-hydration.ts); reduced motion covers the details
  height via `::details-content`.
- Tests: apps/web/scripts/w12-design-system.test.mjs (unit) and apps/web/e2e/design-system.spec.ts (mock). Two old flakes
  fixed on the way (responsive.spec.ts:90, slow.spec.ts:84; the first still failed about 1 in 5 on dev before the wave, so
  a recurrence is #119, not a regression).

Server side, same day: #120 (dev 04009ea6) put `state` and `state_text` on the Customer overview's figures, exposure rows and
history through the one vocabulary (`state_of` / `financing_state_words`; the word is "planned", never "proposed"), so the
Customer page can render StateWord when its turn comes (it is frozen for now; see rule 1).

## Done: Home V2 wave 1, the server (dev a41869a4, behind FEATURE_HOME_V2, default off)

`GET /worklist?lang=` (the alert pinned above the tabs and counted nowhere; `needs_you`, `waiting`, `customers`; the
deterministic `order`: cash safety by the recommended path's breach, then deadline, then missed receipt, then material
severity, then ordinary; every leg of the company plan belongs to the alert via the `alert:<id>:` prefix, other approvals
stay rows). `GET /customers?lang=` (the customer rows and their search terms). The `home_v2` block on `GET /home` (three
KPIs with `cash_available.buffer` for the CashBufferIndicator, the company `action` with `control` RUN_PLAN / APPROVE_PLAN /
null, the chart scope, legend and `lowest_inspector`, the links). Context echoes (`customer`, `decision`, `scenario`) beside
`context.back` on the Customer overview and the exposure reads. Files: services/api/app/api/{worklist.py, home_v2.py,
home_hybrid.py}; tests test_worklist.py (23), test_home_v2.py (17), test_customers_list.py. Reviewed and fixed before merge.

## Verified: the twelve states (13 Oct, against dev d8598f8d with the flags on)

docs/design/home-v2-2026-10-12/04_state_recipes.md has the exact request sequence for each. Eleven of twelve are reachable
from the Demo books with existing calls (reset, the sample offers EX01–EX07, the plan run, clock advance, bank receipt,
`?scenario=short_facilities` for the approval alert, `?scenario=public_sme` for the busy six-customer list). The twelfth,
"a scenario still calculating", is the browser's fetch-pending state (a cold exposure read takes about a second); no server
field, a dictionary word, tested with a delayed mock route. Known server items, none on the critical path: the zh APPROVAL
subject keeps the English facility name (a words fix, batch it with whatever slice 1 reports missing); the stress delay is
fixed at 30 days; `/offers/{id}/exposure` wants `response=counter:<k>`.

## In motion: Home V2 on `feat/home-v2-web` (worktree .claude/worktrees/home-v2-web, cut from dev d8598f8d)

One frontend owner, ports 3182 / 8182. Spec for slice 1: docs/design/home-v2-2026-10-12/03_slice1_web_spec.md with the
rules in 05_common_web_rules.md.
- **Slice 1, running:** the default Home when `/health` features carry `home_v2` AND the read carries the `home_v2` block;
  otherwise the existing Home byte-for-byte (every old Home spec must pass). Header; the company strip (CASH AVAILABLE with
  the buffer indicator, LOWEST CASH AHEAD, PLANNED FUNDING / FUNDING ARRANGED); the action bar as the one DecisionCard with
  the existing confirm-and-run control (`usePlanRun`, the `fix-*` ids); the compact cash chart reusing event-picture.tsx's
  SVG (current / planned / hypothetical as solid / grey dashed / brand dashed, the lowest point with its cause, the inspector,
  36 · 60 · 120 as SegmentedTabs without icons, no event rail); the link row; the worklist panel (alert, three tabs with
  counts, search over `search_terms`, ActionRow and CustomerRow, `why_first_text` under the first needs-you row, no reorder
  while a row is focused; row click navigates in slice 1); the phone bottom sheet; the recorder's `--home-v2` strategy and
  new mock files with the `tl-mock-home-v2` session seam; e2e/home-v2.spec.ts. Hands back with a report under 120 words.
- **Slice 2, next, same owner:** CustomerFocusPanel and DealFocusPanel in place from a worklist row, the three URL
  selections `customer` / `decision` / `scenario`, on the reads already on dev (`/customers/{id}/overview`, `/offers/{id}`,
  `/offers/{id}/exposure` with customer / decision / path / from, the context echoes). Nothing new on the server.
- **Integration checkpoint** (lead): the full mock suite and the whole live project once on fresh ports; one independent
  pass on the money-and-authority surfaces (the run-the-plan control, which reuses the verified hook, and the KPI strings
  equal to the read); one screenshot set for the owner's five-second test; the `--no-ff` merge into dev.
- **Slice 3:** the state matrix as tests from 04_state_recipes.md (desktop and 390, en and zh, reduced motion, axe), by a
  verifier in parallel with slice 2 against a frozen commit. Then the **release checkpoint** and the swap to default
  (the old Home retired) with the owner's sign-off.

## Why the process changed: the measured cost of #112

From the agent transcript (its own clock, the owner's 48-minute pause excluded):

| Activity | Build (72 min) | Fix round (66 min) |
|---|---|---|
| Writing code and docs | 10 min, 14% | 5 min, 8% |
| Reading the codebase | 6 min, 9% | 8 min, 12% |
| Debugging after a failure | 5 min, 7% | 5 min, 8% |
| Focused spec runs | 20 min, 28% | 20 min, 30% |
| Full-suite runs and waiting on them | 24 min, 33% | 25 min, 38% |
| Typecheck, lint, unit | 5 min, 7% | 2 min, 3% |

17 full-suite runs, 48 focused runs, 50 quick checks; about 70% of agent time was test execution and 11% was writing
code. Around the agent: 2 min idle before the reviews, 6 min of reviews in parallel, 1 min to compose the fix list, 10 min
for the lead's verification and merge. The two-round structure (build, full gates, review, fix, full gates) was the cost,
not coordination. Hence rules 2 and 3: two full web gate pairs per feature instead of about six.

## Where things are

- dev d8598f8d, pushed. API gate last run on dev: 1502 (wave 1) and 935 in tests/api (#120). Web: mock 384, live 117.
- Specs of record: docs/design/design-system-2026-10-12/, docs/design/home-v2-2026-10-12/ (00–05 and the boards), the
  owner's canvas https://claude.ai/artifact/JNBJtChTQVtziLwbLwYw8e (v23, private).
- Tickets: #112 closed; #117 Home V2 open (the feature); #113, #114, #118, #119 parked by rule 1; #103, #104 (owner), #106,
  #66, #59, #101, #102 unchanged; the three economics tracks (#97, #98, #100) are with the external engineer per handoff 11.
- Environment quirks still bite: macOS has no `timeout`; zsh expands `=` and `[0-9]`; the cwd resets between calls (absolute
  paths); free a stale port with `lsof -ti :<port> | xargs kill`; the exposure cold-read timing bound is 10 s under
  SKIP_PERF_BENCH.
