# Continuous optimisation: backlog, uncertainty debt, scorecard

Live document of the continuous technical owner (`docs/AGENT_MISSION.md`). Updated after every merge. Rules for each
quantity are in `docs/FINANCIAL_SEMANTICS.md`. Audit ids (A01…, F-FIN-…, S-…, F1…) refer to
`docs/research/independent-principal-audit-2026-10-03.md` and its three working papers.

Last updated: 3 Oct 2026, after the plan-binding, valuation and funding-lots merges.

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
| R01 | P1 | Router tests the rate cap on the tariff; the executor on the effective cost | 3 Oct, own finding | subagent | | Medium | S | IN PROGRESS | Router marks an above-ceiling action as needing the owner; no plan the router calls autonomous is queued by the executor |
| R02 | P1 | Multi-leg plan is not one transaction: a later leg can be refused after an earlier one ran | audit §7 | owner | A10 | Medium | M | OPEN | Whole plan admitted before the first leg; partial outcome reported truthfully |
| R03 | P1 | Same bank event with a new key settles twice | audit §7, code-inspected | subagent | | Medium | S | OPEN | External event id required on bank receipts; same id with a new key is a duplicate, different payload conflicts |
| F-FIN-10 | P2 | Level bullet DSCR presented as the bank covenant | F-FIN-10 | owner | | Medium | S | OPEN | Label "reserve-coverage reading" everywhere it is shown; covenant text states its basis |
| F6 | P2 | Borrower-file approval authorises nothing meaningful | flows F6 | subagent | A13 | Low | S | OPEN | Preparing the file is read-only for the owner |
| UI1 | P2 | UI does not separate requested, awaiting approval, awaiting settlement, settled, refused | audit §11 | frontend subagent | A08 | High | M | OPEN | e2e on the demo path |
| UI2 | P2 | Reconciliation page does not show promised payments; approvals show the current day as decision day | flows "Additional UI evidence" | frontend subagent | | Medium | S | OPEN | e2e |
| UI3 | P3 | Phone layout: security page 6 px overflow, chat panel past the viewport | audit integration record | frontend subagent | | Low | S | OPEN | `e2e/responsive.spec.ts` phone project |
| DOC1 | P1 | Documents, mocks, evidence, video script quote numbers that these fixes change | | owner | all P0 | High | M | OPEN (last) | `scripts/evaluate.py` clean; mocks re-recorded |
| R04 | P2 | `POST /offers` stores a compiled offer for a sender id taken from the body, unauthenticated | counterparty-channel report | owner | | Low (nothing executes) | S | OPEN | Unauthenticated intake is capped or marked untrusted; evaluate still needs the owner |
| R05 | P2 | Unauthenticated buyer messages and wrong keys grow the offer, verdict and security-event tables without limit | same report | owner | | Low | S | OPEN | A cap per day; test |
| R06 | P1 | Three refused agent attempts on a lender open its circuit and then block the owner's own approval | admission follow-through report | owner | | Medium | S | DONE 3 Oct (with RT1-2) | Refused approval attempts by a non-owner do not count toward the lender's circuit; owner approval still executes |
| R07 | P2 | Commitments made ACTIVE before ADR-0009 in a persistent store carry no adjustments | invoice-terms report | owner | | Low (no such store in use) | S | OPEN | One-off backfill or a startup check that refuses to hydrate such a store silently |
| RT1 | P0 | Fresh red team on `dev` after the six merges | `docs/research/redteam-2026-10-03/REPORT.md` | subagent | | High | M | DONE 3 Oct: three findings, triaged below | |
| RT1-1 | P0 | A receipt on a financed invoice repays the whole advance from the owner's cash; 1 fen took cash negative and reopened the invoice | probe `p03` | subagent | A08 | Very high | S | DONE 3 Oct | p03 sequence: cash never falls on a receipt; invoice stays FINANCED until cleared |
| RT1-2 | P0 | Agent-key refusals opened a buyer's circuit and blocked bank receipts; a refused key was burnt | probe `p01` | owner | | High | S | DONE 3 Oct | `tests/operations/test_circuit_scope.py` |
| RT1-3 | P1 | A price cut could take an invoice below its settled amount | red team suggestion, confirmed in code | owner | | Medium | S | DONE 3 Oct | `test_a_price_cut_cannot_take_an_invoice_below_what_is_already_settled` |
| R08 | P2 | `RequestOwnerApproval`: caller's free text becomes the reason the owner sees; `payload_op_id` need not be unique | red team suggestion, not reproduced | owner | | Medium | S | OPEN | The owner sees the operation's own description, never caller text; ambiguous op ids refused |
| RT2 | P0 | Second fresh red team, aimed at the seams of the 3 Oct rewrites: seven reproduced findings (probes in `docs/research/redteam-2026-10-03b/`) | red-team round b | subagent | | Very high | M | IN PROGRESS `fix/redteam-b` | Each probe prints held; `tests/operations/test_redteam_b.py` |
| RT2-1 | P0 | An invoice under an early-pay agreement could be financed; any receipt before the advance landed cancelled it (cash fell to half the reserve) | p03 | subagent | | High | S | IN PROGRESS | |
| RT2-2 | P0 | "Next invoice" terms valued on the next invoice but written onto an older, even overdue, one | p07, p06 | subagent | | High | S | IN PROGRESS | |
| RT2-3 | P1 | Advance repaid but charges short: invoice FINANCED with nothing outstanding, lot nobody can clear | p05 | subagent | N03 | Medium | S | IN PROGRESS | |
| RT2-4 | P1 | Default early-pay settlement day was absolute day 2, so early-pay offers failed from day 3 | p13 | subagent | | Medium | S | IN PROGRESS | |
| RT2-5 | P1 | Bank and owner receipts refused after the mandate expires | p08 | subagent | | Medium | S | IN PROGRESS | |
| RT2-6 | P1 | A different operation reusing an idempotency key made a bank receipt a DUPLICATE | p10 | subagent | | Medium | S | IN PROGRESS | |
| RT2-7 | P2 | Aggregate cap bypassed by splitting an agreement into one-invoice agreements over time | p06 | subagent | | Low | S | IN PROGRESS | |
| N01 | P1 | Chat does not say when funding cash lands; the repay proposal defaults to the whole drawn balance including cash not yet landed | funding-lots report | subagent | | High | S | IN PROGRESS | Replies name the landing day; repay proposes the landed balance |
| N02 | P1 | After a negotiation, the fallback and remaining-gap funding legs are rebuilt and do not stop at a refused or queued leg | plan-binding report | subagent | | Medium | M | IN PROGRESS | Stored legs sent; stop at the first leg not executed |
| N03 | P2 | A financed invoice whose face is fully settled while its advance is open drops out of the projection; its lot is repaid at the horizon end | funding-lots report | subagent | | Low | S | IN PROGRESS | Projection repays the remaining lot today |
| N04 | P2 | A receipt that covers the advance but not its charges capitalises the unpaid charges and charges them again | funding-lots report (agent's own choice) | owner | | Low | S | OPEN (accepted for now; documented) | |
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
| U-011 | The mock e2e and recorded mocks describe the pre-audit behaviour until re-recorded | UI tests can pass against stale shapes | Re-record at DOC1 | Open |
| U-012 | Chinese negation and consent coverage is by rule lists | A phrasing outside the list must fail closed, not open | Closed grammar (A01) makes unknown phrasing non-executable; property test | In progress |

## 3. Scorecard

Reproduce with `scripts/evaluate.py`, `scripts/run_scenarios.py --inproc`, the audit probes and the backend suite.
Numbers are measurements on the commit named, never targets.

| Area | Measure | `beb8c66` (audit baseline) | Latest `dev` |
| --- | --- | --- | --- |
| Financial | Backend tests passed | 4,042 (26 skipped) | 4,614 (26 skipped) after the ADR-0010 merge |
| Financial | Planner/executor mismatches reproduced by the audit probes | 6 of 6 | 0 of 6 defects; the discretionary line repayment is a labelled assumption (ADR-0010) |
| Financial | Formula discrepancies open | 9 (F-FIN-01, 02, 03, 04, 06, 07, 09, 10, 11) | 1 (F-FIN-10: label) |
| Financial | Accepted-terms lifecycle failures (A06, A07) | 2 | 0 |
| Security | Catalogue attacks / with harm | 182 / 0 | 241 (122 API + 119 chat) / 0, by the suite; report not yet regenerated |
| Security | Audit attacks with harm (A01, A02, A03, A04, A10) | 5 of 5 | 0 of 5 |
| Language | Wrong and financially material interpretations known | 13 texts (S-01 ×8, S-02 ×5) | 0 known |
| Execution | Scenarios passed | 46 / 46 (79 turns) | 46 / 46 (85 turns) |
| Execution | Restart preserves state | No | Yes |
| Product | Demo path (`scripts/demo_run.py`) | exit 0 | exit 0 |

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
