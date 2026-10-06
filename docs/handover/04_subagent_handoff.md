# Handoff for subagent delegation (6 Oct 2026)

For the technical lead session on the owner's PC that will delegate the remaining work. Read `docs/HANDOVER.md`
first (sections 3, 4 and 6); this file turns its backlog into bounded briefs. The repository is at `dev` `53cd1cc`
(`main` at `682a610`); everything is committed and pushed.

## 1. State in one paragraph

The engine is frozen (stability mode: fix regressions, keep the evidence true, rehearse the demo). The UI redesign of
the owner's third brief is merged: two shells (Business and Demo), the Business home on the presentation read
`GET /home`, approval cards as questions, the Deals, Cash & funding, Receivables, Activity and Limits pages, the story
page `/demo`. Measured on 5 Oct after the merge: backend 5,452 passed and 33 skipped (two chunks, `SKIP_PERF_BENCH=1`),
scenarios 49/49, demo run exit 0, attacks 255 with 0 harm, web mock e2e 36 passed and 1 skipped, web live e2e 31 passed.
The audit and the after-implementation report are `docs/UX_AUDIT.md`.

## 2. How to run the lead session

Clone, `git checkout dev`, `cd services/api && uv sync`, `cd apps/web && pnpm install`. On Windows use
`SKIP_PERF_BENCH=1` and `PYTHONUTF8=1`. Start subagents with a cheaper model, each in its own worktree, each brief
beginning `git fetch origin && git checkout -B <branch> origin/dev`. Subagents push their branch and never merge. The
lead merges one branch at a time into `dev` with `--no-ff`, then runs the integration loop before the next merge.

Integration loop after every merge (from `docs/HANDOVER.md` section 3 and 6): read the diff; backend suite in two
chunks; `scripts/run_scenarios.py --inproc` (49/49); `scripts/demo_run.py` (exit 0); the attack report when the change
touches security or the API; `E2E_TARGET=mock pnpm exec playwright test` and, for a web change, the live project with
`E2E_API_PORT=8010`; `git checkout -- services/api/evals` unless the task is to refresh evidence; update
`docs/CONTINUOUS_OPTIMIZATION.md` and `docs/NEXT_FIXES.md`; push `dev`.

Rules every brief must carry (the owner's, verbatim in spirit): "Make the smallest change that satisfies the acceptance
tests. Do not rename unrelated types, change package structure, upgrade dependencies, rewrite functioning components,
introduce frameworks or clean up unrelated code." A task past 1.5× its estimate stops and reports. Never recompute money
in JavaScript (INVARIANT 13); a missing figure is a narrow server presentation field. No change to alert, verdict,
executor, mandate or current-books semantics without the lead. A material financial formula is derived by one agent and
checked by another. Plain one-line commit messages, no prefixes, no co-author trailers.

Return format, fixed: STATUS / FILES CHANGED / BUG or FEATURE CLOSED / TESTS ADDED / TEST COMMAND / TEST RESULT /
REGRESSIONS / INTERFACE CHANGE REQUESTS / ASSUMPTIONS.

## 3. What the lead keeps (do not delegate)

Architecture, prioritisation, financial and security invariants, shared schemas, state semantics, merges, integration,
final acceptance, demo-path decisions, and anything that moves a golden figure. The owner-only items stay with the
owner: the PostgreSQL URL and keys for the two certification runs, NR1, registration, the organiser email, the roster,
the region, the licence, the deck, the video, the ¥360,000 borrower-file question, the `[TEAM:]` placeholders.

## 4. Delegable tasks, in priority order

Each is one subagent, one branch, bounded. Estimates are for a cheaper implementer model.

### T1. Chat turn: the reply first, the trace behind a disclosure (P1, web, S)

- TASK: in `apps/web/components/chat/assistant-turn.tsx` show the reply, the confirmation buttons and the clarification
  options at level 1; move the intent badge, the plan steps and the operation list with hashes into one `<details>`
  labelled "Details" (dictionary key, English and Chinese). Keep every `data-testid` the specs use (`chat-intent`,
  `chat-plan`, `plan-step-*`, `chat-ops`, `chat-op-*`, `chat-awaiting`, `chat-goahead`, `chat-cancel`, `chat-clarify`,
  `clarify-option-*`, `chat-security`, `chat-nothing-executed`) inside the disclosure, and open the disclosure by
  default when the turn has security events or a REFUSED operation.
- WHY: `docs/UX_AUDIT.md` section 2 ("a trace viewer that also talks") and section 17 remaining debt.
- OWNED FILES: `components/chat/assistant-turn.tsx`, `lib/dictionary.ts` (new keys only), `e2e/chat.spec.ts`.
- READ-ONLY: `lib/chat.ts`, `lib/types.ts`, `components/home/fix-alert.tsx` (it renders `OperationList` from this file;
  keep that export and its behaviour).
- INTERFACE CONTRACT: no API change; `OperationList` keeps its signature.
- TESTS: `chat.spec.ts` passes in mock and live projects; add one assertion that the details are closed on a plain reply
  and open on the FastCapital turn.
- ACCEPTANCE: `pnpm lint && pnpm typecheck && E2E_TARGET=mock pnpm exec playwright test e2e/chat.spec.ts e2e/home.spec.ts`
  green; live `chat.spec.ts` green.
- FORBIDDEN: changing what the server sends, `lib/chat.ts`, the home's answer block.
- Estimate 2 h.

### T2. Deals: list the session's offers, pick one (P1, web, S)

- TASK: `app/deals/page.tsx` shows a list of the offers in `demoStore.offers` (buyer name from `GET /state`
  counterparties, received day, status of the verdict if any) above the detail; clicking one calls `selectOffer`. The
  latest stays selected by default.
- WHY: section 17 debt: "the Deals page lists the session's latest offer only".
- OWNED FILES: `app/deals/page.tsx`, `lib/dictionary.ts` (new keys), a new `e2e/deals.spec.ts` (mock project).
- READ-ONLY: `lib/demo-store.ts`, `lib/use-current.ts`, `components/verdict-parts.tsx`.
- INTERFACE CONTRACT: none.
- TESTS: new spec walks the stepper to step 11 (EX01 and EX01B both compiled), opens `/deals`, sees two rows, picks the
  reworded one, sees its recommendation.
- ACCEPTANCE: mock project green including `responsive.spec.ts`.
- FORBIDDEN: new API routes; computing anything from obligations.
- Estimate 2 h.

### T3. "What changed since my last visit" (P1, backend presentation field + web, M)

- TASK: `GET /home` accepts `since_day` (optional integer); `changes` then covers entries from that day, else the last
  seven days as now; the response echoes `since_day`. The web keeps the day of the owner's last home visit in
  `localStorage` (`tl-last-visit`, try/catch) and sends it; the block's subtitle says "since day N".
- WHY: brief section 6 D and section 17 debt.
- OWNED FILES: `services/api/app/api/home.py` (`_changes` and the route signature only), `tests/api/test_home.py` (one
  new test), `apps/web/lib/api.ts`, `lib/live/index.ts`, `lib/mock/handlers.ts` (ignore the parameter),
  `components/business/blocks.tsx` (`ChangesBlock`), `app/page.tsx`, `lib/dictionary.ts`.
- READ-ONLY: `app/api/presentation.py`, `app/operations/log.py`.
- INTERFACE CONTRACT: the new query parameter is optional and the default behaviour is unchanged, so the recorded mocks
  stay valid.
- TESTS: API test: with `since_day` set after the receipt, the receipt is not listed; without it, it is.
- ACCEPTANCE: `tests/api` green, mock e2e green, no mock re-recording needed.
- FORBIDDEN: touching alerts, the executor or the ledger format.
- Estimate 3 h.

### T4. Invoice ids inside server sentences (P2, backend presentation, S)

- TASK: in `app/api/presentation.py` extend `in_words` so an issued invoice id and a recurring-invoice id
  (`RI:<buyer>:<n>`) become "the ¥X invoice to <buyer>" where the books know the face (reuse `invoice_words`); apply it
  where `in_words` is already called. Do not touch the executor's messages themselves.
- WHY: section 17 debt: ids such as RI:BUYER-1:2 still appear in "What changed" and the approval reason.
- OWNED FILES: `app/api/presentation.py`, `tests/api/test_home.py` (extend the day-34 test to assert the change text
  names the invoice by amount and buyer).
- READ-ONLY: `app/api/home.py`, `app/api/operations.py`.
- INTERFACE CONTRACT: none; after the change re-record the mocks (`pnpm mocks:record` against an API on port 8011) and
  commit them, since the recorded sentences change.
- ACCEPTANCE: `tests/api` green; mock e2e green after re-recording; `home.spec.ts` assertions on the late buyer still pass.
- FORBIDDEN: changing any `message` the executor writes to the log.
- Estimate 2 h.

### T5. EX01 evaluate benchmark over its 250 ms target (P2, backend, S to M)

- TASK: find why `EX01` evaluation takes 270 ms cold on the Mac (and at or just over on Windows) against the 250 ms
  target in the perf test, or raise the target with a measured reason. Profile first (`python -X importtime`,
  `cProfile` on one evaluate); report before changing anything.
- WHY: `docs/HANDOVER.md` known loose ends; it is the one failing test without `SKIP_PERF_BENCH=1`.
- OWNED FILES: the perf test under `tests/` that asserts the target, and, only after the lead agrees, the hot path it
  names.
- READ-ONLY: everything financial; verdicts must stay byte-identical (`scripts/evaluate.py` targets, 67/67 golden values).
- ACCEPTANCE: full suite without `SKIP_PERF_BENCH` green on the owner's machine, or the target changed with the profile
  attached in the commit message's body file under `docs/research/`.
- FORBIDDEN: any change that moves a figure in `fixtures/golden/golden_values.json`.
- Estimate 3 h, stop at 4.5 h and report.

### T6. R04 and R05: cap unauthenticated intake (P2, backend, S)

- TASK: `POST /offers` and buyer turns on `POST /nl` without a channel key are capped per day (a setting, default 200)
  so the offer, verdict and security-event tables cannot grow without bound; over the cap answer 429 with a code and
  log one security event. Nothing changes for authenticated callers.
- WHY: `docs/CONTINUOUS_OPTIMIZATION.md` rows R04 and R05.
- OWNED FILES: `app/api/offers.py`, `app/api/nl.py`, `app/config.py` (one setting), new tests under `tests/api` and
  `tests/security`.
- READ-ONLY: `app/security/`, the executor.
- INTERFACE CONTRACT: the 429 body is `{"code": "INTAKE_CAPPED", "message": ...}`; the web client already explains
  non-2xx answers.
- ACCEPTANCE: the attack report still 255 with 0 harm; scenarios 49/49.
- FORBIDDEN: touching the owner or agent paths.
- Estimate 2 h.

### T7. F-FIN-10: label the level DSCR as a reserve-coverage reading on every screen (P2, web, S)

- TASK: audit every place the engine views show "DSCR" (Trajectory months table, Capex structures, Verdict checks,
  What-if covenants) and add the words "reserve-coverage reading, not a bank covenant" in the label or a hint, from one
  dictionary key, English and Chinese. The Business pages already carry it (`biz.readings.note`).
- WHY: `docs/CONTINUOUS_OPTIMIZATION.md` row F-FIN-10; the documents' required wording.
- OWNED FILES: the four engine pages, `lib/dictionary.ts`.
- ACCEPTANCE: mock e2e green; a grep for "DSCR" in `apps/web/app` finds the hint beside each.
- FORBIDDEN: changing any number or chart.
- Estimate 1 h.

### T8. Engine-view terminology (P2, web, M; only after T1 to T4)

- TASK: in Demo mode's engine views, rename labels per `docs/UX_AUDIT.md` section 7 where the term is a label and not
  server text (Reserve floor to safe cash level; Forward concession to future give-aways with the cap; Tier badges get
  the sentence from `tier.short` beside them). Codes and formulas stay, under the same disclosure pattern as the Business
  pages where a page has none.
- OWNED FILES: `lib/dictionary.ts`, the engine pages that use the renamed keys, the specs that assert the old labels.
- ACCEPTANCE: mock and live e2e green; the golden figures asserted by `demo.spec.ts` unchanged.
- FORBIDDEN: deleting any engine view; changing routes.
- Estimate 4 h.

## 5. Not delegable in stability mode

Wave F (named stresses, payment instrument, guarded supplier payment, recurring outflows, Chinese server text,
deployment), new red-team rounds, R02 (a multi-leg plan as one transaction), R07 (the pre-ADR-0009 backfill), and the
NR1 behaviour, until the owner lifts the mode or decides.

## 6. Files a subagent should read before any web task

`apps/web/README.md` (the modes, the one client, the mocks), `docs/UX_AUDIT.md` sections 11 to 13 and 17,
`apps/web/lib/mode.ts`, `apps/web/components/app-shell.tsx`, `apps/web/lib/types.ts` (the `HomeView` and
`ApprovalPresentation` shapes). Before any API task: `services/api/app/api/home.py`, `app/api/presentation.py`,
`docs/FINANCIAL_SEMANTICS.md` (do not re-derive any quantity it defines).
