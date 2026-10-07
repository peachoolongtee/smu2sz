# 01. Repository primitives for the strategy brief

Read-only reconnaissance of `dev` at `d1eadb0` (8 October 2026) for wayfinder map #39, ticket #40. What FLOW already
holds that the Safe Deal Envelope, the multi-deal portfolio and collections prioritisation would reuse; what each would
have to add; what a spike must respect. Every figure below was either read from the code or measured on the golden
fixture with `uv run` on the research worktree (section 2.4, 3.3, 7). No code was changed.

File paths are relative to `services/api/app/` unless stated.

## 1. The financial state model and current books

`FinancialState` (`domain/models.py`) is the actual position at the start of `as_of_day`; only the executor and the
clock write it. Every model is a frozen, strict pydantic `Contract`; money is integer fen, rates integer bp, days are
absolute integers. `current_books(state, commitments)` (`books/__init__.py`) adds the cash-relevant obligations of
ACCEPTED/ACTIVE commitments that the state does not already carry (today only live `IMMEDIATE_DISCOUNT` legs and dated
rebates), reports the ones that no longer bind as `lapsed`, and every module projects from `books.state` plus
`books.with_(extra)`; none from the raw state (ADR-0006).

| Holder | Fields that matter for the three ideas |
| --- | --- |
| `FinancialState` | `cash_fen`, `as_of_day`, `flows[]`, `receivables[]`, `recurring_invoices[]`, `facilities[]`, `debts[]`, `forward_concessions[]` (booked cap usage, one per ACTIVE commitment), `invoice_adjustments[]` (ADR-0009 scopes), `lots[]` (ADR-0010), `expected_orders[]` (rebate bases; `firm`), `counterparties[]` (`role`, `known`), `monthly_ebitda_fen`, `state_version` |
| `Receivable` | `counterparty_id`, `face_fen` and `terms_days` (contractual, adjustments already written on), `issue_day`, `due_day` property, `status` OPEN/FINANCED/SETTLED/FAILED, `confirmed` (确权), `settled_fen` (outstanding = face − settled), `advance_fen`/`advance_facility_id`, `base_face_fen`/`base_terms_days`/`applied[]` (provenance), `early_paid_fen{}` per early-pay obligation |
| `RecurringInvoice` | one per buyer in practice (`_recurring` refuses two): `face_fen`, `every_days`, `next_issue_day`, `terms_days`; generated ids `RI:<buyer>:<issue day>` |
| `Facility` | `kind` (8 kinds), `status` COMMITTED/PENDING/NOT_APPLIED/REFERENCE_ONLY, `owner_approved`, `limit_fen`, `drawn_fen`, `advance_rate_bp`, `rate_bp`, `fee_bp_per_advance`/`fee_period_days`, `upfront_fee_bp`, `lead_time_days`, `term_months`, `repayment` BULLET/AMORTISING/ON_RECEIPT, `counts_in_leverage`, `counts_in_debt_service`, `covenants[]`, `collateral`, `personal_guarantee` |
| `FundingLot` | `facility_id`, `principal_fen`, `remaining_fen`, `request_day`, `arrival_day`, `receivable_id`, `maturity_day`, `settled`, `assumed_date`; Σ remaining over a facility's lots = its `drawn_fen` |
| `Commitment` | `offer_id`, `verdict_id`, `terms_hash`, `obligations[]`, `status` PROPOSED→ACCEPTED→ACTIVE→FULFILLED or EXPIRED/REVOKED (`commitments/lifecycle.py`), `nonce`, `expires_day`, `forward_value_fen`, `settled_obligations[]`, `lapsed_obligations[]` |
| `Obligation` | `type` (IMMEDIATE_DISCOUNT, TERMS_EXTENSION, CONTINGENT_REBATE, VOLUME_COMMITMENT, OPERATIONAL_CONCESSION, PRICE_ADJUSTMENT, CLAIMED_PRIOR_CONCESSION), `rate_bp`, `amount_fen`, `days_delta`, `target_terms_days`, `effective_day`, `base` (`kind` INVOICE/FUTURE_INVOICES/PERIOD_PURCHASES/PER_EVENT, `amount_fen`, `receivable_id`), `contingency` FIRM/CONTINGENT/CLAIMED_UNEVIDENCED, `duration` ONE_OFF/RECURRING_PERPETUAL/RECURRING_BOUNDED(`invoices`, `end_day`), `spans[]` (one required) |
| `Mandate` | `min_cash_fen`, `max_aggregate_forward_concession_fen`, `forward_concession_horizon_days`, `per_buyer_caps_fen{}`, `max_immediate_discount_bp`, `min_dscr_bp`, `max_leverage_bp`, `max_apr_bp`, `require_clean_down`, `allow_new_borrowing`, `tier2_single_commitment_fen`, `horizon_days`, `issued_day`/`expires_day`/`revoked`, signature |

Golden books (`fixtures/scenarios/golden_sme.json`): cash ¥400,000, floor ¥300,000; payroll −¥340,000 day 12,
supplier −¥120,000 day 20, bill −¥100,000 day 47; RCV-A ¥420,000 due day 32; a ¥420,000 monthly invoice from day 2 on
45-day terms; existing loan ¥45,000 a month from day 30; three committed sources (line ¥150,000 at 6.4%, invoice
financing ¥350,000 at 7.8% + 0.25%/30 days, lead 3; buyer early pay); mandate budget ¥5,000 forward concessions,
APR ceiling 15%, horizon 120 days, concession window 365 days. One buyer with a recurring invoice (BUYER-1), one
without (BUYER-2).

**Accepting, in state terms** (`operations/executor.py::_commit`): the commitment goes ACTIVE; `invoices.accept`
turns each TERMS_EXTENSION/PRICE_ADJUSTMENT into an `InvoiceAdjustment` with a scope fixed now and writes it on
issued invoices (face raised, terms moved); one `ForwardConcession` of `forward_value_fen` is appended; early-pay
legs stay as live obligations that `current_books` carries until paid or lapsed. Before that, `_check_binding`
re-checks open faces, exclusivity (one live commitment per named receivable), both caps, and re-verifies on
current books when `state_version` moved (`STALE_VERDICT`).

## 2. The verifier

`verifier/evaluate.py::evaluate(offer, state, mandate, *, trusted_owner_key_hex, day, owner_declared, commitments,
owner_constraints, plans)` returns a `VerdictBundle`:

| Field | Content |
| --- | --- |
| `verdict: Verdict` | `outcome` ACCEPT/COUNTER/REJECT/NO_DEAL/NEEDS_OWNER_APPROVAL/NO_VERDICT, `violations[]` (code, day/month, observed, limit, `curable`, `cure_cost_fen`, `cure_note`, formula, inputs, spans), `bound_obligations[]`, `concession_values[]`, `forward_concession_total_fen`, `counters[]`, `plan` (the cure when a breach is induced, else the committed plan), `required_tier`, `mandate_version`, `state_version`, `calc_version`, `summary` |
| `trajectory` | conservative, offer applied, no new funding |
| `plan_committed`, `plan_expected`, `cure_plan` | router results; expected is display-only (INVARIANT 11) |
| `passed_checks[]` | MIN_CASH, MAX_APR, DSCR_MIN, LEVERAGE_MAX, CLEAN_DOWN, EARLY_PAY_VS_PLAN with observed/limit/formula |
| `comparison[]` | the spec §7.4 rows at the offered discount |
| `notes[]`, `security_events[]`, `bound_obligations[]` | binding decisions and the screen's events |

Steps, in order: (1) status gate (ABSTAINED/CONFLICTING_SOURCES → NO_VERDICT); (2) `screen()` (unknown
counterparty, funding claims, unevidenced claims, data requests); (3) `check_validity` of the signed mandate; (4)
`bind()` (`verifier/bind.py`: resolves the receivable, the terms delta against `terms_in_force`, rebate bases from
`expected_orders`, declared per-event costs; an unresolved material field is UNRESOLVED_SCOPE); then `project(state,
live+bound, [], CONSERVATIVE)`, the cached no-offer `baseline()` (`verifier/reserve.py`), `plan(state, live+bound)`
COMMITTED (and EXPECTED), `marginal_cost()` (FAC-IF, ≈10.8417%), `value_concessions(bound, state, rate, label,
H)`; (5) predicates; (6) outcome, counters, tier, summary.

**Predicate codes** (`ViolationCode`): hard — RESERVE_BREACH (only when induced: offer cash below the floor *and*
below the baseline; `curable` when `cure_plan` on permanent-capable sources is admissible), AGG_CONCESSION_EXCEEDED,
PER_BUYER_CAP_EXCEEDED, DSCR_BREACH, LEVERAGE_BREACH, CLEAN_DOWN_BREACH, the security and mandate codes; price codes
(lead to COUNTER, not REJECT) — IMMEDIATE_DISCOUNT_EXCEEDED, MAX_APR_EXCEEDED, DISCOUNT_ABOVE_BREAK_EVEN,
EARLY_PAY_NOT_NEEDED, EARLY_PAY_DEARER_THAN_PLAN (ADR-0007 tests 1–3: C1 with the offer vs C0 without, both as
interest + fees + discounts posted over the horizon under the router's plan). Covenants are read on the funded
trajectory with `covenants.evaluate` and `ratios_for`; a lengthening extension also gets a pro-forma DSCR
(`extension_pro_forma`: extra debt = face × Δ / interval, service = that × r / 12).

**Concession valuation** (`financial/concessions.py`): window W = [today, today + H); an obligation is worth the sum
over the dated invoices of its fixed scope issued in W. Extension: Σ face × Δ × r / 365 (13 invoices in the golden
year: ¥24,326.92 for +15 days, ¥1,871.30 per invoice). Price adjustment: −Σ post(p × face) (a gain). Rebate: rate ×
base at maximum when CONTINGENT. Only FIRM gains net against costs (INVARIANT 5), and a package never creates headroom
(`_forward_total` floors net new value at 0). The **forward budget** is `max_aggregate_forward_concession_fen` minus
`Σ state.forward_concessions`, with `per_buyer_caps_fen` beside it.

**Counters** (`verifier/counters.py`): Option A (early pay) takes the largest whole-5 bp rate below the break-even for
the actual tenor, a face of (near-term need − committed line) / (1 − d) rounded up to ¥100, prices it from the
projection with the router's plan for the rest, and offers it only if cheaper than the standing plan. Option B (price
adjustment) takes the offered terms, computes the per-invoice extension cost with `value_concessions`, picks the
smallest 5 bp price step covering it (`smallest_step_covering`), checks the budget, plans liquidity, then steps terms
down 5 days at a time until a counter passes. Bounded-extension and rebate counters fit the remaining budget. **Every
counter is re-checked** as an offer on the same books (`counter_recheck` → `_evaluate(..., with_counters=False)`)
and must give ACCEPT or NEEDS_OWNER_APPROVAL with no covenant or APR code and every RESERVE_BREACH curable in time;
a failing counter is dropped with one sentence why. That re-check is why EX01's Option B is 55 days at 0.30%, not 60.

**Runtime (measured, golden EX01, Apple Silicon, caches cleared with `clear_caches()`):**

| Call | Time | Notes |
| --- | --- | --- |
| `evaluate(EX01)`, `plans="all"`, cold | 304 ms | 4 searches through the evaluation's `_Router` memo plus the two counters' re-checks (the 6 Oct profile counts 12 distinct searches); benchmark target < 350 ms |
| same, warm (baseline and comparison LRU caches hit) | 223 ms | 5 runs, median |
| `evaluate(EX01)`, `plans="committed"`, cold | 269 ms | skips the EXPECTED search |
| what-if status quo (45 days, no discount), cold | 36 ms | no breach, no counters |
| what-if +Δ terms only, cold | 210 → 612 ms for 50 → 90 days | the cure search grows with the shortfall |
| what-if discount only (50–200 bp), cold | 76–129 ms | |

## 3. The router

`funding/router.py::plan(state, obligations, mandate, basis)` builds a `Search` (`funding/search.py`), runs it and
returns a `FundingPlan`; `compare()` returns the spec §7.4 `ComparisonRow`s from the same search (shared inside
`shared_runs()`).

- **Search.** Baseline projection → `breach_days`, `need_fen` (deepest shortfall), `rcvs` (every receipt the engine
  dates, including unissued recurring invoices). `_slots()` enumerates one way to use each usable facility: a bullet
  line per candidate repayment day (recovery days and later inflow days, EV-06), an invoice advance per receivable
  that lands before its due day (capped by the advance rate and `receipt_covered_advance`), a buyer early payment per
  receivable, a bill discount, a term loan or lease draw. Grid: `GRID_STEP_FEN` ¥10,000, `MIN_ACTION_FEN` ¥1,000.
  `_search()` probes each slot alone sized to the need, then pairs (one slot on the grid, the other filled to the
  residual by `fill()`), then triples (first at cap, second on the grid, third filled). Probes run on `CashProjector`
  (cash only); a probe that could become the best is re-run through `project` + `covenants.evaluate`. Amounts are
  searched, not dates: every action is requested today (ADR-0003). The EXPECTED basis stops after 2,000 probes.
- **Admission and ranking.** `Eval.admissible` = engine accepted it, floor held every day, no covenant violation,
  borrowing allowed. Rank = (cannot run today, needs owner approval, cost, number of legs, peak debt). "Needs
  approval" is any leg whose `action_rate` (effective annual cost on the days held) is above `max_apr_bp`; "cannot
  run today" is an advance on an unissued invoice, an early payment or a bill. A COMMITTED plan must also have a leg
  order every prefix of which admission accepts (`funding/legs.py`, `executable_order`), the same rule
  `funding/admission.py::admit` applies inside the executor.
- **Costing.** Cost = interest + fees + discounts the trajectory posts minus what the obligations alone post;
  `cost_lines()` attributes each posting to its action with the engine's formula. `FundingPlan` carries `need_fen`,
  `actions[]` (`FundingAction`: kind, facility, day, amount, receivable, repay_day, rate_bp, `lands_day`,
  `available_from_day`), `costs[]` (`CostLine` with `needs_owner_approval`, `executable_now`), `total_cost_fen`,
  `admissible`, `violations`, `marginal_cost_annual`, `rejected[]`, `label`, the two flags and reasons.
- **Comparison rows** (`alternatives()`): `full_discount`, `line_partial_early_pay`, `router_optimum`,
  `line_guaranteed_loan`, `line_only`, each SELECTED/ADMISSIBLE/NOT_ADMISSIBLE with reasons, `breach_day`,
  `shortfall_fen`, `worst_day`, flags.
- **Recommendation rule** (`funding/recommend.py`): the owner is shown the router's runnable plan (admissible,
  executable now, every leg a DRAW or an advance on a named invoice) unless it needs more than one approval and the
  alert's greedy cure needs at most one; then the cure is shown and the cheaper plan named. Behind
  `features.debt_desk`.

**Runtime (measured, golden books, no obligations):** `plan()` COMMITTED 33 ms (need ¥405,000; line ¥150,000 +
advance ¥255,000 on RCV-A = ¥3,113.93); `compare()` 33 ms (shares the search); `plan(..., "EXPECTED")` 98 ms.
Targets in `tests/funding/test_benchmark.py`: < 100 ms each, cold.

## 4. Receivables and reconciliation

- **Receipt timing in the trajectory** (`financial/trajectory.py::_build`): every OPEN/FINANCED receivable with
  outstanding face and `due_day >= today` posts one RECEIPT of its residual on `issue_day + terms_days` (the
  contractual terms, adjustments written on); recurring invoices are generated up to the horizon with the scoped
  adjustments applied as the clock will. Unconfirmed receivables are skipped in CONSERVATIVE. A receivable overdue
  before today posts nothing: the conservative projection never assumes a late buyer pays. An `IMMEDIATE_DISCOUNT`
  obligation moves the covered portion to its `effective_day` (today + the buyer's early-pay lead, 2 days) as an
  EARLY_RECEIPT net of the posted discount. There is no payment-probability or expected-delay input: a receipt is
  either dated on its due day or absent.
- **Receipts** come only from `ReceivePayment` (bank feed or owner; an agent's report is Tier 2). `_receive` credits
  cash, settles face (an early-pay match settles the portion P with R = P − post(d × P)), pays the lender first from
  a FINANCED invoice's receipt (ADR-0010), marks SETTLED when nothing is outstanding.
- **Promised payments and lots.** `alerts/reconcile.py::reconcile(store, day)` replays receipts against what was
  outstanding and returns `ReceiptMatch` rows (MATCHED, SHORT_PAYMENT, DISCOUNT_IGNORED, UNEXPECTED_AMOUNT,
  UNMATCHED), `outstanding[]` (`OutstandingReceivable` with `past_due`), `promised[]` (`PromisedReceipt`: AWAITED,
  RECEIVED, LAPSED, SETTLED_OTHERWISE) and `lapsed_promises`. Funding lots land on `arrival_day` (the clock posts
  the cash), appear as FUNDING_IN_TRANSIT alerts until then, and are repaid by `contractual_payments` or on the
  financed invoice's receipt.
- **Late invoices.** `alerts/engine.py::_past_due` emits RECEIVABLE_PAST_DUE per receivable whose due day on current
  books is before today (CRITICAL when FINANCED), with a RECEIVE_PAYMENT suggestion ("chase the buyer"), and one per
  lapsed early-payment promise. `past_due_invoices()` is what the verifier asks before letting the agent accept
  anything from that buyer alone.
- **Alerts and cures.** `alerts(state, mandate, store, day, obligations=())` projects current books once and
  returns RESERVE_BREACH_AHEAD (per episode, with `committed_cure`: a greedy feasibility proof over draws and
  advances, sized to the peak shortfall, priced per leg by the engine; a zero-floor fallback when no cure restores
  the reserve), RESERVE_HEADROOM_LOW, COVENANT_HEADROOM_LOW, CLEAN_DOWN_AT_RISK, COMMITMENT_EXPIRING,
  MANDATE_EXPIRING, RECEIVABLE_PAST_DUE, CONCESSIONS_NEAR_CAP, FACILITY_REPAYABLE, FUNDING_IN_TRANSIT. Measured: 4 ms
  on the golden books. `POST /alerts/{id}/act` turns a suggestion into typed operations bound to the state version.

## 5. Covenants, the mandate's limits and tiers, the NL intents

Covenants (`covenants/`): per-facility `Covenant` rows of kind DSCR_MIN, LEVERAGE_MAX, CLEAN_DOWN, tested on every
`MonthPoint` of a trajectory with one definition (`ratios_for`: DSCR = EBITDA / debt service with bullet term loans
on a level basis, ADR-0008; leverage = month-end drawn debt / 12 × EBITDA); clean-down rebuilds the line balance from
DRAW/REPAYMENT events and needs a zero run ≥ `clean_down_days`. The mandate's own `min_dscr_bp` and `max_leverage_bp`
are tested beside them. Admission makes reserve, DSCR, leverage and the borrowing switch hard for everyone at
execution; `max_apr_bp` is an autonomy ceiling (Tier 2 above it); clean-down is plan-level.

Tiers (`mandate/tiers.py::tier_for`) are computed from the typed operation: Tier 3 for guarantee, collateral,
equity, mandate change, non-owner AddFacility; Tier 2 for ApplyForFacility, a receipt reported by the agent or a
buyer, a draw on an uncommitted facility, any acceptance that lengthens terms or binds anything but an early-pay
discount on a named invoice, or a value above `tier2_single_commitment_fen`; Tier 1 otherwise. ADR-0005 adds the
coverage proof: `autonomy_eligible` must be true and the discount must name the whole face.

NL (`nl/models.py::Intent`, closed set): EVALUATE_OFFER, NEGOTIATE, ACCELERATE_RECEIPT, FUND_GAP, REPAY_FACILITY,
SHOW_STATUS, SHOW_ALERTS, COMPARE_FINANCING, RECONCILE, SHOW_RATIOS, CAPEX, BORROWER_FILE, EXPLAIN, WHAT_IF,
RECORD_FACT (read-only by design), APPROVE, REJECT, COUNTERPARTY_MESSAGE, OUT_OF_SCOPE, AMBIGUOUS. Slots are typed
(ids, fen, bp, days, `zero_forward`, `use_financing`). `OwnerConstraints` (max early-pay bp, zero forward
concessions, max terms days) is the only owner-goal object the verifier accepts today. There is no "what can I offer
this buyer", "which deals together" or "whom should I chase" intent.

## 6. The presentation layer and where a new answer could live

`api/` is a presentation read over engine results; INVARIANT 13 (the UI never computes money) means every display
string is formatted on the server (`api/display.py::displayed`, `api/presentation.py`, `api/views.py`).

| Route | What it returns | Page on `dev` |
| --- | --- | --- |
| `GET /home` (`api/home.py`) | status word, headline/note/worst, `cash` (today, floor, headroom, lowest, first breach as distances), `next_action` (the recommended plan or cure with legs, costs, `after`, `if_nothing`, `why`, `state_version`), `approvals[]`, `changes[]`, `receivables` (open count/total, overdue total, `past_due[]` with `days_late`, `next_receipt`, `promised`, `lapsed_promises`), `in_transit`, `series[]` | Home (`app/page.tsx`: StatusBlock, NextActionBlock, DecisionsBlock, ReceivablesBlock, ChangesBlock, DetailsBlock) and Cash & funding (`app/cash/page.tsx`: risk card, NextActionBlock or CurrentFunding, FundingOptions from `/router/plan`, CashForecast) |
| `POST /offers/{id}/evaluate` (`api/decide.py`) | the verdict with `business_action`, guarded counters, `concession_values[].interpretation`, `*_when` sentences, `passed_checks`, `autonomy`, `annualised`, `trajectory`, `plan_committed`, `cure_plan`, `cured_trajectory`, `comparison`, `forward_concession` {total, cap, over_cap} | Deals (`app/deals/page.tsx`: InboxList, BuyerAsks, DealDecision, RecommendedResponse, ActiveCommitments, WhyRecommended, original message, calculations) |
| `POST /router/plan` | committed and expected plans, the menu (`MenuRow`), marginal rate, break-even, extension bases, comparison | Cash & funding; Demo "Funding" |
| `GET /reconciliation` | `ReconciliationReport` | Receivables (`app/receivables/page.tsx`: summary from `/home`, open invoices late-first, promised payments, receipts) |
| `GET /alerts`, `POST /alerts/{id}/act` | alerts and the bound act | Home/Cash (fix-alert), Demo Alerts |
| `POST /whatif`, `GET /whatif/presets` (`whatif/`) | the real verifier on a synthetic offer built from sliders (terms 30–90 by 5, discount/rebate 0–200 bp by 5, price 0–100 bp by 5, settle face by ¥100); cached by (state, mandate, day, params) | Demo What-if |
| `POST /nl`, `/nl/opener` | chat turns with typed plans | Chat |

Natural homes for the three ideas without a new top-level section: a per-buyer envelope on Deals (beside BuyerAsks,
before a message arrives) and as a chat intent; the portfolio on Deals (ActiveCommitments and the inbox already list
the open deals) or on Home's DecisionsBlock; collections on Receivables (the late-first table) and Home's
ReceivablesBlock. The what-if sandbox is the closest existing "owner-built offer" path and is already a verifier call
with no text.

## 7. The call sequence that would compute each idea today

### 7.1 Safe Deal Envelope

The what-if builder is the synthetic-offer constructor: `whatif.offer.build(WhatIfParams(terms_days, discount_bp,
rebate_bp, price_adjustment_bp, settle_face_fen), context(state))` gives a `CompiledOffer` with compiler
`whatif-sandbox` (exempt from the autonomy proof), then `evaluate(offer, state, mandate, trusted_owner_key_hex,
commitments=..., plans="committed")`. It is bound to one buyer: the one with a recurring invoice and an open
receivable (BUYER-1); a buyer without a recurring invoice (BUYER-2) has no terms lever to value.

Measured sweep, golden books, one lever at a time (cold each):

| Terms (Δ vs 45) | Outcome | Codes | Forward value | Reserve | Time |
| --- | --- | --- | --- | --- | --- |
| 45 | ACCEPT | — | 0 | — | 36 ms |
| 50 | REJECT | AGG, RESERVE_BREACH | ¥8,108.97 | day 47, curable ¥1,570.36 | 210 ms |
| 55 | REJECT | AGG, RESERVE_BREACH | ¥16,217.95 | day 47, curable ¥1,570.36 | 231 ms |
| 60–90 | REJECT | AGG, RESERVE_BREACH | ¥24,326.92 → ¥72,980.75 | day 47, not curable | 267–612 ms |

| 60 days + price | Codes | Forward value |
| --- | --- | --- |
| +0 bp | AGG, RESERVE | ¥24,326.92 |
| +30 bp | AGG, RESERVE | ¥7,946.92 |
| +50 bp | RESERVE only | 0 (gain nets the cost) |

| Discount on RCV-A | Outcome | Codes |
| --- | --- | --- |
| 50 bp | ACCEPT | — |
| 85 bp | COUNTER | EARLY_PAY_DEARER_THAN_PLAN (whole face) |
| 90–120 bp | COUNTER | + DISCOUNT_ABOVE_BREAK_EVEN |
| 150 bp | COUNTER | + MAX_APR_EXCEEDED |
| 200 bp | COUNTER | + IMMEDIATE_DISCOUNT_EXCEEDED |

What the sweep shows: the envelope is cut by three different walls, the forward budget (¥5,000 is smaller than one
5-day step on a ¥420,000 monthly invoice), liquidity (curable to 55 days, not beyond) and price (break-even 0.8832%
for 30 days). Outcomes were monotone in each lever here, so a binary search per lever is sound on this fixture
(10 terms points → 4 evaluations; 41 discount points → 6; 21 price points → 5; 41 rebate points → 6: about 21
evaluations, 2–8 s cold, less warm since the baseline and comparison are cached across calls). Monotonicity is not
guaranteed in general (a bigger early payment can retire a drawn balance and lower C1), so a spike should verify the
boundary with neighbours rather than trust bisection alone. The verifier returns, per point, the outcome, the codes,
the forward total, and for a breach `curable` and `cure_cost_fen`; it does not return "the largest admissible Δ".

**Compensation comes directly from existing functions.** `value_concessions([extension])[0].per_invoice_fen` is the
per-invoice funding cost and `counters.smallest_step_covering(per_invoice, face)` the compensating price step:
50 days → ¥623.77/invoice → 15 bp; 55 → ¥1,247.53 → 30 bp; 60 → ¥1,871.30 → 45 bp; 75 → 90 bp; 90 → 135 bp. The
price-adjustment counter already walks terms down until liquidity and the budget both pass, so "the longest terms
with compensation that FLOW can live with" is Option B of a what-if evaluation (55 days + 0.30% on the golden books).
`plan()` gives the liquidity cost of any point; it does not give a compensating price itself.

### 7.2 Multi-deal portfolio

Accepting deal *i* in state terms = adding its bound obligations to the books (`bind()` or the verdict's
`bound_obligations`), its forward value to `state.forward_concessions`, and, for terms and price changes, writing
`InvoiceAdjustment`s (`financial.invoices.accept` on a synthetic ACTIVE commitment, or simply passing the obligations
to `project`/`plan`, which `_apply_terms_and_prices` applies on the fly). Countering = replacing them with a
counter's `obligations`. Rejecting = omitting them. The sequence per combination: `obs = [*books.obligations,
*chosen]` → `plan(books.state, obs, mandate)` for liquidity and cost → `value_concessions(chosen, ...)` and the
caps for the budget → optionally `evaluate` per deal on the reserved state. `evaluate_many()` already does the
sequential version (each accepted package reserves its forward value against the caps for the next; a later offer
that fits alone but not jointly gets COUNTER), which is a greedy order, not a search.

Measured: EX08A (0.75% rebate, BUYER-1), EX08B (1% rebate, BUYER-2), EX05 (consolidation + 15 days shorter): all 8
subsets through `plan()` in 241 ms. Need and cost were identical (¥405,000, ¥3,113.93) in every subset: rebates and
operational concessions are forward costs outside the 120-day cash horizon, so the budget (¥5,000 against ¥3,000,
¥2,500 and ¥7,800) is the only binding constraint for these; only terms and early-pay legs move the plan.
Combinatorics: accept/counter/reject over *n* deals is 3^n packages (27 for 3, 729 for 6) at 33 ms per `plan()`
plus 40–600 ms per `evaluate`; accept/reject alone is 2^n (8 to 64). With one counter per deal fixed by the
verifier, 6 deals × 3 choices is about 24 s of `plan()` or 3–7 minutes of full `evaluate`; pruning by the budget
(a subset over the cap stays over it) and by buyer (deals of different buyers interact only through cash and the
aggregate cap) cuts most of it.

### 7.3 Collections prioritisation

Simulating a receipt today: `paid = state.model_copy(update={"cash_fen": cash + face, "receivables": [r with status
SETTLED, settled_fen = face]})` → `plan(paid, books.obligations, mandate)` and `alerts(paid, mandate, store, day)`.
Simulating "paid N days earlier" has no first-class lever; the ledger's own ways are a shorter `terms_days` on the
receivable copy (moves the RECEIPT event), or an `IMMEDIATE_DISCOUNT` obligation at 0 bp with `effective_day` =
today + N on the covered face. Measured on the golden books (baseline: need ¥405,000, cost ¥3,113.93, first breach
day 12, alerts RESERVE_BREACH_AHEAD + RESERVE_HEADROOM_LOW):

| RCV-A received | Need | Plan cost | First breach | Alerts |
| --- | --- | --- | --- | --- |
| today (day 0) | 0 | 0 | none | RESERVE_HEADROOM_LOW only |
| day 12 (20 days early) | 0 | 0 | none | |
| day 20 (12 days early) | ¥240,000 | ¥1,328.02, needs the owner (short advance above 15%) | day 12 | |
| day 25 (7 days early) | ¥360,000 | ¥2,528.83 | day 12 | |
| day 31 (1 day early) | ¥405,000 | ¥3,087.63 | day 12 | |
| recurring invoice on 30- or 40-day terms | ¥405,000 | ¥3,113.93 | day 12 | the gap closes before day 32 |

So "what does chasing this invoice buy" is `cost(plan without)` − `cost(plan with the receipt moved)`, plus the
breach days and alerts removed, each a 33 ms `plan()` and a 4 ms `alerts()`. The reconciliation's `outstanding[]`,
`past_due`, `promised[]` and the home's `days_late` give the list to rank.

### 7.4 Inputs each idea lacks

| Missing input | Nearest existing field | Gap |
| --- | --- | --- |
| Payment probability / expected delay per buyer or invoice | `Receivable.confirmed` (binary; conservative mode drops unconfirmed), `CashFlow.confirmed`, `ExpectedOrder.firm`, the LAPSED promise history in `reconcile()` | No distribution, no history of days-late per buyer; the clock keeps a log, so days-late could be derived from `ReceivePayment` entries against due days, but nothing aggregates it |
| Dispute status | none; `Receivable.status` has FAILED but nothing sets it | would need a new status or a flag |
| Buyer importance / strategic value / margin | `Counterparty` has `id`, `name`, `role`, `known` only; `ExpectedOrder.amount_fen` hints at volume | no revenue, margin, concentration or relationship fields |
| Order volume elasticity (what a concession buys) | `VOLUME_COMMITMENT` is valued at 0; `ExpectedOrder` is a rebate base | no model of revenue gained from terms |
| A buyer-level envelope for a buyer without a recurring invoice | `recurring_for()` returns None | only early-pay levers can be valued |
| Deal interdependence or sequencing preferences | `evaluate_many` reserves caps in input order | no objective across deals |
| Owner weights (safety vs value vs optionality) | `OwnerConstraints` (three tightening fields) | no utility or ranking input |
| Collection effort / cost of chasing | none | |

## 8. The brief's candidate primitives against what exists

| Candidate primitive | Exists as | Genuinely missing |
| --- | --- | --- |
| CandidateAction | `FundingAction` (funding), `Obligation` (commercial), `SuggestedAction` (alerts), typed `Operation` (execution) | one union type; a commercial action is only ever a whole offer |
| DecisionSet | `FundingPlan` (a set of funding actions with one cost and admissibility), `CounterProposal.obligations` | a set mixing commercial and funding actions across several deals |
| Opportunity | `CompiledOffer` + `Verdict` (an inbound offer), `Alert` (a risk), `ReceivableAlert.suggested` (a collection) | an opportunity the system originates (a deal to propose, an invoice to chase) with an expected value |
| ResourceCapacity | the forward budget (cap − booked), `Facility.limit_fen − drawn_fen`, headroom above `min_cash_fen`, covenant headroom (`covenant_limits`), the Tier-2 threshold | one object listing the capacities and what each candidate consumes |
| CommercialPackage | `CounterProposal` (obligations + supplier cost + forward value + text), `WhatIfParams` (the slider grid) | a package addressed to a buyer with no inbound offer |
| DealAlternative | the `counters[]` of a verdict and the comparison rows for funding | alternatives generated across the lever grid rather than by the two counter templates |
| PortfolioDecision | `evaluate_many()` (greedy, cap-only) | joint liquidity and covenant evaluation of a set of deals; an objective |
| MarginalImpact | `cost_fen` on a cure leg (with minus without), ADR-0007's C1 − C0, `induced_breach_days` (offer vs baseline), `ConcessionValue.per_invoice_fen` | a general "delta of (cost, breach days, headroom, budget) when X changes" return type |
| DecisionDependency | exclusivity of a receivable across commitments, `early_pay_hold`, cap reservation order | explicit dependencies between candidate actions |
| ConditionalAction | `PlanStep.condition` in NL plans ("if the buyer refuses"), the negotiation's fallback, `_repay_carried`'s "first affordable receipt day" assumption | a typed action contingent on a future event with a trigger |
| ScenarioState | `project()` on a `model_copy` of the state (what-if, cure_state, expected_state, the 7.3 copies) | a named scenario object with its assumptions (delay, probability) and a way to compare several |

The engine already is "state + candidate actions + constraints + objective" for funding (the router) and
"state + one package + constraints" for offers (the verifier). What does not exist is an objective across deals,
any uncertainty object, and any originating (outbound) commercial action.

## 9. Constraints a spike must respect

- **Stability mode** (HANDOVER §4–5, CONTINUOUS_OPTIMIZATION §0.12): no broad features in `services/api/app` or
  `apps/web`; a spike reuses `evaluate`, `plan`, `compare`, `alerts`, `reconcile`, `value_concessions`, `project`,
  `current_books` read-only on `model_copy` states, lives on a `research/strategy-*` branch, and if it touches the
  app at all it is behind a `Features` flag (`config.py`: `FEATURE_*` env flags; `require_feature()` on routes).
  Nothing merges into `dev`.
- **INVARIANT 13**: the UI never computes money; any envelope, ranking or delta is formatted on the server with
  `fmt_yuan`/`displayed`. INVARIANTS 2, 9 and 11 follow: typed inputs only, exact fen, conservative mode decides.
- **State semantics not to bend**: days absolute; `cash_fen` is today's opening; receipts only from the feed or the
  owner (a simulated receipt is a projection assumption and must be labelled); accepted terms are written once with a
  fixed scope; cure pricing excludes clean-down lines, early pay, bills and equity; counters must pass their own
  re-check; the forward budget never gains headroom from a package; `max_apr_bp` is a ceiling on autonomy.
- **Determinism and caching**: `verdict_id` hashes the whole state, so a sweep over synthetic offers produces
  distinct ids and nothing is stored unless a route calls `put_verdict`; the baseline and comparison LRUs (32 entries)
  and the what-if cache (256 entries) make warm sweeps cheaper; `clear_caches()` for cold measurements.
- **Validation assets**: `fixtures/golden/golden_values.json` (67 values, independent oracle
  `compute_golden.py`); `fixtures/offers/offers.yaml` (EX01–EX12 with expectations) and three held-out sets (50,
  49, 66 offers); `fixtures/scenarios/golden_sme.json` and `short_facilities.json`; 1,735 test functions (about
  5,450 cases), the pinning ones being `tests/verifier/test_golden_verdicts.py` (EX01 codes, ¥28,326.92, day 47,
  ¥2,406.67 cure, Option A ¥257,200 at 0.85%, Option B 55 days), `tests/verifier/test_counter_property.py`,
  `tests/funding/test_golden.py` (¥3,113.93, rows), `tests/funding/test_differential.py` (brute-force optimality
  26/26), `tests/books/*`, `tests/alerts/*`; `services/api/evals/e2e/scenarios.yaml` (49 scenarios, 87 turns);
  `evals/security/attacks.yaml` (122 API attacks, 133 chat); `scripts/evaluate.py` (eight suites); hand derivations
  under `docs/research/*handcalc*`. A spike's figures should be checked against the golden values where they overlap
  (the 7.1 and 7.3 tables above reproduce ¥3,113.93, ¥24,326.92, ¥1,871.30 and the day-47 breach).
- **Performance envelope**: one `evaluate` is 40–600 ms cold, one `plan` 33 ms, one `alerts` 4 ms; a per-buyer
  envelope of about 20 evaluations fits a request; 3^6 portfolio evaluations do not, without pruning.
