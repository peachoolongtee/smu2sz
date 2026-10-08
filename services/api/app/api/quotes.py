"""The quote an alert act records (ADR-0011 section 2, QUOTED): what the owner was shown when the cure was run or queued.

Built before the executor runs, from the alert and the router plan the act route has just recomputed and bound to the shown
`state_version` and suggestions. Every number is copied from the alert's priced suggestions, the alert's inputs, the plan's cost
lines and the after-state projection the home already shows (`home.after_facts`); nothing is priced here. The alert's inputs
hold money as the display strings the home reads, so a figure is read back exactly (`fen_of` is the inverse of `fmt_yuan`).
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any, Literal

from app.alerts import Alert, AlertKind
from app.api.home import _alert_actions as alert_actions
from app.api.home import after_facts, plan_legs
from app.api.presentation import cure_legs
from app.decisions.facts import IfDecline, QuotedFact, QuotedLeg
from app.domain.models import FinancialState, FundingPlan, Mandate, Operation
from app.domain.money import Ratio

_YUAN = re.compile(r"^(?P<sign>[-−])?¥(?P<whole>[\d,]+)\.(?P<cents>\d{2})$")


def fen_of(display: str | None) -> int | None:
    """The fen in a `fmt_yuan` string ("¥1,234.56" is 123456); None for anything else."""
    m = _YUAN.match(display or "")
    if m is None:
        return None
    fen = int(m["whole"].replace(",", "")) * 100 + int(m["cents"])
    return -fen if m["sign"] else fen


def rate_of(text: str | None) -> Ratio | None:
    """The yearly rate a router cost line names ("16.26%") as an exact ratio. The cost line states it to two decimals, so this is
    that statement exactly, not the unrounded rate behind it; the web shows it back at the same two places."""
    m = re.match(r"^(\d+(?:\.\d+)?)%$", text or "")
    if m is None:
        return None
    f = Fraction(m[1]) / 100
    return Ratio(num=f.numerator, den=f.denominator)


def _int(text: str | None) -> int | None:
    return int(text) if text is not None and text.lstrip("-").isdigit() else None


def _leg_index(op: Operation) -> int:
    return int(op.op_id.rsplit(":", 1)[1])


def _if_decline(alert: Alert) -> IfDecline | None:
    if alert.kind != AlertKind.RESERVE_BREACH_AHEAD:
        return IfDecline(kind="closed", day=alert.day, zero_day=None, shortfall_fen=None, max_shortfall_fen=None, worst_day=None)
    if alert.inputs.get("cure_restores_reserve") == "false":
        return IfDecline(kind="below_zero", day=alert.day, zero_day=_int(alert.inputs.get("zero_day")), shortfall_fen=alert.amount_fen,
                         max_shortfall_fen=fen_of(alert.inputs.get("max_shortfall")), worst_day=_int(alert.inputs.get("worst_day")))
    return IfDecline(kind="below_reserve", day=alert.day, zero_day=None, shortfall_fen=alert.amount_fen,
                     max_shortfall_fen=fen_of(alert.inputs.get("max_shortfall")), worst_day=_int(alert.inputs.get("worst_day")))


def build_quote(state: FinancialState, obs: list[Any], mandate: Mandate, alert: Alert, plan: FundingPlan | None,
                ops: list[Operation], today: int) -> QuotedFact:
    """The QUOTED fact for `ops`, the operations the act is about to run for `alert` (or for the router `plan`)."""
    if plan is not None:
        pl = plan_legs(state, plan, today, "en")
        by_index = {leg["index"]: leg for leg in pl}
        rates: dict[int, Any] = {leg["index"]: rate_of(leg["rate_text"]) for leg in pl}
        actions = list(plan.actions)
        total: int | None = plan.total_cost_fen
        note: Literal["draw_interest_excluded"] | None = None
        needs_owner = plan.needs_owner_approval
        source: Literal["cure", "router"] = "router"
    else:
        cl = cure_legs(state, alert, today, "en")
        by_index = {leg["index"]: leg for leg in cl}
        rates = {i: s.annual_rate for i, s in enumerate(alert.suggested)}
        actions = alert_actions(state, alert, today)
        total = fen_of(alert.inputs.get("cure_cost"))
        priced = [leg for leg in cl if leg["cost_fen"] is not None]
        if total is None and len(priced) == 1:
            total = priced[0]["cost_fen"]
        unpriced_draw = [leg for leg in cl if leg["operation_kind"] == "DRAW_FACILITY" and leg["cost_fen"] is None]
        note = "draw_interest_excluded" if unpriced_draw and total is not None else None
        needs_owner = any(leg["above_apr_cap"] for leg in cl) or any(leg["operation_kind"] == "APPLY_FOR_FACILITY" for leg in cl)
        source = "cure"
    legs: list[QuotedLeg] = []
    for op in ops:
        i = _leg_index(op)
        leg = by_index.get(i)
        if leg is None:
            continue
        legs.append(QuotedLeg(
            op_id=op.op_id, kind=op.kind, facility_id=leg["facility_id"], receivable_id=leg["receivable_id"],
            amount_fen=leg["amount_fen"] or 0, cost_fen=leg["cost_fen"], annual_rate=rates.get(i), cost_days=leg["cost_days"],
            cost_end_day=leg["cost_due_day"], lands_day=leg["lands_day"], above_ceiling=bool(leg["above_apr_cap"]),
        ))
    restores, first_short, lowest_day = after_facts(state, obs, mandate, actions, today)
    residual = fen_of(alert.inputs.get("residual_shortfall")) if alert.inputs.get("cure_restores_reserve") == "false" else None
    return QuotedFact(
        alert_id=alert.id, alert_kind=alert.kind.value, alert_day=alert.day, state_version_shown=state.state_version,
        source=source, legs=legs, total_cost_fen=total, cost_note=note, needs_owner=needs_owner, max_apr_bp=mandate.max_apr_bp,
        projected=restores is not None,
        restores_reserve=None if restores is None else (restores and alert.inputs.get("cure_restores_reserve") != "false"),
        after_first_short_day=first_short, horizon_days=mandate.horizon_days, if_decline=_if_decline(alert),
        residual_shortfall_fen=residual,
        after_lowest_day=lowest_day if alert.inputs.get("cure_restores_reserve") == "false" else None,
    )


__all__ = ["build_quote", "fen_of"]
