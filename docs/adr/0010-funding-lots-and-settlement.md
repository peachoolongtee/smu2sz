# ADR-0010: Funding lots with dates; cash lands after the lead time

Status: accepted, 3 Oct 2026. Owner: technical owner. Closes audit A08 and F-FIN-02.

## Problem

The projection lands funding cash after the facility's lead time; the executor credits it on the request day.
The state keeps only a drawn balance per facility, so the projection dates every balance to day 0, re-posts
instalments into days that are already closed, and the executor rebuilds lot dates from the operations log. The
clock posts scheduled flows but no loan instalment or maturity. Three modules hold three versions of the same debt.

## Decision

1. **Lots in the state.** `FinancialState.lots: list[FundingLot]`. A lot has: `id` (the operation id),
   `facility_id`, `principal_fen`, `remaining_fen`, `request_day`, `arrival_day` (request day + lead time),
   `receivable_id` (an invoice advance), `maturity_day` (bullet term loans: arrival + 30 × term months; else none),
   `settled` (the cash has been credited) and `assumed_date` (a balance that existed before the books started;
   dated to the first day of the books). The sum of `remaining_fen` over a facility's lots always equals its
   `drawn_fen`.
2. **Requested is not cash.** A draw or advance takes facility room and creates the lot at once. Cash is credited
   on the arrival day: at once when the lead time is zero, otherwise by the simulated bank when the clock closes
   that day (like a scheduled flow), net of the upfront fee. Until then the lot is unsettled and the projection
   shows the inflow on its arrival day.
3. **Interest runs from the arrival day**, in the projection and in the executor. A repayment or an invoice
   receipt reads the lot from the state, not from the log.
4. **One schedule function.** `app/financial/lots.py` gives the dated contractual payments of a lot (amortising
   instalments; a term bullet's maturity; an invoice advance's repayment on the receipt). The projection posts the
   payments dated today or later; the clock posts the ones it closes, reducing the lot and the drawn balance and
   logging them. Nothing is ever posted into a closed day.
5. **Discretionary repayment stays a proposal.** A revolving line has no contractual repayment day. The projection
   assumes the first affordable day (existing rule) and labels it "assumed"; only a RepayFacility operation makes
   it real. The repay alert proposes it.
6. **Only a settled lot can be repaid**, and an unsettled advance still marks its invoice FINANCED (it is pledged
   from the request).

7. **Existing debt follows the same rule.** A `DebtPosition` (a loan that predates the books) is paid on one
   schedule, `app/financial/debts.py` (`next_payment_day`, `payment_every_days`, simple interest at `rate_bp` since
   the last payment, the rest of the fixed service as principal). The projection posts the payments dated today or
   later as DEBT_SERVICE outflows and lowers the debt by the principal; the clock pays the ones on the days it
   closes, lowers `principal_fen`, moves `next_payment_day` and lists them in the ADVANCE_CLOCK payload
   (`posted_debt_service`). Closing days then projecting gives the suffix of the earlier projection.

## Consequences

- The day-34 cure requested on day 34 is cash on day 37; the UI and the chat say so. Its cost is unchanged
  (one 30-day period, ¥1,782.19); its effective annual cost is on 10 days.
- `operations.log.open_lots` and `advance_for` are no longer the source of lot dates.
- A projection made on any day starts from actual cash and actual lots; closing days then projecting gives the
  remaining suffix of the earlier projection when nothing else changed (new property test).
- A funding request that has not settled is visible as such, which lets the alerts say when expected cash has not
  arrived.
