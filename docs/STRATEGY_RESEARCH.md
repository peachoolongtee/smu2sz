# FLOW strategy research: synthesis

Ticket #45 of wayfinder map #39, 8 October 2026. The deliverables A to L of the owner's strategy brief (section 33),
written from four documents on the research branches, all copied beside this one under `docs/research/strategy/`:
`01-repo-primitives.md` (ticket #40, what the engine already holds), `02-market-map.md` (#41, 80 sources),
`03-deep-dives.md` (#42, the maths on the golden books), `04-spikes.md` (#43, three read-only scripts that ran the
engine). The owner's direction decisions (#44) are fixed inputs here, not questions.

**Three rules of this document.** Every money figure is quoted from one of the four documents and never recomputed.
Where the spikes' figures differ from the deep dive, the spike is the truth, because it ran the engine on the real
books; the correction is said where the figure is quoted and every correction is listed once in section H. Nothing in
this document authorises a production build (the brief's section 34): the recommended capabilities are read-only
first (section 28), behind feature flags, on the branches the roadmap names; nothing merges into `dev` from this map.

Vocabulary is CONTEXT.md's; the quantities are `docs/FINANCIAL_SEMANTICS.md`'s. "Passes" means the verifier's outcome
is ACCEPT or NEEDS_OWNER_APPROVAL; a curable RESERVE_BREACH is not a hard violation, AGG_CONCESSION_EXCEEDED is.
"Posted cost" is interest plus fees plus discounts the trajectory posts under the router's plan (ADR-0007's C1 and
C0). The golden books are `fixtures/scenarios/golden_sme.json`: cash ¥400,000, floor ¥300,000, one buyer with a
¥420,000 monthly invoice on 45-day terms (Foshan, BUYER-1), a ¥5,000 forward-concession budget, and a standing plan
that needs ¥405,000 and costs ¥3,113.93.

## The owner's decisions (fixed inputs, from #44)

1. "Commercial capital allocation" is the internal principle and the one-line explanation for judges and investors;
   FLOW is sold under existing categories (SME cash flow and working capital; AR and collections; 供应链金融) with the
   owner's words on the surface.
2. Owner and CFO remain the user; the Safe Deal Envelope answers the salesperson's question on the buyer's thread in
   Deals; no separate role views.
3. The objective is lexicographic: never breach hard safety; respect the mandate; lowest posted cost plus concession
   value; optionality as a worded tie-break. Owner preferences enter as constraints, never as weights.
4. To a read-only MVP on one kernel (evaluate / plan / project / alerts) with four new types (CandidatePackage,
   Capacity, MarginalImpact, ScenarioState): the envelope as approved packages first with the zone as detail, the cash
   price curve, and collections marginal value with its action set. The multi-deal portfolio is VALIDATE FIRST.
5. Validation is a fixture backtest plus a shadow pilot with one or two reachable SMEs; the five interview sets run
   first if none is reachable. The owner names the SMEs and the month.
6. The deep dive's kill criteria stand as written.

## A. Product opportunity map

Score is the deep dive's section-13 net (Σ positive − Σ negative, section J has the columns). Class is this
document's (section J gives the line of judgment per class).

| Capability | The owner's question | Reuses | Lacks | Score | Class |
| --- | --- | --- | --- | --- | --- |
| Safe Deal Envelope (approved packages, the zone as detail) | What can I offer Foshan before they ask? | the what-if builder, `evaluate`, the counters (Option A and B rules), `value_concessions`, `smallest_step_covering`, `counters.infeasibility` | a package addressed to a buyer with no inbound offer; a search over the lever grid; a buyer without a recurring invoice has no terms lever | 45 | BUILD NOW |
| Cash price curve (marginal value of earlier cash, ¥ per ¥10,000 per 30 days) | What is cash on day d worth to me? | `plan()` on a flow copy, `project` | a `ScenarioState` with a labelled assumption; a sentence on three pages | 41 | BUILD NOW |
| Collections marginal value with its action set | Whom should I chase first, and how? | `plan()`, `alerts()`, `reconcile()`, `_early_pay_vs_plan`, `past_due_invoices()` | observed days-late per buyer (the ledger holds it, nothing aggregates it); a dispute flag | 40 | BUILD NOW |
| Stress-to-action | If Foshan pays 15 days late, what happens and what do I do? | `settled(state, rid, due + d)` and `plan()`; the what-if sandbox | nothing | 38 | PROTOTYPE NEXT |
| Liquidity tripwires with owner thresholds | What would trip my reserve, and when? | `alerts()` (RESERVE_BREACH_AHEAD, HEADROOM_LOW, COVENANT_HEADROOM_LOW, CLEAN_DOWN_AT_RISK, CONCESSIONS_NEAR_CAP) | owner-set thresholds (mandate fields); "what would trip it" | 35 | PROTOTYPE NEXT |
| Learning ledger (outcome column) | Did what FLOW said turn out right? | the hash-chained log, `reconcile()` | the outcome column (paid on the promised day; chosen response versus the envelope) | 31 | PROTOTYPE NEXT (the pilot's instrument) |
| Funding capacity reservation | Will this deal eat the room I need next month? | `cure_state` already deducts the standing plan's use (¥255,000) | explicit reservations | 28 | POST-PILOT |
| Trade-credit budget in exposure units | How much more credit can I carry? | `extension_pro_forma` (¥140,000 of extra receivables at 55 days, from 03; not checked by the spike) | an owner cap in exposure units, a second cap to set | 28 | POST-PILOT |
| Conditional deals | Accept D only if A pays early | commitments' lifecycle, the promise dating | `ConditionalAction` and a trigger evaluated by the clock | 26 | VALIDATE FIRST |
| Multi-deal portfolio (enumeration with pruning) | Which of these deals together? | `books.with_()`, `plan()`, the verifier's candidates, `evaluate_many` | contribution or customer value; evidence that deals overlap | 26 | VALIDATE FIRST |
| Buyer behaviour (days-late averages) | How late does Foshan really pay? | the ledger's `ReceivePayment` entries against due days | the aggregation; a year of data | 22 | VALIDATE FIRST (data, not a feature) |
| Mandate optimisation (owner-only report) | Which budget would have admitted the deals I wanted? | a sweep over mandate copies (the ¥5,000 budget needs to be ¥8,108.97 for one 5-day step) | nothing technical; the agent must never propose loosening | 19 | DO NOT BUILD (as a feature) |
| Multi-action liquidity planner | One optimiser over everything | the router | an objective across deals; explainability | 18 | DO NOT BUILD |
| Liquidity capacity allocation | Who gets the ¥5,000 and the ¥95,000 of cure room? | the portfolio | it is the portfolio | 18 | DO NOT BUILD (folded into the portfolio) |
| Concentration optimisation | Am I too exposed to Foshan? | the share of open receivables (100% BUYER-1) | any lever; FLOW can show it, not change it | 16 | DO NOT BUILD |
| Commercial capacity score | One number for how much room I have | the seven capacities | a composite hides the wall that binds; the engine names it | 11 | DO NOT BUILD |
| True customer profitability | Is Foshan worth it? | `value_concessions`, `terms_in_force` (¥1,871.30 per invoice for 15 days) | revenue, margin, cost to serve: the accounting system | 10 | DO NOT BUILD |

## B. Deep dives on the three starting ideas

### B.1 The Safe Deal Envelope

**Worked numbers (Foshan, day-0 golden books).** The lever maxima the verifier derives, one lever at a time; the
deep dive's figures, confirmed by the spike where it says so.

| Lever alone | Largest that passes | Wall | What the next step fails with |
| --- | --- | --- | --- |
| Terms | 45 days (no extension) | forward budget | 50 days books ¥8,108.97 over 13 invoices against ¥5,000: AGG_CONCESSION_EXCEEDED |
| Terms, budget ignored | 55 days | liquidity, curable: ¥1,570.36 on FAC-IF, day 47, "cannot run today" | 60 days: RESERVE_BREACH on day 47, not curable (03 wrote "¥130,000 on day 60", the deepest shortfall; the verifier's violation day is 47) |
| Terms with the compensating price | 55 days at 0.25% (spike; 03 said 0.30%) | liquidity | 60 days at any price up to 1.00%: RESERVE_BREACH, no cure |
| Early pay, whole ¥420,000 | 0.70% | plan comparison | 0.75% × ¥420,000 = ¥3,150 > ¥3,113.93: EARLY_PAY_DEARER_THAN_PLAN |
| Early pay on ¥257,200 (Option A's face) | 0.85% | break-even | 0.90%: DISCOUNT_ABOVE_BREAK_EVEN (C1 ¥3,027.77 against C0 ¥3,113.93 at 0.85%) |
| Rebate on the ¥400,000 next-quarter order | 1.25% (¥5,000 exactly) | forward budget | 1.30% = ¥5,200: AGG |

On the price step the spike corrects the deep dive: 0.30% is the Option B rule, the price that nets the extension's
per-invoice cost (¥1,247.53 at 55 days) to zero, and remains the counter FLOW would send; the smallest price the
verifier passes is 0.25%, because the ¥5,000 budget absorbs the remainder (forward value ¥2,567.95). Likewise 50 days
passes from 0.10% (03: 0.15%), and 60 days with Option A's early payment passes from 0.40% (03: 0.45%).

**How the levers interact.** The nine packages of the deep dive's interaction table reproduce to the fen in the spike:
50 days + 1.25% rebate fails AGG at ¥13,108.97; 55 days + 0.30% passes at ¥0; adding the 1.25% rebate passes at
¥4,837.95 and 1.30% fails at ¥5,037.95; 55 days + 0.30% + 0.85% on ¥257,200 passes at ¥0 but the cure becomes
¥2,673.04 instead of ¥1,570.36; 60 days + 0.45% + 0.85% on ¥257,200 passes (the early payment closes the day-47 gap
no cure could); EX01 as offered fails at ¥28,326.92 with cure ¥2,406.67. The spike went further than the deep dive
tested: with Option A's early payment in the package the verifier passes terms up to 80 days (75 at 0.80%, 80 at
0.95%, cure ¥4,009.57, every cure "cannot run today", the cure needing the owner's approval from 65 days); 85 days
fails AGG at ¥10,271.78. And the whole-invoice early payment at its standalone maximum (0.70%) never passes together
with any extension (EARLY_PAY_DEARER_THAN_PLAN); a smaller whole-face rate inside a package was not searched.

Three lessons from the deep dive stand. The forward budget is one pool, so a price step of 0.05% buys ¥2,730 of
budget and the price is the lever that buys the rebate. Liquidity is not additive: the early payment changes which
cure is possible, in both directions. A maximum per lever misleads: "up to 60 days" is true with Option A's cash and
false without it; "up to 0.85%" is true for ¥257,200 and false for the whole invoice. The envelope is a feasible
region in four levers cut by three walls (budget, cure room, break-even), and the walls move with the books: on the
day-34 books the line has ¥13.80 left and headroom is ¥0, so no terms extension passes at all.

**Output form.** Approved packages first, the zone as detail. The counters are approved packages by construction
(each passes its own re-check, FINANCIAL_SEMANTICS §7a); the zone is a what-if sweep. One-dimensional thresholds are
wrong; a continuous region is right but unreadable; `per_buyer_caps_fen` is a mandate input, not a derivation.

**UX.** Question: "What can I offer Foshan?" Primary answer: "Up to 55-day terms if the price rises 0.30%, or early
payment at up to 0.85% on ¥257,200; no rebate above 1.25%; not 60 days without an early payment." Key reason: "60
days leaves the day-47 shortfall with no cure; the ¥5,000 budget buys no terms without a price step." Money impact:
"Cost to you ¥0 (Option B) or ¥3,027.77 posted (Option A); the standing plan without a deal costs ¥3,113.93." Action:
"Send Option A or B" (the existing counter cards, before a message arrives). Detail: the lever table with the wall
each hits, the cure and its approval flag; the terms × price zone. Where: Deals, a "Before they ask" card beside
BuyerAsks on the buyer's thread; later a chat intent. Persona: the owner; sales reads it (decision 2).

**Kill criterion (accepted).** Killed if, in the pilot's first ten real offers, the owner's chosen response was outside
the zone or ignored the packages more than half the time, or if fewer than half the pilot's buyers have a recurring
invoice.

**Spike's verdict.** Confirmed in every figure the deep dive stated; corrected on the price floor (0.25% and 0.10%),
the 60-day step with Option A (0.40%), the breach day (47), the longest package (80 days, not 60), and the cost:
51 verifier runs in 5.4 s cold for the maxima and the zone, 185 runs in 29.7 s with 30 approved packages (03: 22
evaluations in 1.6 s warm, the five maxima only). Bisection agreed with the exhaustive 273-point scan on this fixture;
nothing in the engine guarantees monotone levers elsewhere, so a build must keep the neighbour check.

### B.2 The multi-deal portfolio

**Worked numbers (EX01 with its counters, EX08A, EX08B; day 0).** Enumeration over accept / counter / reject, each
package re-planned on `books.with_(chosen)`:

| Portfolio | Need | Funding cost | Posted cost | Budget used | Feasible |
| --- | --- | --- | --- | --- | --- |
| EX01 Option A, reject, reject | ¥149,986.20 | ¥841.57 | ¥3,027.77 | ¥0 | yes, best |
| status quo | ¥405,000 | ¥3,113.93 | ¥3,113.93 | ¥0 | yes |
| EX01 Option B, reject, reject | ¥405,000 | ¥3,706.46 | ¥3,706.46 | ¥0 | yes |
| Option A, reject, EX08B | ¥149,986.20 | ¥841.57 | ¥3,027.77 | ¥2,500 | yes |
| Option A, EX08A, reject | ¥149,986.20 | ¥841.57 | ¥3,027.77 | ¥3,000 | yes |
| Option A, EX08A, EX08B | ¥149,986.20 | ¥841.57 | — | ¥5,500 | no (cap ¥5,000) |
| EX01 as asked, any | ¥135,040 | ¥1,468.05 | — | ≥ ¥28,326.92 | no, and not acceptable alone |

The spike adds the posted cost beside the funding cost (03 gave the second only) and ranks by posted cost plus
concession value, so the top order is the deep dive's and rank 4 onward is "fewest concessions first", since a
rebate counts at its maximum. With EX05 and EX06 added, 64 packages: EX06's three extended invoices cost ¥3,873.58 to
fund alone and ¥1,630.53 under Option A, and EX06 stays over the budget at ¥5,613.90. Pruning (drop a package the
verifier will not accept alone; cut a partial choice over the cap; one router call per distinct set of cash-moving
packages) removed 7 of 16 and 46 of 64 packages and changed no result. Runtime: 0.52 s and 0.79 s (1.00 s unpruned),
verifier evaluations included (03: 0.43 s and 1.63 s with one `plan()` per package).

What the content is: the rebates do not touch cash inside the 120-day horizon, so the portfolio here is a knapsack on
the ¥5,000 budget (EX08A or EX08B, not both), and the one real cash interaction is EX01's early payment. The engine
cannot rank EX08A against EX08B because contribution is not modelled; every ranking is "cheapest safe way to do what
you choose to do". Method: enumeration with pruning, not LP or MIP; the cost is a black-box projection, n is small, and
every candidate must pass the same `evaluate` as a single deal, so an optimiser would only propose what enumeration
then verifies. The spike also found that two offers whose counters settle the same invoice (EX02 and EX04 against
EX01's Option A) are refused by the engine (`ObligationError`) and reported as a conflict; no exclusivity rule beyond
that is modelled, and per-buyer caps are implemented but untested (the golden mandate has none).

**The spike's most consequential finding.** The engine's own sequential joint check, `evaluate_many` on the offers
as asked, yields "accept EX08A, reject the rest" at ¥6,113.93, rank 7 of 9 against ¥3,027.77 for the best (14 of 18
with five deals); it takes no counter by design. The deep dive's kill criterion ("premature if the greedy order picks
the same packages as the enumeration in every case") therefore fails on the first fixture set; the other half of the
criterion (fewer than two deals open at once in most pilot weeks) is what the pilot must answer. This is why the
class is VALIDATE FIRST and not DO NOT BUILD.

**UX.** Question: "Which of these deals together?" Primary answer: "Option A on Foshan and one of the two rebates,
not both." Key reason: "the ¥5,000 budget holds ¥3,000 or ¥2,500, not ¥5,500." Money impact: "¥841.57 of funding
against ¥3,113.93 (posted ¥3,027.77)." Action: accept, counter, hold. Detail: the enumeration table with what blocks
the next step up. Where: Deals (inbox and ActiveCommitments) or Home's DecisionsBlock. Persona: the owner.

**Kill criterion (accepted).** Premature if, over the pilot's first 60 days, fewer than two deals are open at the same
time in most weeks, or the greedy order picks the same packages as the enumeration in every case that occurs.

### B.3 Collections prioritisation

**Worked numbers (day-34 books: cash ¥300,000, need ¥200,000, cure ¥1,706.10 needing approval, breach day 42, three
open receivables, all Foshan).** Marginal value of a collection = the standing plan's cost less the cost with the
receipt on a copy of the books, plus the breach days and alerts removed; one `plan()` and one `alerts()` per point.

| Receivable | If received today | Need left | Early-pay ceiling (spike) | Net of the discount | Action |
| --- | --- | --- | --- | --- | --- |
| RCV-A residual ¥162,800, due day 32, 2 days late | saves ¥1,374.61 | ¥37,200 (cost ¥331.49 left, still needs approval) | none: never on an overdue invoice | ¥1,374.61 | call now |
| RI:BUYER-1:2 ¥420,000, due day 47 | saves ¥1,706.10, breach gone | ¥0 | 0.80% on ¥200,000; 0.40% on the whole ¥420,000 | ¥77.58 | offer early pay, or finance it |
| RI:BUYER-1:32 ¥420,000, due day 77 | saves ¥1,706.10, breach gone | ¥0 | 1.20% on ¥200,000; 0.65% on the whole | ¥73.68 | spike: offer early pay; 03: wait (judgment) |

Two corrections from the spike. The deep dive's headline "offer early payment on ¥200,000 at ≤ 0.40%" mixed the two
faces: 0.40% is the ceiling on the whole ¥420,000 (it beats the plan by ¥26.10; 0.45% is dearer by ¥183.90), and
0.80% is the ceiling on ¥200,000; the deep dive's own ¥888.28 (0.40% on ¥200,000 beats the cure) and ¥24.20 (0.85%
dearer) are exact, so 0.40% is a safe rate on ¥200,000, not the ceiling. And the ranking depends on the measure: by
gross marginal value the two coming invoices (¥1,706.10 each) rank above RCV-A (¥1,374.61); net of the discount that
earns it, the deep dive's order returns (RCV-A ¥1,374.61, then ¥77.58, then ¥73.68), and the call is the only action
that is free. The MVP ranks by net value and shows the gross figure beside it. The "wait" on RI:BUYER-1:32 is the
deep dive's judgment (35 days before due no buyer pays without a discount above the break-even); the engine does not
model whether a buyer pays 41 days early, so a build encodes "wait" as a rule on days-to-due, not as an engine output.

Day 0 (one receivable): RCV-A is worth ¥3,113.93 if it arrives by day 12, ¥532.49 if five days early (day 27); the
whole-face early-pay ceiling is 0.70%, and 0.75% on the ¥405,000 the plan covers. The deep dive's partial figures
(¥100,000 today ¥891.09; ¥257,200 ¥2,284.63; by day 20 ¥1,785.91, by day 25 ¥585.10, by day 31 ¥26.30) were not
checked by the spike. New from the spike: RI:BUYER-1:32 received five days early (day 72) costs ¥76.09 more than not,
because the router's cost is not monotone in the receipt date (a ¥10,000 grid, whole-period fees); a build must show a
negative delta as "no saving", never hide it.

**Action set.** Call now: past due (deterministic, free). Reminder: due within the breach episode, not promised.
Offer early payment: due after the first breach day and the discount beats the cure it replaces (the plan comparison,
not the 30-day break-even). Finance instead: the owner will not discount, or the advance lands before the breach.
Wait: due beyond the episode. Escalate: a lapsed promise (`reconcile().lapsed_promises`) or days late past an owner
threshold. Missing inputs and their source: payment timing from observed days-late per buyer in the ledger plus the
owner's promised date (deterministic, no probability model: the conservative projection already assumes a late buyer
pays nothing); a dispute flag on the receivable (new field); importance as the owner's tag, not in the ranking;
effort ignored.

**UX.** Question: "Whom should I chase, and how?" Primary answer: "Call Foshan for the ¥162,800 today; on the
¥420,000 due day 47, offer early payment at up to 0.80% on ¥200,000 (0.40% on the whole) or finance it." Key reason:
"the day-42 breach is ¥200,000; the cure costs ¥1,706.10 and needs your approval." Money impact: "¥1,374.61 avoided by
the call; ¥888.28 saved at 0.40% on ¥200,000 against the cure." Action: call; send the early-pay offer; run the plan.
Detail: per-receivable delta, days late, promise status, the ceiling on each face. Where: Receivables (the late-first
table gains a "worth" column and the action) and Home's ReceivablesBlock. Persona: the owner; AR reads it.

**Kill criterion (accepted).** Killed if the marginal-value order equals the overdue-amount order every week, or no
pilot has more than two open receivables at once; then keep only the early-pay-versus-finance comparison.

**Spike's verdict.** Confirmed: ¥200,000, ¥1,706.10, day 42, ¥1,374.61 and ¥37,200, ¥1,706.10 twice, 0.40% whole-face,
¥888.28 and ¥24.20, ¥3,113.93 by day 12, 0.70%. Corrected: the ceiling on ¥200,000 (0.80%), the gross-versus-net
ranking, the action on RI:BUYER-1:32. Runtime 0.33 s (day 0) and 0.66 s (day 34) without the curve.

## C. Other ideas discovered

**The cash price curve (second overall, 41).** The marginal value of ¥10,000 arriving 30 days earlier, by arrival
day, is one `plan()` pair per day and makes every other question commensurable: an early-pay discount, a terms
extension, a collection and a draw are all "cash on day d at price p". On the day-0 books the spike reads ¥89.11 per
¥10,000 for arrival days 1 to 30 and ¥0 from day 31 (and on day 0 itself, because arrival on day 0 and on day 30 both
serve the day-30 trough); the deep dive's ¥89.10 before day 32 reproduces to the fen within rounding, its ¥84.15 band
(the line's share) is not seen at a ¥10,000 step, and its "¥0 after day 47" is a different definition (cash priced on
a day, not the same cash 30 days earlier), so not a conflict. On the day-34 books, new: ¥178.22 for arrival days 34 to
42, ¥89.12 for 43 to 60, ¥0 from 61. It is the number behind the envelope's break-even, the collections ranking and the
funding plan, and the "money impact" line of every answer. Shown as one sentence ("cash before day 32 is worth 0.89%
to you; after day 47 nothing"), never as a chart of rates. Its kill criterion: owners read "0.89%" as a rate they are
charged (a comprehension test on three owners). Cost: 91 arrival days × 2 plans = 6.8 s on day 0, 3.3 s on day 34; a
build computes the curve at the breach-episode boundaries, not every day, and caches by state version.

**Stress-to-action (38).** "If Foshan pays 15 days late, the plan becomes X" is `settled(state, rid, due + 15)` and
`plan()`; on day 34 a 10-day delay of RI:BUYER-1:2 leaves the ¥200,000 gap as it is because the breach is already
assumed. Reuses everything, lacks nothing; a row on the Cash page with owner-chosen bands (5, 15, 30 days). Existing
stress tools stop at the breaking month; FLOW attaches the cure. Dies if the alerts page already answers the question
in the cold-user walk.

**Tripwires with owner thresholds (35).** `alerts()` already has the episodes; what is missing is owner-set thresholds
(mandate fields) and "what would trip it" (¥50,000 more going out on day 12 trips nothing and costs ¥840.07; ¥100,000
needs an advance that cannot run today). Same kill criterion as stress-to-action.

**Learning ledger (31).** The hash-chained log has every verdict and operation; the missing column is the outcome
(did the buyer pay on the promised day, `reconcile()` knows; what did the owner choose against what the envelope
said). It decides nothing itself, feeds the days-late input of collections, and is the shadow pilot's measuring
instrument, which is why it starts in the 90-day window.

**Funding capacity reservation (28).** Reserve FAC-IF room for a known future gap so a deal today does not consume it;
`cure_state` already deducts the standing plan's ¥255,000. Small, post-pilot.

**Trade-credit budget in exposure units (28).** The forward budget is already a trade-credit budget in cost terms; a
cap in exposure units (days × face: ¥140,000 of extra receivables at 55 days, 03's figure, unchecked) is a second cap
the owner must set. Post-pilot, if the pilot's owners think in exposure rather than cost.

**Conditional deals (26).** "Accept D only if A pays early" is a `ConditionalAction` with a receipt trigger, held as a
PROPOSED commitment and activated by the `ReceivePayment` that satisfies it (re-verified on current books, as the
commit hook does), or expired. The mirror of the early-pay promise FLOW already dates. Needs a trigger in the clock
and a lifecycle change; killed unless a pilot owner asks for one unprompted.

**Ruled out.** True customer profitability (10): FLOW has no revenue, margin or cost to serve, only the funding cost
of a buyer's terms; everything else lives in the accounting system (UD 5, the worst data score in the table). The
commercial capacity score (11): a composite hides the wall that binds, and the engine already names it ("forward
budget", "liquidity (reserve)", "break-even"). Concentration optimisation (16): 100% Foshan in the fixture, FLOW can
show it and cannot change it. Mandate optimisation (19) as a feature: the mandate is the owner's safety rule and the
agent must never propose loosening it unprompted (RL 4); as an owner-only report it can wait. The multi-action
liquidity planner (18): the one-engine temptation, section G.

## D. Competitor and market map

| Product or group | What it decides | How FLOW differs |
| --- | --- | --- |
| Allianz Trade, Coface, Sinosure 中国信保 | the insured credit limit per buyer, from the buyer's grade | FLOW asks what the supplier can afford to offer from its own cash and facilities; the insurer's limit is an input to the envelope |
| Creditsafe; 企查查 / 天眼查 / 启信慧眼 | a recommended limit (启信慧眼: an initial 账期 and 授信额度) from the buyer's risk | one-sided: how much the buyer can bear, not how much the seller can carry |
| HighRadius Credit Cloud, Esker, Serrala | automated low-risk approvals; limit changes; blocked-order release | enterprise, buyer-scoring; FLOW prices the cost of a term for an owner-mandated SME |
| 用友 U8 / 金蝶 K3 Cloud, 精斗云 | credit rating and hard limit blocks inside the ERP | where a Chinese SME's AR lives; FLOW reads from them |
| HighRadius Collections, Sidetrade Aimie, Esker, Billtrust, Quadient (YayPay) | the worklist, by delinquency likelihood and size, on network payment data | FLOW ranks by the receipt's effect on the cash floor and the funding cost; none states a cash-projection or facility-cost objective |
| Tesorio | collections tied to a 13-week forecast | closest; not tied to facilities, cost of funding or a mandate |
| Chaser, Upflow, Agicap CashCollect; 账款管家, 合思 | who and when to chase (SME); reminders | same persona; FLOW ranks by cash consequence and chasing is one lever beside funding and counter-terms |
| Salesforce Revenue Cloud / CPQ; PROS, Vendavo, Zilliant, Pricefx | discount approval routing by tier; pocket-price guidance | payment terms are a field, not a priced cost; no cost-of-capital line found in any public waterfall |
| Kyriba Working Capital | SCF and dynamic discounting programme terms, from the buyer's seat | FLOW is the counterparty's agent and prices the programme against the supplier's facilities |
| Trovata, Nomentia, GTreasury, Agicap, Float, Fathom, Futrli, Finmark | cash visibility and forecasts; Agicap scenarios | they forecast and stop; FLOW's projection is a constraint in a decision wired to a verifier and a router |
| Ramp, Brex, Rho, Mercury | agentic enforcement of a signed spend policy; sweeps | the proof SMEs accept a signed policy enforced by an agent, on the spend side; FLOW is the revenue and funding side |
| C2FO, Taulia, PrimeRevenue, Previse | the clearing price of early payment; the supplier names a rate by judgment | FLOW computes the supplier's reservation rate from its own floor and facility costs: a direct complement |
| Fundbox, Amex Business Blueprint, Kriya; WeBank 微业贷, MYbank 大雁, JD 京保贝 | eligibility and advance | candidate legs in the router; FLOW decides when and how much to draw |
| Zeni, Digits, Puzzle; Runway, Pigment, Datarails | books and projections; planning cadence | their decisions are a by-product of books; FLOW's books are a by-product of decisions |

**The source gap.** No product was found that (a) tells a supplier what terms, discount or rebate it can afford a
named buyer given its own cash projection and facilities, (b) prices payment days as a financing-cost line in a deal,
or (c) ranks collections by their effect on a cash floor and funding cost. This is a source gap, not a proof of
novelty: enterprise vendors' internals are not public, Chinese search was not exhaustive, and a bank RM or a good
credit manager does this in their head.

**Category verdict (decision 1).** "Capital allocation software" resolves to capex and investment portfolio planning
(Copperleaf, Board, Gartner's capital investment management); no vendor or listing uses "commercial capital
allocation"; SME owners do not think of a payment term as capital. Keep it as the internal principle and the one
sentence for judges and investors. Sell under the categories buyers search: SME cash flow and working capital, AR and
collections, 供应链金融 and 应收账款管理 in China, with the owner's words on the surface ("what can I offer", "who to
chase", "am I safe").

**Market numbers that matter.** China: average terms 76 days and delays 65 (141 days from delivery to cash), only 65%
now grant terms (Coface 2025); 35% of B2B credit sales overdue, 4% bad debt (Atradius 2025); industrial receivables
¥26.55tn, collection period 76.4 days (NBS, Jan–Feb 2026); large enterprises must pay SMEs within 60 days since 1 June
2025. Europe: 56% of executives accepted unfavourable terms to protect relationships (Intrum 2025, 9,150 executives).
UK: late payment costs £11bn a year, 38 closures a day, 86 hours a year chasing per affected business (DBT 2025).
Sales versus finance: 47% of sales have up to 10 deals a month rejected by finance, 44% would chase habitual late
payers, 21% have no formal credit policy and 42% do not understand theirs (Creditsafe). Forecasting: over 60% of
treasurers call it their hardest task, 96% of FP&A use spreadsheets weekly (AFP 2025). The strongest pains: terms
accepted to protect the relationship after a stale-spreadsheet loop; deals accepted one at a time until the line hits
95%; the aged-debtor sort is the collections policy.

**Budget owner.** The SME owner (in China the 老板 negotiates big accounts personally); the CFO in mid-market; the
finance manager or CFO for collections software; sales ops owns the CPQ budget only in larger firms.

## E. User workflow map

**Envelope, before.** A buyer's procurement asks the sales manager for 60 days instead of 45, a 1.2% early-payment
discount on the current invoice and a 1% rebate next quarter. Sales forwards it to the owner on WeChat ("our
second-largest account"). The owner asks finance "can we take 60 days?"; finance opens a cash spreadsheet last
refreshed two weeks ago and says "tight in November". Nobody prices the rebate or notices the discount is about 14.6% a
year. The owner calls the bank RM, who asks for the accounts. Three days pass; the buyer chases. The owner accepts to
protect the relationship, tells finance afterwards; in November the reserve is breached and the line is drawn at the
worst rate. Four handoffs, three days, one incomplete calculation, the credit policy not consulted.

**Envelope, after.** The same message lands in FLOW. It types the three obligations, prices them against the books and
the committed facilities, verifies them against the mandate (the concession cost exceeds the ¥5,000 cap; the reserve
breaks on day 47), and offers the two counters the mandate allows with the funding plan if the buyer insists. With the
envelope, the card is there before the message: sales sends the counter the same afternoon with a reason the buyer
can read; the owner approves only the piece above the mandate; finance sees the commitment appear in the books with
the funding leg scheduled. One handoff, hours, no manual calculation, policy enforced by construction.

**Portfolio, before.** Late October; three orders in a week: ¥1.2m from the anchor buyer on 90 days, ¥400k from a new
buyer on 30 days with a 3% discount, a ¥700k tender needing a bond. Each salesperson accepts because each alone fits.
Finance learns of all three at month-end, finds the line at 95% by December, asks the owner to delay the tender's
materials; sales learns the delay from the customer. Three parallel judgments, no shared view of commitments,
month-end as the bottleneck.

**Portfolio, after.** Each order is a candidate with typed terms and a projected cash path. FLOW shows the three
against the same trajectory, mandate and budget: all three breach in December; the anchor order alone is fine; the new
buyer's discount is dearer than financing; the tender is fine if the anchor's funding runs on the invoice. It proposes
the set, the order of acceptance and the funding legs, flags what needs the owner. Sales gets the answer before
promising dates; the month-end surprise disappears because commitments enter the books when accepted.

**Collections, before.** Monday. The AR clerk exports the aged-debtor report sorted by amount, sends the standard
reminder to everything over seven days and phones the three largest balances, one of which is the anchor buyer that
always pays on day 75. Sales complains. The ¥180k invoice from a buyer whose litigation record changed last week is on
page two. Nobody connects the list to the line being drawn on Thursday unless ¥200k lands. Thursday, it is drawn. The
sort order is the policy; cash timing, buyer risk and sales context sit in three places.

**Collections, after.** FLOW ranks open receivables by what each receipt does to the projected floor and the planned
draw, with observed payment behaviour, and says why: "chase B first: ¥180k due in 4 days averts Thursday's ¥200k draw
(¥841 saved); A pays on day 75 historically, do not chase before day 70; C's risk changed, confirm the invoice is
accepted." The clerk works a list of five with reasons; sales sees the anchor buyer is left alone and why. The chase
and the funding decision are the same decision.

## F. Shared technical primitives

**The kernel.** `evaluate` (the verifier: one package against the books and the mandate, with counters that pass their
own re-check), `plan` (the router: the cheapest admissible funding mix within the bounded search), `project` (the
conservative trajectory that decides) and `alerts` (the episodes and their cures). All three spikes computed their
answers with these four calls on `model_copy` states and nothing else; the deep dive's verdict "one kernel, three thin
questions" held under execution.

| New type | What it is | Existing code it generalises | What is genuinely new |
| --- | --- | --- | --- |
| `CandidatePackage` | a buyer id plus typed obligations with no inbound offer | `WhatIfParams` and `whatif.offer.build` (bound to the one buyer with a recurring invoice and an open receivable), `CounterProposal.obligations` | a package the system originates for a named buyer; the sweep over the lever grid with the neighbour check; refusing a buyer with no lever to value |
| `Capacity` | the seven capacities with their formulas: headroom today, lowest projected headroom, after the standing plan, concession capacity, borrowing capacity, receivable-finance capacity, concentration | scattered: `cash_fen − min_cash_fen`, `max_aggregate − Σ forward_concessions`, `limit − drawn`, `covenant_limits`, `cure_state` | one read-only view; the wall each lever hits, named |
| `MarginalImpact` | two books in; the delta of need, posted cost, first breach day, lowest headroom, budget use and approval flags out | `cost_fen` on a cure leg, ADR-0007's C1 − C0, `induced_breach_days`, `ConcessionValue.per_invoice_fen`, the spikes' "saved" and "beats by" columns | one return type for a delta that three places compute ad hoc today; a negative delta is a legitimate value (−¥76.09), never clamped |
| `ScenarioState` | a labelled `model_copy` with its assumption: "RCV-A received day 20", "60-day terms", "¥10,000 arrives day d" | `project()` on copies in what-if, `cure_state`, `expected_state`, the spikes' labelled projections | the label and the assumption travel with the figure, so the UI can say "hypothetical" (receipts come only from the bank feed or the owner) |

Everything else exists: feasibility (`evaluate`'s outcome and codes, `plan().admissible`); action alternatives (the
counters and the comparison rows); the compensating price (`value_concessions` plus `smallest_step_covering`); the
early-pay test (`_early_pay_vs_plan`); the late list (`reconcile()`, `past_due_invoices()`). What is genuinely new
is small: an originating commercial action, one delta type, one labelled copy, one capacity view. A fifth type,
`ConditionalAction`, only if conditional deals pass their gate.

## G. Architectural options

**One engine or three.** Three separate engines (an envelope solver, a portfolio optimiser, a collections scorer)
would each rebuild the projection, the cure and the costing the kernel already owns, and would each need their own
tests against the golden values. A general optimiser over everything would search a black-box projection for a "best
feasible action set" mixing commercial and funding actions across deals: unexplainable (INVARIANT 13 wants every
number traceable to a formula), unnecessary at n ≤ 6 (the spike enumerated 64 portfolios in 0.79 s), and unsafe (an
objective that trades value against a breach). **Decision: one kernel, three thin question layers** (the owner's
decision 4). Keep `evaluate`, `plan`, `project` and `alerts` as they are; the three answers are sweeps, deltas and
rankings over their outputs, with the four types of section F as the only additions. The reasons: the spikes proved
it (every figure came from the four calls); the objective is already lexicographic in both the verifier (hard codes,
then price codes, then tiers) and the router (cannot run today, needs approval, cost, legs, peak debt), so the new
answers inherit it; and the golden fixtures and 1,735 test functions pin the kernel, so a thin layer is testable by
differential against them.

**What not to build.** No general optimiser (the enumeration verifies; an optimiser would only propose). No weighted
utility: a weight is a number the owner cannot audit and can trade a breach against value; owner preferences enter as
constraints (`OwnerConstraints`: at most 0.85%, no forward concessions, terms at most 50 days), the repo's existing
pattern. No ML: a per-buyer days-late average from the ledger is all the first year of data supports and already
improves the ranking; the conservative projection assumes a late buyer pays nothing, the right default for a reserve
rule. No expected values in anything that decides (INVARIANT 11); scenario bands only for display. No refactor of the
engine for speculative features (the map's out-of-scope).

## H. MVP spikes

Three scripts under `services/api/scripts/research/` on `research/strategy-spikes`, run only with
`FLOW_RESEARCH_SPIKES=1`, on the in-memory runtime with cached compiler output, importing nothing into the app and
never merged. `git diff origin/dev -- services/api/app apps` was empty; the suite (`tests/api`, `tests/verifier`,
`tests/funding`) passed 1,513 with 22 skipped; ruff and mypy clean.

| Spike | What it did | Runtime |
| --- | --- | --- |
| `envelope_spike.py` | the what-if builder's call for BUYER-1; bisection per lever with the two neighbours past the boundary checked; the smallest passing price per terms value (13 × 21 grid); approved packages per terms value and early-pay variant (smallest price, then largest rebate), each one whole evaluation re-checked with `counters.infeasibility`; `--exhaustive` scans all 273 grid points | 51 runs, 5.4 s (maxima and zone); 134 runs, 24.3 s (30 packages); 185 runs, 29.7 s whole, cold; +242 runs, 51 s exhaustive; about 160 ms a run |
| `portfolio_spike.py` | compile and evaluate each fixture offer; candidates = as asked, each counter (re-checked alone), reject; prune (not acceptable alone; over the cap; one router call per distinct cash-moving set); `plan()` and `project()` per survivor; lexicographic rank; `evaluate_many` for comparison; `--no-prune` soundness check | 16 packages 0.52 s; 72 (EX01, EX02, EX04, EX06) 0.70 s; 64 0.79 s, 1.00 s unpruned |
| `collections_spike.py` | day-0 books and the day-34 books replayed in process through the real app (`TestClient`, the demo path); per open receivable three labelled copies (today, five days before due, the first breach day) each re-read by `plan`, `project`, `alerts`; the early-pay ceiling on two faces by `_early_pay_vs_plan`'s test; the action rules; the cash price curve | 0.33 s (day 0), 0.66 s (day 34) without the curve; curve 6.8 s and 3.3 s; 11.9 s whole |

**Corrections: where the spike and the deep dive differ, the spike is the truth.**

| # | Item | 03 said | Spike says (truth) | Why |
| --- | --- | --- | --- | --- |
| 1 | Smallest price that passes at 55 days; at 50 days | 0.30%; 0.15% | 0.25%; 0.10% | 0.30% and 0.15% are the Option B rule (nets the cost to zero) and remain the counter sent; the verifier passes less because the budget absorbs the rest |
| 2 | 60 days with Option A's early payment | passes at 0.45% | passes from 0.40% | same reason |
| 3 | Reserve breach at 60 days alone | ¥130,000 on day 60 | violation on day 47, not curable | the verifier reports the first induced breach day; ¥130,000 is the deepest shortfall, not printed |
| 4 | Longest terms in a passing package | 60 days tested | up to 80 days with 0.85% on ¥257,200 (75 at 0.80%, 80 at 0.95%); cure ¥4,009.57, "cannot run today", owner approval from 65 days | 03 tested 60 only |
| 5 | Whole-invoice early pay (0.70%) with an extension | not tested | never passes at any price up to 1.00% | EARLY_PAY_DEARER_THAN_PLAN; a smaller rate inside a package was not searched |
| 6 | Early-pay ceiling on RI:BUYER-1:2 | ≤ 0.40% on ¥200,000 | 0.80% on ¥200,000; 0.40% on the whole ¥420,000 | 03 mixed the two faces; its ¥888.28 and ¥24.20 are exact |
| 7 | Collections order on day 34 | RCV-A, RI:2, RI:32 | by gross value RI:2 and RI:32 (¥1,706.10) before RCV-A (¥1,374.61); by net value 03's order (¥1,374.61, ¥77.58, ¥73.68) | two measures; the MVP ranks by net and shows gross |
| 8 | Action on RI:BUYER-1:32 | wait | offer early pay up to 1.20% on ¥200,000 (0.65% whole) | "wait" is a judgment on days-to-due the engine does not hold; encode it as a rule |
| 9 | Cash price curve, day 0 | ¥89.10 before day 32; ¥84.15 on the line; ¥0 after 47 | ¥89.11 for arrival days 1–30; ¥0 from 31 and on day 0; no ¥84.15 band at ¥10,000 | definitions differ (cash on a day versus the same cash 30 days earlier); not a conflict |
| 10 | Greedy `evaluate_many` against the enumeration | no figure | rank 7 of 9 at ¥6,113.93 against ¥3,027.77; 14 of 18 with five deals | it takes no counter by design |
| 11 | Run times | 22 evaluations, 1.6 s; 0.43 s and 1.63 s | 51 runs 5.4 s, 185 runs 29.7 s cold; 0.52 s and 0.79 s | wider scope, cold caches; verifier evaluations included in the portfolio totals |
| 12 | Cost of the best portfolio | funding cost ¥841.57 | posted cost ¥3,027.77 beside ¥841.57 (the early-pay discount ¥2,186.20 is posted) | the owner pays the posted cost |
| 13 | A receipt five days early | not computed | RI:BUYER-1:32 on day 72 costs ¥76.09 more than none | the router's cost is not monotone in the receipt date |

Not checked by any spike (so the deep dive's figures stand unverified): the trade-credit exposure ¥140,000 at 55
days; the pro-forma DSCR 1.92× and leverage 1.72× at 60 days (the 1.72× matches the withdrawn line-limit definition;
FINANCIAL_SEMANTICS §5 gives 1.47× for EX01 after the extension on the one definition, so this figure should be
re-read before it is shown anywhere); the day-0 partial and dated receipts (¥891.09, ¥2,284.63, ¥1,785.91, ¥585.10,
¥26.30); "escalate by day 39"; the day-34 envelope ("no extension passes").

## I. Validation experiments

**The fixture backtest (30 days).** Assets: `fixtures/offers/offers.yaml` (EX01–EX12 with expectations) and the three
held-out sets (50, 49 and 66 offers); `fixtures/golden/golden_values.json` (67 values with an independent oracle);
`evals/e2e/scenarios.yaml` (49 scenarios, 87 turns, with a clock); the spikes' `--json` outputs as a differential
oracle. Envelope: for every fixture offer, compute the envelope for its buyer on the books before the offer and check
that every counter the verifier returns is among the approved packages (they are approved by construction, so the
envelope must contain them), that "as asked" falls inside or outside the zone exactly as its verdict says, that every
approved package passes its own re-check and `counters.infeasibility`, and that bisection agrees with the exhaustive
grid on every fixture (the neighbour check). Collections: replay the e2e scenarios day by day; at each day the
"call now" receivable is a past-due one, no early-pay ceiling exceeds the mandate's immediate-discount cap or the
plan comparison, and the net ranking is stable under `clear_caches()`. Cash price curve: the curve's value at an
arrival day agrees with the receipt-moved saving of a ¥10,000 flow on that day, on day 0 and day 34, and the
sentence never exceeds the marginal cost of funds.

**The shadow pilot (90 days).** One or two SMEs the owner can reach, for the four to eight weeks the owner names.
Each week the pilot's books are entered as the demo's are (facilities, invoices, recurring invoices, mandate); FLOW
computes the three read-only answers; nobody acts on them; the owner records what they did (the chosen response to
each real offer, the order they chased, the receipt dates). The learning ledger's first entries are these records
against FLOW's answers. If no SME is reachable, the five interview sets below run first with the same thresholds
read from the interviews' "what did you do" answers.

**Interview question sets (from 02, actual behaviour, not "would you use").**

| Persona | Questions |
| --- | --- |
| SME owner | 1 The last time a buyer asked for longer terms: who asked, how did you decide, how long did it take? 2 What did you check before saying yes, and where was it? 3 Have you discovered after signing that a deal made cash tight; what then? 4 When did you last call your bank RM, and what did you ask? 5 How much of your receivables sits with your largest buyer; do you know without looking? 6 Who may give a discount without asking you; is it written down? 7 When cash was tightest last year, what did you do first, second, third? 8 How many hours a week do you spend on getting paid? 9 Which buyers have you kept despite poor payment, and why? 10 What would have to be true for software to send a counter-offer in your name? |
| CFO (mid-market) | 1 Your deal-approval process: thresholds, signers, turnaround. 2 Last quarter, how many deals did finance push back on, how many were overridden? 3 How do you cost payment terms in a deal today? 4 How often is the cash forecast refreshed, by whom, in what, and when did it last miss badly? 5 Facility utilisation now, and when did it last exceed your comfort? 6 Which covenants do you watch; how would you know a month early? 7 Who decides draw versus chase harder, on what evidence? 8 Credit policy on new buyers; last updated? 9 The one number you wish sales saw before quoting? 10 What has stopped you buying AR or treasury software? |
| Finance manager | 1 The cash spreadsheet: tabs, refresh, editors. 2 When sales agrees terms, how and how late do you find out? 3 How do you compute the cost of an early-payment discount? 4 What does month-end reveal you wish you knew on day 5? 5 The last unplanned draw: cause, notice, cost. 6 Which supplier do you pay late when short, and how do you decide? 7 Which reports does the owner ask for, which by hand? 8 Which buyer's behaviour changed recently, how did you learn? 9 How do you track rebates and contingent concessions owed? 10 What breaks when you are on leave? |
| Credit controller / AR | 1 Yesterday morning: which list, what order, why? 2 How many accounts touched, by which channel? 3 Which accounts are you told not to chase, by whom? 4 How do you know a buyer's risk changed? 5 A disputed invoice: how long to resolve, who? 6 How do you record a promise to pay; does the forecast use it? 7 Asked to chase harder because a facility was about to be drawn; how did you know? 8 What do you do with the aged-debtor report the system cannot? 9 What would make you trust a ranked list you did not build? 10 When did a chase damage a relationship? |
| Sales manager | 1 A deal finance rejected or slowed in the last three months: what happened, what did the buyer do? 2 What discount or terms can you grant alone; how do you know? 3 When a buyer asks for 90 days, what do you say in the room and check afterwards? 4 How do you learn a customer pays late; does it change how you sell? 5 Who told you about the last credit-limit cut, and when? 6 Have you offered price instead of terms, or the reverse; how did you pick? 7 How are you paid: bookings, revenue, cash, margin? 8 How long do you wait for approval; what do you tell the buyer? 9 What would you want on your phone before a negotiation? 10 When did finance's "no" turn out right? |

**Acceptance thresholds, tied to the kill criteria.**

| Capability | Passes the gate when | Killed when (accepted criterion) |
| --- | --- | --- |
| Envelope | on at least five of the first ten real offers the owner's chosen response is inside the zone or is one of the packages; at least half the pilot's buyers have a recurring invoice; backtest: 100% of counters inside the envelope, zero approved package fails its re-check | chosen response outside the zone or packages ignored on more than half of the first ten offers; fewer than half the buyers have a recurring invoice |
| Collections | in at least one pilot week the net-value order differs from the overdue-amount order and the owner's chase order followed it (or they say it should have); at least one pilot has more than two open receivables at once | the orders coincide every week; no pilot has more than two open receivables |
| Cash price curve | three of three owners in the comprehension test explain "0.89%" as what earlier cash is worth to them, not a rate charged | any owner reads it as a charged rate (reword and retest once; then kill) |
| Portfolio (VALIDATE FIRST) | two or more deals open at the same time in most pilot weeks, and the greedy order differs from the enumeration in a case that occurs (it already does on the fixtures) | fewer than two simultaneous deals in most weeks |
| Stress-to-action, tripwires | the cold-user walk shows the alerts page does not already answer the question | it does |
| Conditional deals | a pilot owner asks for one unprompted | nobody does |

## J. Priority ranking

Section-13 scores from the deep dive, 1 to 5. Positive: CV customer value, Fq frequency, DI decision impact, Df
differentiation, Ft fit, Fs feasibility, DA data availability, Ex explainability, Dm demo value, Pl pilot value, Rv
revenue. Negative (higher is worse): Cx complexity, AS attack surface, UD unproven data, UX complexity, RL liability.

| Candidate | CV | Fq | DI | Df | Ft | Fs | DA | Ex | Dm | Pl | Rv | Cx | AS | UD | UX | RL | Net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Envelope (approved packages + zone) | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 4 | 2 | 1 | 1 | 2 | 1 | 45 |
| Cash price curve / cash value of a negotiation | 4 | 5 | 3 | 4 | 5 | 5 | 5 | 5 | 4 | 4 | 2 | 1 | 1 | 1 | 1 | 1 | 41 |
| Collections ranking + early-pay vs finance | 4 | 5 | 4 | 4 | 5 | 5 | 4 | 5 | 4 | 5 | 3 | 2 | 1 | 2 | 2 | 1 | 40 |
| Stress-to-action | 4 | 3 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 4 | 2 | 1 | 1 | 1 | 2 | 1 | 38 |
| Tripwires with owner thresholds | 3 | 4 | 3 | 2 | 5 | 5 | 5 | 5 | 2 | 4 | 2 | 1 | 1 | 1 | 1 | 1 | 35 |
| Learning ledger (outcome column) | 3 | 3 | 2 | 3 | 5 | 4 | 4 | 5 | 2 | 4 | 2 | 2 | 1 | 1 | 1 | 1 | 31 |
| Funding capacity reservation | 3 | 2 | 3 | 3 | 5 | 4 | 5 | 4 | 2 | 3 | 1 | 2 | 1 | 1 | 2 | 1 | 28 |
| Trade-credit budget (exposure units) | 3 | 2 | 3 | 3 | 4 | 4 | 5 | 4 | 2 | 3 | 2 | 2 | 1 | 1 | 2 | 1 | 28 |
| Conditional deals | 4 | 2 | 4 | 5 | 3 | 3 | 4 | 4 | 4 | 3 | 2 | 4 | 2 | 1 | 3 | 2 | 26 |
| Portfolio enumeration | 3 | 2 | 4 | 4 | 4 | 4 | 4 | 3 | 4 | 2 | 3 | 3 | 1 | 2 | 4 | 1 | 26 |
| Buyer behaviour (days-late averages) | 3 | 3 | 2 | 2 | 4 | 4 | 3 | 4 | 1 | 3 | 1 | 2 | 1 | 3 | 1 | 1 | 22 |
| Mandate optimisation (owner report) | 3 | 1 | 3 | 3 | 3 | 4 | 5 | 4 | 2 | 2 | 1 | 2 | 3 | 1 | 2 | 4 | 19 |
| Multi-action liquidity planner | 3 | 2 | 3 | 3 | 3 | 3 | 4 | 2 | 3 | 2 | 2 | 4 | 2 | 2 | 3 | 1 | 18 |
| Liquidity capacity allocation | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 3 | 2 | 2 | 1 | 3 | 1 | 2 | 3 | 1 | 18 |
| Concentration optimisation | 2 | 1 | 2 | 1 | 2 | 3 | 5 | 4 | 1 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 16 |
| Commercial capacity score | 1 | 2 | 1 | 2 | 2 | 4 | 5 | 1 | 2 | 1 | 1 | 2 | 1 | 2 | 3 | 1 | 11 |
| Customer profitability | 4 | 2 | 3 | 2 | 1 | 2 | 1 | 3 | 3 | 2 | 3 | 4 | 2 | 5 | 3 | 2 | 10 |

**Classification.** Judgment, not the total, decides; the owner's decision 4 fixes the first two classes.

| Class | Capabilities | One line of judgment |
| --- | --- | --- |
| BUILD NOW (read-only MVP, flagged) | Safe Deal Envelope (approved packages first); cash price curve; collections marginal value with its action set | the two user questions FLOW does not yet answer and the primitive both need; every figure already comes from the kernel and the spikes reproduced them |
| PROTOTYPE NEXT | Stress-to-action; tripwires with owner thresholds; learning ledger (outcome column) | rows on pages that exist, no new type; the ledger is the pilot's instrument and starts in the 90-day window |
| VALIDATE FIRST | Multi-deal portfolio; conditional deals; buyer behaviour (days-late) | the enumeration works (0.79 s for 64) and beats the greedy order on the fixtures, but value is not modelled and nobody has shown that deals overlap; the other two need pilot evidence or a pilot owner's request |
| POST-PILOT | Funding capacity reservation; trade-credit budget in exposure units | small, explainable, and each is a second thing the owner must set; wait to see which capacity the pilot owners actually watch |
| DO NOT BUILD | Customer profitability; commercial capacity score; concentration optimisation; multi-action liquidity planner; liquidity capacity allocation; mandate optimisation as a feature | needs data FLOW does not hold, hides the binding wall, cannot act, is the optimiser the decision rejects, is the portfolio under another name, or would have the agent propose loosening the owner's safety rule |

## K. Recommended product direction

FLOW stays what it is: the supplier's agent that reads a buyer's offer, prices it against the supplier's own cash and
committed facilities, verifies it against the owner's signed mandate, counters, funds the gap and keeps the books. It
becomes, in the next quarter, the agent that answers three questions before anyone asks them, with the same engine and
the same rules.

**What FLOW becomes.** On Deals, before a message arrives, the buyer's thread shows what we can offer Foshan today:
the approved packages ("55 days if the price rises 0.30%, or early payment at up to 0.85% on ¥257,200; a rebate up to
1.25%; not 60 days without an early payment") and, behind them, the zone and the wall each lever hits. The sales
question is answered on the owner's page in the owner's words, with the counter cards already there to send. On
Receivables, the late-first table says what each invoice is worth to collect and what to do: call Foshan for the
¥162,800 today (¥1,374.61 avoided, the only free action); on the ¥420,000 due day 47, offer early payment up to 0.80%
on ¥200,000 or finance it; on the one due day 77, wait. On Cash & funding, one sentence prices time: cash before day 32
is worth 0.89% to you, after day 47 nothing; on the day-34 books, cash in the next eight days is worth twice that. Every
number is the kernel's, formatted on the server, traceable to a formula, and hypothetical until the bank feed says
otherwise.

**What FLOW does not become.** Not a portfolio optimiser: the enumeration exists and runs in under a second, but
FLOW cannot say whether Foshan's rebate is worth more than the other buyer's, and no pilot has yet shown two deals
colliding in one week; it waits for that evidence. Not a scorer of buyers: no probability model, no ML, no composite
capacity score; a per-buyer days-late average from our own ledger when the pilot has produced one. Not a judge of
customers: profitability needs the accounting system. Not a proposer of looser mandates. Not an actor: in the 30-day
and 90-day windows nothing new sends, books or draws; the owner compares what FLOW said with what they did, and
controlled action is earned feature by feature, where the pilot shows the answer was right.

**Why.** The three answers are the same computation seen from three sides: a package, a receipt or ¥10,000 on day d,
through `evaluate`, `plan`, `project` and `alerts` on a copy of the books, and the delta that comes back. The spikes
proved every figure with those four calls and no engine change. The market has no product that tells a supplier what
it can afford a named buyer, prices payment days in a deal, or ranks collections by cash consequence; the insurers set
limits from the buyer's risk, the collections tools rank by delinquency on network data we do not have, the early-pay
marketplaces leave the rate to judgment, the forecasting tools stop at the forecast. Our edge is the one thing none of
them hold: the supplier's own living cash state, facilities and mandate, with a verifier that will not let a number
pass that breaks the floor. "Commercial capital allocation" is the one-sentence reason these are one product; the
owner hears "what can I offer", "who to chase", "am I safe", and buys it as cash flow and collections software.

## L. Roadmap

**30 days: the read-only MVP and the backtest.** On one research branch behind `FEATURE_*` flags (`config.py`,
`require_feature()` on every new route), with no file under `apps/web` or `services/api/app` changed outside the
flag: the four types of section F and the `MarginalImpact` function; the envelope's approved packages for the buyer's
thread on Deals (terms in force plus two steps, the three early-pay variants, the smallest price and largest rebate,
with the zone on demand), computed once per state version and cached; the cash price curve as one sentence on Cash &
funding (and as the money line of the other two cards); collections marginal value with its action set as a "worth"
column and an action on Receivables and in Home's ReceivablesBlock; the backtest harness of section I over the
fixtures, the held-out sets and the e2e scenarios, with the spikes' `--json` as the differential oracle. The demo path
and the hackathon build are untouched; nothing merges into `dev` in this window without the owner's separate word.

**90 days: the shadow pilot.** The owner names one or two SMEs and the month. Weekly, their books are entered and the
three answers computed; nobody acts on them; the learning ledger gets its first entries (the owner's chosen response
against the envelope, the chase order against the ranking, receipt dates against due dates). The comprehension test of
the cash price curve on three owners. The portfolio's validation gate is read from the pilot's inbox: how many deals
were open at once, and whether the greedy order and the enumeration differed in a case that occurred. Stress-to-action
and tripwires are prototyped as rows only if the cold-user walk shows the alerts page does not already answer them.
If no SME is reachable, the five interview sets run in the first fortnight and the thresholds are read from them.

**Post-pilot.** Controlled action only where the pilot earned it: the envelope's "send Option A or B" becomes the
existing counter path (already Tier 1 or 2 by the mandate's rules) only if the owner's responses stayed inside the
zone on at least half of the first ten offers; the collections "call now" stays a human action, and "send the early-pay
offer" becomes a queued operation only if the net ranking differed from the amount sort in pilot weeks and the owner
followed it. The portfolio is built as enumeration with pruning only if its gate passed; otherwise it stays deferred
and `evaluate_many` remains the joint check. Killed: whatever failed its criterion in section I; customer
profitability, the capacity score, concentration optimisation and mandate optimisation as a feature are not revisited.
Reservation and the exposure budget are considered then, if pilot owners watched those capacities.

## Implementation plans (the brief's section 25)

Effort is in agent-days of one implementer in a worktree with a reviewer, at the stability-mode rules (smallest
change, flagged, tests first against the golden values). The shared kernel types are costed once.

### Shared: the four types and `MarginalImpact` (4 agent-days)

`CandidatePackage`, `Capacity`, `ScenarioState` as frozen `Contract` models beside the domain models (1.5);
`marginal_impact(before: Books, after: Books, mandate) -> MarginalImpact` calling `plan`, `project` and `alerts` on
each side and returning the deltas with the approval flags (1.5, with golden tests: ¥3,113.93 − ¥0 for RCV-A by day
12; ¥1,706.10 − ¥331.49 = ¥1,374.61 for the day-34 residual; −¥76.09 for RI:BUYER-1:32 on day 72); the `Capacity`
read-only view with the day-0 and day-34 values of 03's table as tests (1). No engine function changes.

### Winner 1: the Safe Deal Envelope (8 agent-days)

| Field | Content |
| --- | --- |
| Problem | The owner accepts terms to protect the relationship after a stale-spreadsheet loop (56% do); the answer "what can we live with" exists in the verifier but only after a message arrives |
| User | The owner (sales reads the card on the buyer's thread; decision 2) |
| User question | "What can I offer Foshan?" |
| Business value | A priced yes in hours instead of a slow no or an unpriced yes; on the golden books the difference between EX01 as asked (REJECT at ¥28,326.92 of concessions, cure ¥2,406.67) and 55 days at 0.30% (¥0 net, cure ¥1,570.36) |
| Why FLOW is uniquely positioned | The counters are approved packages by construction; the compensating price is `value_concessions` plus `smallest_step_covering`; no product found prices the supplier's own affordability |
| Required data | Current books and the signed mandate; the buyer's recurring invoice and open receivables; nothing new |
| Existing code reused | `whatif.offer.build` and `context`, `whatif.params` ranges, `evaluate(plans="committed")`, `counters.smallest_step_covering`, `counters.infeasibility`, `value_concessions`, `marginal_cost`, `fmt_yuan`/`fmt_pct`, `displayed` |
| New domain model | `CandidatePackage` (buyer, terms, price, early-pay rate and face, rebate); `EnvelopeAnswer` (packages, each a verdict summary with budget used, cure and flags; the zone rows; the lever walls) |
| New algorithms | Bisection per lever with the two neighbours past the boundary checked (fall back to a scan if a neighbour disagrees); the package grid (terms in force plus two steps × three early-pay variants); the smallest passing price then the largest passing rebate; nothing else |
| API changes | `GET /buyers/{id}/envelope` behind a flag, returning server-formatted strings and the `state_version`; refuses a buyer with no recurring invoice and no open receivable with one sentence ("no terms lever to value") |
| UI changes | A "Before they ask" card beside BuyerAsks on Deals: primary answer, key reason, money impact, the two send buttons that open the existing counter cards, a detail disclosure with the lever table and the zone |
| Security and authority | Read-only; no operation, no new tier; "approved" means passes the verifier and the counters' re-check, not that the deal is good; a package whose cure "cannot run today" or needs the owner is flagged, never downgraded silently; the card never sends; the state version is checked on display as the alert button does (409 when moved); never proposes a mandate change |
| Test strategy | Golden pins from the spike (45; 55 at 0.25%, Option B 0.30%; 0.70% whole, 0.85% on ¥257,200; 1.25%; the nine interaction packages to the fen); property: every package passes its re-check and `infeasibility`; differential against `envelope_spike.py --json`; the exhaustive grid on the fixtures; INVARIANT 13 (no money arithmetic in `apps/web`); benchmark under 8 s cold for the default grid |
| Edge cases | BUYER-2 (no recurring invoice); day-34 books where no extension passes (line ¥13.80, headroom ¥0); non-monotone levers; a whole-face early payment inside a package (search a smaller rate, not only the standalone maximum); per-buyer caps (untested on the golden mandate); a mandate about to expire; a buyer with a past-due invoice (the verdict already names it) |
| MVP | Day-0-style books, one buyer at a time, the default grid, cached per state version, flagged |
| V2 | The full zone on demand; live commitments read into the builder; a chat intent ("what can I offer Foshan"); the price-rebate trade-off curve |
| What not to build | A continuous region as the primary view; buyer acceptance prediction; volume or margin modelling; any search outside the what-if ranges |
| Dependencies | The shared types; the what-if builder's generalisation past one buyer |
| Effort | 8 agent-days: builder generalisation 1.5, sweep and neighbour check 2, packages 1, route and display 1.5, card 1.5, tests 0.5 |
| Risks | Runtime (30 packages cost 29.7 s cold; the MVP grid is about 40 runs, about 6–8 s, so compute in the background on state change); the owner reads a package as a recommendation to give terms (wording: "what you can live with", not "what to offer"); the pilot's buyers lack recurring invoices (the kill criterion) |
| Success metrics | The kill criterion's inverse: on at least five of the first ten real offers the owner's response is inside the zone or a package; backtest 100% of counters inside the envelope; p95 under 8 s cold |

### Winner 2: the cash price curve (3 agent-days)

| Field | Content |
| --- | --- |
| Problem | Owners give away 30 days for nothing or accept a 1.2% discount that is about 14.6% a year because nothing prices time in their own books |
| User | The owner |
| User question | "What is cash on day d worth to me?" (and, inside every other answer, "what does this cost me?") |
| Business value | Makes a discount, an extension, a chase and a draw commensurable; the money line of every card |
| Why FLOW is uniquely positioned | The router's plan on a copy of the books is the only honest source of the marginal value of liquidity: ¥89.11 per ¥10,000 per 30 days before day 31 on day 0; ¥178.22 for days 34 to 42 on day 34 |
| Required data | Current books and mandate; nothing new |
| Existing code reused | `plan()`, `project`, `current_books`, `marginal_cost` |
| New domain model | `ScenarioState` with a confirmed ¥10,000 inflow on day d; `PriceCurve` (bands of arrival days with a value each, as fen and as a percentage) |
| New algorithms | One `MarginalImpact` per band boundary (the breach episodes' first and recovery days and the plan's repayment days), not per day; linear within a band is asserted by a check at the band's two ends |
| API changes | `GET /cash/price-curve` behind a flag; the sentence also embedded in the envelope and collections responses as their money line |
| UI changes | One sentence on Cash & funding under the risk card; the same sentence as the money line on the two other cards; no chart of rates |
| Security and authority | Read-only; wording must never read as a rate charged ("worth to you", never "rate"); the value never exceeds the marginal cost of funds |
| Test strategy | Golden pins (¥89.11, ¥0 from day 31; ¥178.22, ¥89.12, ¥0 from 61); consistency with the receipt-moved saving; wording test on the display strings; differential against `collections_spike.py --json` |
| Edge cases | ¥0 on day 0 itself (arrival on day 0 and day 30 both serve the trough); the ¥10,000 grid step (the curve amount equals it); non-monotone plans; books with no breach (a flat ¥0 curve, say so); a pending facility (counts zero) |
| MVP | The banded curve and the sentence, flagged |
| V2 | A larger amount (to see the line's ¥84.15 band); the curve per receivable rather than per flow |
| What not to build | A chart; a daily table; any interpolation across band boundaries |
| Dependencies | The shared types |
| Effort | 3 agent-days: scenario and bands 1, route and sentence 1, tests and comprehension-test script 1 |
| Risks | Comprehension (the kill criterion); runtime if computed daily (6.8 s), so bands |
| Success metrics | Three of three owners pass the comprehension test; the sentence appears on all three cards with the same figure |

### Winner 3: collections marginal value and its action set (6 agent-days)

| Field | Content |
| --- | --- |
| Problem | The aged-debtor sort is the collections policy; an unnecessary draw happens while a collectable receipt sits idle; the anchor buyer is chased for nothing |
| User | The owner (AR reads it) |
| User question | "Whom should I chase first, and how?" |
| Business value | On day 34: ¥1,374.61 avoided by one free call; ¥888.28 saved by a 0.40% offer on ¥200,000 against the cure that needs approval |
| Why FLOW is uniquely positioned | It holds the plan the receipt replaces; collections tools rank by delinquency on data FLOW does not have, and none states a funding-cost objective |
| Required data | Open receivables and promises (`reconcile()`), the standing plan; observed days-late from the ledger (new aggregation, V2); a dispute flag (new field, V2) |
| Existing code reused | `plan()`, `alerts()`, `project`, `reconcile()`, `past_due_invoices()`, `_early_pay_vs_plan`'s test (through a public wrapper), the IMMEDIATE_DISCOUNT obligation builder |
| New domain model | `ScenarioState` per receivable (received today; by the first breach day); `ReceivableWorth` (gross saving, net saving, need left, breach days and alerts removed, the ceiling on each face, the action and its sentence) |
| New algorithms | The action rules in order (call now; wait; offer early pay up to X%; finance); the ceiling by bisection over whole-5bp rates on two faces (the whole outstanding and the plan's need); ranking by net value with gross shown |
| API changes | `GET /receivables/worth` behind a flag, or a flagged extension of `GET /reconciliation`; sentences server-formatted |
| UI changes | A "worth" column and an action on the late-first table in Receivables; the top action in Home's ReceivablesBlock |
| Security and authority | Read-only; a simulated receipt is a projection assumption labelled hypothetical, never a bank receipt; no discount is ever offered on an overdue invoice; the ceiling never exceeds the mandate's immediate-discount cap; "send the early-pay offer" is a V2 queued operation at the mandate's tier, not an MVP action |
| Test strategy | Golden pins (¥1,374.61 and ¥37,200; ¥1,706.10; 0.80% on ¥200,000 and 0.40% on ¥420,000; ¥888.28, ¥24.20; day 0: ¥3,113.93 by day 12, 0.70%); the negative delta −¥76.09 shown as "no saving"; e2e replay with the ranking at each day; differential against `collections_spike.py --json` |
| Edge cases | FINANCED receivables (the lender is paid first, ADR-0010); unissued invoices; an overdue invoice has only the "today" case; a lapsed promise (escalate); a buyer with one open invoice; two receivables of the same buyer in one call; the ¥10,000 grid |
| MVP | Deterministic ranking on current books with the action set, flagged; "wait" as a days-to-due rule |
| V2 | Days-late averages from the ledger; the dispute flag; the early-pay offer as a queued operation; "escalate by day 39" (the last request day for an advance) |
| What not to build | Payment probability; a buyer score; effort modelling; automated dunning |
| Dependencies | The shared types; the learning ledger's outcome column for V2's days-late |
| Effort | 6 agent-days: scenarios and worth 1.5, ceilings 1, action rules and sentences 1, route and table 1.5, tests 1 |
| Risks | The ranking equals the amount sort on small books (the kill criterion); owners read the ceiling as advice to discount (wording: "what you can afford, not what to offer"); the sales-versus-finance resistance when a strategic account tops the list (the reason sentence is the answer) |
| Success metrics | In at least one pilot week the net order differs from the amount sort and the owner followed it; zero ceiling above the cap or the plan comparison in the backtest |

## The dependency graph (the brief's section 26)

```
current_books ── evaluate / plan / project / alerts  (the kernel, unchanged)
        │
        ├─ ScenarioState  (a labelled copy with its assumption)
        ├─ CandidatePackage  (a buyer-addressed package with no inbound offer)
        └─ Capacity  (the seven capacities, read-only)
                │
                ▼
        MarginalImpact  (two books in; Δ need, Δ posted cost, Δ first breach, Δ lowest headroom, Δ budget, flags out)
                │
    ┌───────────┼─────────────────────┐
    ▼           ▼                     ▼
Envelope    Cash price curve     Collections worth
(packages   (a ¥10,000 flow on   (a receipt moved;
through     day d; one impact    one impact per
evaluate;   per band)            receivable; ceilings
impact as                        by the early-pay test)
money line)
                │
                └─ later, gated: Portfolio (sets of CandidatePackages through plan; MarginalImpact per set)
                                 ConditionalAction (a CandidatePackage with a receipt trigger)
```

**Is the foundation justified or invented?** Justified, with one caveat. The three spikes each rebuilt the same three
things by hand: a labelled copy of the books with an assumption (the envelope's synthetic offer, the collections'
"received today" copy, the curve's ¥10,000 flow), a delta between two plans with the breach days and flags
(`saved`, `beats by`, `budget used`, `cure`), and a package addressed to a buyer that no message produced. That is
`ScenarioState`, `MarginalImpact` and `CandidatePackage`, and the collections and cash-price answers are literally
one `MarginalImpact` per scenario; the envelope uses it for the money line and the budget column. `Capacity` is the
caveat: the spikes did not need it (the verifier names the wall in its violation codes), so it is justified only as the
read-only view behind "the wall each lever hits" and the worded tie-break ("also leaves ¥95,000 of financing room");
if the MVP card can say the wall from the violation codes alone, `Capacity` waits for the post-pilot ideas
(reservation, the exposure budget) that are its real consumers. Nothing above the kernel is a new engine: no type
holds a computation the four calls do not already perform.

## Not checked, and open

- The deep dive's figures no spike ran: ¥140,000 of exposure at 55 days; DSCR 1.92× and leverage 1.72× at 60 days
  (1.72× looks like the withdrawn line-limit definition; FINANCIAL_SEMANTICS gives 1.47×); the day-0 partial and dated
  receipt values; "escalate by day 39"; the day-34 envelope.
- Uncertainty (the map's "not yet specified"): resolved here as deterministic conservative assumptions plus observed
  days-late and owner promise dates, scenario bands for display only; the pilot may show owners want bands on the
  envelope too.
- Which SMEs and which month: the owner's, in the handoff.
- The 02 document worked from the ticket's paraphrase of the brief, not its text; the brief's sections 5, 6 and 22 are
  not in the repository.
- Page and component names (BuyerAsks, ReceivablesBlock, the risk card) are as 01 read them at `d1eadb0`; the
  simplification map's later waves may have renamed them.
- Effort figures are this document's estimates, not measured; a task past 1.5× its estimate stops and reports
  (HANDOVER §3).
