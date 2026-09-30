"""The naive policy the router must beat: draw the credit line first, then fill the rest from the
cheapest next source by its nominal all-in annual rate (the way cash is often raised by phone).

Deliberately simple and independent of the router's search: it uses only financial.project,
covenants.evaluate and the menu's nominal rates.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.covenants import evaluate as evaluate_covenants
from app.domain.models import (
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    LedgerEventKind,
    Mandate,
    Mode,
    Obligation,
    Trajectory,
)
from app.domain.money import DAYS_PER_YEAR, bp, gross_up_face
from app.financial import EngineError, project
from app.funding import menu_view


@dataclass
class BaselineResult:
    actions: list[FundingAction]
    trajectory: Trajectory | None
    cost_fen: int | None
    admissible: bool


def _cost(t: Trajectory) -> int:
    return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen


def line_first_then_cheapest(state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> BaselineResult:
    floor = mandate.min_cash_fen
    base = project(state, obligations, [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    below = [p for p in base.days if p.closing_fen < floor]
    need = max((floor - p.closing_fen for p in below), default=0)
    if not need:
        return BaselineResult([], base, 0, True)
    first = below[0].day
    recovery = next((p.day for p in base.days if p.day > first and p.closing_fen >= floor), base.horizon_days)
    receipts = [(p.day, e.ref, e.amount_fen) for p in base.days for e in p.events
                if e.kind == LedgerEventKind.RECEIPT and p.day > first]
    facs = {f.id: f for f in state.facilities}
    actions: list[FundingAction] = []
    residual = need
    line = next((f for f in state.facilities if f.kind == FacilityKind.CREDIT_LINE
                 and f.status == FacilityStatus.COMMITTED and f.owner_approved), None)
    if line is not None:
        amt = min(line.limit_fen - line.drawn_fen, need)
        actions.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=line.id, day=0, amount_fen=amt,
                                     repay_day=recovery))
        residual -= amt
    if residual > 0:
        rows = sorted((r for r in menu_view(state, mandate) if r.admissible_for_need
                       and r.kind != FacilityKind.CREDIT_LINE), key=lambda r: r.all_in_rate.value)
        if rows:
            f = facs[rows[0].facility_id]
            rid = receipts[0][1] if receipts else None
            if f.kind == FacilityKind.INVOICE_FINANCING:
                actions.append(FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=f.id, day=0,
                                             amount_fen=residual, receivable_id=rid))
            elif f.kind == FacilityKind.BUYER_EARLY_PAY:
                actions.append(FundingAction(kind=FundingActionKind.EARLY_PAY, facility_id=f.id, day=0,
                                             amount_fen=gross_up_face(residual, bp(f.rate_bp)), receivable_id=rid,
                                             rate_bp=f.rate_bp))
            elif f.kind == FacilityKind.BANK_ACCEPTANCE_BILL:
                maturity = 30 * (f.term_months or 6)
                d = bp(f.rate_bp) * (maturity - f.lead_time_days) / DAYS_PER_YEAR
                actions.append(FundingAction(kind=FundingActionKind.DISCOUNT_BILL, facility_id=f.id, day=0,
                                             amount_fen=gross_up_face(residual, d), repay_day=maturity,
                                             rate_bp=f.rate_bp))
            else:
                actions.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=0,
                                             amount_fen=residual))
    try:
        t = project(state, obligations, actions, Mode.CONSERVATIVE, mandate.horizon_days, floor)
    except EngineError:
        return BaselineResult(actions, None, None, False)
    used = {a.facility_id for a in actions}
    binding = [f for f in state.facilities if f.status == FacilityStatus.COMMITTED or f.id in used]
    ok = t.first_breach_day is None and not evaluate_covenants(t, binding, mandate)
    debt = any(facs[a.facility_id].kind not in (FacilityKind.BUYER_EARLY_PAY, FacilityKind.BANK_ACCEPTANCE_BILL)
               for a in actions)
    if debt and not mandate.allow_new_borrowing:
        ok = False
    return BaselineResult(actions, t, _cost(t) - _cost(base), ok)
