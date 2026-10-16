# ADR-0007: When an early-payment discount is worth taking

Status: accepted, 1 Oct 2026. Owner: main architect. Implements audit F1, F2 (C5). Supersedes the fixed
30-day break-even in spec v2 §5.3 as the acceptance test; the break-even stays as a first screen and as
the figure shown to the owner.

## Problem

The verifier accepts an early-payment discount when it is below a break-even computed for a 30-day
period, whatever the days early, and without asking whether the cash is needed or whether the funding
router has a cheaper plan. Two wrong decisions follow:

- 1.2% for paying 90 days early is countered as "dearer than 0.88%", although over 90 days it is cheap.
- 0.85% on the whole ¥420,000 invoice is accepted alone (cost ¥3,570.00) when the router's plan costs
  ¥2,712.94, and it would be accepted even with no cash need at all.

## Decision

An early-payment obligation (IMMEDIATE_DISCOUNT on a named invoice, discount `d`, settled `n` days before
the due day) is acceptable only if it passes all three tests, in this order.

### Test 1: break-even for the actual tenor (first screen, and the number shown)

`c(n)` = what the marginal committed source would charge, as a share of principal, to carry the money for
`n` days:

- invoice financing: `rate × p × k / 365 + fee × k`, with period `p` (30 days) and `k = ceil(n / p)` whole
  periods, as it is billed;
- any other source: `rate × n / 365`.

Break-even `d* = c / (1 + c)`. Fail (`DISCOUNT_ABOVE_BREAK_EVEN`) when `d ≥ d*`.
For `n = 30` on the golden books this is the existing 0.8832% (88 bp floor), unchanged.

### Test 2: the cash is needed

On current books without the offer, let `C0` be the total posted cost (interest + fees + discounts over the
horizon) of the cheapest committed plan that keeps cash at or above the floor; `C0` includes interest on
balances already drawn. Let `C1` be the same with the offer's obligations added to the books; `C1`
includes the discount itself.

If no funding is needed without the offer and `C1 > C0`: fail with `EARLY_PAY_NOT_NEEDED`. The discount
buys nothing. (If early cash retires a drawn balance and so lowers total cost, `C1 < C0` and it passes.)

### Test 3: cheaper than the plan

Fail with `EARLY_PAY_DEARER_THAN_PLAN` when `C1 ≥ C0`. Observed = `C1`, limit = `< C0`, both in yuan, with
the two plans named in the inputs.

If the books cannot be cured at all without the offer but can with it, tests 2 and 3 pass.

### Outcome

All three are pricing faults, like `DISCOUNT_ABOVE_BREAK_EVEN` today: the outcome is COUNTER when the
verifier can price a counter (the existing partial early-pay counter: only the face that closes what the
cheaper sources leave open), otherwise REJECT. None of them is a security event.

Tier 1 (agent accepts alone) still needs everything ADR-0005 requires, plus all three tests passing.

## Hand-calculated cases (golden books, floor ¥300,000, day 0)

Without any offer the router draws ¥150,000 on the line to day 32 and finances ¥210,000 of RCV-A:
`C0 = ¥2,712.94`.

| Offer | Arithmetic | Result |
| --- | --- | --- |
| Whole RCV-A (¥420,000) at 0.85%, day 2 | discount 420,000 × 0.0085 = ¥3,570.00; nets ¥416,430 ≥ the ¥360,000 need, so no other funding; C1 = 3,570.00 > 2,712.94 | Test 1 passes (0.85% < 0.8832%), test 3 fails → COUNTER |
| Whole RCV-A at 0.64% | 420,000 × 0.0064 = ¥2,688.00 < 2,712.94 | accept |
| Whole RCV-A at 0.65% | 420,000 × 0.0065 = ¥2,730.00 > 2,712.94 | COUNTER |
| ¥211,900 of RCV-A at 0.85% (Counter A, after the F8 rounding fix) | discount 211,900 × 0.0085 = ¥1,801.15, nets ¥210,098.85; line ¥149,901.15 × 6.4% × 32/365 = ¥841.09; C1 = ¥2,642.24 < 2,712.94 | accept |
| Any discount > 0 when cash never nears the floor and nothing is drawn | C0 = 0, C1 = discount > 0 | `EARLY_PAY_NOT_NEEDED` |
| Whole invoice at 0.89%, 30 days early | 0.89% ≥ 0.8832% | `DISCOUNT_ABOVE_BREAK_EVEN` (unchanged) |

The line figure above assumes the line is repaid on day 32 as in the golden plan; the implementation takes
`C0` and `C1` from the router, not from this table. A second person re-derives every row independently
before the change merges.

## Implementation notes (added 1 Oct 2026, before the code change)

- **What `C` is.** `C(obligations)` = interest + fees + discounts the engine posts over the horizon when
  current books plus `obligations` are projected with the router's committed plan for those same books. It
  is read from the projection, not assembled from plan rows, so the offer's own discount and interest on
  balances already drawn are both in it.
- **Packages.** The tests price the early-pay leg at the margin: `C0` = books + the offer's other bound
  obligations (everything except its early-pay legs), `C1` = books + all bound obligations. For an offer
  that is only an early payment, `C0` is the standing plan, as in the table.
- **When a plan is missing.** If the `C0` plan is inadmissible and the `C1` plan is admissible, tests 2 and
  3 pass. If the `C1` plan is inadmissible, tests 2 and 3 are not evaluated; the reserve predicate reports
  the breach.
- **Test 1 source and tenor.** The source is the one `marginal_cost()` returns. `n` = the invoice's due day
  on current books minus the settlement day; `n ≤ 0` is not an early payment and is not tested.
- **The counter follows the same rule.** The early-pay counter is priced at the largest whole-5bp rate
  strictly below `d*(n)` for its own invoice and day (and never above the buyer's offered rate), and is
  offered only when its total cost (its discount plus the plan for the rest) is below `C0`. Otherwise no
  early-pay counter exists and the outcome is REJECT.
- **The offer's rate is not a standing rate** (found by the independent check, 1 Oct). The router used to
  price the buyer's early-payment facility at the rate of any early-pay obligation in the books, and then
  used it on other faces or other invoices, which the offer never said. That made `C1` too low (3 days
  early at 0.02% on the whole invoice was accepted although it costs more than the plan). The router now
  always prices that facility at its standing rate; an offer's own leg is in the books as an obligation
  and nothing more. On books with a live terms extension for the same buyer the early-pay counter no longer
  beats the standing plan, so only the price-adjustment counter is offered there.
- **Known conservative convention.** An invoice the buyer has agreed to settle early cannot also be
  financed. For an early payment only a few days before the due day this prices the gap dearer than
  financing that invoice would (3 days early at 0.01% is refused where a hand calculation that finances
  the invoice would take it). It can only refuse, never wrongly accept. See
  `docs/research/early-pay-handcalc-2026-10-01.md`.
- A whole-invoice discount that passes the break-even can still fail test 3. Example: 1.2% for paying 90
  days early passes the first screen (limit 2.60%) and is then countered, because the standing plan
  (¥3,786.77) is cheaper than discounting the whole ¥420,000 (¥5,040.00); 0.85% for 90 days is accepted.
- Counter A's face is ¥211,900 since tracker row B5 (it was ¥211,800, which netted ¥0.30 short of the gap).

## Consequences

- Golden verdicts that accepted a whole-invoice discount between 0.65% and 0.88% become COUNTER. The
  documents, the demo script and the mock data must follow. The 0.8832% break-even figure survives as the
  first screen.
- The verifier runs the router twice more per early-pay offer. Both runs are cached per (state,
  obligations).

## Implementation note, 3 Oct 2026

The "known conservative convention" above is now a rule in the code, not only a pricing convention:

- An invoice under an early-pay agreement is never financed. The engine refuses to finance an invoice with an early
  settlement booked, and the executor refuses `SubmitInvoiceForFinancing` while an early-pay agreement names the
  invoice (second red team, finding F1; `services/api/tests/operations/test_redteam_b.py`). The router and the
  admission check therefore agree with the executor.
- The partial-gap hand calculation changed accordingly. For 100,000 of RCV-A at 0.5% on day 2 the gap that must
  still be funded is 260,500. Because the residual of RCV-A cannot be financed, the rest is the line for 32 days
  (84,164 fen) plus more early pay on RCV-A at the buyer's standing 1.2% (a face of 11,184,211 fen, discount
  134,211 fen). C1 = 50,000 + 84,164 + 134,211 = 268,375 fen, that is ¥2,683.75, still below C0 = 271,294 fen
  (¥2,712.94). Before the rule the plan financed the residual and C1 was 232,630 fen. The test is
  `services/api/tests/verifier/test_early_pay_handcalc.py::test_partial_gap_c1_figure`.
- Early-pay settlement day: when an offer names no day, it is today plus the facility's lead time (it was absolute
  day 2, which made early-pay offers fail from day 3). The discount is earned only by a receipt on or before the
  promised day (audit A09).
- The rate ceiling is a separate rule: `max_apr_bp` decides who may run a plan, not whether it is admissible
  (`docs/FINANCIAL_SEMANTICS.md` section 4).

## Implementation note, 3 Oct 2026 (the existing loan's payments are cash)

The equipment loan's ¥45,000 payments now leave cash (`docs/FINANCIAL_SEMANTICS.md` section 5), so the golden gap
before day 32 is ¥405,000 and the standing plan is C0 = ¥3,113.93 (line 84,164 fen + an advance of ¥255,000, 227,229
fen). Re-derived in `services/api/tests/verifier/test_early_pay_handcalc.py`:

- The 3 Oct note above is superseded for the partial-gap case. For ¥100,000 of RCV-A at 0.5% on day 2 the gap still to
  be funded is ¥305,500, and the rest is the line plus more early pay at the buyer's standing 1.2% (a face of
  ¥157,388.66, discount ¥1,888.66): C1 = 50,000 + 84,164 + 188,866 = 323,030 fen, **¥3,230.30**, which is above C0, so
  the offer is now COUNTERED (`EARLY_PAY_DEARER_THAN_PLAN`), not accepted as the ¥2,683.75 figure above had it.
- A whole-invoice early payment 30 days early is accepted at 0.74% (420,000 × 0.0074 = ¥3,108.00 < ¥3,113.93) and
  countered at 0.75% (¥3,150.00); the 0.64% and 0.65% boundary quoted earlier moved with the plan's cost.
- Counter A is ¥257,200 at 0.85%: discount ¥2,186.20 plus the line (¥149,986.20 × 6.4% × 32/365 = ¥841.57), ¥3,027.77,
  below C0, so it is offered.
- The other worked figures in this ADR (the hand-calculated table and the 90-day example) were derived on the 1 Oct
  books and are not re-derived here.

## Implementation note, 3 Oct 2026 (the plan C0 is the plan the agent can run)

Fourth red team, finding F1 (`services/api/tests/operations/test_redteam_d.py`). A buyer's early payment and a bill are
not legs any operation runs: the agent cannot make the buyer pay early. So `C0`, the plan an early payment is compared
with, is the cheapest plan the agent can run (the line and the invoice advances), never a plan that depends on the
buyer's early-pay facility or a bill. A plan that needs one of those legs is flagged "cannot run today", and chat and
`/negotiate` never drop such a leg silently.

- The 90-day case now accepts. On the 90-day books of `services/api/tests/verifier/test_early_pay_handcalc.py` the
  plan that can run is the line to day 47 (123,616 fen) plus the invoice advance for 89 days, billed as one posting
  (681,688 fen): `C0` = 805,304 fen, ¥8,053.04 (it was 433,333 fen when the buyer's early pay was in the plan). The
  whole invoice at 1.2% costs ¥5,040.00 and now beats `C0`, so it gives no early-pay code and is accepted; 0.85% (¥3,570.00)
  is accepted as before. The earlier statement in this ADR that 1.2% for 90 days is countered, and its ¥3,786.77 plan,
  were derived on the 1 Oct books and are superseded.
- The buyer's standing early-pay rate still prices the rest of the gap inside `C1`, the plan with the offer, as before.
  With the buyer's programme at 0.40% the router no longer plans on it (the plan stays ¥3,113.93), the whole-invoice
  0.85% offer is dearer than the plan, and Counter A (¥3,027.77) beats it and is offered
  (`test_the_buyers_cheap_standing_early_pay_is_not_a_plan_the_router_can_run`).
- A fixed-sum discount (fifth red team, F1) is tested at its exact rate on its portion, so ¥3,108.00 on ¥420,000 (0.74%)
  is accepted and ¥3,150.00 (0.75%) is countered, exactly as the rates are. Counter A names its day ("paid on or
  before day 2"), and any portion of its face paid by that day earns the rate
  (`services/api/tests/verifier/test_redteam_e.py`, `services/api/tests/operations/test_redteam_e.py`).

## Addendum, 16 Oct 2026 (the counter's face no longer reveals the gap, R-10)

**Why.** Counter A said "up to ¥257,200 at 0.85%", and 257,200 × (1 − 0.85%) ≈ ¥255,000, the owner's funding gap
to the ¥100 (`docs/security/FINDINGS_REGISTER.md` R-10). FLOW now prepares messages the owner sends to real buyers,
so the face is on a real outbound channel. The owner chose to round the face (16 Oct).

**Rule.** The early-pay counter's face is the gap net of the committed line, grossed up at the counter's rate as
before, rounded **up** to a step of two significant figures of the invoice's outstanding amount (step = 10^(digits
of the outstanding fen − 2): ¥10,000 for an invoice of ¥100,000 to ¥999,999.99), and never above the outstanding
amount (it was capped at the face). The rounded counter must pass every check the old one passed: the router's
committed plan with it must be admissible, it must beat the standing plan (test 3), and it must pass its own
re-check (FINANCIAL_SEMANTICS §7a). If it fails, the whole outstanding amount is tried under the same checks; if
that fails too, no early-pay counter is offered and the summary says why. It never falls back to the ¥100 rounding.

**Golden figures.** ¥255,000 / (1 − 0.85%) = ¥257,186.08 → **¥260,000**: discount ¥2,210.00, cash ¥257,790.00, the
line carries ¥147,210.00 (× 6.4% × 32/365 = ¥825.99), Counter A ¥3,035.99, still below C0 ¥3,113.93. A buyer can
place the gap only between ¥247,875 and ¥257,790. The whole invoice (rule b) was rejected: ¥3,570.00 at 0.85% is
dearer than C0, so it would have removed Option A from the golden story.

**Consequences, not a change of policy.** A buyer who pays the whole face pays ¥2,790 more early, so ¥160,000 of
RCV-A stays owed (was ¥162,800) and ¥2,790 of the line is left unused. On day 34 of the missed-receipt story the
router therefore draws that ¥2,790 on the line (6.40%, under the 15.00% ceiling, Tier 1) before the invoice advances,
the second advance is ¥117,210 (was ¥120,000) and the plan costs ¥1,702.20 (was ¥1,706.10). The advances still need
the owner (APR-000001, 16.26% and 32.53% against 15.00%), and the demo's day-34 cure (¥200,000, 32.52%) is unchanged.
