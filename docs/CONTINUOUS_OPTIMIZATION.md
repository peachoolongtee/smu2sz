# Continuous optimisation: backlog, uncertainty debt, scorecard

Live document of the continuous technical owner (`docs/AGENT_MISSION.md`). Updated after every merge. Rules for each
quantity are in `docs/FINANCIAL_SEMANTICS.md`. Audit ids (A01…, F-FIN-…, S-…, F1…) refer to
`docs/research/independent-principal-audit-2026-10-03.md` and its three working papers.

Last updated: 3 Oct 2026 (late): debt service as cash, review gaps, simplifications, counter feasibility, the web catch-up and leg ordering merged; documents and evidence regenerated on the cash-corrected books (`docs/cash-figures`); backend 4,817 passed.

## 0. Engine Stability Gate (set by the owner, 3 Oct, late)

The financial engine is declared stable, and broad new financial features may be considered, only when all of these
hold. Until then the queue below is correctness and certification only; capex stays as a supporting demo scene; the
explicit Tier-2 approval for an above-ceiling rate stays.

| Condition | Status |
| --- | --- |
| G1. A fourth unanchored red team on the checkpoint finds no P0 or high-confidence P1 | IN PROGRESS `redteam/fresh-4` |
| G2. One leverage definition (actual drawn debt) used by the projection, the verifier's pro forma, capex, the borrower file and chat | IN PROGRESS (`fix/one-leverage`) |
| G3. Live-model fail-closed certification: with the real compiler backend (and its fallback), a fresh adversarial and malformed-output set produces zero wrong-and-material executable interpretations; abstentions and clarifications counted separately | QUEUED after G1 |
| G4. PostgreSQL concurrency invariants: forced interleavings (concurrent draws against the last room, receipt vs finance, accept vs revoke, duplicate external event, rollback on log failure, restart) on a real database; no double booking; one serialization boundary per organisation | QUEUED after G1 |
| G5. Planner/executor agreement test green at 500 examples on three seeds, counter property green | DONE 3 Oct (re-run at the gate) |

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
| DOC1 | P1 | Documents, mocks, evidence, video script quote numbers that these fixes change | | owner | all P0 | High | M | DONE 3 Oct: documents, evidence and reports regenerated on `docs/audit-closeout` and again on `docs/cash-figures` after the debt-service change; mocks re-recorded in `ed4a5c4` (re-run after the next cash-derived change) | `scripts/evaluate.py` targets all pass (15 item-level misses, 4 of them new, see the scorecard note); all 49 evidence chains VALID; mocks re-recorded |
| R04 | P2 | `POST /offers` stores a compiled offer for a sender id taken from the body, unauthenticated | counterparty-channel report | owner | | Low (nothing executes) | S | OPEN | Unauthenticated intake is capped or marked untrusted; evaluate still needs the owner |
| R05 | P2 | Unauthenticated buyer messages and wrong keys grow the offer, verdict and security-event tables without limit | same report | owner | | Low | S | OPEN | A cap per day; test |
| R06 | P1 | Three refused agent attempts on a lender open its circuit and then block the owner's own approval | admission follow-through report | owner | | Medium | S | DONE 3 Oct (with RT1-2) | Refused approval attempts by a non-owner do not count toward the lender's circuit; owner approval still executes |
| R07 | P2 | Commitments made ACTIVE before ADR-0009 in a persistent store carry no adjustments | invoice-terms report | owner | | Low (no such store in use) | S | OPEN | One-off backfill or a startup check that refuses to hydrate such a store silently |
| RT1 | P0 | Fresh red team on `dev` after the six merges | `docs/research/redteam-2026-10-03/REPORT.md` | subagent | | High | M | DONE 3 Oct: three findings, triaged below | |
| RT1-1 | P0 | A receipt on a financed invoice repays the whole advance from the owner's cash; 1 fen took cash negative and reopened the invoice | probe `p03` | subagent | A08 | Very high | S | DONE 3 Oct | p03 sequence: cash never falls on a receipt; invoice stays FINANCED until cleared |
| RT1-2 | P0 | Agent-key refusals opened a buyer's circuit and blocked bank receipts; a refused key was burnt | probe `p01` | owner | | High | S | DONE 3 Oct | `tests/operations/test_circuit_scope.py` |
| RT1-3 | P1 | A price cut could take an invoice below its settled amount | red team suggestion, confirmed in code | owner | | Medium | S | DONE 3 Oct | `test_a_price_cut_cannot_take_an_invoice_below_what_is_already_settled` |
| R08 | P1 | `RequestOwnerApproval`: caller's free text became the reason the owner saw (third red team reproduced it: an agent-reported receipt described as "no payment") | `docs/research/redteam-2026-10-03c/p06` | owner | | High | S | DONE 3 Oct | The owner sees the operation's own description, never caller text; ambiguous op ids refused |
| RT2 | P0 | Second fresh red team, aimed at the seams of the 3 Oct rewrites: seven reproduced findings (probes in `docs/research/redteam-2026-10-03b/`) | red-team round b | subagent | | Very high | M | DONE 3 Oct | Each probe prints held; `tests/operations/test_redteam_b.py` |
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
| RT3 | P0 | Third fresh red team: three findings | `docs/research/redteam-2026-10-03c/` | subagent | | High | M | DONE 3 Oct: all three fixed (`tests/operations/test_redteam_c.py`) | |
| RT3-2 | P0 | Admission (my own fix 11acc56) omitted a line draw's cash, so a runnable plan was refused for everyone | p03, p05 | owner | | High | S | DONE 3 Oct | |
| RT3-3 | P1 | A recreated chat session reused old idempotency keys: a later command was a DUPLICATE or a REPLAY | p07 | owner | | Medium | S | DONE 3 Oct | |
| C01 | P1 | Owner-session chat ran an above-ceiling leg directly while the agent channel queued it | plan-flags report | owner | | Medium | S | DONE 3 Oct: chat funding legs are the agent's act in every session | |
| W01 | P2 | Approvals queue has no decision day; plan actions carry no landing day; executed ledger rows lack the approval id they ran under; no demo scenario for the zero-floor cure | web report | subagent | | Low | S | IN PROGRESS `fix/api-gaps` | |
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
| D1 | P1 | Covenant ratios computed in four places with two leverage definitions (line at limit vs drawn) | review D1 | subagent | | High | M | IN PROGRESS `fix/one-leverage` (gate G2) | One function; identical figures from every caller on identical books |
| EV1 | P2 | Evidence chain heads are not reproducible run to run (session nonce, commitment nonces) | close-out report | owner | | Low | S | OPEN (claim narrowed to "integrity-checkable") | |
| MW1 | P1 | Several API workers: process-local lock, no state-version compare-and-swap | audit §7, unverified | owner | | Medium | M | OPEN | SQLite two-connection interleaving test; PostgreSQL test when a database is available |

Not doing before the deadline (audit §14 agrees): supplier payments, lender connectors, tax, FX, calendars, lease
residuals, PV ranking of financing, a general solver.

## 2. Uncertainty debt

Things the system assumes or claims that have not been verified. Each is either paid down (verified), made explicit
to the user, or the claim is removed.

| Id | Assumption or untested claim | Why it matters | How to pay it down | Status |
| --- | --- | --- | --- | --- |
| U-001 | Live Claude has not been tested against adversarial multi-document offers on this revision | The deterministic boundary is being repaired; the live extraction path can still mis-type terms | Fresh held-out adversarial set run live, scored as executable / clarification / abstention / wrong-harmless / wrong-material | Open |
| U-002 | PostgreSQL crash recovery and concurrent workers have not been fault-injected | Process lock is local; a race could double-book | Forced interleavings on a real database; until then deploy one worker and say so | Open |
| U-003 | Facility lead times, tariffs, billing periods and limits are synthetic fixture values with no external evidence | Every cost and timing conclusion rests on them | Label as owner-entered; state in the UI and documents; a facility letter parser is out of scope | Open (label) |
| U-004 | The DSCR convention (monthly, level bullet service) is a modelling assumption, not lender contract language | A bank may measure annually or on cash paid | Name it a reserve-coverage reading; let a covenant carry its own basis later | Open (label) |
| U-005 | Recurring invoices are treated as confirmed future sales and collected exactly on the due day | Collateral and cash are overstated if the buyer pays late or orders less; one buyer is 100% of receivables | State it; keep the missed-payment scenario; a late-payment stress is IF TIME | Open |
| U-006 | The outflow schedule is whatever was entered; EBITDA is not a cash forecast | A recommendation horizon needs complete outflows | Say "screens the entered obligations only" where a plan is shown | Open (label) |
| U-007 | The bank feed, the buyer and the lenders are simulated; a clock stands in for time | No real settlement, failure or delay has been observed | Say "simulated" on every demo surface; pending-settlement state after A08 | Open |
| U-008 | The hash chain's head is not anchored outside the store | Truncation of the tail is undetectable | Claim "internally checkable" only; external checkpoint after the hackathon | Open (claim narrowed) |
| U-009 | The effective-rate ceiling uses simple annualisation over the days held | A lender or regulator may define APR differently | Named "effective annual cost" with its formula on screen | Open (label) |
| U-010 | The search for the cheapest plan is bounded (three actions, ¥10,000 grid) | "Cheapest" is cheapest within that search | Say so where the plan is shown; differential test against a finer grid exists | Open (label) |
| U-011 | The mock e2e and recorded mocks describe the pre-audit behaviour until re-recorded | UI tests can pass against stale shapes | Re-record at DOC1 | Paid down 3 Oct: mocks re-recorded from the live API (`ed4a5c4`), mock e2e 35 and live e2e 30 pass; re-record after any change to a cash-derived figure |
| U-012 | Chinese negation and consent coverage is by rule lists | A phrasing outside the list must fail closed, not open | Closed grammar (A01) makes unknown phrasing non-executable; property test | In progress |

## 3. Scorecard

Reproduce with `scripts/evaluate.py`, `scripts/run_scenarios.py --inproc`, the audit probes and the backend suite.
Numbers are measurements on the commit named, never targets.

| Area | Measure | `beb8c66` (audit baseline) | Latest `dev` |
| --- | --- | --- | --- |
| Financial | Backend tests passed | 4,042 (26 skipped) | 4,817 (22 skipped) |
| Financial | Planner/executor mismatches reproduced by the audit probes | 6 of 6 | 0 of 6 defects; the discretionary line repayment is a labelled assumption (ADR-0010) |
| Financial | Formula discrepancies open | 9 (F-FIN-01, 02, 03, 04, 06, 07, 09, 10, 11) | 1 (F-FIN-10: label) |
| Financial | Accepted-terms lifecycle failures (A06, A07) | 2 | 0 |
| Security | Catalogue attacks / with harm | 182 / 0 | 255 (122 API + 133 chat) / 0, report regenerated 3 Oct |
| Security | Audit attacks with harm (A01, A02, A03, A04, A10) | 5 of 5 | 0 of 5; three red-team rounds: 13 findings, 13 fixed |
| Language | Wrong and financially material interpretations known | 13 texts (S-01 ×8, S-02 ×5) | 0 known; held-out offer labels agree 45 of 50 (the four 60-day-terms items H09a, H09b, H12a, H39 now return REJECT on the cash-corrected books and their labels were not changed) |
| Execution | Scenarios passed | 46 / 46 (79 turns) | 49 / 49 (87 turns); 49 of 49 evidence chains VALID |
| Execution | Restart preserves state | No | Yes |
| Product | Demo path (`scripts/demo_run.py`) | exit 0 | exit 0 (cure queued → approved → lands day 37) |
| Product | Web e2e mock / live | 29 / 27 | 35 / 30 |

## 4. New questions

- Should a covenant carry its own measurement basis (monthly, annual, cash paid) instead of one engine convention?
- Should the agent's autonomy shrink automatically when covenant headroom is thin?
- After A08: should a funding request that has not settled by its landing day raise an alert and trigger a re-plan?

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
