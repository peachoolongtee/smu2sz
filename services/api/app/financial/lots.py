"""Funding lots (ADR-0010): one dated record per draw or invoice advance, read by the projection, the executor
and the clock alike.

- A lot takes facility room at once; its cash lands on `arrival_day` (request day + lead time), net of the
  upfront fee, at once when the lead time is zero and otherwise when the clock closes that day.
- Interest runs from `arrival_day`.
- `contractual_payments` is the one schedule: amortising instalments, or a bullet term loan's maturity. A credit
  line has none (its repayment is discretionary) and an invoice advance is repaid from its invoice's receipt.

Pure: no I/O, no clock.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.models import Facility, FacilityKind, FinancialState, FundingLot, Repayment
from app.domain.money import fmt_yuan
from app.financial.amortisation import amortisation_schedule
from app.financial.charges import finance_invoice_charges, line_interest, upfront_fee

MONTH_DAYS = 30
ASSUMED_PREFIX = "ASSUMED:"


def has_maturity(f: Facility) -> bool:
    """A bullet loan with a term (never a revolving credit line) is repaid in full at maturity."""
    return f.repayment == Repayment.BULLET and bool(f.term_months) and f.kind != FacilityKind.CREDIT_LINE


def maturity_day(f: Facility, arrival_day: int) -> int | None:
    return arrival_day + MONTH_DAYS * (f.term_months or 0) if has_maturity(f) else None


def new_lot(lot_id: str, f: Facility, amount_fen: int, request_day: int,
            receivable_id: str | None = None) -> FundingLot:
    """The lot a draw or advance requested on `request_day` creates. Settled at once only with no lead time."""
    arrival = request_day + f.lead_time_days
    return FundingLot(id=lot_id, facility_id=f.id, principal_fen=amount_fen, remaining_fen=amount_fen,
                      request_day=request_day, arrival_day=arrival, receivable_id=receivable_id,
                      maturity_day=maturity_day(f, arrival), settled=f.lead_time_days == 0)


def unique_id(lots: list[FundingLot], wanted: str) -> str:
    have = {lot.id for lot in lots}
    if wanted not in have:
        return wanted
    n = 2
    while f"{wanted}#{n}" in have:
        n += 1
    return f"{wanted}#{n}"


def landing_cash(f: Facility, lot: FundingLot) -> int:
    """The cash a lot credits when it lands: the amount requested net of the upfront fee."""
    return lot.remaining_fen - upfront_fee(f, lot.remaining_fen)


# ---------------------------------------------------------------- the schedule


@dataclass(frozen=True, slots=True)
class LotPayment:
    """One contractual payment of a lot: `principal` and `interest` fall due on `day`. `month` is the instalment
    number of an amortising lot; None for a bullet maturity."""

    day: int
    principal: int
    interest: int
    month: int | None = None


def contractual_payments(lot: FundingLot, f: Facility) -> list[LotPayment]:
    """The payments still due on `lot`, in day order (ADR-0010 §4): the amortising instalments its remaining
    balance has not yet paid, or a bullet term loan's maturity. Empty for a credit line or an invoice advance."""
    if lot.remaining_fen <= 0:
        return []
    if f.repayment == Repayment.AMORTISING and f.term_months:
        rows = amortisation_schedule(lot.principal_fen, f.rate_bp, f.term_months)
        paid, k, cum = lot.principal_fen - lot.remaining_fen, 0, 0
        while k < len(rows) and cum < paid:
            cum += rows[k].principal
            k += 1
        if cum == paid:
            return [LotPayment(lot.arrival_day + MONTH_DAYS * r.month, r.principal, r.interest, r.month)
                    for r in rows[k:]]
        # off the schedule (a balance trimmed by a what-if): the remainder amortises over the months left
        k -= 1
        rest = amortisation_schedule(lot.remaining_fen, f.rate_bp, max(1, len(rows) - k))
        return [LotPayment(lot.arrival_day + MONTH_DAYS * (k + r.month), r.principal, r.interest, k + r.month)
                for r in rest]
    if lot.maturity_day is not None:
        days = lot.maturity_day - lot.arrival_day
        return [LotPayment(lot.maturity_day, lot.remaining_fen, line_interest(lot.remaining_fen, f.rate_bp, days))]
    return []


# ---------------------------------------------------------------- balances older than the lots


def _trim(lots: list[FundingLot], fid: str, excess: int) -> list[FundingLot]:
    """Take `excess` off a facility's lots, oldest landed first (as a repayment would)."""
    order = sorted((i for i, lot in enumerate(lots) if lot.facility_id == fid),
                   key=lambda i: (not lots[i].settled, lots[i].arrival_day, i))
    out = list(lots)
    for i in order:
        if excess == 0:
            break
        part = min(excess, out[i].remaining_fen)
        out[i] = out[i].model_copy(update={"remaining_fen": out[i].remaining_fen - part})
        excess -= part
    return [lot for lot in out if lot.remaining_fen > 0]


def ensure_lots(state: FinancialState) -> FinancialState:
    """Pure normaliser: every facility's lots sum to its drawn balance.

    A balance no lot explains (a fixture, an older stored state) becomes an assumed lot dated today
    (`state.as_of_day`, day 0 for a fixture), already settled: on an invoice-financing facility, one lot per
    advance recorded on a FINANCED invoice, then one for the rest. Lots above the drawn balance (a what-if copy
    that lowered it) are trimmed oldest landed first. Returns `state` itself when nothing is missing."""
    have: dict[str, int] = defaultdict(int)
    for lot in state.lots:
        have[lot.facility_id] += lot.remaining_fen
    if all(f.drawn_fen == have.get(f.id, 0) for f in state.facilities):
        return state
    lots = list(state.lots)
    today = state.as_of_day
    linked = {lot.receivable_id for lot in lots if lot.receivable_id}
    for f in state.facilities:
        gap = f.drawn_fen - have.get(f.id, 0)
        if gap < 0:
            lots = _trim(lots, f.id, -gap)
            continue
        if gap == 0:
            continue
        if f.kind == FacilityKind.INVOICE_FINANCING:
            recorded = sorted((r for r in state.receivables if r.status == "FINANCED" and r.advance_fen > 0
                               and r.advance_facility_id == f.id and r.id not in linked),
                              key=lambda r: (r.due_day, r.id))
            for r in recorded:
                amount = min(gap, r.advance_fen)
                if amount <= 0:
                    break
                lots.append(FundingLot(id=unique_id(lots, f"{ASSUMED_PREFIX}{f.id}:{r.id}"), facility_id=f.id,
                                       principal_fen=amount, remaining_fen=amount, request_day=today,
                                       arrival_day=today, receivable_id=r.id, settled=True, assumed_date=True))
                gap -= amount
        if gap > 0:
            lots.append(FundingLot(id=unique_id(lots, f"{ASSUMED_PREFIX}{f.id}"), facility_id=f.id,
                                   principal_fen=gap, remaining_fen=gap, request_day=today, arrival_day=today,
                                   maturity_day=maturity_day(f, today), settled=True, assumed_date=True))
    return state.model_copy(update={"lots": lots})


# ---------------------------------------------------------------- a discretionary repayment


@dataclass(frozen=True, slots=True)
class Repaid:
    lots: list[FundingLot]  # the state's lots after the repayment
    interest: int
    parts: list[str]  # one formula per lot repaid


def landed(lots: list[FundingLot], facility_id: str) -> int:
    """What can be repaid on a facility today: the remaining balance of its settled lots."""
    return sum(lot.remaining_fen for lot in lots if lot.facility_id == facility_id and lot.settled)


def first_unsettled(lots: list[FundingLot], facility_id: str) -> FundingLot | None:
    pending = [lot for lot in lots if lot.facility_id == facility_id and not lot.settled]
    return min(pending, key=lambda lot: lot.arrival_day) if pending else None


def repay(lots: list[FundingLot], f: Facility, amount_fen: int, day: int) -> Repaid:
    """Repay `amount_fen` on `f` on `day` from its settled lots, earliest landed first, with each part's interest
    from its landing day (ADR-0010 §3, §6). Raises ValueError when the settled lots hold less."""
    if amount_fen > landed(lots, f.id):
        raise ValueError(f"{f.id} has only {fmt_yuan(landed(lots, f.id))} landed to repay")
    order = sorted((i for i, lot in enumerate(lots) if lot.facility_id == f.id and lot.settled and lot.remaining_fen),
                   key=lambda i: (lots[i].arrival_day, i))
    out, left, interest, parts = list(lots), amount_fen, 0, []
    for i in order:
        if left == 0:
            break
        lot = out[i]
        part = min(left, lot.remaining_fen)
        days = day - lot.arrival_day
        lot_interest = line_interest(part, f.rate_bp, days)
        interest += lot_interest
        parts.append(f"{fmt_yuan(part)} × {f.rate_bp}bp × {days}/365 = {fmt_yuan(lot_interest)}")
        out[i] = lot.model_copy(update={"remaining_fen": lot.remaining_fen - part})
        left -= part
    return Repaid([lot for lot in out if lot.remaining_fen > 0], interest, parts)


# ---------------------------------------------------------------- a receipt on a financed invoice


def advance_charges(f: Facility, lot: FundingLot, day: int) -> tuple[int, int, int]:
    """(interest, period fee, periods) an invoice advance owes when it is cleared on `day`: on its original
    principal, from the day its cash landed, in whole periods. Billed once, by the receipt that clears it."""
    return finance_invoice_charges(f, lot.principal_fen, day - lot.arrival_day)


@dataclass(frozen=True, slots=True)
class ReceiptApplied:
    applied: int  # what the lender takes from the receipt; the owner keeps the rest
    lot: FundingLot | None  # the advance still outstanding, or None when this receipt cleared it
    principal: int  # principal repaid by this receipt
    interest: int = 0  # charges billed by this receipt (only when it clears the advance)
    fee: int = 0
    periods: int = 0
    days: int = 0


def is_fixed_remainder(lot: FundingLot) -> bool:
    """A lot whose charges have been billed (`principal_fen` 0): `remaining_fen` is a fixed amount due to the
    lender and nothing accrues on it (`advance_charges` is zero). Created by `apply_receipt`."""
    return lot.principal_fen == 0 and lot.remaining_fen > 0


def apply_receipt(f: Facility, lot: FundingLot, amount_fen: int, day: int, final: bool = False) -> ReceiptApplied:
    """A buyer's receipt on a FINANCED invoice whose advance `lot` has landed goes to the lender first. `final`:
    this receipt brings the invoice's outstanding face to zero.

    - It clears the advance when it covers the remaining principal plus the charges (`advance_charges`): the
      lender takes exactly that and the owner keeps the rest.
    - A smaller receipt that is not the invoice's last goes wholly to the lender and reduces the remaining
      principal; the charges stay due on the lot and are billed by the receipt that clears it, so the advance is
      charged once, on its original principal, from landing to clearing.
    - Otherwise (the receipt covers the principal but not all the charges, or it is the invoice's last and does
      not cover the claim) it also goes wholly to the lender and the charges are billed now: what the receipt does
      not cover stays on the lot as a FIXED amount (`is_fixed_remainder`: principal 0, nothing accrues, never
      charged again). After a final receipt the invoice is SETTLED and the owner owes that amount directly
      (RepayFacility on the orphaned lot).
    The owner's cash never falls because of a receipt."""
    interest, fee, periods = advance_charges(f, lot, day)
    days = day - lot.arrival_day
    claim = lot.remaining_fen + interest + fee
    if amount_fen >= claim:
        return ReceiptApplied(claim, None, lot.remaining_fen, interest, fee, periods, days)
    if amount_fen < lot.remaining_fen and not final:
        return ReceiptApplied(amount_fen, lot.model_copy(update={"remaining_fen": lot.remaining_fen - amount_fen}),
                              amount_fen)
    fixed = lot.model_copy(update={"principal_fen": 0, "remaining_fen": claim - amount_fen})
    return ReceiptApplied(amount_fen, fixed, min(amount_fen, lot.remaining_fen), interest, fee, periods, days)


def orphaned(state: FinancialState, facility_id: str) -> list[FundingLot]:
    """Landed lots on `facility_id` whose invoice is SETTLED (or no longer on the books): what is left on them is
    owed by the owner directly, as a fixed amount, oldest landed first."""
    status = {r.id: r.status for r in state.receivables}
    return sorted((lot for lot in state.lots if lot.facility_id == facility_id and lot.settled
                   and lot.remaining_fen > 0 and lot.receivable_id is not None
                   and status.get(lot.receivable_id, "SETTLED") == "SETTLED"),
                  key=lambda lot: (lot.arrival_day, lot.id))


__all__ = [
    "ASSUMED_PREFIX",
    "LotPayment",
    "ReceiptApplied",
    "Repaid",
    "advance_charges",
    "apply_receipt",
    "contractual_payments",
    "ensure_lots",
    "first_unsettled",
    "has_maturity",
    "is_fixed_remainder",
    "landed",
    "landing_cash",
    "maturity_day",
    "new_lot",
    "orphaned",
    "repay",
    "unique_id",
]
