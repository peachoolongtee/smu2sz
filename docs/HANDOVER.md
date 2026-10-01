# Handover: TermsLedger v2, 1 Oct 2026

For a new Claude Code session on another machine. Read this file first, then the files it points to.
Everything you need is in this repository; nothing depends on the previous machine.

## 1. Start here

```bash
git clone https://github.com/peachoolongtee/smu2sz.git
cd smu2sz && git checkout dev
cd services/api && uv sync && uv run pytest -o addopts= -q
```

Needs `uv` (Python 3.12), Node with `pnpm`, and `gh` logged in to GitHub. Expect about 3,700 tests passing in
3 to 4 minutes. Then, from the repo root: `python3 scripts/run_scenarios.py --inproc` (expect 37/37), followed by
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

## 4. Where things stand

`dev` is green: 3,806 passed, 17 skipped; scenarios 37/37; attacks 182 (122 API + 60 chat), 0 with harm. Baseline before this
phase was `6d500a9` (3,557 passed).

**Done and merged into `dev`**

| Item | What changed |
| --- | --- |
| Chat boundary (S1, S2) | A buyer-role `/nl` response carries only reply and session fields. Quoted or pasted buyer text never becomes owner intent or an approval id; it logs an INJECTION event |
| Computed scoreboard (S11) | `/audit` computes money moved and disclosed fields (`app/security/scoreboard.py`) |
| Coverage proof (S3) | Any unread word sends the offer to the owner. "Agreed as proposed." replaced by a restatement of the typed terms |
| Re-verify at commitment (S4) | Executor `_check_binding`: receivable still owed with enough outstanding, one live commitment per receivable, aggregate and per-buyer caps, and a re-verify hook when the state version moved. New codes `STALE_VERDICT`, `CONFLICTING_COMMITMENT` |
| Current books | `FinancialState.as_of_day`, `Receivable.settled_fen`, `advance_fen`, `advance_facility_id`; engine skips closed days and counts the horizon from today; `app/books` (`current_books`); funding is requested today |
| Clock | `app/clock`, `POST /clock/advance`, `Runtime.advance_to`. Posts scheduled flows, issues recurring invoices, expires stale commitments, applies scenario events (`fixtures/scenarios/golden_sme.events.json`), never records a receipt |
| Partial settlement | A receipt equal to the agreed early-pay amount settles that face and marks the commitment FULFILLED; other amounts settle their own amount |
| Capex, borrower file, alerts on current books | Alerts work past day 0, report past-due and missed early payments, and date cures today |

**Nothing is in flight.** Both branches that were running when this file was first written are merged:

| Item | What changed |
| --- | --- |
| Verifier, router callers, `/trajectory`, what-if and chat handlers on current books (B3) | After an accepted commitment, the next verdict, plans and trajectory all include it; `/alerts` agrees with `/trajectory`. `ctx.books()` and `ctx.evaluate_accepted()` in `app/nl/context.py` |
| Attack suite through chat (A3) | 60 attacks through `/nl` in owner, buyer and agent-key roles on top of the 122 through the API; 0 with harm. `LedgerStore.verdicts()`; the scenario runner checks buyer turns against the store (`store_outcome`, `store_codes`, `store_ops`); three new rows in `scripts/evaluate.py` |
| Two holes A3 found, fixed | A chat session is bound to the credential that opened it (`Session.owner_auth`). An approval, decline or go-ahead counts only as a short direct instruction (`_direct_command` in `app/nl/service.py`): one line, at most 80 characters, no counterparty name, no forwarding or attachment marks. Otherwise nothing is decided, an INJECTION event is logged and the owner is told what to type |

**Integrated demo run on 1 Oct** (evaluate EX01, deal on Counter A, bank receipt of ¥209,999.70 on day 2, clock to
day 34): the ¥208,200 residual is reported past due and the gap peaks at ¥200,000.30 on day 42 because of the
month-2 payroll event. No cure is offered yet for one reason: Counter A leaves cash ¥0.30 under the floor, so the
breach starts "today". That is tracker row B5.

## 5. Decisions made in this phase that a new session must not undo

- Days stay absolute; the books close days before `as_of_day`. Nothing is re-based.
- Receipts come only from the bank feed (`ReceivePayment` by SYSTEM with the bank-feed key). The clock never
  assumes one arrived.
- An overdue financed invoice repays its advance today in the projection (recourse).
- The golden scenario has no outflows after day 47, so the proactive scene relies on the scenario event that adds
  month-2 payroll (¥200,000, day 42) on day 25. It does not exist on day 0, so day-0 golden values are unchanged.
- Coverage: words inside an obligation's source span are not exempt from the filler list. One held-out offer
  (H3-A03) now goes to the owner instead of being accepted alone. Accepted; do not widen the list with words that
  can carry a commercial term.
- Buyer-role scenario expectations were moved from the response to the store.
- Early pay (ADR-0007): accept only if below the tenor-aware break-even, the cash is needed, and total cost with
  it is lower than the router's plan without it. This will turn some accepted whole-invoice discounts
  (0.65%–0.88%) into counters.

## 6. What to do next, in order

1. Confirm the baseline on the new machine (section 1 commands).
2. **B5, Counter A rounding (F8).** The counter's face must net at least the gap after the discount: roughly
   ¥211,900 instead of ¥211,800, rounded up to a tidy unit, and the counter must be checked against the floor.
   Code is in `services/api/app/verifier/counters.py`. This changes a headline number in tests, mocks, the demo
   script and the documents; update them all. Proof: no critical alert straight after the demo deal.
3. **D1/D2, implement ADR-0007** in the verifier (`_apr_checks` and the outcome logic). One agent
   implements; a different agent re-derives every row of the ADR's table by hand and adds cases for 3, 30 and 90
   days early, no cash need, partial gap, and break-even ±1 bp. Check that the re-verify hook in
   `app/api/runtime.py` still passes verified counters.
4. **C2, alert with a button.** `POST /alerts/{id}/act` turns an alert's suggested cure into a typed operation:
   Tier 1 executes, Tier 2 queues an approval. Proof: at day 34 the alert offers to finance about ¥200,000 of
   invoice `RI:BUYER-1:2` and one call executes it.
5. **C3, C4.** Reconcile against what commitments promised (partly done in `app/alerts/reconcile.py`); a proactive
   opener in `/nl` and the UI after a clock or bank-feed event. Then run demo steps 1–17 from the technical-lead
   brief, section 19.
6. **D4** DSCR counts scheduled bullet principal (F6), with a second agent checking. **D5** if time.
7. **Wave E:** chat intents for financing comparison, alerts, reconcile, ratios, capex and borrower file, with a
   nearest-capability fallback; owner home at `/`; richer approval card; visible autonomy proof; annualised
   column; compliance half-page and LICENSE; demo fixes (Start 401, mock/live mismatch, REJECT badge).
8. **Close-out:** regenerate evidence (`uv run --project services/api python scripts/build_deliverables.py
   --refresh-evidence`), update documents, demo script and web mocks for changed numbers, fast-forward `main`.

Known loose ends to fold in where convenient:

- `apps/web/mocks/nl_script.json` still holds a verdict for a buyer turn; the live API now returns none. The buyer
  chat UI needs checking and the mock regenerating.
- `/nl` status text reports breach days from day 0 even when today is later (should start at today). Still open.
- A consequence of credential-bound sessions: a web client that sends some turns without the owner token gets a
  fresh session for those turns. Check the chat panel keeps the token on every owner turn.
- `services/api/evals/latest_report.*` has not been regenerated with the three new scoreboard rows; do it in the
  close-out.
- An over-cap Tier-2 offer is queued as pending and only refused when the owner approves it.
- The alert cure search is greedy (one facility's room on the earliest invoice) and can miss a multi-invoice cure.
- `committed_cure` does not check `mandate.allow_new_borrowing`.
- Reconciliation reuses `SHORT_PAYMENT` for partial payments; a distinct status would need a web type change.
- Supabase is at migration 0002; `alembic upgrade head` applies 0003. The new state fields live inside the stored
  state JSON; confirm no migration is needed before pointing the app at Postgres.
- Audit items deferred to after the hackathon: S6, S7, S8, C13, F9. Medium items not yet scheduled: S5 (counter
  grid as an oracle), S9 (agent key reads status through chat), S10 (bind "go ahead" to the plan shown).

## 7. Stop conditions

- A task past 1.5× its estimate stops and reports.
- If the proactive loop (steps 4 and 5) is not green by 9 Oct, ship only the alert with a button.
- UI work never delays the video recording.
- Optional features (named stresses, payment instrument, guarded supplier payment, recurring outflows, Chinese
  server text, deployment) start only when waves A to D are closed.

## 8. What only the owner can do

Team eligibility and registration (issue #10); the organiser email (issue #9, draft posted); team roster (#5);
deployment region (#7); deck branding; building the deck (outline only exists) and recording the video; the
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
