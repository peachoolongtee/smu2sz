# R4 (ticket #93, map #88): capacity consumption, the additional-need figure, shadow cost, and the scenario comparator

Researcher's resolution, 10 October 2026. Repository `/Users/ianpong/Hackathons/smu2sz`, branch `dev` at `0cd60cb`, read-only.
Paths below are relative to `services/api/` unless they start with `docs/` or `fixtures/`. Every Demo figure was computed by
hand from the fixture and then checked against the engine: read-only scripts, in-memory store, in
`scratchpad/r4work/r4_calc*.py`. `git status --short` was empty at the end. Calendar: day 0 = 2026-10-01
(`fixtures/scenarios/golden_sme.json:4`), so day 31 = 1 Nov, day 32 = 2 Nov, day 47 = 17 Nov, day 56 = 26 Nov,
day 61 = 1 Dec, day 62 = 2 Dec, day 120 = 29 Jan 2027.

## 0. Answer in brief

- **Capacity can be stated now from canonical state, with no owner input and no engine change.** Each of the five
  definable dimensions is a day series read from the CONSERVATIVE trajectory under the router's plan. Each has an exact
  reconciliation to a figure the product already shows. The sixth, customer-credit capacity, has no field in the books and
  is refused.
- **The "additional working-capital need FLOW could still support" (section 15) is defensible as a search over the existing
  router on labelled copies of the books.** It needs three things stated: a defined shape for the need, a defined autonomy
  criterion, and the buyer's early-payment source taken off the copy. On the Demo books it is ¥81,000 today, ¥14,000 after
  accepting Foshan's request, **¥0 after FLOW's recommended counter (Option A)** and ¥62,000 after Option B. Adding up the
  per-dimension headrooms gives a different answer (¥81,000 under Option B, against ¥62,000 from the search), which is why
  the figure has to come from the search.
- **Shadow cost:** the router's `marginal_cost_annual` is a fixed tariff, not a shadow price. It does not get a surface now.
  One derived sentence ("the next yuan would come from X at Y%, and needs the owner / the buyer") falls out of the search
  for free.
- **The comparator** reduces to five rows plus a late-payment overlay: current books, accept as asked, each counter,
  customer loss, and late receipt. Every row is either the verifier's own verdict or a `ScenarioState` read by
  `read_books`. Nothing is weighted and no probability is shown.
- **Verdict (section 7): lead with capacity (D), not the comparator.** The comparator needs capacity's fields, and its most
  distinctive row (customer loss) depends on owner-entered economics from #91. The Demo shows why: the counter FLOW
  recommends today (Option A) is the cheapest response, yet it leaves no room for any other payment until 1 Nov. No
  surface says that today.

## 1. What exists: corrections to the map's Reconciliation lines

**Capability D ("the state exists, the statement does not").** Confirmed, with five corrections.

1. **The trajectory has no per-facility balance.** `DayPoint` carries only `debt_outstanding_fen` (all debts plus all
   facility balances, `app/domain/models.py:560-566`, built at `app/financial/trajectory.py:1007,1055`). A per-facility
   series must be rebuilt from events. One canonical rebuild exists, `covenants.line_balances`
   (`app/covenants/clean_down.py:52-66`), but it counts only `DRAW` and `REPAYMENT`, so it cannot be used for invoice
   financing (`ADVANCE`).
   - **Latent defect.** `line_balances` double-counts a lot that has not landed on a line with a lead time. `drawn_fen`
     already holds the lot (ADR-0010 §2), and `_land` posts a `DRAW` event again on its arrival day
     (`app/financial/trajectory.py:671-683`).
   - **Reproduced.** On a copy with a ¥50,000 unsettled lot on a 2-day line, the balance reads ¥100,000 on day 2 and
     ¥50,000 for ever after repayment, while `debt_outstanding_fen` returns to the debt alone (`r4_calc5.py`).
   - **Where it bites.** It is reachable only when a credit line has a lead time and a clean-down covenant. On today's
     fixtures that never happens: the golden line has lead 0 (`golden_sme.json:70`), and the public SME line has lead 2
     but no covenants. A capacity module must not reuse this function as it is.
2. **The router draws today for a later need.** Slots are requested on `state.as_of_day` (`app/funding/search.py:155`).
   For Foshan's request the gap runs day 47 to day 61, yet the plan draws ¥135,040 on day 0, repaid on day 62. Capacity
   read from today's plan therefore over-states October usage, so the need window must be shown next to it (§2.2).
3. **The trajectory's forward-concession series is not the mandate budget.** `DayPoint.forward_concession_fen` holds only
   booked concessions plus rebates and operational concessions (`trajectory.py:380-404,1050`). A terms extension never
   enters it.
   - `read_books` reads `budget_used_fen = max(trajectory forward, booked)` (`app/strategy/impact.py:172,178`). For an
     unbooked package it therefore sees ¥4,000 for Foshan's request, where the verifier counts ¥28,326.92
     (`Verdict.forward_concession_total_fen`, `app/verifier/evaluate.py:248-257`).
   - **Consequence.** Concession headroom must be read from the verdict, or from booked `ForwardConcession` rows (the
     executor books `FC-{commitment}` at `app/operations/executor.py:1003`), never from `MarginalImpact.budget_used_delta_fen`
     on an unbooked package.
4. **"Posted cost" excludes the package's own discount.** The plan's cost is the plan trajectory's charges less the
   baseline-with-obligations charges (`app/funding/search.py:328-329,398,589`).
   - Accepting Foshan's request shows a funding cost of ¥1,468.05, below today's ¥3,113.93, because the early receipt
     shrinks the gap. The ¥5,040 discount that buys it is not in that figure.
   - **Consequence.** `MarginalImpact.posted_cost_delta_fen` for a package reads −¥1,645.88, a "saving". It must never
     be shown alone as the package's cost.
5. **`marginal_cost_annual` is computed on the state before the plan.** See `app/funding/router.py:215` and
   `app/funding/rates.py:203-212`. It changes only when the cheapest permanent source has zero room left
   (`rates.py:183`). It reads ≈10.8417% (FAC-IF) in every scenario below. It is a tariff, not a marginal or shadow cost
   (§4).

**Capability B ("pieces exist, no comparator").** Confirmed, with three corrections.

1. **`scenario_received` refuses a late receipt.** It raises for any day after the due day (`impact.py:109-110`), and for a
   financed receivable it allows only "today" (`impact.py:107-108`). Its later-day mechanism moves `terms_days` on the copy
   (`impact.py:81-88`). Used for a *late* receipt, that same move would push the contractual due day and make the invoice
   financeable for longer than the contract allows (FINANCIAL_SEMANTICS §2, `docs/FINANCIAL_SEMANTICS.md:30`). A
   late-payment scenario therefore needs a different labelled copy (§5.2).
2. **Expected orders are not in the cash projection.** `ExpectedOrder` (`models.py:443-451`) is read only as the rebate base
   (`app/verifier/bind.py:218-240`), by the what-if (`app/whatif/offer.py:75`) and by the chat context. Future revenue in
   the projection comes from `RecurringInvoice` (`trajectory.py:203-212`), which the engine treats as confirmed
   (`trajectory.py:211`). So a customer-loss copy that removed only expected orders would change nothing but the rebate's
   base.
3. **The Demo books contradict the mission's ¥2M.** Foshan bills ¥420,000 every 30 days (`golden_sme.json:46-54`). That is
   13 dated invoices in the 365-day window (`docs/FINANCIAL_SEMANTICS.md:93-94`), or ¥5,460,000 a year, DERIVED. The
   mission's ¥2,000,000 for Foshan (§2) is not consistent with these books. The "next quarter" expected order of ¥400,000
   (`golden_sme.json:290-299`) is also inconsistent with three recurring invoices a quarter (¥1,260,000). The comparator
   must show provenance and refuse to pick silently (§5.6).

**Already built, and reused here (the comparator must not rebuild these):**
- The verdict with its counters, each passing its own re-check (`docs/FINANCIAL_SEMANTICS.md:113`).
- The router plan and the spec §7.4 comparison (`app/funding/router.py:294-372`), and the comparison contract `group` /
  `rank` / `router_order` (`app/api/presentation.py:1491-1527`).
- `ScenarioState` / `MarginalImpact` / `read_books` (`app/strategy/types.py:26-90`, `impact.py:159-206`).
- The executor-acceptable funding candidates for today (`app/alerts/engine.py:103-129`).
- Covenant limits (`alerts/engine.py:375-392`).
- The what-if concession headroom (`app/whatif/simulate.py:191-205`).
- Joint reservation across offers (`evaluate_many`, `app/verifier/evaluate.py:842-880`, `app/verifier/reserve.py:148-155`).
- The portfolio spike's oracle (`fixtures/strategy/portfolio_default.json`).
- The collections ranking (`app/strategy/collections.py:113-145`, `GET /receivables/worth`).
- `Capacity` was explicitly deferred by map #47 (`docs/STRATEGY_MVP_REPORT.md:28,125`).

## 2. Capacity dimensions

### 2.1 Common semantics

- **Books.** BEFORE is the current books (`Books`: state plus the obligations of live commitments). AFTER is the same books
  plus the package's bound obligations as the verifier binds them (`VerdictBundle.bound_obligations`,
  `app/verifier/models.py:57-67`), or a counter's `CounterProposal.obligations` (`models.py:713-721`). These are the
  `MarginalImpact` semantics (`impact.py:182-206`).
- **Series.** Each side is read on two trajectories, both from `project(..., Mode.CONSERVATIVE, mandate.horizon_days,
  min_cash_fen)`, the same call `read_books` makes (`impact.py:167-168`):
  - U, unfunded: no actions.
  - F, funded: the actions of `plan(state, obs, mandate)`, the COMMITTED router plan.
- **Window statement.** For dimension h, compare h_before(d) and h_after(d) over the days from today to H. A statement is
  written for each maximal run of days on which they differ:
  > "from ‹first day› to ‹last day› ‹dimension› falls from h_b to h_a"
- **Recovery day.** The first day after the run on which h_after(d) ≥ h_before(d). When it depends on a discretionary line
  repayment, it is labelled "assumed" (ADR-0010 §5; `docs/FINANCIAL_SEMANTICS.md:20`). The day is the plan's own
  `repay_day`, the same day the home's forecast basis shows (`app/api/home.py:395-409`).
- **No recovery.** If none comes before H: "not within the 120-day horizon (to 29 Jan 2027)".
- **Need window.** Shown next to the plan-based series: [U.first_breach_day, last day U is below the floor]. This corrects
  finding 2 above.
- **Money.** Integer fen (INVARIANT 9), and every display string is written by the server (INVARIANT 13).

### 2.2 The definitions table

| Dimension | Exact formula on canonical fields | Day series | What `MarginalImpact` already carries | Reconciliation test (section 45) |
| --- | --- | --- | --- | --- |
| **Cash buffer above the floor** | b(d) = `DayPoint.closing_fen` − `Mandate.min_cash_fen` (`models.py:563,319`) | U (risk if nothing is funded) and F (after the plan) | `lowest_headroom_delta_fen` = Δ min over U (`impact.py:177,198`) and `first_breach_before/after` | min over U equals `Reading.lowest_headroom_fen` and the home's `cash.lowest_headroom_fen` (`home.py:1123`) on the same books. On F, the min is ≥ 0 exactly when `FundingPlan.admissible`, and the router funds to the floor, so it is 0 whenever a plan is needed. A buffer is therefore a U statement or "0 with the plan"; capacity then sits in the facilities |
| **Credit-line headroom** (each `CREDIT_LINE`, and any `DRAW` facility) | l_f(d) = `limit_fen` − bal_f(d). bal_f(d) = `drawn_fen` + Σ plan actions on f landing on or before d (`FundingAction.lands_day`, `router.py:257-272`) − Σ \|`REPAYMENT`\| events with `ref == f.id` on or before d. Lots already in `drawn_fen` are not added again. | F | Nothing | (i) Every day, Σ_f bal_f(d) + debts principal(d) = `DayPoint.debt_outstanding_fen` (`trajectory.py:1055`); debts principal comes from `app/financial/debts.debt_payments`. Run on 4 Demo cases × 121 days: 0 mismatches. (ii) On the day the plan lands, the peak is ≤ limit (`_check_limits`, `trajectory.py:863`). (iii) Today with no plan, l_f equals the home's `available` (`home.py:1095`) |
| **Invoice-finance headroom** (each `INVOICE_FINANCING`) | i_f(d) = min(`limit_fen` − bal_f(d), Σ over receivables open on d, `confirmed`, not `FINANCED`, not under a live early-payment agreement, not yet due, of ⌊outstanding × `advance_rate_bp` / 10000⌋ − the plan's advances on them). Rule: `docs/FINANCIAL_SEMANTICS.md:30`; models `Receivable` `models.py:360-374`, `Facility.advance_rate_bp` `models.py:266`. Two readings: TODAY (issued invoices only, the executor's rule) and AS ISSUED (recurring invoices issued by d, labelled "assumes the invoice is issued as scheduled") | F | Nothing | TODAY = the sum of the `FINANCE_INVOICE` candidates of `alerts.engine._candidates(state, today)` (`alerts/engine.py:103-129`) less the plan's advances. Demo: ¥336,000 − ¥255,000 = ¥81,000, which equals the §3 search result exactly |
| **Concession headroom** | c = `max_aggregate_forward_concession_fen` − Σ `ForwardConcession.value_fen` (booked; `models.py:320,415-422`). After a package: cap − `Verdict.forward_concession_total_fen` (`evaluate.py:248-257`; existing + max(0, net new), INVARIANT 5). Per buyer b: `per_buyer_caps_fen[b]` − Σ FC of b (`models.py:322`) | Point value over the window [today, today + H_c), H_c = `forward_concession_horizon_days` (`docs/FINANCIAL_SEMANTICS.md:87`). Not a day series: the budget is one 12-month number | `budget_used_delta_fen`, which is wrong for an unbooked package (finding 3) | It must equal the what-if's `forward.headroom_fen` (`simulate.py:203`) and the counter builder's headroom (`app/verifier/counters.py:611-615`) on the same package. AGG_CONCESSION_EXCEEDED fires exactly when c_after < 0 |
| **Covenant headroom** (DSCR, leverage, clean-down) | Binding limits: DSCR_min = max(mandate `min_dscr_bp`, facility DSCR covenants); LEV_max = min(mandate `max_leverage_bp`, facility leverage covenants). These are the alerts' own `covenant_limits` (`alerts/engine.py:375-392`). In money, per month m: DSCR room_m = ⌊EBITDA_m × 10000 / DSCR_min⌋ − `debt_service_fen`_m (extra monthly service the business could carry). Leverage room_m = ⌊LEV_max × 12 × EBITDA_m / 10000⌋ − `total_debt_fen`_m (extra month-end debt). Clean-down: longest zero run − `clean_down_days`, with the line balance corrected as above | `Trajectory.months` on F (`models.py:569-575`; ratios `trajectory.py:1070-1071`) | Nothing | room_m ≥ 0 exactly when the month's `MonthPoint.dscr` / `leverage` are within the limit. That means no DSCR_BREACH / LEVERAGE_BREACH in the verdict and no critical `COVENANT_HEADROOM_LOW` alert (`alerts/engine.py:395-417`) |
| **Customer-credit capacity** | **Refused.** `Counterparty` has only id, name, role and `known` (`models.py:454-458`), and there is no credit limit anywhere. `per_buyer_caps_fen` caps concessions, not exposure. The buyer's exposure (open AR, financed share) is derivable, but it is a concentration fact (ticket #91), not a capacity. It becomes a capacity only if the owner enters a per-buyer credit limit (NEEDS OWNER INPUT) | — | — | — |

**Rounding.** Every figure is integer fen as the engine posts it. The money form of a ratio room is floored, never rounded
up. Percentages of a limit are display only, written half-up by the server, and never stored.

**Edge cases.**
- A facility that is not COMMITTED is never counted as headroom (INVARIANT 4/11).
- `REFERENCE_ONLY` and Tier-3 sources are excluded (`rates.py:57-66,175-185`).
- `allow_new_borrowing = false` makes every borrowing headroom 0, with the reason stated (`docs/FINANCIAL_SEMANTICS.md:46`).
- When EBITDA ≤ 0, leverage room is undefined, and with debt it is a breach (`docs/FINANCIAL_SEMANTICS.md:79`).
- A negative headroom is shown as negative with "over by", never clamped (section 45: "no headroom goes negative
  unnoticed").
- An unlanded lot is already in `drawn_fen`: count it from its request day, as the executor does (ADR-0010 §2), not on its
  arrival day. The projection books balance changes on arrival (`trajectory.py:478,567`), so for a plan action with lead
  time L the series must add it from `FundingAction.day`, not `lands_day`, to match the executor's room. This makes 0 days
  of difference on FAC-LINE (lead 0) and 3 days on FAC-IF.

### 2.3 Does it reuse the section 25 primitive?

Yes, without a new abstraction. A `CapacitySnapshot` is a pure function of (books, mandate, plan) built from
`read_books`' inputs, and `CapacityImpact` is two snapshots subtracted.

**Recommendation.** Extend `Reading` (`impact.py:146-156`) with the per-facility series and the covenant rooms. Add the
capacity deltas to `MarginalImpact` as new optional fields, so the collections and price-curve code, which already call
`marginal_impact`, get them for free. These are strategy files, not frozen engine.

## 3. The "additional working-capital need FLOW could still support" (section 15)

**Definition (defensible).** X\*(shape, criterion) is the largest X on a ¥1,000 grid for which the router, run on a
labelled copy of the books, returns a plan passing the criterion.
- **The copy:** the books, plus the package's obligations, plus a hypothetical need of X. Built as
  `scenario_inflow`'s pair (`impact.py:120-140`), or as a lone outflow.
- **The criterion:** `plan(...)` is `admissible`, not `needs_owner_approval`, and passes the runnability test below.
- **The shape** is part of the answer and is always stated. Three are defined:
  - S1 "a one-off payment of X today that does not come back within the horizon" (the conservative default);
  - S2 "X paid on d₁ and recovered on d₂";
  - S3 "X needed during the window of the deal's own gap".
- **Runnability.**
  - R-TODAY: `executable_now`. This is the executor's rule; the headline uses it.
  - R-AS-ISSUED: every leg that cannot run today is an advance on the supplier's own invoice, issued later as scheduled,
    which the agent may run alone on its issue day. This version is labelled as an assumption.
- **Buyer-dependent sources come off the copy.** The `BUYER_EARLY_PAY` facility is removed from the copy. Otherwise the
  router's cheapest plan can be an early payment that needs the buyer's agreement, and that masks a dearer plan the agent
  could run alone (observed: accept-as-asked under S1 reads ¥14,000 with the early-pay source present under both
  criteria, and ¥250,000 under R-AS-ISSUED without it).
- **What is reported alongside X\*:** the plan at X\*, the plan at X\* + ¥1,000, and the binding reason (the violation
  codes, `approval_reason` or `not_executable_reason`, all already worded by the router, `router.py:136-143`).

**Demo results** (golden books, day 0; `r4_calc2.py`, `r4_calc2c.py`):

| Books | S1, R-TODAY | Binding (next ¥1,000) | S1, R-AS-ISSUED | Binding |
| --- | --- | --- | --- | --- |
| Current books (no deal) | **¥81,000** (line ¥150,000 + IF ¥336,000 on RCV-A) | IF advance-rate cap on RCV-A, 80% × ¥420,000. The next yuan needs an advance on RI:BUYER-1:2 at 15.49% effective, above the 15% ceiling, so it needs the owner | ¥81,000 | Same |
| Accept as asked | **¥14,000** (line ¥149,040) | Line limit: ¥14,960 of room from day 0 to day 61. RCV-A is under the early-payment agreement and cannot be financed | ¥250,000 (adds IF on RI:BUYER-1:2 and RI:BUYER-1:32, not runnable until they are issued, days 2 and 32) | RESERVE_BREACH and CLEAN_DOWN_BREACH |
| Option A (FLOW's counter) | **¥0** | Line room ¥13.80 to day 31. RCV-A is partly under an early-payment agreement, so the whole invoice is ineligible (`docs/FINANCIAL_SEMANTICS.md:30`) | ¥0 | The first ¥1,000 needs the owner (15.49%) |
| Option B | **¥62,000** (line ¥150,000 to day 57 + IF ¥317,000) | Line limit in the second gap episode, 17 to 26 Nov (days 47 to 56) | ¥95,000 | RESERVE_BREACH |

**Why a search and not a sum.** Under Option B the per-dimension headrooms add up to ¥60,000 of line plus ¥21,000 of IF,
or ¥81,000. The search says ¥62,000, because the line must stay drawn to day 57 to cover the November episode and the IF
advance must be repaid from RCV-A's receipt (`rates.py:144-158`). Dimensions interact through repayment timing and the
reserve on every day, and only the router sees that.

**Monotonicity is not assumed** (section 37). The run above uses bisection. The feasible set can be non-monotone because
whole-period billing makes the effective rate step (`docs/FINANCIAL_SEMANTICS.md:69-71`), and runnability can flip as the
router changes legs. The production version should follow the envelope's rule: bisection, both neighbours of the boundary
re-checked, and a full scan on a coarse grid when a neighbour disagrees (map body line 27; `app/strategy/envelope.py`).

**Cost.** 0.2 to 2.5 s per search on the golden books (about 10 to 20 router runs). The public SME's router is the slow
path (ticket #78 of map #58: 17 to 78 s for the envelope), so this must run on request behind the strategy cache's
single-flight (`app/strategy/cache.py`), never on page load.

**What is refused.**
- No figure without its shape and criterion sentence.
- No "you could fund another order", unless a defined `ExpectedOrder` or `RecurringInvoice` is the need (section 15).
- No X\* when the current books already have no admissible plan: then the answer is "none: today's books already need
  the owner or a new facility" with the reason.

**Displayed form (headline).**
> "After accepting, FLOW could still cover a one-off payment of up to ¥14,000 today without another facility or your
> approval (today: up to ¥81,000). The credit line is the limit until 1 Dec."

## 4. Shadow cost and optionality (section 16)

- **What `marginal_cost_annual` says.** It is the all-in tariff of the cheapest COMMITTED, owner-approved source that
  can carry a permanent need (`rates.py:188-212`). On the Demo that is FAC-IF at 7.8% + 0.25% × 365/30 ≈ 10.8417%
  (`golden_sme.json:115-120`; `docs/FINANCIAL_SEMANTICS.md:63`).
  - The line at 6.4% is cheaper but is excluded by its clean-down covenant (`app/covenants/clean_down.py:88-91`).
  - The figure is computed before the plan, and it changes only when that source has no room left.
  - It prices the terms extension as a loan: ¥24,326.92 (`docs/FINANCIAL_SEMANTICS.md:90,94`). **So the opportunity cost
    of capital is already inside the concession cost.** It is not a shadow price of line headroom.
- **When cheap capacity used now forces expensive funding later.** The search makes the price staircase concrete, as
  each next ¥1 moves to the next source:
  - line 6.4%;
  - then IF on RCV-A, 10.84% tariff (more effective for short holds: whole periods);
  - then an advance on a later invoice at 15.49% effective, above the 15% ceiling, so it needs the owner;
  - or the buyer's early payment, 1.2% for 30 days = 14.78% (`rates.py:69-73`), which needs the buyer.
  - The guaranteed loan at 5% is NOT_APPLIED with a 21-day lead (`golden_sme.json:157-179`), so it is no help before
    day 21.
  - Example: accepting keeps ¥135,040 of the line drawn until 1 Dec. A further need in that window is funded on the next
    step, and beyond ¥14,000 that step needs the owner.
  - The marginal cost of a need is the posted-cost difference of two router runs: (cost(X+Δ) − cost(X)) / Δ. For example,
    today's books with S1 X = ¥81,000 cost ¥4,230.24 against ¥3,113.93 without: ¥1,116.31 for that ¥81,000, all on IF.
- **Can one profitable deal shrink the feasible set of future deals?** Yes. Evaluated jointly, a second deal is judged on
  the room and budget the first leaves (`evaluate_many`, `evaluate.py:842-880`; `reserve.py:148-155` reduces each
  facility's limit by what earlier plans use). That is the correct mechanism, and it needs no prices.
- **Does it earn a surface now? No.**
  - A formal shadow price would be one number standing in for a staircase with consent and ceiling steps, which is
    exactly the opaque arithmetic the mission rejects (§22).
  - Keep one derived sentence inside the capacity block, from the search's binding leg: "The next yuan would come from
    ‹source› at ‹effective rate›, and needs ‹the owner / the buyer›".
  - Keep the staircase as a research note for the portfolio work.

## 5. The scenario comparator contract

### 5.1 The scenario set (the mission's seven collapse to five rows plus one overlay)

| Row | Produced by (labelled copy, exactly once) | Assumption sentence shown | Kind |
| --- | --- | --- | --- |
| **Current books** (also "buyer rejects the counter and keeps buying") | The `Books` as they are; no copy | "Your books as they stand: Foshan keeps buying on today's terms." | Fact (current) |
| **Accept as asked** | The verifier's verdict on the offer: `VerdictBundle` (trajectory, `plan_committed`, `bound_obligations`) | "If you accept Foshan's request as asked." | Package |
| **Counter k** (also "buyer accepts counter k") | The verdict's `CounterProposal.obligations`, evaluated on the same books, which is the counter re-check (`docs/FINANCIAL_SEMANTICS.md:113`). An envelope package (`app/strategy/envelope.py`) can be an extra "alternative counter" row, already re-evaluated whole | "If Foshan accepts Option A." | Package |
| **Customer loss** ("buyer rejects and walks") | `ScenarioState` copy. Remove the buyer's `RecurringInvoice` rows (or end them before their next `next_issue_day`) and the buyer's `ExpectedOrder` rows. Already-issued `Receivable`s **stay**, because they are owed. Live commitments on the buyer bind to no future invoice, so their extension cost disappears from the projection with the invoices. Booked `ForwardConcession` rows stay until released by the lifecycle rule (`docs/FINANCIAL_SEMANTICS.md:29`) | "Scenario assumes Foshan stops buying from you after today; the ¥420,000 already invoiced (RCV-A, due 2 Nov) is still paid. This is not a prediction." | Hypothetical |
| **Late receipt** (overlay on any row) | `ScenarioState` copy. The receivable is removed and replaced by one confirmed `CashFlow` of its outstanding amount on the late day (`counterparty_id` = the buyer; `CashFlow` at `models.py:350-357`), so the receipt moves once and is never duplicated (section 39). The copy cannot be financed on that invoice: this is conservative, and it understates capacity by at most advance rate × outstanding, which must be said. **Refused** for a FINANCED receivable (recourse repayment on the due day is not modelled on a copy: `trajectory.py:685-705`) and for a receivable under an early-payment agreement. The delay comes from #91's statistics or an owner-chosen stress; it is never invented | "Scenario assumes RCV-A's ¥420,000 arrives on 2 Dec, 30 days after its due date. This is not a prediction." | Hypothetical |

### 5.2 The comparison fields

Every row carries the following fields, each with a stated reconciliation.

| Field | Definition | Reconciles to |
| --- | --- | --- |
| `outcome`, `required_tier`, `codes` (packages only) | `Verdict` fields (`models.py:724-739`) | Identical to the deal card's verdict: the same call, no copy |
| `concession_forward_fen` (12 months; the mandate's budget) | Package's `Verdict.forward_concession_total_fen` − existing booked (for a counter, `CounterProposal.forward_value_fen`) | Equals the AGG test's observed value. Never added to the funding cost: the extension is already priced at the marginal source |
| `immediate_discount_fen` (cash, posted) | The `DISCOUNT` events the package's obligations post on U (`trajectory.py:376-377`) | Same as `CounterProposal.supplier_cost_fen` less the plan's interest for a counter |
| `funding_cost_fen` (horizon, posted) | `FundingPlan.total_cost_fen` of the row's books | Equals `/router/plan`'s SELECTED row for those books (`router.py:331-372`), and `MarginalImpact.after_cost_fen`. The verdict's RESERVE_BREACH `cure_cost_fen` is a *different* plan (permanent sources only: ¥2,406.67 against the router's ¥1,468.05 for Foshan's request), so the row names which one it shows: the router plan |
| `need_fen`, `lowest_cash_fen` / `lowest_day` (U), `first_breach_day` | `FundingPlan.need_fen`; U's `min_cash_fen` / `min_cash_day` / `first_breach_day` | `MarginalImpact.after_need_fen`, `first_breach_after`; the home's figures for the current-books row |
| `plan_flags` | `admissible`, `needs_owner_approval`, `executable_now` | The comparison contract's group (`presentation.py:1491-1527`) |
| `capacity` | §2 per-dimension windows and recovery days, plus §3 X\* with its binding reason | §2 tests |
| `contribution_context` (from #91; labelled) | annual contribution E = annual billings × margin (provenance per field); "contribution if accepted" = E − forward concession − immediate discount (12 months). For customer loss: billings removed (DERIVED from `RecurringInvoice`), contribution foregone = billings × margin (ESTIMATED), receipts removed within the horizon (DERIVED from U) | Customer loss removes each future invoice exactly once: Σ receipts(current) − Σ receipts(loss) over the horizon = the removed invoices' faces (Demo: 3 × ¥420,000 = ¥1,260,000, checked) |
| `marginal_impact` | `marginal_impact(current, row)` | Every Δ equals row minus the current row, field by field |

### 5.3 Deterministic, assumed, refused

- **Deterministic.** Everything computed from the books and the mandate: verdicts, plans, trajectories, capacity, X\*,
  receipts removed.
- **Assumed (and labelled).** These are the only assumptions:
  - the scenario's own sentence;
  - a line's repayment day (ADR-0010 §5);
  - the "as issued" eligibility of future recurring invoices;
  - the customer economics inputs (OWNER_ENTERED or ESTIMATED);
  - the delay used in the late overlay.
- **Refused.**
  - Any probability, or any expected value that weights the rows (§9). Rows are never combined into one "expected" figure.
  - Causal claims such as "if you counter, Foshan walks": the customer-loss row is unconditional.
  - A customer-loss cash figure "net of costs avoided". `CashFlow` costs carry no customer link (supplier flows have
    `counterparty_id` null, `golden_sme.json:17-23`), so the projection removes gross receipts while the costs stay. The
    row must say "receipts removed; costs that would also stop are not modelled". The economic loss is the contribution
    figure, not the cash figure.
  - Summing concession and funding cost.
  - Adding capacity across rows or packages: the portfolio must re-run them jointly.
  - "Future order cannot be funded" without a defined order.
  - A late overlay on a financed invoice.

## 6. Fields a portfolio optimiser and a collections prioritiser would need (sections 30, 31)

**Portfolio.** The comparator's row is the unit. Each package row must expose:
- `package_id` / `obligations` and `offer_id`;
- `forward_value_fen` (budget use), `immediate_discount_fen` and `funding_cost_fen`;
- `need_fen`, the plan's legs (facility, amount, request day, repay day), the capacity windows and X\*;
- `required_tier` / `cure_needs_owner`, and `state_version`.
- This matches the spike's ranked rows (`need`, `funding_cost`, `posted_cost`, `concession_value`, `budget_used`,
  `budget_cap`, `owner_decisions`, `binding`: `fixtures/strategy/portfolio_default.json`).
- The one rule to keep: **capacity is never summed across packages**. A combination is re-evaluated whole through
  `evaluate_many` / `reserve.py`. So the row must keep its *inputs* (obligations), not only its outputs.
- Nothing proposed here blocks that.

**Collections.** `receivables_worth` already ranks receipts by `marginal_impact` (`app/strategy/collections.py:77-145`).
The only addition it would want from this work is the capacity delta of a receipt: for example, "collecting RCV-A today
frees the line from 2 Nov". That is the same `CapacityImpact` on a `scenario_received` copy. Keep `receivable_id`,
`counterparty_id`, `due_day` and `outstanding_fen` on the snapshot.

## 7. Worked before / after on the Demo books: Foshan's request (EX01)

**Inputs (fixture file:line):**
- cash ¥400,000 (`golden_sme.json:5`);
- payroll −¥340,000 on day 12 (`:7-15`), supplier −¥120,000 on day 20 (`:16-24`), bill −¥100,000 on day 47 (`:25-33`);
- RCV-A ¥420,000, BUYER-1, issued day −13 on 45 days, so due day 32 (`:36-44`);
- recurring ¥420,000 every 30 days from day 2 on 45 days (`:46-54`);
- FAC-LINE ¥150,000 at 6.4%, lead 0, clean-down 30 days (`:57-107`);
- FAC-IF ¥350,000, 80%, 7.8% + 0.25% per 30 days, lead 3 (`:109-131`);
- debt ¥1,500,000 at ¥45,000 a month from day 30 (`:277-288`);
- EBITDA ¥90,000 a month (`:344`);
- mandate (`:347-367`): floor ¥300,000, budget ¥5,000, DSCR 1.25, leverage 2.5, APR ceiling 15%, horizon 120.

The request (`fixtures/offers/offers.yaml:4-15`) is three asks: early settlement of ¥420,000 at 1.2% on day 2, 60-day
terms going forward, and 1% off next quarter.

**Unfunded cash (U), by hand** (engine agrees; golden pins in `fixtures/golden/golden_values.json`):
- **Current books:**
  - day 12: 400,000 − 340,000 = ¥60,000;
  - day 20: −¥60,000;
  - day 30: −¥105,000, the lowest point, so the need is ¥405,000 (`golden_values.json:18`);
  - day 32: +420,000 = ¥315,000.
  - Breach on days 12 to 31 (13 Oct to 1 Nov).
- **Accept as asked:**
  - day 2: +420,000 × 98.8% = +¥414,960, giving ¥814,960;
  - day 12: ¥474,960;
  - day 20: ¥354,960 (`:33`);
  - day 30: ¥309,960;
  - day 47: ¥209,960 (`:35`), the first breach (17 Nov);
  - day 60: ¥164,960 (`:37`), so the need is ¥135,040 (`:38`);
  - day 62: the first 60-day invoice is paid.
  - Breach on days 47 to 61.
- **Option A:** day 2: +257,200 × 99.15% = ¥255,013.80; lowest ¥150,013.80 on day 30; need ¥149,986.20.
- **Option B:** today's near term is unchanged; there is a second gap on days 47 to 56.

**Plans (router; cost by hand):**
- **Current books:** line ¥150,000 from day 0, repaid day 32: 150,000 × 6.4% × 32/365 = ¥841.64. Plus IF ¥255,000 on
  RCV-A, landing day 3: 255,000 × 7.8% × 30/365 + 0.25% × 255,000 = ¥1,634.79 + ¥637.50 = ¥2,272.29. **Total ¥3,113.93**
  (`golden_values.json:16`).
- **Accept as asked:** line ¥135,040 from day 0 to day 62: 135,040 × 6.4% × 62/365 = **¥1,468.05**. The verdict's
  permanent cure is ¥2,406.67 (IF on RI:BUYER-1:32; `:39`).
- **Option A:** line ¥149,986.20 to day 32: **¥841.57**.
- **Option B:** line ¥90,000 to day 57 (¥899.51) plus IF ¥315,000 on RCV-A (¥2,019.45 + ¥787.50): **¥3,706.46**.

**Comparator rows:**

| | Current books | Accept as asked | Option A (recommended) | Option B | Customer loss | Current books + RCV-A 30 days late |
| --- | --- | --- | --- | --- | --- | --- |
| Verdict | — | REJECT: AGG_CONCESSION_EXCEEDED, RESERVE_BREACH (day 47), DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN | passes its re-check | passes its re-check | — | — |
| Forward concession (12 months; budget ¥5,000) | ¥0 | ¥28,326.92 = extension ¥24,326.92 + rebate 1% × ¥400,000 = ¥4,000 | ¥0 | ¥0 added (verdict). By hand: extension 10 days ≈ ¥16,217.95 against a firm price gain of 0.30% × ¥420,000 × 13 = ¥16,380, a net gain not credited (INVARIANT 5) | — | — |
| Immediate discount (cash) | ¥0 | ¥5,040 | ¥2,186.20 | ¥0 | — | — |
| Funding cost (router, horizon) | ¥3,113.93 | ¥1,468.05 | ¥841.57 | ¥3,706.46 | no admissible plan | ¥4,727.85 and cannot run today (line + the buyer's early payment on RI:BUYER-1:2) |
| Lowest cash unfunded (day) | −¥105,000 (31 Oct) | ¥164,960 (30 Nov) | ¥150,013.80 (31 Oct) | −¥105,000 (31 Oct) | −¥105,000 (31 Oct), below the floor on 94 days | −¥105,000 (31 Oct), below the floor on days 12 to 61 |
| First day below ¥300,000 | 13 Oct | 17 Nov | 21 Oct | 13 Oct | 13 Oct | 13 Oct |
| **Line headroom (plan)** | ¥0 to 1 Nov; ¥150,000 from 2 Nov (assumed repayment) | ¥14,960 to 1 Dec; full from 2 Dec (assumed) | ¥13.80 to 1 Nov; full from 2 Nov | ¥60,000 to 26 Nov; full from 27 Nov | ¥150,000 (no plan exists) | ¥0 to 1 Dec |
| **IF headroom today** | ¥81,000 (limit room ¥95,000) | ¥0 (RCV-A paid early; RI:BUYER-1:2 eligible from its issue on 3 Oct, labelled) | ¥0 | ¥21,000 | — | ¥0 on the copy (conservative) |
| **Additional need FLOW could support (S1, R-TODAY)** | **¥81,000** | **¥14,000** | **¥0** | **¥62,000** | none: no admissible plan | — |
| Concession headroom | ¥5,000 | **−¥23,326.92 (over)** | ¥5,000 | ¥5,000 | ¥5,000 | ¥5,000 |
| DSCR room, worst month (min 1.25 → ¥72,000) | ¥23,886.07 (month 2) | ¥25,531.95 (month 3) | ¥26,158.43 (month 2) | ¥23,293.54 (month 2) | ¥27,000 | ¥25,369.32 (month 3) |
| Leverage room, month 1 (2.5 × ¥1,080,000) | ¥840,000 (1.72×) | ¥1,109,960 (1.47×) | ¥1,095,013.80 (1.49×) | ¥840,000 (1.72×) | ¥1,245,000 (1.35×) | ¥1,095,000 (1.49×) |
| Receipts within 120 days | RCV-A + 3 recurring = ¥1,680,000 | — | — | — | ¥420,000; **¥1,260,000 removed, once** | the same ¥420,000 moved from 2 Nov to 2 Dec |

**The capacity sentence for "Accept as asked"** (section 14 form, from the rows above):
> "Accepting keeps ¥135,040 of your ¥150,000 credit line in use until 1 Dec (90%); without the deal it is free from 2 Nov.
> It is free again on 2 Dec, the assumed repayment day. FLOW could still cover a one-off payment of up to ¥14,000 today
> without your approval (today: ¥81,000). The extra funding is needed from 17 Nov to 1 Dec; FLOW's plan draws it today."

October usage is *lower* after accepting: ¥135,040 against ¥150,000 of line, and no IF advance. Both truths are shown as
windows, never netted.

**The fact no surface states today:**
> "Option A costs ¥3,027.77 and keeps the cash above your minimum, but it uses all but ¥13.80 of the line until 1 Nov,
> and the part-early-paid invoice can no longer be financed. Until then FLOW could not cover any further payment
> without you."

That is the "what flexibility do we give up" answer.

**Customer economics (no input exists in the books):**
- Annual billings are DERIVED from `RecurringInvoice`: 13 invoices in the window × ¥420,000 = ¥5,460,000.
- Margin is NOT AVAILABLE. With an **ASSUMED** 20% (the mission's figure, labelled), contribution is ¥1,092,000, and the
  request's forward cost of ¥28,326.92 is **2.59%** of it.
- The mission's ¥400,000 (¥2,000,000 × 20%) gives 7.08%, but ¥2,000,000 contradicts these books (§1, B.3).
- Customer loss: billings foregone ¥5,460,000 a year (DERIVED); contribution foregone ¥1,092,000 (ESTIMATED at the
  assumed 20%); receipts removed within the horizon ¥1,260,000 (DERIVED). Costs that would stop are not modelled.

## 8. Verdict: which avenue the map should lead with

Lead with **capacity (D)**, as the read-only `CapacitySnapshot` / `CapacityImpact` over `read_books`, with the
additional-need search, behind a flag. The comparator (B) follows as composition. The four reasons:

1. **D needs no new data.** It runs on today's books and mandate. The comparator's distinctive row (customer loss) is
   meaningless without owner-entered margin and a resolution of the ¥2M versus ¥5.46M contradiction (#91, #89).
2. **D's facts are new and decision-relevant on the Demo.** "Option A leaves ¥0 of further room until 1 Nov" and "accepting
   holds 90% of the line until 1 Dec" are not on any surface today. The comparator's accept and counter rows mostly re-show
   what the deal card already holds (verdict, counters, costs, breach day).
3. **The comparator needs D's fields** (capacity remaining is one of section 8's five fields). The map already orders
   #100 after #99.
4. **Reuse is proven, not hoped for.** D extends `Reading` and `MarginalImpact`, which collections and the price curve
   already call. The search is the router run on `ScenarioState` copies, the same pattern as the envelope.

**Against the other avenues:**
- **Customer economics (A)** has the highest salience in the owner's final sentence (§52) and the lowest cost, but it is
  input-bound. It should land beside D: a two-number owner entry, shown as context and never in the verdict.
- **The envelope additions (C)** are incremental on a built feature, and the scale cost there is open (ticket #78).
- **Late payment and concentration (E)** needs receipt history the fixtures do not have for P90.

**Risks.**
- The search's cost on large books (cache it; run it on request).
- Criterion confusion: always print the shape and the criterion.
- The latent `line_balances` double count (§1, D.1), which must be fixed or bypassed before any capacity code reads line
  balances. The covenant module is engine code, so this is a separate ticket with a test.

**Kill criterion for D.** If, in the pilot, owners read "up to ¥14,000 today" as a promise about future orders, show only
the windows (line and IF headroom through a date) and drop X\*.

## Appendix: reproduction

Run from `services/api`:
```
SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache uv run --project "$PWD" --directory "$PWD" python <scratchpad>/r4work/r4_calc.py
```
The same command runs `r4_calc2.py`, `r4_calc2c.py`, `r4_calc3.py`, `r4_calc4.py` and `r4_calc5.py`.
- `r4_calc.py`: scenarios, plans, months.
- `r4_calc2.py`: reconciliation (0 mismatches) and the X\* search with the early-pay source present.
- `r4_calc2c.py`: X\* without the buyer's early-pay source, both criteria.
- `r4_calc3.py`: receipts and closings.
- `r4_calc4.py`: Option B's binding constraint.
- `r4_calc5.py`: the `line_balances` double count.

Afterwards run `git -C /Users/ianpong/Hackathons/smu2sz checkout -- services/api/evals`. `git status --short` was empty.
