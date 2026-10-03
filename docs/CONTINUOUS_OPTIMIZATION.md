# Continuous optimisation: backlog, uncertainty debt, scorecard

Live document of the continuous technical owner (`docs/AGENT_MISSION.md`). Updated after every merge. Rules for each
quantity are in `docs/FINANCIAL_SEMANTICS.md`. Audit ids (A01…, F-FIN-…, S-…, F1…) refer to
`docs/research/independent-principal-audit-2026-10-03.md` and its three working papers.

Last updated: 3 Oct 2026 (night), at `db097e0` on `dev`: the API gaps, one leverage definition, the fourth and fifth red-team rounds' fixes, the evaluation speed-up, the concurrency work, the language-boundary certification harness and boundary abstentions, and the evaluation oracle on the runnable rule are merged; evidence and documents regenerated on `docs/gate-checkpoint`. The owner stopped the red-team rounds on 3 Oct (section 0, G1).

## 0. Engine Stability Gate (set by the owner, 3 Oct, late)

The financial engine is declared stable, and broad new financial features may be considered, only when all of these
hold. Until then the queue below is correctness and certification only; capex stays as a supporting demo scene; the
explicit Tier-2 approval for an above-ceiling rate stays.

| Condition | Status |
| --- | --- |
| G1. ~~A fourth unanchored red team on the checkpoint finds no P0 or high-confidence P1~~ | REMOVED. The owner stopped red teaming on 3 Oct. Five rounds were run (`docs/research/redteam-2026-10-03` to `-03e`), 26 findings in all, every one fixed with a regression test (RT1 to RT5 in section 1). No further round unless the owner asks. |
| G2. One leverage definition (actual drawn debt) used by the projection, the verifier's pro forma, capex, the borrower file and chat | DONE 3 Oct (`4b180ec`; `tests/covenants/test_one_leverage_property.py`: the five readers report the same fen-ratio) |
| G3. Live-model fail-closed certification: with the real compiler backend (and its fallback), a fresh adversarial and malformed-output set produces zero wrong-and-material executable interpretations; abstentions and clarifications counted separately | Harness DONE (231 items, `scripts/certify_language_boundary.py`, `82b2628`); cache and fake runs WRONG_MATERIAL 0 (`services/api/evals/certification/language_boundary_cache_20261003T075236Z.md`, `language_boundary_fake_20261003T075307Z.md`). **Live run PENDING a key**: `PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend live` with `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` in the root `.env`. Until it runs, the live model is not certified. |
| G4. PostgreSQL concurrency invariants: forced interleavings (concurrent draws against the last room, receipt vs finance, accept vs revoke, duplicate external event, rollback on log failure, restart) on a real database; no double booking; one serialization boundary per organisation | SQLite DONE (eight two-process invariants, compare-and-swap on the state version and the log head, `BEGIN IMMEDIATE`; `docs/research/concurrency-certification-2026-10-03.md`). **PostgreSQL PENDING a database URL**: `cd services/api && TERMSLEDGER_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host/termsledger_ci SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency` on an empty dedicated database. |
| G5. Planner/executor agreement test green at 500 examples on three seeds, counter property green | DONE 3 Oct; re-run in the full suite at this checkpoint (`tests/funding/test_planner_executor_agree.py`, `tests/verifier/test_counter_property.py`) |

## 1. Open findings

Status: OPEN, IN PROGRESS (branch named), DONE (merged to `dev`, date).

| Id | P | Finding | Evidence | Owner | Depends on | Value | Effort | Status | Test that closes it |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | P0 | Negated, questioning, conditional, future-dated, foreign-currency or unreadable-amount messages execute financing | security working paper S-01 | subagent | | Very high | M | DONE 3 Oct | Every transformation of a valid command leaves state unchanged, both credentials, EN and ZH |
| A02 | P0 | "Do not approve APR-…", a question or a bare id approves | S-02 | subagent | | Very high | S | DONE 3 Oct ("do not approve" declines) | Unclear texts leave the approval PENDING; exact approve runs once |
| A03 | P0 | Anyone can speak as a registered buyer and book a commitment | S-03 | subagent | | Very high | M | DONE 3 Oct | No credentials: zero operations, zero live commitments |
| A04 | P0 | Startup wiped the persisted books and log | S-04 | subagent | | High | S | DONE 3 Oct | `tests/api/test_startup_hydrate.py` |
| A05 | P0 | Executor admitted what the planner rejects (original face, lead time, rate cap, DSCR) | `scripts/independent_audit_books.py` | owner | | Very high | M | DONE 3 Oct | `tests/operations/test_admission.py` |
| A09 | P0 | A late receipt earned the early-payment discount | same script | owner | | High | S | DONE 3 Oct | same file, four pay days |
| A06 | P0 | Accepted price and terms never become the issued invoice; partial receipt loses ¥450 | `counter-repro.py` | owner design, subagent build | | Very high | L | DONE 3 Oct (ADR-0009) | `tests/books/test_invoice_terms.py`: real Option B: issue, full and partial receipt conserve the agreed face and due day in every module |
| A07 | P0 | "Next 3 invoices" rolls on to later invoices as earlier ones settle | `bounded-repro.py` | with A06 | A06 | Very high | M | DONE 3 Oct (ADR-0009) | Scope identical after settlement, retries and clock; invoice four never inherits |
| A08 | P0 | Funding cash and debt dates differ between projection, executor and clock; carried debt posts into closed days | books script, F-FIN-02 | owner design, subagent build | A06 merged first (same files) | Very high | L | DONE 3 Oct (ADR-0010) | `tests/books/test_funding_lots.py`: projection today equals actual cash; close-then-project equals the remaining schedule |
| A10 | P0 | "Go ahead" re-plans and can run a larger, dearer plan | S-05 | subagent | A01 merged first (same files) | High | M | DONE 3 Oct | `tests/nl/test_plan_binding.py`: state change after a proposal: same operations at the same or lower cost run, anything else re-proposes |
| A11 | P1 | Gains outside the horizon offset the cap; perpetual value is quadratic in the horizon; monthly service ignores invoice frequency | F-FIN-01, 06, 07; derivation merged 3 Oct | subagent against the derivation | A07 (shared scope) | High | M | DONE 3 Oct | `tests/financial/test_dated_valuation.py`: derivation tables reproduced by the code |
| F-FIN-09 | P1 | Upfront fee repeated per period in the break-even | derivation part 11 | subagent | | Medium | S | DONE 3 Oct | c(n) equals ledger charges for n = 1…91 |
| A12 | P1 | Capex recommends while omitting fees, drawn debt, liquidity, real tenor | F-FIN-03/04/05, flows F3/F4 | subagent | | High | M | DONE 3 Oct | `tests/capex/test_audit_fixes.py` |
| A13 | P1 | Borrower file keeps the equipment money as cash; window anchored at day 0 | flows F5, F7 | subagent | | High | S | DONE 3 Oct | Purchase deducted; rolling 12 months; day 361 works |
| S-06 | P1 | "today" and "tomorrow" both bind to day 2 | S-06 | subagent | | Medium | S | DONE 3 Oct (fails closed; a typed settlement day would let "today" be accepted again) | Explicit timing is not accepted autonomously |
| R01 | P1 | Router tests the rate cap on the tariff; the executor on the effective cost | 3 Oct, own finding | subagent | | Medium | S | DONE 3 Oct (`574a04f`) | Router marks an above-ceiling action as needing the owner; no plan the router calls autonomous is queued by the executor |
| R02 | P1 | Multi-leg plan is not one transaction: a later leg can be refused after an earlier one ran | audit §7 | owner | A10 | Medium | M | OPEN | Whole plan admitted before the first leg; partial outcome reported truthfully |
| R03 | P1 | Same bank event with a new key settles twice | audit §7, code-inspected | subagent | | Medium | S | DONE 3 Oct for receipts that carry a `bank_reference` (BC5); a receipt without one is still identified by its key only | External event id on bank receipts; same id with a new key is a duplicate, different payload conflicts (`tests/operations/test_bank_reference.py`) |
| F-FIN-10 | P2 | Level bullet DSCR presented as the bank covenant | F-FIN-10 | owner | | Medium | S | OPEN | Label "reserve-coverage reading" everywhere it is shown; covenant text states its basis |
| F6 | P2 | Borrower-file approval authorises nothing meaningful | flows F6 | subagent | A13 | Low | S | DONE 3 Oct (S1–S3: the file is read-only with provenance; no approval) | Preparing the file is read-only for the owner |
| UI1 | P2 | UI does not separate requested, awaiting approval, awaiting settlement, settled, refused | audit §11 | frontend subagent | A08 | High | M | DONE 3 Oct (web follow-up `5fabd4a`: waiting-for-approval states, landing day, funding in transit) | e2e on the demo path |
| UI2 | P2 | Reconciliation page does not show promised payments; approvals show the current day as decision day | flows "Additional UI evidence" | frontend subagent | | Medium | S | DONE 3 Oct (`48eb683`, `5fabd4a`) | e2e |
| UI3 | P3 | Phone layout: security page 6 px overflow, chat panel past the viewport | audit integration record | frontend subagent | | Low | S | DONE 3 Oct (`48eb683`, phone layout guards) | `e2e/responsive.spec.ts` phone project |
| DOC1 | P1 | Documents, mocks, evidence, video script quote numbers that these fixes change | | owner | all P0 | High | M | DONE 3 Oct: documents, evidence and reports regenerated on `docs/audit-closeout`, on `docs/cash-figures` after the debt-service change, and on `docs/gate-checkpoint` at `db097e0` (leverage, Counter A's day, the fourth and fifth rounds, concurrency, certification); mocks re-recorded in `ed4a5c4` and stale again after the later figure changes (WEB1, refresh in progress) | `scripts/evaluate.py` targets all pass (15 item-level misses, 4 of them from the cash change: H09a, H09b, H12a, H39, labels unchanged); all 49 evidence chains VALID at `db097e0` |
| R04 | P2 | `POST /offers` stores a compiled offer for a sender id taken from the body, unauthenticated | counterparty-channel report | owner | | Low (nothing executes) | S | OPEN | Unauthenticated intake is capped or marked untrusted; evaluate still needs the owner |
| R05 | P2 | Unauthenticated buyer messages and wrong keys grow the offer, verdict and security-event tables without limit | same report | owner | | Low | S | OPEN | A cap per day; test |
| R06 | P1 | Three refused agent attempts on a lender open its circuit and then block the owner's own approval | admission follow-through report | owner | | Medium | S | DONE 3 Oct (with RT1-2) | Refused approval attempts by a non-owner do not count toward the lender's circuit; owner approval still executes |
| R07 | P2 | Commitments made ACTIVE before ADR-0009 in a persistent store carry no adjustments | invoice-terms report | owner | | Low (no such store in use) | S | OPEN | One-off backfill or a startup check that refuses to hydrate such a store silently |
| RT1 | P0 | Fresh red team on `dev` after the six merges | `docs/research/redteam-2026-10-03/REPORT.md` | subagent | | High | M | CLOSED 3 Oct: three findings, all fixed (rows below) | `tests/operations/test_circuit_scope.py`, `tests/books/test_funding_lots.py`, `tests/books/test_invoice_terms.py` |
| RT1-1 | P0 | A receipt on a financed invoice repays the whole advance from the owner's cash; 1 fen took cash negative and reopened the invoice | probe `p03` | subagent | A08 | Very high | S | DONE 3 Oct | p03 sequence: cash never falls on a receipt; invoice stays FINANCED until cleared |
| RT1-2 | P0 | Agent-key refusals opened a buyer's circuit and blocked bank receipts; a refused key was burnt | probe `p01` | owner | | High | S | DONE 3 Oct | `tests/operations/test_circuit_scope.py` |
| RT1-3 | P1 | A price cut could take an invoice below its settled amount | red team suggestion, confirmed in code | owner | | Medium | S | DONE 3 Oct | `test_a_price_cut_cannot_take_an_invoice_below_what_is_already_settled` |
| R08 | P1 | `RequestOwnerApproval`: caller's free text became the reason the owner saw (third red team reproduced it: an agent-reported receipt described as "no payment") | `docs/research/redteam-2026-10-03c/p06` | owner | | High | S | DONE 3 Oct | The owner sees the operation's own description, never caller text; ambiguous op ids refused |
| RT2 | P0 | Second fresh red team, aimed at the seams of the 3 Oct rewrites: seven reproduced findings (probes in `docs/research/redteam-2026-10-03b/`) | red-team round b | subagent | | Very high | M | CLOSED 3 Oct: seven findings, all fixed (rows below) | Each probe prints held; `tests/operations/test_redteam_b.py` |
| RT2-1 | P0 | An invoice under an early-pay agreement could be financed; any receipt before the advance landed cancelled it (cash fell to half the reserve) | p03 | subagent | | High | S | DONE 3 Oct | |
| RT2-2 | P0 | "Next invoice" terms valued on the next invoice but written onto an older, even overdue, one | p07, p06 | subagent | | High | S | DONE 3 Oct | |
| RT2-3 | P1 | Advance repaid but charges short: invoice FINANCED with nothing outstanding, lot nobody can clear | p05 | subagent | N03 | Medium | S | DONE 3 Oct | |
| RT2-4 | P1 | Default early-pay settlement day was absolute day 2, so early-pay offers failed from day 3 | p13 | subagent | | Medium | S | DONE 3 Oct | |
| RT2-5 | P1 | Bank and owner receipts refused after the mandate expires | p08 | subagent | | Medium | S | DONE 3 Oct | |
| RT2-6 | P1 | A different operation reusing an idempotency key made a bank receipt a DUPLICATE | p10 | subagent | | Medium | S | DONE 3 Oct | |
| RT2-7 | P2 | Aggregate cap bypassed by splitting an agreement into one-invoice agreements over time | p06 | subagent | | Low | S | DONE 3 Oct | |
| N01 | P1 | Chat does not say when funding cash lands; the repay proposal defaults to the whole drawn balance including cash not yet landed | funding-lots report | subagent | | High | S | DONE 3 Oct | Replies name the landing day; repay proposes the landed balance |
| N02 | P1 | After a negotiation, the fallback and remaining-gap funding legs are rebuilt and do not stop at a refused or queued leg | plan-binding report | subagent | | Medium | M | DONE 3 Oct | Stored legs sent; stop at the first leg not executed |
| N03 | P2 | A financed invoice whose face is fully settled while its advance is open drops out of the projection; its lot is repaid at the horizon end | funding-lots report | subagent | | Low | S | DONE 3 Oct | Projection repays the remaining lot today |
| N04 | P2 | A receipt that covers the advance but not its charges capitalises the unpaid charges and charges them again | funding-lots report (agent's own choice) | owner | | Low | S | DONE 3 Oct (no longer capitalised: a fixed remainder the owner repays) | |
| RT3 | P0 | Third fresh red team: three findings | `docs/research/redteam-2026-10-03c/` | subagent | | High | M | CLOSED 3 Oct: all three fixed (`tests/operations/test_redteam_c.py`) | |
| RT3-2 | P0 | Admission (my own fix 11acc56) omitted a line draw's cash, so a runnable plan was refused for everyone | p03, p05 | owner | | High | S | DONE 3 Oct | |
| RT3-3 | P1 | A recreated chat session reused old idempotency keys: a later command was a DUPLICATE or a REPLAY | p07 | owner | | Medium | S | DONE 3 Oct | |
| C01 | P1 | Owner-session chat ran an above-ceiling leg directly while the agent channel queued it | plan-flags report | owner | | Medium | S | DONE 3 Oct: chat funding legs are the agent's act in every session | |
| W01 | P2 | Approvals queue has no decision day; plan actions carry no landing day; executed ledger rows lack the approval id they ran under; no demo scenario for the zero-floor cure | web report | subagent | | Low | S | DONE 3 Oct (`92b7b0f`): `decided_day` and `result_message` on the approvals queue, `lands_day` on plan actions for draws and invoice advances, the approval id on the executed ledger row, and the `short_facilities` demo scenario (`fixtures/scenarios/short_facilities.json`) | `tests/api/test_api_gaps.py`, `tests/persistence/test_approval_decided_day.py`, `tests/operations/test_approval_log.py` |
| W02 | P3 | 1-fen receipt before landing cancels an advance sitting exactly at the advance-rate limit (by rule; harsh) | third red team | owner | | Low | S | OPEN (accepted) | |
| BC1 | P0 | Existing loan's ¥45,000 monthly service counted in DSCR but never left cash: every cash conclusion optimistic by ¥45,000 a month | business review A1 | subagent | | Very high | M | DONE 3 Oct (`tests/books/test_debt_service.py`); golden figures moved (gap ¥405,000, plan ¥3,113.93, Counter A ¥257,200) | |
| BC2 | P1 | No fallback cure when the reserve cannot be restored even though cash can be kept above zero | review A2 | subagent | | High | S | DONE 3 Oct | |
| BC3 | P1 | Chat answered "we have a bill of ¥80,000" with the cash status as if recorded | review A3 | subagent | | High | S | DONE 3 Oct (RECORD_FACT, read-only) | |
| BC4 | P1 | Mandate expiry had no warning; owner's own draw refused on day 91 | review A4 | subagent | | Medium | S | DONE 3 Oct (alert; renewal offline) | |
| BC5 | P1 | Same bank event under a new key settled twice (R03) | review A5 | subagent | | Medium | S | DONE 3 Oct (`bank_reference`) | |
| BC6 | P1 | Borrower file dated to day 0 whatever the generation day | review A6 | subagent | | Medium | S | DONE 3 Oct | |
| BC7 | P1 | An offer from a buyer with a past-due invoice was judged on cash and caps only | review A7 | subagent | | Medium | S | DONE 3 Oct (needs the owner, invoice named) | |
| BC8 | P1 | Alert button not bound to the cure shown | review A8 | subagent | | Medium | S | DONE 3 Oct (409 ALERT_CHANGED; the web sends the body, `0ea2471`) | |
| BC9 | P1 | Counters the verifier offered did not pass their own re-check (Option B failed on reserve once debt service left cash) | debt-service report | subagent | | High | M | DONE 3 Oct (`tests/verifier/test_counter_property.py`, curable reading) | |
| BC10 | P1 | Router and executor disagreed on a line draw held past the first affordable receipt (found by the agreement test) | agreement test | subagent | | High | S | DONE 3 Oct (`carry_draw` shared) | |
| BC11 | P1 | Router admits an advance leg that admission refuses on the reserve (pinned Hypothesis world) | agreement test | subagent | | High | S | DONE 3 Oct (`fbbc7d3`, `3edf1b6`, `1bc96ba`: legs ordered so every prefix is admissible, one leg rule shared with admission; a plan admissible only as a whole is flagged cannot run today) | `tests/funding/test_planner_executor_agree.py` |
| S1–S3 | P2 | Capex evaluation queued an application; borrower-file approval authorised nothing; dead weight (aftersign, mock lender) | review D2–D4 | subagent | | Medium | S | DONE 3 Oct | |
| D1 | P1 | Covenant ratios computed in four places with two leverage definitions (line at limit vs drawn) | review D1 | subagent | | High | M | DONE 3 Oct (`4b180ec`, gate G2): one definition, month-end drawn debt over annual EBITDA, `covenants.ratios_for` read from a projection by the verifier, capex, the borrower file and chat. Golden figures moved: EX01 leverage after the extension 1.72× to 1.47×, base 1.53× to 1.35×; capex 2.08× / 2.28× to 1.90× / 2.10× | `tests/covenants/test_one_leverage_property.py` (the five readers report the same fen-ratio), `tests/covenants/test_ratios.py`, `tests/capex/test_evaluate.py` |
| EV1 | P2 | Evidence chain heads are not reproducible run to run (session nonce, commitment nonces) | close-out report | owner | | Low | S | OPEN (claim narrowed to "integrity-checkable") | |
| MW1 | P1 | Several API workers: process-local lock, no state-version compare-and-swap | audit §7, reproduced: 16 of 20 SQLite cases failed on the old store | owner | | Medium | M | DONE on SQLite 3 Oct (`3649b24`, `476357c`, `d0d6246`, `7102a46`): compare-and-swap on the state version and on the log head, `BEGIN IMMEDIATE` on file SQLite, the executor and the clock rerun a lost unit (at most 8 times), a conflict that survives answers HTTP 409 with a retry hint. PostgreSQL PENDING (PG1) | `tests/concurrency/test_invariants.py` (eight invariants, two spawned processes, three engines), `tests/persistence/test_concurrency_cas.py`, `tests/clock/test_clock_conflict.py`, `tests/api/test_write_conflict_409.py` |
| RT4 | P1 | Fourth red team (round d, `docs/research/redteam-2026-10-03d/`, probes only; the findings are the regression tests): seven findings, merged `557645b`. Rounds 4 and 5 did not grade each finding; all are listed P1 here | red-team round d | subagent | | High | M | CLOSED 3 Oct: seven findings, all fixed (rows below) | `tests/operations/test_redteam_d.py` |
| RT4-1 | P1 | A plan with an early-pay or bill leg (a leg no operation can run) was sent with the leg silently dropped, and the standing plan C0 was priced on a leg the agent cannot run | probes p02, p09, p13 | subagent | | High | S | DONE 3 Oct (`c23ecb5`, `3c3a1be`): such a plan is flagged cannot run today; chat and `/negotiate` never drop a leg; C0 is the cheapest plan the agent can run (ADR-0007 note) | `tests/operations/test_redteam_d.py::test_f1_*`, `tests/verifier/test_early_pay_handcalc.py` |
| RT4-2 | P1 | An approved agent receipt double-booked a receivable the bank or the owner had booked since it was queued | p06 | subagent | | High | S | DONE 3 Oct (`07f776c`): refused when that receivable was booked since | `test_f2_*` |
| RT4-3 | P1 | A lapsed early-pay agreement still blocked financing and kept its commitment live | p03 | subagent | | High | S | DONE 3 Oct (`da4dbbf`): admission checks live obligations only; the clock closes an early-pay-only commitment whose promises all lapsed | `test_f3_*` |
| RT4-4 | P1 | Consent grammar: a past-tense statement ran as a repayment; a tag question confirmed a plan | p04, p05 | subagent | | High | S | DONE 3 Oct (`5bde7f7`) | `tests/nl/test_consent.py` |
| RT4-5 | P1 | An early receipt fulfilled a commitment that still had live obligations | p10 | subagent | | Medium | S | DONE 3 Oct (`455fa35`): fulfilled only when nothing else in it is live; otherwise the obligation is recorded settled and the package stays revocable | `test_f5_*` |
| RT4-6 | P1 | Reconciliation showed a late discounted receipt as the agreed early payment | p12 | subagent | | Medium | S | DONE 3 Oct (`6869dec`): a late receipt is a plain receipt | `test_f6_*`, `tests/alerts/test_reconcile_promises.py` |
| RT4-7 | P1 | A bullet term lot's upfront fee dropped out of its level debt service once the cash landed | p14 | subagent | | Medium | S | DONE 3 Oct (`ec3ad3d`): the fee stays in the level service before and after landing | `test_f7_*` |
| RT5 | P1 | Fifth red team (round e, `docs/research/redteam-2026-10-03e/`, probes only): six findings, merged `5eb299a` | red-team round e | subagent | | High | M | CLOSED 3 Oct: six findings, all fixed (rows below). The owner then stopped the red-team rounds (G1) | `tests/verifier/test_redteam_e.py`, `tests/operations/test_redteam_e.py` |
| RT5-1 | P1 | A fixed-sum early-pay discount (a yen amount, not a rate) was not tested at its own rate by the cap, the break-even and the rate ceiling | p05 | subagent | | High | M | DONE 3 Oct (`1ca8c91`): tested at its exact rate on its portion (discount cap, break-even, rate ceiling, plan tests) | `test_f1_*` in `tests/verifier/test_redteam_e.py` |
| RT5-2 | P1 | A stated target term ("40 days") was bound against the template's base terms, so a second agreement stacked on the first | p07 | subagent | | High | S | DONE 3 Oct (`6e19415`, `c89fe88`): bound against the terms in force for the buyer's next invoice (the template plus the accepted adjustments); counter texts quote them | `test_f2_*` |
| RT5-3 | P1 | The demo scenario's events (month-2 payroll) could apply to any books | p08 | subagent | | Medium | S | DONE 3 Oct (`da95b15`): events apply only in `DEMO_MODE`, to the books seeded from that scenario; the scenario is stored with the books and hydrated on restart | `tests/operations/test_redteam_e.py::test_f3_*` |
| RT5-4 | P1 | Counter A did not name its settlement day, and an early-pay agreement could not be settled in portions | p02, p04 | subagent | | High | M | DONE 3 Oct (`aa9513c`): Counter A says "paid on or before day 2"; any portion up to the face earns the rate if paid by that day; projection and reconciliation follow | `test_f4_*` |
| RT5-5 | P1 | An owner-requested facility repayment was refused after the mandate expired | p09 | subagent | | Medium | S | DONE 3 Oct (`6429df0`): an owner repayment skips expiry, revocation and version checks (signature and admission still apply); the agent may not | `test_f5_*` |
| RT5-6 | P1 | A queued receipt lost the day it was reported on: approved late, it earned no discount; a request could carry its own reported day | p10 | subagent | | Medium | S | DONE 3 Oct (`aa9513c`): the queued receipt keeps its reported day; the agent cannot backdate one | `test_f6_*` |
| BA1 | P1 | Language boundary: a decimal-comma rate was read as 500 bp (certification BO-012, WRONG_MATERIAL); a per-day rate, 2/10 net 30, foreign currency, a partial amount, another party's invoice, hedges, a payment after the due date and a price freeze were read as a whole-invoice discount | `docs/research/language-boundary-certification-2026-10-03.md` | subagent | | High | M | DONE 3 Oct (`ea92076`, merge `bb30265`): each of these abstains with a reason and the buyer gets a question; nothing is countered, committed or queued | `tests/compiler/test_boundary_abstentions.py`, `tests/nl/test_boundary_abstentions.py` |
| CERT1 | P1 | No measurement of the language boundary against adversarial and malformed model output | audit; gate G3 | subagent | | High | M | Harness DONE 3 Oct (`f3b3124`, `82b2628`): 231 items scored on stored state, cache, fake and live backends. Cache and fake runs: WRONG_MATERIAL 0. Live run PENDING (LC1) | `tests/certification/test_language_boundary.py` |
| EO1 | P2 | The funding evaluation's oracle ranked early-pay and bill levers as runnable, so "optimal" compared the router with plans it cannot run | evaluation review | subagent | | Medium | M | DONE 3 Oct (`979defb`, merge `db097e0`): the oracle classifies runnable levers itself and reports runnable optimality (the gate) and priced optimality separately: 26/26 and 26/26 in `services/api/evals/latest_report.md`. The owner terms constraint also reads the terms in force (`823a1ab`) | `tests/evals/test_funding_oracle.py`, `tests/verifier/test_owner_constraints.py` |
| PF1 | P2 | EX01 evaluation took 3.3 s | latency review | subagent | | Medium | M | DONE 3 Oct (`2fd7fcc`, merge `919de9f`): the cash projector reuses the books the actions do not touch, an exact integer pruning bound, shared router searches within one evaluation; about 0.5 to 0.9 s on Windows by the commit message; verdicts byte-identical | `tests/funding/test_shared_runs.py` |
| PG1 | P1 | Concurrency invariants not run on PostgreSQL | gate G4 | owner | a database URL | High | S | OPEN, PENDING a URL: the suite runs unchanged once `TERMSLEDGER_TEST_DATABASE_URL` is set (its PostgreSQL cases are skipped until then) | `cd services/api && TERMSLEDGER_TEST_DATABASE_URL=... SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency` |
| LC1 | P1 | Language-boundary certification not run against a live model | gate G3, U-001 | owner | API keys | High | S | OPEN, PENDING a key | `PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend live` |
| NR1 | P2 | Product question: in the evaluation's "no runnable plan" worlds (oracle worlds F04, R01, R02, R10, R13, R14) the cheapest plan that closes the gap uses a buyer's early payment or a bill, which no operation runs, so the router flags it and offers nothing the agent can run. Should the agent propose drawing the line and asking the buyer or the owner? | funding evaluation | owner decision | | Medium | M | OPEN (product question) | |
| WEB1 | P2 | The web mocks, recorded outputs and e2e expectations predate the one-leverage change, Counter A's day and the fourth and fifth rounds' texts | web | frontend subagent | | Medium | M | IN PROGRESS (refresh under way; the last known counts are mock 35 and live 30) | `E2E_TARGET=mock pnpm exec playwright test`, then `pnpm mocks:record` |
| EO2 | P3 | The funding suite's `line_first_baseline` metric still uses early pay among its levers, so it compares with a plan the agent cannot run | `services/api/evals/suites/funding.py` | subagent | | Low | S | OPEN | |

Not doing before the deadline (audit §14 agrees): supplier payments, lender connectors, tax, FX, calendars, lease
residuals, PV ranking of financing, a general solver.

## 2. Uncertainty debt

Things the system assumes or claims that have not been verified. Each is either paid down (verified), made explicit
to the user, or the claim is removed.

| Id | Assumption or untested claim | Why it matters | How to pay it down | Status |
| --- | --- | --- | --- | --- |
| U-001 | Live Claude has not been tested against adversarial multi-document offers on this revision | The deterministic boundary is repaired and certified offline (cache and fake: WRONG_MATERIAL 0 on 231 items); the live extraction path can still mis-type terms | Harness built: `PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend live` (needs `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` in the root `.env`); scored as executable / clarification / abstention / wrong-harmless / wrong-material | Open: harness ready, run PENDING a key (LC1) |
| U-002 | PostgreSQL crash recovery and concurrent workers have not been fault-injected | The store now enforces the invariants itself (compare-and-swap, `BEGIN IMMEDIATE`), proven with two processes on SQLite; PostgreSQL is not exercised | Harness built: `cd services/api && TERMSLEDGER_TEST_DATABASE_URL=postgresql+psycopg://... SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency` on an empty dedicated database; until then deploy one worker and say so | Open: SQLite proven, PostgreSQL PENDING a URL (PG1) |
| U-003 | Facility lead times, tariffs, billing periods and limits are synthetic fixture values with no external evidence | Every cost and timing conclusion rests on them | Label as owner-entered; state in the UI and documents; a facility letter parser is out of scope | Open (label) |
| U-004 | The DSCR convention (monthly, level bullet service) is a modelling assumption, not lender contract language | A bank may measure annually or on cash paid | Name it a reserve-coverage reading; let a covenant carry its own basis later | Open (label) |
| U-005 | Recurring invoices are treated as confirmed future sales and collected exactly on the due day | Collateral and cash are overstated if the buyer pays late or orders less; one buyer is 100% of receivables | State it; keep the missed-payment scenario; a late-payment stress is IF TIME | Open |
| U-006 | The outflow schedule is whatever was entered; EBITDA is not a cash forecast | A recommendation horizon needs complete outflows | Say "screens the entered obligations only" where a plan is shown | Open (label) |
| U-007 | The bank feed, the buyer and the lenders are simulated; a clock stands in for time | No real settlement, failure or delay has been observed | Say "simulated" on every demo surface; pending-settlement state after A08 | Open |
| U-008 | The hash chain's head is not anchored outside the store | Truncation of the tail is undetectable | Claim "internally checkable" only; external checkpoint after the hackathon | Open (claim narrowed) |
| U-009 | The effective-rate ceiling uses simple annualisation over the days held | A lender or regulator may define APR differently | Named "effective annual cost" with its formula on screen | Open (label) |
| U-010 | The search for the cheapest plan is bounded (three actions, ¥10,000 grid) | "Cheapest" is cheapest within that search | Say so where the plan is shown; differential test against a finer grid exists | Open (label) |
| U-011 | The mock e2e and recorded mocks describe the pre-audit behaviour until re-recorded | UI tests can pass against stale shapes | Re-record at DOC1 | Paid down 3 Oct (`ed4a5c4`; mock e2e 35 and live e2e 30 then), and stale again: the one-leverage change, Counter A's day and the later texts moved figures after that recording. The web refresh is in progress (WEB1); the 35 / 30 are the last known counts |
| U-012 | Chinese negation and consent coverage is by rule lists | A phrasing outside the list must fail closed, not open | Closed grammar (A01) makes unknown phrasing non-executable; property test; the 231-item certification set adds 33 Chinese and 4 mixed-language items | In progress |
| U-013 | The evaluation oracle's brute force is grid-bounded; runnable optimality cannot see a plan both the router and the oracle missed | "Runnable optimality 26/26" means the router matched the best plan on the oracle's grid within ¥1, not that it found the global optimum | Say so wherever 26/26 is quoted; a finer-grid or exact solver for a sample of worlds if the claim is ever strengthened | Open (label) |

## 3. Scorecard

Reproduce with `scripts/evaluate.py`, `scripts/run_scenarios.py --inproc`, the audit probes and the backend suite.
Numbers are measurements on the commit named, never targets. "Latest `dev`" is `db097e0`, measured on Windows on 3 Oct 2026 by the documents pass `docs/gate-checkpoint`.

| Area | Measure | `beb8c66` (audit baseline) | Latest `dev` |
| --- | --- | --- | --- |
| Financial | Backend tests passed | 4,042 (26 skipped) | 5,446 (33 skipped; two sequential chunks, 3,437 + 2,009; `SKIP_PERF_BENCH=1`) |
| Financial | Funding evaluation: runnable optimality / priced optimality | n/a (the oracle ranked unrunnable levers as runnable) | 26/26 / 26/26 (the brute force is grid-bounded, U-013); flags agree with the oracle 26/26 |
| Financial | Planner/executor mismatches reproduced by the audit probes | 6 of 6 | 0 of 6 defects; the discretionary line repayment is a labelled assumption (ADR-0010) |
| Financial | Formula discrepancies open | 9 (F-FIN-01, 02, 03, 04, 06, 07, 09, 10, 11) | 1 (F-FIN-10: label) |
| Financial | Accepted-terms lifecycle failures (A06, A07) | 2 | 0 |
| Security | Catalogue attacks / with harm | 182 / 0 | 255 (122 API + 133 chat: nl:owner 43, nl:counterparty 64, nl:agent 26) / 0, report regenerated 3 Oct |
| Security | Audit attacks with harm (A01, A02, A03, A04, A10) | 5 of 5 | 0 of 5; five red-team rounds: 26 findings, 26 fixed; the owner stopped the rounds |
| Language | Wrong and financially material interpretations known | 13 texts (S-01 ×8, S-02 ×5) | 0 known; held-out offer labels agree 45 of 50 (the four 60-day-terms items H09a, H09b, H12a, H39 now return REJECT on the cash-corrected books and their labels were not changed) |
| Language | Language-boundary certification (231 items), WRONG_MATERIAL | not built | cache 0 (63 / 6 / 63 / 98 / 1 for executable / read-only / clarification / abstention / wrong-harmless) and fake 0 (57 / 7 / 76 / 88 / 3); live PENDING a key (`language_boundary_cache_20261003T075236Z`, `language_boundary_fake_20261003T075307Z`) |
| Execution | Scenarios passed | 46 / 46 (79 turns) | 49 / 49 (87 turns); 49 of 49 evidence chains VALID |
| Execution | Concurrency: two-process invariants | 16 of 20 SQLite cases failed on the old store | 20 passed, 10 skipped on SQLite (`tests/concurrency`); PostgreSQL PENDING a URL |
| Execution | Restart preserves state | No | Yes |
| Product | Demo path (`scripts/demo_run.py`) | exit 0 | exit 0 (cure queued → approved → lands day 37) |
| Product | Web e2e mock / live | 29 / 27 | 35 / 33 (mock / live, after the web refresh `2fc5aa9`)|

## 4. New questions

- Should a covenant carry its own measurement basis (monthly, annual, cash paid) instead of one engine convention?
- Should the agent's autonomy shrink automatically when covenant headroom is thin?
- After A08: should a funding request that has not settled by its landing day raise an alert and trigger a re-plan?
- When the cheapest plan that closes a gap needs a buyer's early payment or a bill (no operation runs either; oracle
  worlds F04, R01, R02, R10, R13, R14), should the agent propose drawing the line and asking the buyer or the owner
  (NR1)?

## 5. Decisions taken (3 Oct)

1. `max_apr_bp` is a ceiling on what the agent may borrow alone, tested on the effective annual cost; above it the
   owner approves explicitly. (Owner agreed.)
2. "Go ahead" binds to the exact operations shown with the quoted cost as a ceiling. (Owner agreed.)
3. No approval is given by code on the owner's behalf: an above-ceiling cure is queued and the owner approves it as
   a second step.
4. Forward concessions are valued on dated invoices issued in [today, today + H), gains and costs alike. Golden
   12-month figures change (13 invoices, not 12). A cash-date rule for gains was tried and withdrawn the same day.
5. Reserve, DSCR, leverage and the borrowing switch are hard for everyone at execution; clean-down is tested at
   plan level.
6. Leverage is month-end drawn debt over annual EBITDA, one function read from a projection by every caller; a
   committed line's undrawn room is not debt (technical owner, gate G2).
7. The standing plan an early payment is compared with (C0) is the cheapest plan the agent can run: a buyer's early
   payment and a bill are not legs any operation runs, so they are never in C0 and a plan that needs one is flagged
   cannot run today (technical owner, red-team round 4).
8. A fixed-sum discount is judged at its exact rate on its portion; a stated target term binds against the terms in
   force (the template plus the accepted adjustments); Counter A names its settlement day, and any portion of the
   face paid by that day earns the rate (technical owner, red-team round 5).
9. An owner-requested facility repayment is a fact like a receipt: the mandate's expiry does not block it; signature
   and admission still apply and the agent may not do it after expiry (round 5).
10. One serialisation boundary per organisation, enforced by the database: compare-and-swap on the state version and
    the log head, `BEGIN IMMEDIATE` on file SQLite, a lost unit reruns (at most 8 times), a conflict that survives is
    HTTP 409. Deploy one worker until the PostgreSQL run (PG1) is done.
11. A reading the typed rows cannot carry (a decimal comma, a per-day rate, 2/10 net 30, foreign currency, a partial
    amount, another party's invoice, a hedge, a payment after the due date, a price freeze) abstains with a reason and
    the buyer gets a question; it is never rounded to a whole-invoice discount. "Pay early, 0.3% off" with one open
    invoice binds to that invoice and queues for the owner.
12. The owner stopped the red-team rounds on 3 Oct (five rounds, 26 findings, all fixed). The engine is in stability
    mode: fix regressions, keep the evidence current, rehearse the demo, keep the documents true; no broad features
    and no further red-team round unless the owner asks.
