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
- Counter A's face is ¥211,900 since tracker row B5 (it was ¥211,800, which netted ¥0.30 short of the gap).

## Consequences

- Golden verdicts that accepted a whole-invoice discount between 0.65% and 0.88% become COUNTER. The
  documents, the demo script and the mock data must follow. The 0.8832% break-even figure survives as the
  first screen.
- The verifier runs the router twice more per early-pay offer. Both runs are cached per (state,
  obligations).
