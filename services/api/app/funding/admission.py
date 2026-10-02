"""Admission of one funding operation on today's books (audit A05; docs/FINANCIAL_SEMANTICS.md, "Admission").

The executor calls `admit` inside its transaction for every draw, invoice-financing submission and repayment,
whoever asks. It answers two questions with the engine and predicates the planner uses, so a plan the router
would reject cannot be executed leg by leg through `/operations`:

- `violations`: the operation is refused. The engine cannot book it (advance above the advance rate of the
  outstanding face, cash landing on or after the due day, over the limit, invoice already paid early or
  financed), or it breaches DSCR or leverage, or it takes projected cash below the reserve where it was not
  below it before (or deeper below it).
- `approval_reason`: the operation is inside the hard limits but above what the agent may do alone, so the owner
  must approve it (Tier 2). Today: an effective annual cost above the mandate's `max_apr_bp`. The cost is
  `funding.rates.action_rate`, the same function and the same receivable days the router prices its plans with,
  so a plan the router presents as autonomous is admitted without the owner.

Clean-down is not tested here: it is breached by failing to repay, not by one draw; the planner and the alerts
test it over the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from app.books import Books
from app.covenants import evaluate as evaluate_covenants
from app.domain.models import (
    DrawFacility,
    FacilityKind,
    FacilityStatus,
    FundingAction,
    FundingActionKind,
    Mandate,
    Mode,
    RepayFacility,
    SubmitInvoiceForFinancing,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.funding.rates import action_rate, approval_reason, invoice_landing_day
from app.funding.search import receivables

RATIO_CODES = (ViolationCode.DSCR_BREACH, ViolationCode.LEVERAGE_BREACH)


@dataclass(frozen=True, slots=True)
class Admission:
    violations: list[Violation] = field(default_factory=list)
    approval_reason: str | None = None


def action_for(op: object, day: int) -> FundingAction | None:
    """The engine action an operation stands for, requested on `day`; None for an operation that is not one."""
    if isinstance(op, DrawFacility):
        return FundingAction(kind=FundingActionKind.DRAW, facility_id=op.facility_id, day=day, amount_fen=op.amount_fen)
    if isinstance(op, SubmitInvoiceForFinancing):
        return FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=op.facility_id,
                             receivable_id=op.receivable_id, day=day, amount_fen=op.advance_fen)
    if isinstance(op, RepayFacility):
        return FundingAction(kind=FundingActionKind.REPAY, facility_id=op.facility_id, day=day, amount_fen=op.amount_fen)
    return None


def effective_rate(op: object, books: Books, baseline: Trajectory | None = None) -> tuple[Fraction, str] | None:
    """(effective annual cost, how it was computed) of a borrowing operation; None when it has none
    (a repayment, an unknown facility or invoice: the executor's own preconditions refuse those).

    The price is `funding.rates.action_rate`, as in the router. An invoice's issue and due days are the ones the
    unfunded projection (`baseline`, the books without this operation) receives it on, as the router reads them
    (`funding.search.receivables`); the state's own days when the projection does not show the invoice."""
    state = books.state
    f = next((x for x in state.facilities if x.id == getattr(op, "facility_id", None)), None)
    if f is None:
        return None
    if isinstance(op, DrawFacility):
        return action_rate(f, FundingActionKind.DRAW, amount_fen=op.amount_fen)
    if isinstance(op, SubmitInvoiceForFinancing) and f.kind == FacilityKind.INVOICE_FINANCING:
        r = next((x for x in state.receivables if x.id == op.receivable_id), None)
        if r is None or op.advance_fen <= 0:
            return None
        issue, due = r.issue_day, r.due_day
        seen = receivables(state, baseline).get(r.id) if baseline is not None else None
        if seen is not None:
            issue, due = seen.issue_day, seen.due_day
        landing = invoice_landing_day(f, books.day, issue)
        if due <= landing:
            return None  # refused by the engine: the cash would not land before the invoice is due
        return action_rate(f, FundingActionKind.FINANCE_INVOICE, amount_fen=op.advance_fen,
                           landing_day=landing, due_day=due)
    return None


def _worst(t: Trajectory, today: int) -> int:
    return min(p.closing_fen for p in t.days if p.day >= today)


def admit(op: object, books: Books, mandate: Mandate) -> Admission:
    state, today = books.state, books.day
    action = action_for(op, today)
    if action is None:
        return Admission()
    obligations = list(books.obligations)
    floor, horizon = mandate.min_cash_fen, mandate.horizon_days
    try:
        after = project(state, obligations, [action], Mode.CONSERVATIVE, horizon, floor)
    except EngineError as exc:
        return Admission([Violation(code=ViolationCode.PRECONDITION_FAILED, message=str(exc))])
    try:
        before: Trajectory | None = project(state, obligations, [], Mode.CONSERVATIVE, horizon, floor)
    except EngineError:
        before = None  # the books do not project without the operation; judge the result alone

    out: list[Violation] = []
    if action.kind != FundingActionKind.REPAY:
        binding = [f for f in state.facilities if f.status == FacilityStatus.COMMITTED]
        seen: set[tuple[ViolationCode, str | None]] = set()
        for v in evaluate_covenants(after, binding, mandate):
            key = (v.code, v.inputs.get("facility_id"))
            if v.code in RATIO_CODES and key not in seen:
                seen.add(key)
                out.append(v)
    worst_after = _worst(after, today)
    allowed = floor if before is None else min(floor, _worst(before, today))
    if worst_after < allowed:
        day = next(p.day for p in after.days if p.day >= today and p.closing_fen == worst_after)
        out.append(Violation(
            code=ViolationCode.RESERVE_BREACH,
            message=(f"After this operation projected cash would fall to {fmt_yuan(worst_after)} on day {day}, "
                     f"below the reserve {fmt_yuan(floor)}"),
            day=day, observed=fmt_yuan(worst_after), limit=fmt_yuan(floor),
            formula=(f"lowest projected closing after the operation >= min(reserve, lowest before): "
                     f"{fmt_yuan(worst_after)} < {fmt_yuan(allowed)}")))
    if out:
        return Admission(out)

    reason = None
    rated = effective_rate(op, books, before)
    if rated is not None:
        reason = approval_reason(rated[0], rated[1], mandate)
    return Admission([], reason)


__all__ = ["Admission", "action_for", "admit", "effective_rate"]
