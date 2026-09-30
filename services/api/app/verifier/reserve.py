"""The minimum-cash predicate as the verifier applies it, and the cure of a breach.

**Offer-induced breaches only.** The golden state already has a near-term gap (payroll on day 12)
that exists whatever the buyer says; the Debt Desk's standing committed plan covers it. A breach is
charged to an offer only on a day when the offer's conservative cash is below the floor *and* below
the no-offer baseline. A breach that is not induced is reported by the committed plan, not as a
violation of the offer.

**Cure.** A breach the offer induces through a terms change recurs every month, so its cure is priced
only on sources able to carry a *permanent* need: the router runs on a copy of the state without
clean-down credit lines (covenants.line_can_carry_permanent_need), buyer early payment (available
only while offered, not debt), held bills (a finite stock) and equity. If the offer leaves the
baseline gap open, the copy first books the standing committed plan's cash effect as dated flows and
takes the capacity it uses off those facilities' limits, so the cure prices only the induced gap.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from app.covenants import line_can_carry_permanent_need
from app.domain.models import (
    CashFlow,
    Facility,
    FacilityKind,
    FinancialState,
    FlowKind,
    FundingActionKind,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import fmt_yuan
from app.financial import project
from app.funding import plan as funding_plan

NOT_PERMANENT_KINDS = frozenset({FacilityKind.BUYER_EARLY_PAY, FacilityKind.BANK_ACCEPTANCE_BILL, FacilityKind.EQUITY})


# ---------------------------------------------------------------- cached baseline


@lru_cache(maxsize=32)
def _baseline(state_json: str, mandate_json: str) -> tuple[Trajectory, FundingPlan]:
    state = FinancialState.model_validate_json(state_json)
    mandate = Mandate.model_validate_json(mandate_json)
    traj = project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return traj, funding_plan(state, [], mandate, "COMMITTED")


def baseline(state: FinancialState, mandate: Mandate) -> tuple[Trajectory, FundingPlan]:
    """(no-offer conservative trajectory, the Debt Desk's standing committed plan). Cached."""
    return _baseline(state.model_dump_json(), mandate.model_dump_json())


# ---------------------------------------------------------------- induced breach


def _closing(t: Trajectory) -> dict[int, int]:
    return {p.day: p.closing_fen for p in t.days}


def induced_breach_days(offer_traj: Trajectory, base_traj: Trajectory, floor: int) -> list[int]:
    base = _closing(base_traj)
    return [p.day for p in offer_traj.days if p.closing_fen < floor and p.closing_fen < base.get(p.day, floor)]


def reserve_violation(offer_traj: Trajectory, base_traj: Trajectory, floor: int, first: int) -> Violation:
    """RESERVE_BREACH on the first induced day; `curable` is set by the caller."""
    days = sorted(offer_traj.days, key=lambda p: p.day)
    base = _closing(base_traj)
    idx = next(i for i, p in enumerate(days) if p.day == first)
    episode, recovery = [], None
    for p in days[idx:]:
        if p.closing_fen >= floor:
            recovery = p.day
            break
        episode.append(p)
    breach = days[idx]
    worst = min(episode, key=lambda p: (p.closing_fen, p.day))
    shortfall = floor - breach.closing_fen
    return Violation(
        code=ViolationCode.RESERVE_BREACH,
        message=f"Under this offer projected cash falls below the reserve on day {first}",
        day=first,
        observed=fmt_yuan(breach.closing_fen),
        limit=fmt_yuan(floor),
        formula=(
            f"closing_cash(day {first}) >= min_cash: {fmt_yuan(breach.closing_fen)} < {fmt_yuan(floor)}, "
            f"shortfall {fmt_yuan(shortfall)}"
        ),
        inputs={
            "day": str(first),
            "closing_cash": fmt_yuan(breach.closing_fen),
            "baseline_closing_cash": fmt_yuan(base.get(first, breach.closing_fen)),
            "min_cash": fmt_yuan(floor),
            "shortfall": fmt_yuan(shortfall),
            "shortfall_fen": str(shortfall),
            "max_shortfall": fmt_yuan(floor - worst.closing_fen),
            "max_shortfall_day": str(worst.day),
            "recovery_day": "none within horizon" if recovery is None else str(recovery),
            "days_below_floor": str(len(episode)),
            "mode": offer_traj.mode.value,
            "rule": "charged to the offer only where its cash is below the floor and below the no-offer baseline",
        },
    )


# ---------------------------------------------------------------- cure


def permanent_capable(f: Facility) -> bool:
    if f.kind in NOT_PERMANENT_KINDS:
        return False
    return not (f.kind == FacilityKind.CREDIT_LINE and not line_can_carry_permanent_need(f))


def _standing_plan_flows(state: FinancialState, base_traj: Trajectory, base_plan: FundingPlan,
                         mandate: Mandate) -> list[CashFlow]:
    funded = project(state, [], base_plan.actions, Mode.CONSERVATIVE, mandate.horizon_days)
    base = {p.day: p.closing_fen - p.opening_fen for p in base_traj.days}
    flows = []
    for p in funded.days:
        delta = (p.closing_fen - p.opening_fen) - base.get(p.day, 0)
        if delta:
            flows.append(CashFlow(id=f"STANDING-PLAN-{p.day}", day=p.day, amount_fen=delta, kind=FlowKind.OTHER,
                                  label="Standing committed plan (the gap that exists without the offer)",
                                  confirmed=True))
    return flows


def cure_state(state: FinancialState, prefund: tuple[Trajectory, FundingPlan, Mandate] | None) -> FinancialState:
    """What-if copy for pricing a permanent need (never written back)."""
    used: dict[str, int] = {}
    flows = list(state.flows)
    if prefund is not None:
        base_traj, base_plan, mandate = prefund
        for a in base_plan.actions:
            if a.kind in (FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE):
                used[a.facility_id] = used.get(a.facility_id, 0) + a.amount_fen
        flows += _standing_plan_flows(state, base_traj, base_plan, mandate)
    facilities = [
        f.model_copy(update={"limit_fen": max(f.drawn_fen, f.limit_fen - used.get(f.id, 0))})
        for f in state.facilities if permanent_capable(f)
    ]
    return state.model_copy(update={"facilities": facilities, "flows": flows})


def cure_plan(
    state: FinancialState,
    bound: list[Obligation],
    mandate: Mandate,
    offer_traj: Trajectory,
    base_traj: Trajectory,
    base_plan: FundingPlan,
    planner: Callable[[FinancialState, list[Obligation], Mandate, str], FundingPlan] = funding_plan,
) -> FundingPlan:
    """The cheapest committed plan on permanent-capable sources for the offer's trajectory. `planner` is
    the router (the verifier passes its per-evaluation memo)."""
    floor = mandate.min_cash_fen
    base_first = next((p.day for p in base_traj.days if p.closing_fen < floor), None)
    offer = _closing(offer_traj)
    gap_left_open = base_first is not None and offer.get(base_first, floor) < floor and bool(base_plan.actions)
    cstate = cure_state(state, (base_traj, base_plan, mandate) if gap_left_open else None)
    return planner(cstate, bound, mandate, "COMMITTED")
