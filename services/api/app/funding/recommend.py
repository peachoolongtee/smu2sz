"""Which funding plan the owner is shown for a reserve breach, and the operations a click on it sends.

Policy (wayfinder #15, 6 Oct 2026): the recommendation is the router's cheapest runnable plan (`plan()` on current
books: admissible, every leg runnable today, every leg an operation the executor can run), priced all-in on the
router's own convention (a line draw to the first day the baseline recovers, an advance in whole 30-day periods). The
alert's own cure (`alerts.committed_cure`) stays the engine's feasibility proof and the fallback when the router has
no runnable plan.

One refinement, forced by R02 (a multi-leg plan is not one approval) and the chat's one-approval-at-a-time rule: a
runnable plan that needs the owner's approval on more than one leg is not recommended while a single-approval cure
exists; the owner is shown the cure and told that the cheaper option exists and what it would ask of them. Nothing
here decides anything financial: the router priced every plan, and admission re-checks every leg at execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.config import get_settings
from app.domain.models import (
    Actor,
    DrawFacility,
    FinancialState,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    Mandate,
    Obligation,
    Operation,
    SubmitInvoiceForFinancing,
)
from app.financial import EngineError
from app.funding.router import plan as router_plan

Source = Literal["router", "alert"]

KIND_OF = {FundingActionKind.DRAW: "DRAW_FACILITY", FundingActionKind.FINANCE_INVOICE: "SUBMIT_INVOICE_FOR_FINANCING"}


@dataclass(frozen=True)
class Recommendation:
    source: Source
    plan: FundingPlan | None  # the router plan when `source == "router"`
    cheaper: FundingPlan | None  # a cheaper runnable router plan left aside because it needs several approvals


def is_leg(a: FundingAction) -> bool:
    """An action the executor can run as one operation today (a draw, or an advance on a named invoice)."""
    return a.kind == FundingActionKind.DRAW or (a.kind == FundingActionKind.FINANCE_INVOICE and bool(a.receivable_id))


def runnable_plan(state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> FundingPlan | None:
    """The router's committed plan when the executor could run it today, leg by leg; else None."""
    try:
        p = router_plan(state, obligations, mandate)
    except EngineError:
        return None
    if not (p.admissible and p.executable_now and p.actions and all(is_leg(a) for a in p.actions)):
        return None
    if len(p.costs) != len(p.actions):  # the cost lines run in the actions' order; anything else is not presentable
        return None
    return p


def approvals_needed(p: FundingPlan) -> int:
    return sum(1 for cl in p.costs if cl.needs_owner_approval)


def recommend(state: FinancialState, obligations: list[Obligation], mandate: Mandate, *, cure_exists: bool,
              cure_approvals: int) -> Recommendation:
    """The plan to show for a reserve breach. `cure_exists`: the alert carries a cure the agent may submit;
    `cure_approvals`: how many of its legs the executor would queue for the owner."""
    p = runnable_plan(state, obligations, mandate)
    if p is None:
        return Recommendation("alert", None, None)
    if approvals_needed(p) > 1 and cure_exists and cure_approvals <= 1:
        return Recommendation("alert", None, p)
    return Recommendation("router", p, None)


def plan_suggestions(p: FundingPlan) -> list[dict[str, Any]]:
    """The plan's legs as the suggestion signature the act route binds to (kind, facility, receivable, amount)."""
    return [{"operation_kind": KIND_OF[a.kind], "facility_id": a.facility_id, "receivable_id": a.receivable_id,
             "amount_fen": a.amount_fen} for a in p.actions]


def plan_operations(alert_id: str, p: FundingPlan, *, day: int, mandate_version: int,
                    state_version: int) -> list[Operation]:
    """The plan's legs as typed operations for the executor, requested by the agent. The operation id keeps the
    `alert:<id>:` prefix the queue, the home and the chat use to see that this alert's fix is waiting."""
    out: list[Operation] = []
    for i, a in enumerate(p.actions):
        key = f"alert:{alert_id}:v{state_version}:plan:{i}"
        common: dict[str, Any] = {"op_id": key, "idempotency_key": key, "mandate_version": mandate_version,
                                  "requested_by": Actor.AGENT, "day": day}
        if a.kind == FundingActionKind.DRAW:
            out.append(DrawFacility(**common, facility_id=a.facility_id, amount_fen=a.amount_fen))
        elif a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
            out.append(SubmitInvoiceForFinancing(**common, facility_id=a.facility_id, receivable_id=a.receivable_id,
                                                 advance_fen=a.amount_fen))
    return out


def cost_lines_by_leg(p: FundingPlan) -> dict[tuple[str, str, str | None, int], Any]:
    """Each cost line keyed by the operation it prices (kind, facility, receivable, amount), for the queue's cards."""
    return {(KIND_OF[a.kind], a.facility_id, a.receivable_id, a.amount_fen): cl
            for a, cl in zip(p.actions, p.costs, strict=True)}


def offers_plan(alert: Any) -> bool:
    """Whether an alert is one the owner is shown a funding plan for: a reserve breach with a committed cure the agent may
    submit (not the zero-floor fallback, which never restores the reserve). The one guard every caller uses."""
    kind = getattr(getattr(alert, "kind", None), "value", getattr(alert, "kind", None))
    return (kind == "RESERVE_BREACH_AHEAD" and bool(getattr(alert, "actionable", False))
            and bool(getattr(alert, "committed_cure", False)) and alert.inputs.get("cure_restores_reserve") != "false")


def recommend_for_alert(alert: Any, state: FinancialState, obligations: list[Obligation], mandate: Mandate, *,
                        enabled: bool | None = None) -> Recommendation:
    """`recommend` behind the shared guard and the Debt Desk feature flag (off: the alert's cure, as before)."""
    if enabled is None:
        enabled = get_settings().features.debt_desk
    if not enabled or not offers_plan(alert):
        return Recommendation("alert", None, None)
    return recommend(state, obligations, mandate, cure_exists=bool(alert.suggested),
                     cure_approvals=sum(1 for s in alert.suggested if getattr(s, "above_apr_cap", False)))
