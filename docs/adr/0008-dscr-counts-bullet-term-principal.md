# ADR-0008: DSCR counts the principal of bullet term loans

Status: accepted, 1 Oct 2026. Owner: main architect. Implements audit F6 (tracker row D4).

## Problem

The covenant reads "monthly EBITDA / scheduled debt service (principal + interest, all facilities)". The
engine's monthly debt service holds the fixed service on existing debt, interest and fees as they post, and
the principal of amortising facilities. The principal of a bullet term loan is left out, and its interest
posts only in the month it is repaid. A ¥500,000 12-month guaranteed loan at 5% therefore shows 2.00× for
the months of its term and 1.29× in the month it is repaid, and passes a 1.25× covenant that it fails on any annual reading.

## Decision

For DSCR only, a **bullet term facility** (repayment BULLET, `term_months` set, `counts_in_debt_service`)
is serviced on a level basis: its principal and its interest and fees are spread evenly over the months of
its term.

- Each lot drawn on such a facility adds `(principal + interest + fees over its term) / term_months` to the
  debt service of each of the `term_months` months that start with the month it arrives. Division leaves a
  remainder of a few fen; it goes to the last month, so the sum over the term is exact.
- Its interest and fee postings are then not added again in the month they post.
- Cash is untouched: interest and principal still leave cash on the repayment day. Leverage is untouched.
- Nothing else changes:
  - a revolving credit line (BULLET with no `term_months`) is not scheduled principal; its interest counts
    in the month it posts, as today;
  - invoice financing (ON_RECEIPT) is repaid by the invoice it financed; its charges count as today;
  - amortising facilities already carry principal month by month;
  - existing debt keeps its fixed monthly service.
- Months beyond the projection horizon are not shown, but the months inside it carry the level amount, so
  a loan that matures after the horizon is still tested.

## Hand-calculated case (golden books)

EBITDA ¥90,000 a month; existing debt service ¥45,000 a month. Draw ¥500,000 on the guaranteed loan
(5%, 12 months, bullet) arriving in month 1.

- Interest over the term: 500,000 × 5% × 360/365 = ¥24,657.53 for 360 days (the engine charges actual
  days from arrival to repayment; the implementation takes the figure from the engine, not from this line).
- Level service: (500,000 + 24,657.53) / 12 = ¥43,721.46 a month.
- DSCR every month of the term: 90,000 / (45,000 + 43,721.46) = 1.014× < 1.25× → `DSCR_BREACH`.
- Before this decision: 2.00× in every month of the term and 90,000 / (45,000 + 24,657.53) = 1.29× in the
  month of repayment (month 13: the loan arrives on day 21 after its lead time and is repaid on day 381).
- Checked independently (`docs/research/dscr-handcalc-2026-10-01.md`): every figure agrees. Spreading only the
  principal and leaving interest in the repayment month would give 1.038× in months 1 to 12, so the loan
  fails 1.25× either way; spreading both makes the monthly and the annual reading agree (1.0144×).

## Cases settled after the independent check

- A revolving credit line is never a bullet term facility, even if it carries `term_months`.
- A term loan repaid early (an explicit repayment day) is charged interest for the actual days, and that
  total is still spread over the whole term. Service is then shown after the loan is gone. Conservative;
  left as it is.
- A balance already drawn on a bullet term loan when the projection starts is treated as arriving today
  and spread over a full term, which overstates service when part of the term has passed. Conservative;
  left as it is, because the state does not record the original draw day.

## Consequences

- A plan that relies on a bullet term loan can now fail DSCR where it passed. The router already discards
  plans that breach a covenant, so such a plan is replaced or reported inadmissible. Expected-mode plans,
  capex comparisons and the borrower file that show the guaranteed loan change with it. The documents and
  mocks follow.
- A second person re-derives the case above and two more (a 6-month bullet; a loan maturing after the
  horizon) before the change merges.
