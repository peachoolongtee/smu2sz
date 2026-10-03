"""One leg on books where earlier legs already ran: the rule admission applies and the router plans by
(docs/FINANCIAL_SEMANTICS.md, "Admission").

The executor admits a plan leg by leg, each on the books the legs before it left. The router judges every prefix of
its plan the same way, so a plan it presents as runnable is one admission takes leg by leg in the order shown:

- `as_executed`: the books right after legs execute today. A draw on an open line becomes the lot it is (`carry_draw`:
  no repayment day, repaid by the engine on the first affordable receipt day); every other leg stays an action, which
  the engine projects as it projects the lot the executor creates.
- `leg_violations`: what admission refuses, given the projection before the leg and after it: DSCR or leverage
  breached after it (not for a repayment), or the lowest closing from today below min(reserve, lowest before).
"""

from __future__ import annotations

from app.covenants import evaluate as evaluate_covenants
from app.domain.models import (
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    Mandate,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import fmt_yuan
from app.financial.lots import carry_draw, is_open_line

RATIO_CODES = (ViolationCode.DSCR_BREACH, ViolationCode.LEVERAGE_BREACH)


def carries(a: FundingAction, state: FinancialState) -> bool:
    """`a` is a draw today on an open line: once executed it is a carried lot, not the action."""
    f = next((x for x in state.facilities if x.id == a.facility_id), None)
    return (a.kind == FundingActionKind.DRAW and a.day == state.as_of_day and f is not None and is_open_line(f))


def as_executed(state: FinancialState, actions: list[FundingAction] | tuple[FundingAction, ...],
                tag: str = "admission-probe") -> tuple[FinancialState, list[FundingAction]]:
    """(books, actions still to project) right after `actions` execute today (see the module docstring)."""
    rest: list[FundingAction] = []
    for a in actions:
        if carries(a, state):
            f = next(x for x in state.facilities if x.id == a.facility_id)
            state = carry_draw(state, f, a.amount_fen, f"{tag}-{a.facility_id}")
        else:
            rest.append(a)
    return state, rest


def worst(t: Trajectory, today: int) -> int:
    return min(p.closing_fen for p in t.days if p.day >= today)


def leg_violations(state: FinancialState, before: Trajectory | None, after: Trajectory, kind: FundingActionKind,
                   mandate: Mandate) -> list[Violation]:
    """Why admission refuses one leg on `state` (the books before it), given the projection without it (`before`,
    None when the books do not project) and with it (`after`). Empty when admitted."""
    today, floor = state.as_of_day, mandate.min_cash_fen
    out: list[Violation] = []
    if kind != FundingActionKind.REPAY:
        binding = [f for f in state.facilities if f.status == FacilityStatus.COMMITTED]
        seen: set[tuple[ViolationCode, str | None]] = set()
        for v in evaluate_covenants(after, binding, mandate):
            key = (v.code, v.inputs.get("facility_id"))
            if v.code in RATIO_CODES and key not in seen:
                seen.add(key)
                out.append(v)
    worst_after = worst(after, today)
    allowed = floor if before is None else min(floor, worst(before, today))
    if worst_after < allowed:
        day = next(p.day for p in after.days if p.day >= today and p.closing_fen == worst_after)
        out.append(Violation(
            code=ViolationCode.RESERVE_BREACH,
            message=(f"After this operation projected cash would fall to {fmt_yuan(worst_after)} on day {day}, "
                     f"below the reserve {fmt_yuan(floor)}"),
            day=day, observed=fmt_yuan(worst_after), limit=fmt_yuan(floor),
            formula=(f"lowest projected closing after the operation >= min(reserve, lowest before): "
                     f"{fmt_yuan(worst_after)} < {fmt_yuan(allowed)}")))
    return out


__all__ = ["RATIO_CODES", "as_executed", "carries", "leg_violations", "worst"]
