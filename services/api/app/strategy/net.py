"""Net cash at collection (map #88, ticket #107): what an invoice leaves the owner on a day, after the lender.

One pure function, `net_at_collection`. For an invoice with no financing the net is its whole outstanding. For a FINANCED
invoice the lender is paid first (ADR-0010): the receipt clears the advance with the charges the facility sets
(`funding_lots.advance_charges`: whole fee periods, billed once, on the original principal from the day the cash landed),
and the owner keeps the rest. A receipt that does not cover the claim leaves the difference owed by the owner (recourse, the
engine's `orphaned` rule), never a negative net.

Financing has three states, never mixed (the owner's words, 12 Oct): ARRANGED (the lot exists, its cash has not landed),
RECEIVED (landed: the cash is in the account from that day) and REPAID (a receipt cleared the claim). NONE: no financing.

Read-only and deterministic; nothing is stored, booked or sent. The sentences are in `app.strategy.words.net_words`.
"""

from __future__ import annotations

from typing import Literal

from app.domain.models import Contract, Day, Facility, Fen, FinancialState, FundingLot, Receivable
from app.financial import lots as funding_lots
from app.financial.charges import fee_period_days

FinancingState = Literal["ARRANGED", "RECEIVED", "REPAID", "NONE"]


class NetAtCollection(Contract):
    """What one invoice leaves the owner if it is paid on `on_day`. Money is integer fen; nothing here is a sentence."""

    face_fen: Fen
    outstanding_fen: Fen
    financing_state: FinancingState
    advance_fen: Fen  # the advance still on the lender's books (0 without financing)
    charges_fen: Fen  # interest and fee to `on_day`, in whole fee periods
    claim_fen: Fen  # advance + charges on `on_day`: what the lender takes from the receipt
    net_fen: Fen  # outstanding less the claim, never below 0
    owed_by_owner_fen: Fen  # what the claim exceeds the outstanding by: the owner owes it directly
    per_period_more_fen: Fen  # what one more fee period adds to the charges (0 without a running advance)
    period_days: int  # the facility's fee period (0 without financing)
    arrival_day: Day | None  # the day the lot's cash lands / landed (None without financing)
    on_day: Day  # the day priced


def lot_state(lot: FundingLot | None) -> FinancingState:
    """The state of an advance lot: not landed -> ARRANGED; landed with something still owed -> RECEIVED; no lot -> NONE."""
    if lot is None:
        return "NONE"
    return "RECEIVED" if lot.settled else "ARRANGED"


def advance_lot(state: FinancialState, receivable: Receivable) -> FundingLot | None:
    """The advance lot a FINANCED invoice carries (lots as the projection reads them, `ensure_lots`), else None."""
    if receivable.status != "FINANCED":
        return None
    return next((x for x in funding_lots.ensure_lots(state).lots
                 if x.receivable_id == receivable.id and x.remaining_fen > 0), None)


def net_at_collection(state: FinancialState, receivable: Receivable, day: Day | None = None, *,
                      financed_before: bool = False) -> NetAtCollection:
    """The net cash `receivable` leaves if paid in full on `day` (default: its due day).

    `financed_before` says a receivable already settled was financed: once a receipt clears the advance the lot is gone and
    the books keep no trace on the invoice, so a caller that read the log passes it and the state is REPAID."""
    on_day = receivable.due_day if day is None else day
    outstanding = receivable.outstanding_fen
    lot = advance_lot(state, receivable)
    if lot is None:
        repaid = financed_before and outstanding <= 0
        return NetAtCollection(
            face_fen=receivable.face_fen, outstanding_fen=outstanding, financing_state="REPAID" if repaid else "NONE",
            advance_fen=0, charges_fen=0, claim_fen=0, net_fen=max(0, outstanding), owed_by_owner_fen=0,
            per_period_more_fen=0, period_days=0, arrival_day=None, on_day=on_day)
    f: Facility = next(x for x in state.facilities if x.id == lot.facility_id)
    interest, fee, _ = funding_lots.advance_charges(f, lot, on_day)
    charges = interest + fee
    claim = lot.remaining_fen + charges
    period = fee_period_days(f)
    later_interest, later_fee, _ = funding_lots.advance_charges(f, lot, on_day + period)  # one whole period more
    return NetAtCollection(
        face_fen=receivable.face_fen, outstanding_fen=outstanding, financing_state=lot_state(lot),
        advance_fen=lot.remaining_fen, charges_fen=charges, claim_fen=claim, net_fen=max(0, outstanding - claim),
        owed_by_owner_fen=max(0, claim - outstanding),
        per_period_more_fen=later_interest + later_fee - charges, period_days=period, arrival_day=lot.arrival_day, on_day=on_day)


__all__ = ["FinancingState", "NetAtCollection", "advance_lot", "lot_state", "net_at_collection"]
