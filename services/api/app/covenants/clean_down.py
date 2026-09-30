"""Clean-down covenant on CREDIT_LINE facilities.

Line-balance derivation (the Trajectory has no per-facility balance, so it is rebuilt from events):
- The balance before day 0 is `facility.drawn_fen` (the verified starting balance).
- Days are processed in day order. For each `LedgerEvent` whose `ref` equals the facility id:
    DRAW       increases the balance by |amount_fen|  (cash in, debt up)
    REPAYMENT  decreases the balance by |amount_fen|  (cash out, debt down)
  All other kinds (INTEREST, FEE, ...) do not change principal and are ignored.
- A day is a *zero-balance day* when the balance at the close of the day is <= 0 **and** no DRAW
  on the line happened that day (an intraday draw-and-repay is not a clean day). A repayment that
  brings the line to zero makes that day a zero-balance day.
- The covenant holds when the longest run of consecutive zero-balance days is >= clean_down_days.
- It is evaluated only when `trajectory.horizon_days >= clean_down_days`; a shorter horizon cannot
  demonstrate a run of that length and is reported as not evaluated (no violation).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    Covenant,
    CovenantKind,
    Facility,
    FacilityKind,
    LedgerEventKind,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import fmt_yuan


@dataclass(frozen=True)
class LineDay:
    day: int
    balance_fen: int
    drew: bool

    @property
    def zero(self) -> bool:
        return self.balance_fen <= 0 and not self.drew


@dataclass(frozen=True)
class ZeroRun:
    length: int
    start_day: int | None
    end_day: int | None


def line_balances(trajectory: Trajectory, facility: Facility) -> list[LineDay]:
    """Close-of-day balance of `facility`, derived from DRAW/REPAYMENT events (see module doc)."""
    balance = facility.drawn_fen
    out: list[LineDay] = []
    for point in sorted(trajectory.days, key=lambda p: p.day):
        drew = False
        for ev in point.events:
            if ev.ref != facility.id:
                continue
            if ev.kind == LedgerEventKind.DRAW:
                balance += abs(ev.amount_fen)
                drew = True
            elif ev.kind == LedgerEventKind.REPAYMENT:
                balance -= abs(ev.amount_fen)
        out.append(LineDay(day=point.day, balance_fen=balance, drew=drew))
    return out


def longest_zero_run(days: list[LineDay]) -> ZeroRun:
    best = ZeroRun(0, None, None)
    run_len, run_start, prev_day = 0, None, None
    for d in days:
        contiguous = prev_day is not None and d.day == prev_day + 1
        if d.zero:
            if run_len and contiguous:
                run_len += 1
            else:
                run_len, run_start = 1, d.day
            if run_len > best.length:
                best = ZeroRun(run_len, run_start, d.day)
        else:
            run_len = 0
        prev_day = d.day
    return best


def line_can_carry_permanent_need(facility: Facility) -> bool:
    """False when the facility has a clean-down covenant: it must return to zero, so it cannot
    fund a permanent need (e.g. a terms extension). The marginal cost of funds excludes it."""
    return not any(c.kind == CovenantKind.CLEAN_DOWN for c in facility.covenants)


def check_clean_down(trajectory: Trajectory, facility: Facility, covenant: Covenant) -> Violation | None:
    if facility.kind != FacilityKind.CREDIT_LINE:
        return None
    if covenant.clean_down_days is None or covenant.clean_down_days <= 0:
        raise ValueError(f"covenant {covenant.id}: CLEAN_DOWN needs a positive clean_down_days")
    need = covenant.clean_down_days
    if trajectory.horizon_days < need:
        return None
    days = line_balances(trajectory, facility)
    run = longest_zero_run(days)
    if run.length >= need:
        return None
    peak = max((d.balance_fen for d in days), default=facility.drawn_fen)
    first_nonzero = next((d.day for d in days if not d.zero), None)
    return Violation(
        code=ViolationCode.CLEAN_DOWN_BREACH,
        message=(
            f"{facility.name}: longest zero-balance run is {run.length} days, "
            f"covenant requires {need} consecutive days ({covenant.id})"
        ),
        day=first_nonzero,
        observed=f"{run.length} days",
        limit=f"{need} days",
        formula=f"{covenant.formula}: {run.length} < {need}",
        inputs={
            "facility_id": facility.id,
            "covenant_id": covenant.id,
            "definition": covenant.definition,
            "horizon_days": str(trajectory.horizon_days),
            "opening_balance": fmt_yuan(facility.drawn_fen),
            "peak_balance": fmt_yuan(peak),
            "longest_zero_run_days": str(run.length),
            "longest_zero_run_from_day": "none" if run.start_day is None else str(run.start_day),
            "longest_zero_run_to_day": "none" if run.end_day is None else str(run.end_day),
            "balance_basis": "close-of-day balance from DRAW/REPAYMENT events on this facility",
        },
    )
