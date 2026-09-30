# ADR-0002: One rounding rule: exact until posted, half-up to the fen, once

**Status:** accepted, 1 Oct 2026. It resolves the rounding ticket (issue #3).

## Rule
- Money is integer fen. Rates are integer basis points. Intermediate values are exact rationals (`fractions.Fraction`) measured in fen.
- A value is rounded **once**, half-up (四舍五入, away from zero), at one of two moments:
  - **Posting:** a cash movement enters the ledger. Examples: interest at repayment, a fee, a discount.
  - **Reporting a valuation:** a forward value, a per-invoice funding cost, or an NPV.
- **A total is the sum of already-rounded parts.** A plan's cost is what the ledger actually pays. Unrounded parts are never summed and then rounded.
- Day count is Actual/365 simple interest. Amortising loans and leases use monthly rate `r/12`:
  - the payment is rounded half-up;
  - each month's interest is `post(balance × r/12)`;
  - the final payment clears the balance.
- The NPV uses the effective monthly rate `(1+h)^(1/12) − 1` in 50-digit `Decimal`, rounded once.
- Ratios (DSCR, leverage) are compared exactly and displayed to 2 dp, half-up.
- A grossed-up invoice face (`net / (1 − d)`) is rounded to the fen. The discount is then `face − net`, so cash is exact.

## Differences from spec v2 (the fixture script was never found)
| Quantity | Spec v2 | Now | Why |
| --- | --- | --- | --- |
| v2 optimum (line + invoice financing) | ¥2,712.95 | **¥2,712.94** | ¥841.64 + ¥1,871.30; the spec rounded the unrounded sum |
| Counter A total | ¥2,641.95 | **¥2,641.94** | ¥1,800.30 + ¥841.64 |
| 18-month loan interest | ¥26,950.85 | **¥26,950.84** | the actual rounded schedule |
| 36-month loan interest | ¥53,206.17 | **¥53,206.14** | the actual rounded schedule |
| 48-month lease interest | ¥92,327.34 | **¥92,327.32** | the actual rounded schedule |
| Lease vs 36-month loan | ¥39,121.17 | **¥39,121.18** | the difference of the two schedules |

Every other golden value in handoff §7 matches exactly. The oracle is `fixtures/golden/compute_golden.py` and its output is `fixtures/golden/golden_values.json`. It is written independently of the engine, so tests compare two implementations.

## Alternatives rejected
Banker's rounding, because it's unfamiliar to Chinese SME accounting. Rounding only displayed totals, because the ledger can't pay a sub-fen balance and the totals would disagree with the posted rows.
