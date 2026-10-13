# Handover: TermsLedger v2, 3 Oct 2026 (sections 4 to 6 updated at the gate checkpoint, `dev` at `db097e0`; reconciled on the Mac on 5 Oct at `bac61f3`)

For a new Claude Code session on another machine. Read this file first, then the files it points to.
Everything you need is in this repository; nothing depends on the previous machine.

## 1. Start here

```bash
git clone https://github.com/peachoolongtee/smu2sz.git
cd smu2sz && git checkout dev
cd services/api && uv sync && uv run pytest -o addopts= -q
```

Needs `uv` (Python 3.12), Node with `pnpm`, and `gh` logged in to GitHub. Expect about 5,446 tests passing in
about 14 minutes on Windows (two sequential chunks, section 6). Then, from the repo root: `python3 scripts/run_scenarios.py --inproc` (expect 49/49),
followed by `git checkout -- services/api/evals` so regenerated evidence is not committed by accident.

On Windows (confirmed 1 Oct on a second machine): `.gitattributes` keeps every text file LF, because fixture
text is hashed and span-matched byte for byte. Run the suite as `SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q`
(the latency targets were set on the Mac; expect about 5,446 passed, 33 skipped) and prefix scripts that print
with `PYTHONUTF8=1`, for example
`PYTHONUTF8=1 uv run --project services/api python scripts/run_scenarios.py --inproc`.

First message to give the new session:

> Read docs/HANDOVER.md and everything it points to, then continue from section 6. Follow the standing
> instructions in section 3 without asking me to repeat them.

**Not in the repository** (copy by hand if wanted): the root `.env` with `SUPABASE_DB_URL` (session pooler),
`DEEPSEEK_API_KEY`, and optionally `ANTHROPIC_API_KEY`. None of the remaining work needs them: tests and
scenarios run on the in-memory store with cached model output (`DATABASE_URL=memory`, `LLM_MODE=cache`). To run
the app locally see the README quickstart; use `DATABASE_URL=sqlite:///./termsledger.db` so local runs do not
write to Supabase.

## 2. What this is

TermsLedger v2: entry for FinTechathon 2026, International track, Topic E (SME Finance Copilot). Deadline
**20 Oct 2026, 23:59 UTC+8**. Rubric: 40% task completion, 30% security and compliance, 30% innovation and
interaction. A supplier-side agent that reads a buyer's commercial offer, prices its hidden financing cost,
verifies it against an owner-signed mandate, counters, funds the gap from the owner's committed facilities, and
(new) keeps watching the books as time passes.

Read, in this order:

| File | Why |
| --- | --- |
| `docs/SYSTEM_WALKTHROUGH.md` | Every feature step by step, how the modules interact, and the end-to-end flow with real numbers |
| `docs/AGENT_MISSION.md`, `docs/CONTINUOUS_OPTIMIZATION.md`, `docs/FINANCIAL_SEMANTICS.md` | The three mission documents of 3 Oct: the role, the live backlog and scorecard, and the contract for every financial quantity |
| `docs/research/independent-principal-audit-2026-10-03.md` and the five `docs/research/redteam-2026-10-03*` folders (`-03`, `-03b` to `-03e`; rounds 4 and 5 hold probes only) | The audit and the red-team rounds whose findings were fixed on 3 Oct |
| `docs/research/concurrency-certification-2026-10-03.md`, `docs/research/language-boundary-certification-2026-10-03.md` | The two certifications: what was proven, what is pending (the language-boundary file's section 5 is the first dry run; the latest reports are under `services/api/evals/certification/`) |
| `docs/NEXT_FIXES.md` | History up to the audit; the live tracker is `docs/CONTINUOUS_OPTIMIZATION.md` |
| `docs/research/audit-2026-10-01.md` | The 1 Oct audit (findings S1–S11, F1–F10, changes C1–C13) |
| `docs/adr/0006-current-books-and-clock.md` | The state model: current books, the clock, settlement, re-verification at commitment |
| `docs/adr/0007`–`0010` | Early pay (implemented, with a 3 Oct note), DSCR on bullet loans, invoice terms, funding lots |
| `docs/adr/0001`–`0005`, `docs/ARCHITECTURE.md`, `docs/INVARIANTS.md`, `CONTEXT.md` | Earlier decisions and vocabulary |
| `docs/handover/01_main_architect_brief.md` | The owner's first long brief, verbatim |
| `docs/handover/02_technical_lead_brief.md` | The owner's second long brief, verbatim (the one in force now) |
| `docs/handover/03_ux_redesign_brief.md` and `03_ux_reference_dashboard.webp` | The owner's third brief, 5 Oct, verbatim: the UI/UX audit and redesign (Business vs Demo modes, the home answering "am I safe, what should I do, what does it cost"), with the design reference. It lifts stability mode for the frontend only; the engine stays frozen |
| `docs/handover/04_subagent_handoff.md` | The delegation handoff of 6 Oct: the state, the lead's rules, and eight bounded subagent briefs for the remaining UX debt and the delegable engine rows |

## 3. Standing instructions from the owner (all still in force)

The two briefs in `docs/handover/` are the full text. The rules that govern day-to-day work:

**Role.** You are the technical lead, prioritisation owner and integration lead. You own architecture,
prioritisation, financial and security invariants, shared schemas, state semantics, merges, integration, final
acceptance and demo-path decisions. Do not delegate those. Delegate bounded grunt work to lower-tier subagents.

**Autonomy.** Keep working through the tracker without asking routine questions. Ask the owner only when a
genuine product decision blocks everything.

**Priorities.** Security hole or financially wrong decision (P0) before workflow coherence (P1) before exposing
existing features (P2) before anything new (P3). No P3 while P0 or P1 is open. Prefer connecting existing modules
over new modules, one living financial state over more screens, a proactive closed loop over more calculators,
zero wrong autonomous decisions over higher autonomous coverage, and a repeatable end-to-end demo over
cleverness. Never preserve a headline number if the financially correct answer changes.

**Delegation.** Every subagent brief has: TASK (one objective), WHY (audit finding), OWNED FILES, READ-ONLY
DEPENDENCIES, INTERFACE CONTRACT, TESTS REQUIRED, ACCEPTANCE CRITERIA, FORBIDDEN CHANGES, and this return
format: STATUS / FILES CHANGED / BUG or FEATURE CLOSED / TESTS ADDED / TEST COMMAND / TEST RESULT / REGRESSIONS /
INTERFACE CHANGE REQUESTS / ASSUMPTIONS. Tell every implementer: "Make the smallest change that satisfies the
acceptance tests. Do not rename unrelated types, change package structure, upgrade dependencies, rewrite
functioning components, introduce frameworks or clean up unrelated code." A task past 1.5× its estimate stops and
reports. Do not parallelise competing edits to domain models, current-books semantics, mandate semantics,
executor semantics, financial formulas or shared API contracts. A material financial formula is derived by one
agent and independently checked by another.

**Integration loop, after every merge.** Read the diff; run the full suite, the scenarios, and the attack report
when security-relevant; run the main end-to-end path; update `docs/NEXT_FIXES.md`. Never merge several branches
and test at the end.

**Git.** `dev` is the working branch; `main` is fast-forwarded to `dev` only at checkpoints (last done at this handover). One branch per task (`fix/...`, `feat/...`), merged into `dev` with `--no-ff`. Commit often. Commit
messages are plain, concise, one line, easy to understand; no prefixes such as "fix:", and **no co-author
trailers**. Push after each merge.

**Subagent mechanics that worked.** Use a cheaper model for implementers, each in its own git worktree. Their
worktrees start from an old commit, so every brief begins: `git fetch origin && git checkout -B <branch> origin/dev`.
They push their branch and do not merge. Scenario and attack runs rewrite tracked files under
`services/api/evals/`; revert with `git checkout -- services/api/evals` unless the task is to refresh evidence.

**Reporting.** Report outcomes plainly, including failures. Keep `docs/NEXT_FIXES.md` as the scoreboard; no
hard-coded success metrics anywhere.

**Earlier choices.** Issue tracker is GitHub Issues with the `gh` CLI; agent config lives in `AGENTS.md`; the
wayfinder map is issue #1. Features the owner asked to add earlier (done): outbound leak guard with canaries,
what-if sandbox. Team of five. A DeepSeek key exists; an Anthropic key is optional.

## 4. Where things stand (3 Oct 2026)

`dev` carries the fixes for an independent audit's 13 findings, five red-team rounds' 26 findings and the business
review's items (BC1 to BC11 and S1 to S3), all fixed on 3 Oct (`git log --oneline b0e0ab6..origin/dev` lists the
merges; the findings, decisions and scorecard are in `docs/CONTINUOUS_OPTIMIZATION.md` sections 0, 1, 3 and 5).
`main` was fast-forwarded to `dev` at `bac61f3` on 3 Oct (they are equal). The gate on `dev` at `db097e0`:
backend 5,446 passed (33 skipped; Windows, `SKIP_PERF_BENCH=1`, two sequential chunks), scenarios 49/49 (87
turns, 49 evidence chains VALID), 255 attacks (122 API + 133 chat) with 0 harm, `scripts/evaluate.py` with every
target passing (runnable optimality 26/26, priced 26/26), `scripts/demo_run.py` exits 0, language-boundary
certification WRONG_MATERIAL 0 on 231 items (cache and fake runs), concurrency 20 passed and 10 skipped (the
PostgreSQL cases). Web e2e after the refresh `2fc5aa9`: mock 35, live 33. This is a simulation: lenders, the buyer and the bank feed are simulated, and
nothing is a bank covenant test.

Re-run on the Mac on 5 Oct 2026 at `bac61f3` (the application code is unchanged since `db097e0`; only the web refresh and documents merged after it): backend 5,452 passed, 26 skipped, 1 failed (the EX01 evaluate benchmark at 270 ms against a 250 ms target, full suite in 8 min 15 s without `SKIP_PERF_BENCH`); scenarios 49/49 (87 turns); `scripts/demo_run.py` exit 0; attacks 255 (122 API + 133 chat), 0 with harm; language-boundary certification (cache) WRONG_MATERIAL 0; `scripts/evaluate.py` every target passing (0 missed in all eight suites; runnable optimality 26/26, 67/67 golden values, 264 chat texts scanned, 0 disclosed); web mock e2e 34 passed, 1 skipped, 1 failed (`responsive.spec.ts` phone project: the chat slide-over measures 431 px on a 412 px viewport; it fails on every rerun on macOS Chromium, while the other phone tests pass). A five-item live smoke of the certification with DeepSeek as the only provider gave 5 CORRECT_EXECUTABLE, WRONG_MATERIAL 0 (exit 3: the fallback provider is not certified).

Re-run in the cloud on 5 Oct 2026 after the UI redesign (`feat/ux-redesign`, Linux, `SKIP_PERF_BENCH=1`, two chunks): backend 5,452 passed, 33 skipped, 0 failed; scenarios 49/49 (87 turns); `scripts/demo_run.py` exit 0; attacks 255 (122 API + 133 chat), 0 with harm; web mock e2e 36 passed, 1 skipped; web live e2e 31 passed (the `live.spec.ts` home checks rewritten for the Business home). The application engine is unchanged by the redesign; `GET /home` and the queue's `presentation` fields are presentation reads.

**Contract ingestion (5 Oct 2026, branch `feat/contract-ingestion` from `experiments`, local commits).** Brief 03
(`docs/handover/03_contract_ingestion_brief.md`) is built: document upload and reading, owner confirmation logged in the
chain, the deal summary on Deals once a deal is agreed, the documents page, `SHOW_DEAL` in chat, four attacks, the
golden equality test and the held-out harness (the set itself is pending). The demo reset opens on the three demo
documents confirmed by the owner (three CONFIRM_DOCUMENT ledger entries; `Runtime.reset()` alone leaves the chain empty).
`docs/SYSTEM_WALKTHROUGH.md` sections 5.21 and 13 describe it. Its gate (8 Oct): backend 5,669 passed, 33 skipped; scenarios 49/49; 259 attacks (126 API + 133 chat) with
0 harm; `scripts/demo_run.py` exit 0; `scripts/evaluate.py` every target PASS; language-boundary certification WRONG_MATERIAL 0
(cache and fake, unchanged); web mock e2e 45 passed (1 skipped), live e2e 40 passed (2 skipped). Merged into the redesigned
UI (`feat/upgrading-contracts`, 8 Oct): backend 5,716 passed, 33 skipped (the first run's one failure, two golden
digests in `tests/books/test_modules_on_books.py` that feat/upgrading's Wave 1 had not updated, was fixed and that file
re-run); scenarios 49/49; `scripts/demo_run.py` exit 0; web mock e2e 58 passed (7 skipped), live e2e 41 passed (2
skipped).
Then merged into `dev` as it stood late on 9 Oct (`b68c41c`: the UX remediation and its follow-ups; branch
`feat/strategy-mvp-contracts`, gate on 10 Oct): Ian's screens kept, contract ingestion on them (the deal summary in
Deals' agreements part once agreed, Documents a detail page of Deals with the way back, Activity's links), and the two
pieces of feat/upgrading his port had not taken: the simulated buyer's lean in his send step's question ("Holds firm"
ends with no deal) and the borrower file's tables (`docs/UX_SIMPLIFICATION_BRIEF.md` section 11). Our migration follows
his as `0007_contract_records`; his bilingual presentation says the document decisions in both languages. Gate: backend
6,712 passed, 37 skipped; scenarios 49/49; `scripts/demo_run.py` exit 0; 259 attacks (126 API + 133 chat) with 0 harm;
web unit 91; mock e2e 159 passed (168 with `E2E_STRATEGY=1`); live e2e 79 passed (87 with the flag); on the Windows
machine run the flagged live project with nothing else running: under load, six of its tests time out behind the first
envelope read (about 50 s there), and they pass when run alone.

Merged into `dev` on 12 Oct 2026 (`int/contracts`): the contracts branch, its review fixes (`fix/contracts-api`, `fix/contracts-web`),
ADR-0012 and the reskin (`feat/endowus-redesign`). Gate on this machine: API 6,813 passed, 37 skipped; web unit 91; mock e2e 163 / 172;
live e2e 86 / 94; zero retries. The walkthrough's section 14 lists what the fixes changed; the debt is ticket #103; `feat/ui-changes-biz`
(a money-in-and-out chart) is the owner's decision on #104. Fonts are not shipped: vendor Lato and Libre Caslon Text under
`apps/web/public/fonts` if the look matters on the judging machine.

The session handoff of 12 Oct 2026, with the delegation protocol, the owner's recorded decisions, the outstanding list by owner and the instructions for the merge's API debt, is `docs/handover/08_session_handoff_2026-10-12.md`; map #88's research is under `docs/research/customer-economics-2026-10-10/` and its specification is `docs/CUSTOMER_ECONOMICS_BRIEF.md`.

**The UI overhaul of 12 Oct 2026 (the owner's instruction; mockup "A1 · Seamless").** Every Business page (Deals last, after the owner chose its layout) was rebuilt to one pattern: the answer as the heading on the page, one picture, one raised action, everything else unboxed (`apps/web/DESIGN.md`, last four sections); the API gained additive presentation reads for the pictures and ticket #103's API half. The engine is unchanged. What was built, the gate, what is open and how the session worked are in `docs/handover/09_session_handoff_2026-10-12_ui_overhaul.md`: read it before this file's older sections.

**The owner stopped the red-team rounds on 3 Oct.** Five rounds (3, 7, 3, 7 and 6 findings) are done and all fixed.
The engine is in **stability mode**: fix regressions, keep the evidence regenerated, rehearse the demo, keep the
documents true. No broad features and no more red-team rounds unless the owner asks.

**Two things are pending a credential, each with one command:**

| Pending | Needs | Command |
| --- | --- | --- |
| Concurrency invariants on PostgreSQL (gate G4, backlog PG1, U-002) | An empty dedicated PostgreSQL database URL | `cd services/api && TERMSLEDGER_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host/termsledger_ci SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency` |
| Language-boundary certification against a live model (gate G3, backlog LC1, U-001) | `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` in the root `.env` | `PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend live` |

Until the first runs, deploy one worker, and do not claim that the live model or PostgreSQL concurrency is certified.

**Merged on 3 Oct** (the changes with their test files are in `docs/SYSTEM_WALKTHROUGH.md` section 11):

| Merge | What changed |
| --- | --- |
| `b78e205` chat consent | Only a closed affirmative command executes; approvals need an exact decision |
| `cf9dab9` counterparty channel | A buyer is who its `X-Counterparty-Key` says; no key means a proposal only |
| `0bb25ab` startup hydration | A restart keeps the persisted books, log and approvals |
| `d2fe408` executor admission | Funding operations pass the planner's checks at execution; a rate above the ceiling waits for the owner (Tier 2); a late receipt earns no discount |
| `5ebb7c7` ADR-0009 | Accepted terms and prices are written onto invoices, with a scope fixed at acceptance |
| `13db5e0` capex and borrower file | Fees, drawn debt, liquidity and real tenor count; no winner for an unworthy project; the purchase is deducted |
| `1a4621f`, `4729621` first red team | Circuit breaker scope, burnt keys, price-cut guard |
| `436c9e7` plan binding | "Go ahead" runs the exact operations shown; negotiation proposes first |
| `cebdebf` dated valuation | Concessions valued on the dated invoices in the window: 13 invoices; ¥28,326.92, ¥24,326.92, ¥210,000.00, ¥1,897.29 |
| `a95f97d` ADR-0010 | Funding lots with dates; cash lands after the lead time; a receipt pays the lender from the receipt |
| `a6da4bb`, `91b8b53` | Landing days in chat; second red team's seven findings |
| `574a04f` | One rate rule for router and executor; plans flag needs-the-owner and cannot-run-today; orphaned lots are repayable |
| `5fabd4a` web follow-up | Landing days, waiting-for-approval states, funding in transit, promised payments; mocks re-recorded |
| `8358ae0` and the plan-flag merges | Third red team's probes; owner sees the operation's own reason; chat funding is the agent's act in every session |

**Merged after the document close-out `c25ff08`** (also in section 11 of the walkthrough):

| Merge | What changed |
| --- | --- |
| `ffb89f8` existing debt service as cash | The equipment loan's ¥45,000 a month leaves cash in the projection and the clock; the day-0 gap is ¥405,000, the plan ¥3,113.93, Counter A ¥257,200 at 0.85% |
| `abbf439` review gaps | Chat refuses to record facts (RECORD_FACT); a mandate-expiry alert; a zero-floor fallback cure; the alert button bound to the state version and the suggestions shown; bank references on receipts; borrower file dated by its generation day; a buyer with a past-due invoice needs the owner |
| `094319e` simplifications | Capex evaluation is side-effect free with `POST /capex/apply`; the borrower file is read-only with provenance and an evidence hash; the aftersign stub and the mock lender were deleted |
| `3db68b0` counter feasibility | Every counter passes its own re-check (curable reading); EX01's Option B is 55-day terms at 0.30% |
| `635d13b` web catch-up | The bound alert act and its 409, RECORD_FACT, mandate expiry, bank references, the 55-day Option B; mocks re-recorded |
| `3edf1b6` leg ordering | The router orders legs so every prefix is admissible, with one leg rule shared with admission; a plan admissible only as a whole is flagged cannot run today |

**Merged after the first gate `1bc96ba`** (each with its test file in the second table of section 11 of the walkthrough):

| Merge | What changed |
| --- | --- |
| `92b7b0f` API gaps | `decided_day` and `result_message` on approvals, `lands_day` on plan actions, the approval id on executed ledger rows, the `short_facilities` demo scenario |
| `4b180ec` one leverage definition | Actual drawn debt over annual EBITDA, one function read from a projection by the verifier, capex, the borrower file and chat; EX01 1.72× to 1.47×, capex 2.08× / 2.28× to 1.90× / 2.10× |
| `557645b` fourth red team (7 findings) | Unrunnable early-pay legs flagged, no double-booked approved receipt, a lapsed early-pay agreement no longer blocks financing, consent grammar, package fulfilment, reconciliation window, term-lot fee |
| `919de9f` evaluation speed-up | EX01 evaluates in about 0.5 to 0.9 s (3.3 s before); verdicts byte-identical |
| `3649b24` concurrency | Compare-and-swap on the state version and the log head, `BEGIN IMMEDIATE`, executor retry; eight two-process invariants proven on SQLite, PostgreSQL pending |
| `82b2628` language-boundary certification harness | 231 items scored on stored state; cache and fake runs; the live run is ready and pending a key |
| `5eb299a` fifth red team (6 findings) | Fixed-sum discounts checked by rate, terms in force, scenario events only for the stored demo scenario, counters name their day and honour portions, owner repayment after expiry, reported day on queued receipts |
| `bb30265` boundary abstentions | Unusual number forms, per-day rates, discount codes, foreign currency, hedges, post-due discounts and riders abstain; the clock retries on a conflict; conflicts answer 409 |
| `db097e0` evaluation oracle | The oracle classifies runnable levers itself: runnable optimality 26/26, priced 26/26; the owner terms constraint reads the terms in force |

Earlier merges (1 Oct): the chat boundary, the computed scoreboard, the coverage proof, re-verification at
commitment, current books, the clock, partial settlement, attacks through chat, credential-bound sessions,
reconciliation of promised receipts, the alert button and opener, the early-pay rule (ADR-0007), DSCR on bullet
loans (ADR-0008), the owner home and the chat capabilities. Both financial rules of 1 Oct were re-derived by hand
by a second agent (`docs/research/early-pay-handcalc-2026-10-01.md`, `dscr-handcalc-2026-10-01.md`), and the
forward-concession valuation of 3 Oct likewise (`docs/research/concession-valuation-handcalc-2026-10-03.md`).

The evidence (`services/api/evals/e2e/latest`, `latest_report.*`, `security/latest_report.*`) and the docx
deliverables were regenerated on `docs/gate-checkpoint` at `db097e0`; if a later change moves a cash-derived figure,
regenerate them again (section 6, step 6). The web mocks are the exception: they predate the one-leverage change and
Counter A's day, and were re-recorded in the web refresh `2fc5aa9` (WEB1 done). `scripts/evaluate.py` reports 15 item-level misses (all targets pass):
four held-out 60-day-terms offers (H09a, H09b, H12a, H39), labelled NEEDS_OWNER_APPROVAL, now return REJECT with
RESERVE_BREACH on the cash-corrected books, so the label file `fixtures/heldout/offers.yaml` needs an owner decision
(relabel, or leave as a record that the verdict moved); the other misses were already there.

## 5. Decisions made that a new session must not undo

- Days stay absolute; the books close days before `as_of_day`. Nothing is re-based.
- Receipts come only from the bank feed (or the owner). The clock never assumes one arrived, and never repays a
  credit line.
- `docs/FINANCIAL_SEMANTICS.md` is the contract for every quantity. `max_apr_bp` is a ceiling on what the agent
  may borrow alone, tested on the effective annual cost; above it the owner approves explicitly (decided 3 Oct:
  Tier 2; this closes the old D5). No code approves on the owner's behalf: an above-ceiling cure is queued and the
  owner approves it as a second step.
- Reserve, DSCR, leverage and the borrowing switch are hard for everyone at execution (admission); clean-down is
  tested at plan level. The owner cannot waive a hard rule by approving.
- "Go ahead" binds to the exact operations shown with the quoted cost as a ceiling. Free text executes only as a
  closed affirmative command.
- Forward concessions are valued on dated invoices issued in [today, today + H): the golden 12-month figures use 13
  invoices. A cash-date rule for gains was tried and withdrawn.
- Accepted terms are written onto invoices once, with a scope fixed at acceptance (ADR-0009). Funding is a dated lot
  that lands after the lead time (ADR-0010).
- ADR-0007 (early pay; an invoice under an early-pay agreement is never financed) and ADR-0008 (level service for
  bullet loans, a reserve-coverage reading, never described as a bank covenant).
- Coverage: words inside an obligation's source span are not exempt from the filler list; do not widen the list
  with words that can carry a commercial term. A stated timing ("today", "tomorrow") is not accepted alone.
- Buyer-role scenario expectations live in the store, not the response. A buyer's chat response carries the reply
  and the session id only.
- Wording to keep: "simulation", "screens the entered obligations only", "reserve-coverage reading" for the bullet
  DSCR, "cheapest within the bounded search", "internally checkable chain". Do not claim bank-covenant compliance
  or "safe by construction".
- The chat read intents need the owner token; a caller with only the agent key gets "needs the owner's sign-in".
- Existing debt is cash: one schedule (`app/financial/debts.py`) for the projection, the clock and the capex ratios.
  The golden D-EQUIP's 0% rate is a fixture assumption.
- Every counter a verdict offers passes its own re-check on the same books (curable reading); a counter that fails is
  dropped with one sentence why. EX01's Option B is therefore 55 days, not 60.
- Capex evaluation writes nothing; `POST /capex/apply` is the owner's separate step. The borrower file is read-only
  and is never queued; there is no GENERATE_BORROWER_FILE operation.
- Chat does not record facts: RECORD_FACT answers "cannot record it, forecast unchanged". The alert button sends the
  state version and the suggestions shown and gets 409 `ALERT_CHANGED` when they moved.
- A plan admissible only as a whole is "cannot run today", not "needs the owner": the owner cannot approve past a
  hard rule.
- Leverage is one definition (month-end drawn debt over annual EBITDA, `covenants.ratios_for`); do not reintroduce a
  line-limit variant.
- The standing plan C0 is the cheapest plan the agent can run; a buyer's early payment and a bill are never in it
  (ADR-0007 note).
- Terms in force are the template plus the accepted adjustments; a fixed-sum discount is judged at its exact rate; an
  early-pay agreement is settled by portions up to its face by its day; an owner repayment is a fact that survives
  the mandate's expiry (`docs/FINANCIAL_SEMANTICS.md`).
- The store enforces concurrency (compare-and-swap, retry, 409); keep one worker until the PostgreSQL run is done.
- A reading the typed rows cannot carry abstains with a reason; never round it to a whole-invoice discount.
- Stability mode (section 4): no broad features, no new red-team rounds unless the owner asks.

## 6. What to do next, in order

**Independent end-to-end FLOW UX audit, 9 Oct:** `docs/research/independent-flow-ux-audit-2026-10-09.md` contains the
32-section report, 28 findings (4 P0, 14 P1, 10 P2), task walks and implementation order. Evidence is in
`docs/research/flow-ux-audit-2026-10-09/`. This was an audit only: no proposed UX fixes were implemented. The original
documented dev startup returned HTTP 500 from the malformed touch variant; the temporary correction used for inspection
was restored. Prioritize F01/F03 time presentation, F02 essential approval terms and F04 execution-state wording, after
restoring startup. The report distinguishes verified behavior from source-only paths and scoped test limitations.

**The integration of 6 and 7 Oct (the owner's fourth brief) is done:** `docs/UX_INTEGRATION_BRIEF.md`, the wayfinder map
(GitHub issue #13) and `docs/UX_AUDIT.md` section 18 record it; `docs/UX_INTEGRATION_REPORT.md` is the final report. The
recommendation shown to the owner is the router's runnable plan (`services/api/app/funding/recommend.py`), the home carries its
own projection series, Business mode speaks in distances from today and the minimum cash reserve, the brand is FLOW 流.

**The UI/UX audit and redesign of `docs/handover/03_ux_redesign_brief.md` was done on 5 Oct** (`docs/UX_AUDIT.md`, then
the merge `feat/ux-redesign`): two shells (Business and Demo), the Business home on the presentation read `GET /home`
(`services/api/app/api/home.py`, tests in `tests/api/test_home.py`), approval cards as questions on the queue's
`presentation` fields, the Deals, Cash & funding, Receivables, Activity and Limits pages, the story page `/demo`; mocks
re-recorded; `home.spec.ts`, `catchup.spec.ts` and `responsive.spec.ts` rewritten. The engine is unchanged. Remaining UX
debt is listed at the end of `docs/UX_AUDIT.md`. The list below remains the backlog for the engine, in stability mode.

1. Read the three mission documents first: `docs/AGENT_MISSION.md`, `docs/CONTINUOUS_OPTIMIZATION.md` (the live
   tracker; `docs/NEXT_FIXES.md` is history) and `docs/FINANCIAL_SEMANTICS.md`.
2. Run the gate. From `services/api`, as two sequential chunks (about 8 and 6 minutes on Windows; expect
   about 6,712 passed, 37 skipped in all), each `SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider`:
   chunk A = `tests/alerts tests/api tests/books tests/borrower_file tests/capex tests/clock tests/commitments
   tests/compiler tests/contracts tests/counterparties tests/covenants tests/egress tests/evals tests/financial
   tests/funding tests/ingest`;
   chunk B = `tests/mandate tests/nl tests/operations tests/persistence tests/security tests/verifier tests/whatif
   tests/concurrency tests/certification tests/test_fixtures.py tests/test_money.py`. From the repo root, with
   `PYTHONUTF8=1`: `uv run --project services/api python scripts/run_scenarios.py --inproc` (49/49),
   `uv run --project services/api python scripts/demo_run.py` (exit 0, 14 ledger entries),
   `cd services/api && uv run python -m app.security.attacks --report` (259 attacks, 0 with harm),
   `uv run --project services/api python scripts/evaluate.py` (every target PASS; about 6 minutes), and
   `uv run --project services/api python scripts/certify_language_boundary.py --backend cache` and `--backend fake`
   (WRONG_MATERIAL 0). For the web app `E2E_TARGET=mock pnpm exec playwright test` (159 passed, 37 skipped on 10 Oct; 168 with `E2E_STRATEGY=1`) and, if another
   program holds port 8000, `E2E_API_PORT=8010 E2E_TARGET=live pnpm exec playwright test` (79 passed, 14 skipped; 87 with the flag). Scenario, attack, evaluation and certification runs rewrite tracked files under
   `services/api/evals/`; commit them only when the task is to refresh evidence.
3. Open rows of the backlog (`docs/CONTINUOUS_OPTIMIZATION.md` section 1): PG1 (PostgreSQL run, needs a URL), LC1 (live
   certification, needs a key; a five-item DeepSeek-only smoke passed on the Mac on 5 Oct), NR1 (the "no runnable plan" worlds: should the agent propose drawing the line and
   asking the buyer or the owner? an owner decision), EO2 (the
   `line_first_baseline` metric still uses early pay), R02 (a multi-leg plan is not one transaction), R04 and R05
   (unauthenticated intake is not capped), R07 (a backfill for stores that hold commitments from before ADR-0009),
   F-FIN-10 (label the level DSCR as a reserve-coverage reading on every screen), W02 (accepted), EV1, and the
   uncertainty debt U-001 to U-013. Closed since the last handover: W01, D1, MW1 on SQLite, RT4, RT5, BA1, CERT1
   (harness), EO1, PF1, BC11.
4. If the web mocks drift from the API again: start the API on a free port and run `pnpm mocks:record` (see
   `apps/web/README.md`); never edit a mock by hand.
5. Small items worth doing next: an "AI-generated, for reference" label in the UI (a listed gap); suggested chat
   prompts for the newer capabilities. These are small; in stability mode do not start anything broad.
6. After any change that moves a figure: scenarios, attack report, `scripts/evaluate.py`,
   `scripts/build_deliverables.py --refresh-evidence`, `scripts/verify_evidence.py` on each per-task chain, then
   the documents that quote the figure, then commit the regenerated files.
7. Optional work (wave F) only after the P0 and P1 rows are closed and the owner lifts stability mode: named stresses,
   payment instrument, guarded supplier payment, recurring outflows, Chinese server text, deployment.

Known loose ends:

- The EX01 evaluate benchmark is over its 250 ms target on both machines (Windows: at or just over; Mac, 5 Oct: 270 ms
  cold). Either raise the target with a reason or find the regression; `SKIP_PERF_BENCH=1` hides it.
- `apps/web/e2e/responsive.spec.ts` "the slide-over chat fits the viewport with a long reply" fails on macOS Chromium
  (Pixel 7 project): the dialog's bounding box is 431 px wide on a 412 px viewport although its own rule is
  `max-w-[min(32rem,100vw)]`. Not diagnosed; it passed on the Windows machine on 3 Oct.
- `/nl/opener` and `/clock/advance` answer 403 without the owner token where other owner routes answer 401; the web
  client handles both.
- An over-cap Tier-2 offer is queued as pending and only refused when the owner approves it.
- The alert cure search is greedy and can miss a multi-invoice cure.
- Reconciliation reuses `SHORT_PAYMENT` for partial payments.
- Supabase is at migration 0002; `alembic upgrade head` applies 0003. Confirm no migration is needed for the new
  state fields (`lots`, `invoice_adjustments`, the invoice base fields) before pointing the app at Postgres; stored
  states gain fields with defaults.
- Audit items deferred to after the hackathon: S6, S7, S8 (the chain head is not anchored; the claim is
  "internally checkable"), C13, F9. S5 (the accept/counter threshold can be probed; an authenticated buyer finds it to
  1 bp) and S9 (the agent key reads protected labels through chat status replies) are open and reported, not
  harmful in the suite.

## 7. Stop conditions

- A task past 1.5× its estimate stops and reports.
- UI work never delays the video recording.
- Optional features start only when the P0 and P1 rows are closed.

## 8. What only the owner can do

Supply a PostgreSQL URL (an empty dedicated database) and the API keys (`ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`) so the two pending certification runs in section 4 can be made; decide NR1 (should the agent propose drawing the line and asking the buyer or owner when no runnable plan closes the gap); team eligibility and registration (issue #10); the organiser email (issue #9, draft posted); team roster (#5);
deployment region (#7); the licence for the LICENSE file; whether the borrower file's ¥360,000 request stays as an
honest shortfall or is made smaller; whether the video drops the capex scene or Scene 2 and the chat segment;
deck branding; building the deck (outline only exists) and recording the video; the `[TEAM:]` placeholders in the
documents.

## 9. Useful commands

```bash
cd services/api && uv run pytest -o addopts= -q                  # full suite with a summary line (SKIP_PERF_BENCH=1 on Windows; two chunks, section 6)
python3 scripts/run_scenarios.py --inproc                        # 49 chat scenarios (repo root)
cd services/api && uv run python -m app.security.attacks --report
uv run --project services/api python scripts/evaluate.py         # scoreboard rows
git checkout -- services/api/evals                               # drop regenerated evidence
```

Credentials in demo mode: owner `X-Owner-Token: demo-owner-token`, agent `X-Agent-Key: demo-agent-key`, bank feed
`X-Bank-Feed-Key: demo-bank-feed-key`, buyer channel keys `X-Counterparty-Key: demo-buyer-1-key` (BUYER-1) and
`demo-buyer-2-key` (BUYER-2).

**Paused work of 14 Oct 2026 (second machine).** Slice D (Activity and Demo, #145) and the deal tracker (map #148) are built, verified twice by independent agents and pushed on their branches, not yet merged: what stands, what is unproven, the open owner decisions and the kickoff are in `docs/handover/16_session_handoff_2026-10-14_slice_d_and_tracker.md`. Read handoffs 14 and 15 with it.
