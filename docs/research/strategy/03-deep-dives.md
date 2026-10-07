# 03. Deep dives: the envelope, the portfolio, optionality, collections, adjacent ideas, one engine or three

Ticket #42 of wayfinder map #39. Builds on `01-repo-primitives.md` (ticket #40). Every figure was computed read-only on
`dev` at `d1eadb0` with the real engine (`evaluate`, `plan`, `project`, `value_concessions`, `alerts`) on the golden
books: day 0 as loaded from `fixtures/scenarios/golden_sme.json`, and the day-34 books reached by the demo path
(EX01, Option A agreed, ¥255,013.80 received on day 2, clock to day 34, month-2 payroll of ¥200,000 added on day 42).
Nothing was written. "Passes" below means the verifier's outcome is ACCEPT or NEEDS_OWNER_APPROVAL; a curable
RESERVE_BREACH is not a hard violation (`_is_hard`), AGG_CONCESSION_EXCEEDED is.

## 1. The Safe Deal Envelope

### 1.1 What the verifier derives for Foshan (BUYER-1) on the day-0 books

| Lever, alone | Maximum that passes | Wall | Figures |
| --- | --- | --- | --- |
| Terms (perpetual, recurring ¥420,000 every 30 days, 45 now) | **45 days** (no extension) | forward budget | +5 days = ¥8,108.97 over 13 invoices against a ¥5,000 budget; every step from 50 to 90 fails AGG |
| Terms, budget ignored (liquidity only) | **55 days** | reserve, curable | 55: max shortfall ¥85,000 on day 47, recovery day 57, cure ¥1,570.36 on FAC-IF (an advance on RI:BUYER-1:32, "cannot run today"). 60: max shortfall ¥130,000 on day 60, no cure |
| Terms with the compensating price (Option B rule) | **55 days at 0.30%** | reserve | 50 → 0.15%, 55 → 0.30%, 60 → 0.45% cover the per-invoice cost (¥623.77, ¥1,247.53, ¥1,871.30) and the budget; 60 days still fails: the price lands on the invoice, not on day 47 |
| Early-pay discount, whole face ¥420,000 | **0.70%** | plan comparison | 0.75% × ¥420,000 = ¥3,150 > the standing plan ¥3,113.93 → EARLY_PAY_DEARER_THAN_PLAN; break-even 0.8832% is reached only at 0.90% |
| Early-pay discount, Option A face ¥257,200 | **0.85%** | break-even | C1 ¥3,027.77 < C0 ¥3,113.93; 0.90% fails DISCOUNT_ABOVE_BREAK_EVEN; 1.50% adds MAX_APR, 1.55% adds the 1.50% immediate-discount cap |
| Rebate on the ¥400,000 next-quarter order | **1.25%** | forward budget | ¥5,000 exactly; 1.30% = ¥5,200 → AGG |
| Trade-credit exposure the reserve allows | **¥140,000 more** in steady state | permanent-capable cure room | 55 days ties up face × 10/30 = ¥140,000 beside the ¥420,000 open; the induced shortfall (¥85,000) fits the ¥95,000 FAC-IF has left after the standing plan takes ¥255,000 (the line is clean-down, so it cannot cure a permanent need); 60 days needs ¥130,000 |
| Covenants | not binding | — | pro-forma DSCR 1.92× (≥ 1.25×) and leverage 1.72× (≤ 2.50×) at 60 days |

Twenty-two evaluations found every maximum by bisection in 1.6 s warm (the recon's estimate of about 21 holds);
bisection is sound here because each lever was monotone on this fixture, which a spike must still check with the
boundary's neighbours.

### 1.2 How the dimensions interact

| Package | Outcome | Forward total | Reserve |
| --- | --- | --- | --- |
| 50 days + 1.25% rebate | REJECT (AGG) | ¥13,108.97 | curable ¥1,570.36 |
| 55 days + 0.30% price | passes | ¥0 (−¥162.05 floored) | curable ¥1,570.36 |
| 55 days + 0.30% price + 1.25% rebate | **passes** | ¥4,837.95 | curable ¥1,570.36 |
| 55 days + 0.30% price + 1.30% rebate | REJECT (AGG) | ¥5,037.95 | curable |
| 55 days + 0.35% price + 1.25% rebate | passes | ¥2,107.95 | curable |
| 55 days + 0.30% + 0.85% on ¥257,200 | passes | ¥0 | curable, but the cure is now ¥2,673.04 |
| 45 days + 0.85% on ¥257,200 + 1.25% rebate | passes, no breach | ¥5,000 | — |
| 60 days + 0.45% + 0.85% on ¥257,200 | passes | ¥0 | curable ¥2,673.04: the early payment closes the day-47 gap that no cure could |
| EX01 as offered (60, 1.2%, 1%) | REJECT | ¥28,326.92 | curable ¥2,406.67 |

Three lessons. The forward budget is one pool: the three independent maxima (55 days with price, 1.25% rebate,
0.85% on ¥257,200) happen to coexist only because Option B nets to zero; a price step of 0.05% is worth ¥2,730 of
budget, so the price is the lever that buys the rebate. Liquidity is not additive either way: the early payment in the
package changes which cure is possible, in both directions (60 days becomes curable with Option A's cash; the cure for
55 days is a different, dearer plan, ¥2,673.04 instead of ¥1,570.36, once RCV-A is settled early). And a maximum per lever would mislead: "up to 60 days" is
true with Option A's early payment and false without it; "up to 0.85%" is true for ¥257,200 and false for the whole
invoice. The envelope is a feasible region in four levers cut by three walls (budget, cure room, break-even), not a
set of thresholds; the walls move with the books (on day 34 the line has ¥13.80 left and headroom is ¥0, so no terms
extension passes at all).

### 1.3 Output form and the user question

Recommend **both, in this order: approved packages first, the zone as detail.** The verifier already produces the
packages (the counters are approved packages by construction: each passes its own re-check), and a what-if sweep
produces the zone. One-dimensional thresholds are wrong (1.2); a continuous region is right but unreadable;
buyer-specific limits exist only as `per_buyer_caps_fen` and are a mandate input, not a derivation; dynamic limits on
current books is what every number above already is.

"What can I offer Foshan?" → **Primary answer:** "Up to 55-day terms if the price rises 0.30%, or early payment at up to
0.85% on ¥257,200; no rebate above 1.25%; not 60 days." **Key reason:** "60 days leaves ¥130,000 uncovered on day 60;
the ¥5,000 concession budget buys no terms at all without a price step." **Money impact:** "Cost to you ¥0 (Option B)
or ¥3,027.77 (Option A); the standing plan without a deal costs ¥3,113.93." **Action:** "Send Option A or B" (the
existing counter cards, before a message arrives). **Detail:** the four-lever table with the wall each lever hits, the
cure and its approval flag.

What the verifier cannot derive: whether the buyer would accept (the kernel's buyer profiles are hidden state); what
volume or margin a concession buys (`VOLUME_COMMITMENT` is valued at 0; no revenue or contribution anywhere); the buyer's
importance or dispute status; the budget and reserve themselves (owner inputs); and anything for a buyer without a
recurring invoice (BUYER-2 has only early-pay levers, and no open invoice today).

## 2. The multi-deal portfolio

**Decision set** per deal: accept as offered, counter (each verifier counter), reject, delay (evaluate on the books
expected on day d, a `model_copy` with the clock's events), conditional acceptance (2.3), alternative package (a
what-if point that passes). **Objectives** available in the engine: funding cost (`plan().total_cost_fen`, C1 − C0),
concession cost (`value_concessions` at the marginal rate), liquidity (need, first breach, lowest headroom), approval
burden (`needs_owner_approval`). Not available: contribution, expected profit, customer value, risk of non-payment,
optionality (3). **Constraints**: the reserve on every day, facility room (`limit − drawn`), DSCR and leverage per
month, the aggregate and per-buyer caps, the immediate-discount cap, `max_apr_bp` (autonomy), exclusivity of a
receivable, lead times and issue days (timing), the mandate's expiry. Concentration and buyer credit limits do not
exist as constraints.

**Worked enumeration** (EX01 with Option A and Option B, EX08A, EX08B; each `plan()` on `books.with_(chosen)`, budget
= Σ max(0, net new value) per package as a commitment books it):

| Package (EX01, EX08A, EX08B) | Need | Funding cost | Budget used | Feasible |
| --- | --- | --- | --- | --- |
| Option A, reject, reject | ¥149,986.20 | **¥841.57** | ¥0 | yes |
| Option A, reject, accept | ¥149,986.20 | ¥841.57 | ¥2,500 | yes |
| Option A, accept, reject | ¥149,986.20 | ¥841.57 | ¥3,000 | yes |
| reject, reject, reject (status quo) | ¥405,000 | ¥3,113.93 | ¥0 | yes |
| Option B, reject, reject | ¥405,000 | ¥3,706.46 | ¥0 | yes |
| Option A, accept, accept | ¥149,986.20 | ¥841.57 | ¥5,500 | **no** (cap ¥5,000) |
| accept EX01, any | ¥135,040 | ¥1,468.05 | ≥ ¥28,326.92 | no |

Sixteen packages in 0.43 s; with EX05 and EX06 added, 64 packages in 1.63 s. What it shows: the rebates do not touch
cash inside the 120-day horizon, so the portfolio question here is a knapsack on the ¥5,000 budget (EX08A or EX08B,
not both) that `evaluate_many()` answers greedily in input order today; the one real cash interaction is EX01's early
payment, which cuts the need from ¥405,000 to ¥149,986.20 and lowers the cost of funding EX06's three extended
invoices from ¥3,873.58 to ¥1,630.53 (EX06 stays over the budget at ¥5,613.90); and the engine cannot rank the feasible packages beyond cost because the value of EX08A against
EX08B (which order matters more) is not modelled.

**Method.** Enumeration with pruning. The cost is a black-box projection (whole-period fees, lead times, admission
order), not linear; n is small; and every candidate must pass the same `evaluate` as a single deal, so any optimiser
would only propose what enumeration then verifies. Prune by the budget (a superset of an over-cap set stays over cap)
and by buyer (deals of different buyers interact only through cash timing and the shared cap; rebate-only deals
interact through the cap alone). Scale: an SME at FLOW's target size negotiates with a handful of key accounts; the
fixture has two buyers and one recurring invoice; a realistic peak is 3 to 5 open negotiations in one week, of which 2
or 3 interact materially (same month's cash or the same budget). Reasoned, not sourced; the pilot's inbox will give the
number. 3^5 = 243 `plan()` calls is 8 s, 3^6 is 24 s before pruning; a full `evaluate` per package is 3 to 7 minutes
for six deals, so the enumeration should use `plan()` plus the cap and run `evaluate` only on the shortlist.

**Conditional decisions in state terms.** "Accept D only if A pays early" = a `ConditionalAction(trigger=Receipt(rid=A,
min_fen, by_day=d), then=Commit(D))`: D is evaluated today on `settled(state, A, d)` and the live books, held as a
PROPOSED commitment bound to that trigger, and either activated by the `ReceivePayment` that satisfies the trigger
(re-verified on current books, as the commit hook already does) or expired when day d passes. The mirror of the early-pay
promise FLOW already dates ("paid on or before day 2").

**Kill criterion.** Premature if, over the pilot's first 60 days, fewer than two deals are open at the same time in
most weeks, or the greedy `evaluate_many` order picks the same packages as the enumeration in every case that occurs.

## 3. Optionality and shadow cost

Capacities in the engine's terms, on the golden books:

| Capacity | Definition | Day 0 | Day 34 |
| --- | --- | --- | --- |
| Liquidity headroom today | `cash_fen − min_cash_fen` | ¥100,000 | ¥0 |
| Lowest projected headroom | `min(closing) − floor` on the no-funding conservative trajectory | −¥405,000 (day 30), first breach day 12 | −¥200,000 (day 42) |
| After the standing plan | same with `plan().actions` | ¥0 on day 30 | plan needs approval (32.5% on a 10-day advance) |
| Concession capacity | `max_aggregate − Σ forward_concessions` | ¥5,000 (100%) | ¥5,000 (Option A booked ¥0) |
| Borrowing capacity | `Σ (limit − drawn)` of committed facilities, less the standing plan | line ¥0, FAC-IF ¥95,000 | line ¥13.80, FAC-IF ¥350,000 |
| Receivable-finance capacity | 80% of open confirmed faces landing before due, capped by the IF limit | ¥336,000 (plan uses ¥255,000) | ¥802,240, capped at ¥350,000 |
| Concentration | share of open receivables per buyer | BUYER-1 100% | BUYER-1 100% (¥1,002,800) |

**Marginal value of liquidity** = Δ `plan().total_cost_fen` for Δ cash today: ¥89.10 per ¥10,000 for the first
¥300,000 (the invoice-financing cost share for one 30-day period, 0.8911%), ¥84.15 per ¥10,000 for the next ¥105,000
(the line's share), zero beyond the ¥405,000 need. It is day-specific: ¥50,000 more going out on day 12 costs ¥840.07;
¥100,000 more on day 47 costs nothing (cash is ¥629,960 that day). **Shadow price of the forward budget:** the engine
can say what a yuan of budget buys (1/1,621.79 of a day of terms on this buyer, or ¥80 of rebate base at 1.25%, or that
one 0.05% price step is worth ¥2,730 of it), not what it is worth in profit. Those are the shadow prices worth
showing, as sentences on the relevant card, not as a score.

Sentences like "this deal consumes 72% of your remaining concession capacity" add value where the capacity is a hard
cap the owner set (the budget: "this rebate uses ¥2,500 of the ¥5,000 you allowed this year; Foshan's ask would need
¥28,326.92") and add complexity everywhere else (a percentage of financeable receivables means nothing to an owner;
the engine already says "cost ¥X, cure ¥Y, needs your approval"). Place: Deals (the budget line beside a verdict), Cash &
funding (headroom and facility room, already shown), nowhere else.

## 4. Collections prioritisation

**Marginal value of a collection** = cost of the standing plan on current books − cost of the plan on
`settled(state, rid, day)` (cash credited today, or the receipt moved to day d), plus the breach days and alerts that
disappear. Each point is one `plan()` (33 ms) and one `alerts()` (4 ms).

Day 0 (one receivable): RCV-A ¥420,000 due day 32 is worth ¥3,113.93 if it arrives by day 12 (no funding needed),
¥1,785.91 by day 20, ¥585.10 by day 25, ¥26.30 by day 31; a partial ¥100,000 today is worth ¥891.09, ¥257,200 is worth
¥2,284.63. The curve is linear in amount at about ¥89 per ¥10,000 per 30 days until the need is gone.

Day 34 (three open receivables, all Foshan; need ¥200,000, cure ¥1,706.10 needing approval, breach day 42):

| Rank | Receivable | If collected | Saving | Breach | Realistic action | Why |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | RCV-A residual ¥162,800, due day 32, 2 days late | today | ¥1,374.61 | stays (¥37,200 to cure, ¥331.49, still needs approval) | **call now; escalate by day 39** (the last day an advance can be requested to land before day 42) | it is owed; no discount is ever offered on an overdue invoice; clears the past-due alert |
| 2 | RI:BUYER-1:2 ¥420,000, due day 47 | by day 42 | ¥1,706.10 | gone | **offer early payment** on ¥200,000 at ≤ 0.40%, or finance it | at 0.40% (¥800) it beats the cure by ¥888.28; 0.85% (¥1,700) is ¥24.20 dearer; whole face at 0.40% saves ¥26.10, 0.45% is dearer |
| 3 | RI:BUYER-1:32 ¥420,000, due day 77 | by day 42 | ¥1,706.10 | gone | **wait**; it is the cure's collateral | 35 days before due no buyer pays without a discount above the break-even; the plan advances ¥80,000 on it |

**Action set and when each wins.** Call now: an invoice past due (deterministic, free). Reminder: due within the
breach episode and not promised. Offer early payment: due after the first breach day, and discount × face settled <
the cure it replaces (the plan comparison, not the 30-day break-even: the cure here is ¥1,706.10 on ¥200,000 of need,
so the whole-face ceiling is 0.40% while the ¥200,000 portion bears 0.85%). Finance instead: the owner will not
discount, or the buyer is slow and the advance lands before the breach (day 37 against day 42). Wait: due beyond the
episode. Escalate: a lapsed promise (`reconcile().lapsed_promises`) or days late past an owner threshold.

**Missing inputs** and the recommended source: payment probability and expected delay → observed days-late per buyer
from the ledger's `ReceivePayment` entries against due days (nothing aggregates them yet) plus the owner's promised
date, deterministic; dispute status → an owner flag on the receivable (a new field; FAILED exists but nothing sets it);
importance → not needed for the cash ranking, shown as the owner's tag; effort → ignore (a call costs minutes). No
probability model: the conservative projection already assumes a late buyer pays nothing, which is the right default for
a reserve rule.

**Kill criterion.** If on pilot books the ranking by marginal value equals "largest overdue amount first" in every
week, the engine adds a number but no decision; keep only the early-pay-versus-finance comparison.

## 5. Adjacent ideas (section 11 of the brief) and one stronger idea

Score = quick 1 to 5 judgement before section 10's full scoring.

- **True customer profitability.** Value: high for the owner, but FLOW has no revenue, margin or cost of serving; it
  can supply only the funding cost of a buyer's terms (¥1,871.30 per invoice for 15 days) and concessions booked. Reuse:
  `value_concessions`, `terms_in_force`. Missing: everything from the accounting system. Score 2.
- **Trade-credit budget.** The forward budget is already a trade-credit budget in cost terms; a budget in exposure
  terms (days × face) would be the pro-forma extra receivables (¥140,000 at 55 days). Reuse: `extension_pro_forma`.
  Missing: an owner cap in exposure units. Score 3: a small addition to the mandate, high explainability.
- **Liquidity capacity allocation.** "Who gets the ¥5,000 and the ¥95,000 of cure room" is section 2's knapsack;
  it is the portfolio. Score 2 on its own.
- **Multi-action liquidity planner.** The router already mixes draws, advances and early pay; adding collections and
  concessions as actions is section 6's single kernel. Score 3, as the shared primitive rather than a product.
- **Liquidity tripwires.** `alerts()` has RESERVE_BREACH_AHEAD, HEADROOM_LOW, COVENANT_HEADROOM_LOW, CLEAN_DOWN_AT_RISK,
  CONCESSIONS_NEAR_CAP; what is missing is owner-set thresholds and "what would trip it" (¥50,000 more on day 12 trips
  nothing; ¥100,000 needs an advance that cannot run today). Reuse: `plan()` on a flow copy. Score 3.
- **Stress-to-action.** "If Foshan pays 15 days late, the plan becomes X" is `settled(state, rid, due + 15)` and
  `plan()`; on day 34 a 10-day delay of RI:BUYER-1:2 leaves the ¥200,000 gap as it is (the breach is already assumed).
  Reuse: everything. Missing: nothing. Score 4, as a row on the Cash page.
- **Mandate optimisation.** Which budget or reserve would admit the deals the owner wanted: a sweep over mandate
  copies (the ¥5,000 budget needs to be ¥8,108.97 for one 5-day step). Dangerous: the mandate is the owner's safety
  rule and the agent must never propose loosening it unprompted. Score 1 as a feature, 3 as an owner-only report.
- **Decision review / learning ledger.** The hash-chained log has every verdict and operation; what is missing is the
  outcome column (did the buyer pay on the promised day; `reconcile()` knows). Reuse: ledger, reconciliation. Score 3;
  cheap and it feeds the days-late input of section 4.
- **Buyer behaviour model.** Days-late and promise-kept rates per buyer from the ledger. No ML; a per-buyer average is
  enough for the first year. Score 3, as data for 4 and 8, not a feature.
- **Commercial capacity score.** A composite of the capacities in section 3. Composite scores hide the wall that
  binds; the engine names it. Score 1.
- **Concentration optimisation.** 100% Foshan in the fixture; FLOW can show it, cannot change it. Score 1.
- **Funding capacity reservation.** Reserve FAC-IF room for a known future gap so a deal today does not consume it:
  `cure_state` already deducts the standing plan's use (¥255,000). Making reservations explicit is small. Score 3.
- **Cash value of a negotiation.** C0 − C1 for the package against the status quo (EX01's Option A saves ¥86.16;
  collecting RCV-A by day 12 saves ¥3,113.93). Reuse: ADR-0007's comparison. Score 4: it is the "money impact" line
  of every answer in section 9.
- **Conditional deals.** Section 2.3. Reuse: commitments' lifecycle, the promise dating. Missing: `ConditionalAction`
  and a trigger evaluation in the clock. Score 3; valuable, needs a state-machine change.
- **Stronger idea found: the cash price curve.** The marginal value of ¥10,000 on each day of the horizon (¥89.10 before
  day 32, ¥84.15 on the line, ¥0 after day 47 on day-0 books) is one `plan()` per day and makes every other question
  commensurable: an early-pay discount, a terms extension, a collection and a draw are all "cash on day d at price p".
  It is the number behind the envelope's break-even, the collections ranking and the funding plan. Score 4 as the shared
  primitive; shown as one sentence ("cash before day 32 is worth 0.89% to you; after day 47 nothing").

## 6. One engine or three

The engine is already "state + candidate actions + constraints + cost" for funding (the router's search over slots)
and "state + one package + constraints" for offers (the verifier), and the three capabilities above were all computed
with those two calls on `model_copy` states. A general "best feasible action set" that mixes commercial and funding
actions across deals would be an optimiser over a black-box projection: unexplainable (INVARIANT 13 wants every number
traceable to a formula) and unnecessary at n ≤ 6. **Verdict: one kernel, three thin questions.** Keep `evaluate`,
`plan`, `project` and `alerts` as they are; add no optimiser.

Shared primitives the three questions need, against what exists: feasibility (`evaluate` outcome and codes, `plan().
admissible`: exists); financial capacity (section 3's table: scattered, needs one read-only `Capacity` view); resource
consumption (a package's budget use, facility use, cure room use: computed inside the verifier, not returned); marginal
economic value (C1 − C0 and the collection delta: computed ad hoc in three places); opportunity cost (the cash price
curve); action alternatives (counters and comparison rows: exist, per deal only).

Smallest set of new types, four: `CandidatePackage` (buyer id + obligations, with no inbound offer; `WhatIfParams`
generalised past the one buyer with a recurring invoice), `Capacity` (the seven rows of section 3 with their formulas),
`MarginalImpact` (two books in, the delta of need, cost, first breach, lowest headroom, budget use and approval flags
out), and `ScenarioState` (a labelled `model_copy` with its assumption: "RCV-A received day 20", "60-day terms"). A fifth,
`ConditionalAction`, only if conditional deals go ahead.

## 7. The objective function

Lexicographic, and it already is: the verifier orders hard codes (REJECT) before price codes (COUNTER) before the
mandate's tiers (NEEDS_OWNER_APPROVAL) before ACCEPT; the router ranks (cannot run today, needs approval, cost, legs,
peak debt). Recommend keeping that order for every new capability: never breach the reserve, covenants or caps; respect
the mandate (tiers, APR ceiling, owner constraints); then minimise economic cost; then prefer the package that leaves
more capacity, as a tie-break shown in words ("also leaves ¥95,000 of financing room"), never as a weight. Owner-weighted
utility fails explainability (a weight is a number the owner cannot audit) and safety (a weight can trade a breach
against value); the owner's preferences enter as constraints (`OwnerConstraints`: at most 0.85%, no forward
concessions, terms at most 50 days), which is the repo's existing pattern.

"Economic value" in the engine's terms is cost avoided, not profit: interest + fees + discounts posted over the horizon
under the router's plan (C1 − C0, ADR-0007), plus the forward value of concessions at the marginal rate over the
concession window, plus FIRM gains netted. Contribution, revenue and the value of the relationship are not modelled;
every ranking FLOW produces is therefore "cheapest safe way to do what you choose to do", and the owner chooses.

## 8. Uncertainty

| Idea | Uncertain input | Use |
| --- | --- | --- |
| Envelope | none on the supplier side; buyer acceptance | deterministic; acceptance is the buyer's, not predicted |
| Portfolio | which deals close; delays | enumerate; delay as a `ScenarioState`, not a probability |
| Collections | payment timing, disputes | observed days-late per buyer and owner promise dates; conservative default (late pays nothing) |
| Stress-to-action | the stress itself | owner-chosen scenario bands (5, 15, 30 days late) |
| Rebate value | order volume | counted at maximum (CONTINGENT), as today |
| Funding | facility approval | pending counts zero (INVARIANT 4), as today |

No expected values in anything that decides (INVARIANT 11); scenario bands only for display; no ML, since a per-buyer
days-late average from the ledger is all the first year of data can support and already improves the ranking.

## 9. UX per capability

| | Envelope | Portfolio | Collections |
| --- | --- | --- | --- |
| Question | What can I offer Foshan? | Which of these deals together? | Whom should I chase, and how? |
| Primary answer | 55 days at +0.30%, or 0.85% on ¥257,200; not 60 | Option A on Foshan and one of the two rebates, not both | Call Foshan for the ¥162,800 today; offer ≤ 0.40% on the ¥420,000 due day 47 or finance it |
| Key reason | 60 days leaves ¥130,000 uncovered on day 60; the budget buys no terms without a price step | the ¥5,000 budget holds ¥3,000 or ¥2,500, not ¥5,500 | the day-42 breach is ¥200,000; the cure costs ¥1,706.10 and needs your approval |
| Money impact | ¥0 or ¥3,027.77 against ¥3,113.93 | ¥841.57 against ¥3,113.93 | ¥1,374.61 and ¥888.28 saved |
| Action | send Option A or B | accept, counter, hold | call; send early-pay offer; run the plan |
| Detail | lever table with walls, cure and approval flags | the enumeration table | per-receivable delta, days late, promise status |
| Lives in | Deals, a "Before they ask" card beside BuyerAsks; a chat intent | Deals, inbox and ActiveCommitments; Home DecisionsBlock | Receivables (late-first table gains a "worth" column and the action); Home ReceivablesBlock |
| Persona | owner; sales reads it | owner | owner; AR reads it |

Role views are scope, not value, at this size: the owner is the CFO, the salesperson and the collector on most pilot
SMEs, and the mandate gives authority to one person. Give the owner the three cards on the existing pages; a share
link to one card (read-only, numbers already server-formatted) covers sales and AR without a role model.

## 10. Scores, kill criteria and a first ranking

Section 13 criteria, 1 to 5 (positive: CV customer value, Fq frequency, DI decision impact, Df differentiation, Ft fit,
Fs feasibility, DA data availability, Ex explainability, Dm demo value, Pl pilot value, Rv revenue; negative, higher
is worse: Cx complexity, AS attack surface, UD unproven data, UX complexity, RL liability). Net = Σ positive − Σ negative.

| Candidate | CV | Fq | DI | Df | Ft | Fs | DA | Ex | Dm | Pl | Rv | Cx | AS | UD | UX | RL | Net | Judgment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Envelope (approved packages + zone) | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 4 | 2 | 1 | 1 | 2 | 1 | 45 | the counters already are it; 22 evaluations, one card |
| Collections ranking + early-pay vs finance | 4 | 5 | 4 | 4 | 5 | 5 | 4 | 5 | 4 | 5 | 3 | 2 | 1 | 2 | 2 | 1 | 40 | one `plan()` per receivable; days-late needs a small ledger read |
| Cash value of a negotiation / cash price curve | 4 | 5 | 3 | 4 | 5 | 5 | 5 | 5 | 4 | 4 | 2 | 1 | 1 | 1 | 1 | 1 | 41 | a sentence on every card; the shared primitive |
| Stress-to-action | 4 | 3 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 4 | 2 | 1 | 1 | 1 | 2 | 1 | 38 | a row on Cash; no new type |
| Tripwires with owner thresholds | 3 | 4 | 3 | 2 | 5 | 5 | 5 | 5 | 2 | 4 | 2 | 1 | 1 | 1 | 1 | 1 | 35 | alerts exist; thresholds are mandate fields |
| Learning ledger (outcome column) | 3 | 3 | 2 | 3 | 5 | 4 | 4 | 5 | 2 | 4 | 2 | 2 | 1 | 1 | 1 | 1 | 31 | feeds days-late; no decision of its own |
| Funding capacity reservation | 3 | 2 | 3 | 3 | 5 | 4 | 5 | 4 | 2 | 3 | 1 | 2 | 1 | 1 | 2 | 1 | 28 | `cure_state` half does it |
| Trade-credit budget (exposure units) | 3 | 2 | 3 | 3 | 4 | 4 | 5 | 4 | 2 | 3 | 2 | 2 | 1 | 1 | 2 | 1 | 28 | a second cap the owner must set |
| Conditional deals | 4 | 2 | 4 | 5 | 3 | 3 | 4 | 4 | 4 | 3 | 2 | 4 | 2 | 1 | 3 | 2 | 26 | needs a trigger in the clock and lifecycle |
| Portfolio enumeration | 3 | 2 | 4 | 4 | 4 | 4 | 4 | 3 | 4 | 2 | 3 | 3 | 1 | 2 | 4 | 1 | 26 | value not modelled; budget knapsack is the real content |
| Buyer behaviour (days-late averages) | 3 | 3 | 2 | 2 | 4 | 4 | 3 | 4 | 1 | 3 | 1 | 2 | 1 | 3 | 1 | 1 | 22 | data for others, not a feature |
| Multi-action liquidity planner | 3 | 2 | 3 | 3 | 3 | 3 | 4 | 2 | 3 | 2 | 2 | 4 | 2 | 2 | 3 | 1 | 18 | the one-engine temptation |
| Liquidity capacity allocation | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 3 | 2 | 2 | 1 | 3 | 1 | 2 | 3 | 1 | 18 | is the portfolio |
| Mandate optimisation (owner report) | 3 | 1 | 3 | 3 | 3 | 4 | 5 | 4 | 2 | 2 | 1 | 2 | 3 | 1 | 2 | 4 | 19 | agent must never propose loosening |
| Customer profitability | 4 | 2 | 3 | 2 | 1 | 2 | 1 | 3 | 3 | 2 | 3 | 4 | 2 | 5 | 3 | 2 | 10 | needs the accounting system |
| Concentration optimisation | 2 | 1 | 2 | 1 | 2 | 3 | 5 | 4 | 1 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 16 | show, cannot act |
| Commercial capacity score | 1 | 2 | 1 | 2 | 2 | 4 | 5 | 1 | 2 | 1 | 1 | 2 | 1 | 2 | 3 | 1 | 11 | hides the binding wall |

**Kill criteria.** Envelope: killed if, in the pilot's first ten real offers, the owner's chosen response was outside
the zone or ignored the packages more than half the time, or if fewer than half of the pilot's buyers have a recurring
invoice (no terms lever to value). Collections: killed if the marginal-value order equals the overdue-amount order every
week, or no pilot has more than two open receivables at once. Cash price curve: killed if owners read "0.89%" as a rate
they are charged (a comprehension test on three owners). Portfolio: section 2's criterion. Stress-to-action and
tripwires: killed if the alerts page already answers the owner's question in the cold-user walk. Conditional deals:
killed unless a pilot owner asks for one unprompted.

**First ranking.** 1 Envelope (45); 2 cash value of a negotiation as the shared money line (41); 3 collections (40);
4 stress-to-action (38); 5 tripwires (35); 6 learning ledger (31); then reservation and the exposure budget (28), and
conditional deals and the portfolio (26) as later candidates. Judgment, not the total: 1 and 3 are the two user
questions FLOW does not yet answer; 2 is the primitive both need; 4 to 6 are small additions to pages that exist; the
portfolio waits for evidence that deals overlap.
