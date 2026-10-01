# Handover: TermsLedger v2, 1 Oct 2026 (updated that evening)

For a new Claude Code session on another machine. Read this file first, then the files it points to.
Everything you need is in this repository; nothing depends on the previous machine.

## 1. Start here

```bash
git clone https://github.com/peachoolongtee/smu2sz.git
cd smu2sz && git checkout dev
cd services/api && uv sync && uv run pytest -o addopts= -q
```

Needs `uv` (Python 3.12), Node with `pnpm`, and `gh` logged in to GitHub. Expect about 4,000 tests passing in
4 to 6 minutes. Then, from the repo root: `python3 scripts/run_scenarios.py --inproc` (expect 46/46), followed by
`git checkout -- services/api/evals` so regenerated evidence is not committed by accident.

On Windows (confirmed 1 Oct on a second machine): `.gitattributes` keeps every text file LF, because fixture
text is hashed and span-matched byte for byte. Run the suite as `SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q`
(the latency targets were set on the Mac; expect about 3,800 passed, 24 skipped, 6 to 8 minutes) and prefix
scripts that print with `PYTHONUTF8=1`, for example
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
| `docs/research/audit-2026-10-01.md` | The independent audit this phase works from (findings S1–S11, F1–F10, changes C1–C13) |
| `docs/NEXT_FIXES.md` | Live tracker: every fix, status, dependencies, stop conditions |
| `docs/adr/0006-current-books-and-clock.md` | The state model: current books, the clock, settlement, re-verification at commitment |
| `docs/adr/0007-early-pay-acceptance-rule.md` | The early-pay rule, decided but NOT yet implemented |
| `docs/adr/0001`–`0005`, `docs/ARCHITECTURE.md`, `docs/INVARIANTS.md`, `CONTEXT.md` | Earlier decisions and vocabulary |
| `docs/handover/01_main_architect_brief.md` | The owner's first long brief, verbatim |
| `docs/handover/02_technical_lead_brief.md` | The owner's second long brief, verbatim (the one in force now) |

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

## 4. Where things stand (evening of 1 Oct)

`dev` is green: 4,044 passed, 26 skipped (Windows, perf benchmarks skipped); scenarios 46/46; attacks 182
(122 API + 60 chat), 0 with harm; web mock e2e 29 passed, live e2e 27 passed. `scripts/demo_run.py` walks demo steps 1 to 17 in
process and exits 0. Baseline before this phase was `6d500a9` (3,557 passed).

**Merged into `dev` before this session** (waves A, B and the clock): chat boundary (S1, S2), computed scoreboard
(S11), coverage proof (S3), re-verification at commitment (S4), current books, the clock, partial settlement,
alerts/capex/borrower file on current books, attacks through chat, credential-bound sessions and the
direct-command rule for approvals and go-aheads. See `docs/NEXT_FIXES.md` for each row.

**Merged on 1 Oct in this session**

| Item | What changed |
| --- | --- |
| Windows portability | `.gitattributes` keeps text LF; files are read as UTF-8; the offline guard allows loopback |
| B5 Counter A | ¥211,900 at 0.85% (nets ¥210,098.85; cost ¥1,801.15 + ¥841.09 = ¥2,642.24). Offered only when the router's plan on books that include it is admissible, and (ADR-0007) only when it beats the standing plan |
| C3 reconciliation | `ReconciliationReport.promised`: every promised early payment as AWAITED, RECEIVED, LAPSED or SETTLED_OTHERWISE |
| C2 alert button | `POST /alerts/{id}/act` submits the alert's cure to the executor as the agent. No cure is offered when the mandate forbids new borrowing |
| C4 opener | `POST /nl/opener` and the intent SHOW_ALERTS: the agent says what needs the owner and proposes the cure; a direct "go ahead" runs it |
| C5 repay alert | A drawn credit line the books can afford to repay raises `ALERT-REPAY-<facility>`; the opener offers it |
| D1/D2 early pay | ADR-0007 in the verifier: tenor-aware break-even, `EARLY_PAY_NOT_NEEDED`, `EARLY_PAY_DEARER_THAN_PLAN`. Whole-invoice early pay at 0.65% to 0.88% (30 days) now counters. The router prices the buyer's early-pay facility at its standing rate only |
| D4 DSCR | ADR-0008: a bullet term loan is serviced on a level basis. The ¥500,000 guaranteed loan shows 1.014× and fails 1.25×; the borrower file's ¥360,000 request shows 1.18× (below covenant) |
| E1/E2 chat | Intents COMPARE_FINANCING, RECONCILE, SHOW_RATIOS, CAPEX, BORROWER_FILE (owner token required) and a nearest-capability fallback |
| E3 home | `/` is the owner home: the day and a demo clock, the opener with Go ahead, position, approvals, alerts with "Let the agent fix this", recent agent actions |
| E4/E5 | Approval card with the operation, reason and terms; autonomy proof panel; no tier badge on REJECT; the stepper resumes after sign-in |
| C6 cure cost | Every proposed cure states its cost and effective annual rate and flags a rate above the APR cap; nothing is blocked |
| E6 and owner view fields | `annualised` and `autonomy` on owner verdict responses; shown on the verdict page, counters and chat |
| Web mocks | Every mock file is recorded from the live API by `apps/web/scripts/record-mocks.mjs`; mock and live agree |
| Documents | Technical document, video script, demo flow, self-assessment, deck outline and README follow today's product; compliance statements added |

Both financial rules were re-derived by hand by a second agent before merging
(`docs/research/early-pay-handcalc-2026-10-01.md`, `docs/research/dscr-handcalc-2026-10-01.md`). The early-pay
check found one real fault (the router used an offer's discount as a standing rate), fixed before the merge.

## 5. Decisions made in this phase that a new session must not undo

- Days stay absolute; the books close days before `as_of_day`. Nothing is re-based.
- Receipts come only from the bank feed (`ReceivePayment` by SYSTEM with the bank-feed key). The clock never
  assumes one arrived.
- An overdue financed invoice repays its advance today in the projection (recourse).
- The golden scenario has no outflows after day 47, so the proactive scene relies on the scenario event that adds
  month-2 payroll (¥200,000, day 42) on day 25. It does not exist on day 0, so day-0 golden values are unchanged.
- Coverage: words inside an obligation's source span are not exempt from the filler list. Do not widen the list
  with words that can carry a commercial term.
- Buyer-role scenario expectations live in the store, not the response.
- ADR-0007 and its implementation notes: `C` is read from the projection; the early-pay leg of a package is priced
  at the margin; an offer's discount is never a standing rate; an invoice under an early-pay commitment cannot also
  be financed (conservative).
- ADR-0008: level service for bullet term loans; never for a revolving credit line.
- A cure runs only on the owner's click or direct "go ahead", is submitted as the AGENT, and the executor decides
  the tier. The repay proposal is never made while a reserve breach is open.
- The new chat read intents need the owner token; a caller with only the agent key gets "needs the owner's sign-in".

## 6. What to do next, in order

Everything on the 1 Oct list is merged; `main` was fast-forwarded to `dev` at the end of 1 Oct. The gate at that
commit: 4,044 backend tests passed, 26 skipped; scenarios 46/46 with 46 evidence chains VALID; attacks 182 with
0 harm; web mock e2e 29 passed, live e2e 27 passed; `scripts/demo_run.py` exits 0. Evidence, the evaluation
report, the security report and the three docx deliverables were regenerated at that commit.

1. Confirm the baseline (section 1 commands), then `PYTHONUTF8=1 uv run --project services/api python
   scripts/demo_run.py` (expect exit 0). For the web app: `E2E_TARGET=mock pnpm exec playwright test` and, if another
   program holds port 8000, `E2E_API_PORT=8010 E2E_TARGET=live pnpm exec playwright test`.
2. **Owner decisions pending** (section 8): whether the 15% APR cap gates invoice financing on its effective annual
   rate (D5; today the day-34 cure is disclosed as 25.0% a year and flagged, not blocked); the licence; whether the
   borrower file's ¥360,000 request (1.18×, below the 1.25× covenant) stays as an honest shortfall or is made smaller;
   whether the video drops the capex scene (the current script does) or Scene 2 and the chat segment instead.
3. If the web mocks drift from the API again: start the API on a free port and run `pnpm mocks:record` (see
   `apps/web/README.md`); never edit a mock by hand.
4. Small items worth doing next: suggested chat prompts for the new capabilities (the recorded script now allows
   it); an "AI-generated, for reference" label in the UI (listed as a gap in the compliance statements); S9 (make
   status and alerts in chat owner-only, as the new read intents already are).
5. Optional work (wave F) after that: named stresses, payment instrument, guarded supplier payment, recurring
   outflows, Chinese server text, deployment.
6. After any change that moves a figure: scenarios, attack report, `scripts/evaluate.py`,
   `scripts/build_deliverables.py --refresh-evidence`, commit the regenerated files, and fast-forward `main`.

Known loose ends:

- The EX01 evaluate benchmark is at or just over its 250 ms target on the Windows machine after the extra router
  calls; re-measure on the Mac before deciding anything.
- `/nl/opener` and `/clock/advance` answer 403 without the owner token where other owner routes answer 401; the
  web client handles both.
- `app/alerts/engine.py` imports `app.operations.log` for the repay alert's interest; it bends the module map
  (alerts → domain, financial) without creating a cycle.
- The approvals queue has no after-state for a pending item; the card shows none.
- An over-cap Tier-2 offer is queued as pending and only refused when the owner approves it.
- The alert cure search is greedy and can miss a multi-invoice cure.
- Reconciliation reuses `SHORT_PAYMENT` for partial payments.
- Supabase is at migration 0002; `alembic upgrade head` applies 0003. Confirm no migration is needed for the new
  state fields before pointing the app at Postgres.
- Audit items deferred to after the hackathon: S6, S7, S8, C13, F9. Medium items not scheduled: S5 (the
  accept/counter threshold can be probed, now at 0.64%/0.65%), S9 (the agent key reads status and alerts through
  chat; the new read intents are already owner-only), S10 (bind "go ahead" to the plan shown).

## 7. Stop conditions

- A task past 1.5× its estimate stops and reports.
- If the proactive loop (steps 4 and 5) is not green by 9 Oct, ship only the alert with a button.
- UI work never delays the video recording.
- Optional features (named stresses, payment instrument, guarded supplier payment, recurring outflows, Chinese
  server text, deployment) start only when waves A to D are closed.

## 8. What only the owner can do

Team eligibility and registration (issue #10); the organiser email (issue #9, draft posted); team roster (#5);
deployment region (#7); the licence for the LICENSE file; whether the 15% APR cap should gate invoice
financing on its effective annual rate (D5: it would refuse the demo's 13-day cure at about 25% a year); deck branding; building the deck (outline only exists) and recording the video; the
`[TEAM:]` placeholders in the documents.

## 9. Useful commands

```bash
cd services/api && uv run pytest -o addopts= -q                  # full suite with a summary line
python3 scripts/run_scenarios.py --inproc                        # 37 chat scenarios (repo root)
cd services/api && uv run python -m app.security.attacks --report
uv run --project services/api python scripts/evaluate.py         # scoreboard rows
git checkout -- services/api/evals                               # drop regenerated evidence
```

Credentials in demo mode: owner `X-Owner-Token: demo-owner-token`, agent `X-Agent-Key: demo-agent-key`, bank feed
`X-Bank-Feed-Key: demo-bank-feed-key`.
