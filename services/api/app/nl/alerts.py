"""SHOW_ALERTS: the agent tells the owner the one thing that needs them, proposes the mandate-bounded cure, and runs
it on the owner's "go ahead" (tracker row C4).

The message is built from `app.alerts.alerts()` (the conservative trajectory of current books); the cure is the
alert's own typed suggestion, turned into operations by `cure_operations` and sent to the executor as the agent,
exactly as POST /alerts/{id}/act does. Nothing here executes on its own: the plan is pending until a direct
"go ahead" (the same guard as every other plan), and the executor still decides every tier.
"""

from __future__ import annotations

from app.alerts import Alert, AlertKind, Severity, alerts, cure_operations
from app.domain.models import (
    ApplyForFacility,
    DrawFacility,
    FinancialState,
    Operation,
    OperationResult,
    OperationStatus,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_yuan
from app.financial import EngineError
from app.nl.context import NlContext
from app.nl.models import Intent, Slots
from app.nl.pipeline import Steps, t
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn

MAX_PAST_DUE = 2
MAX_TITLES = 3


def _news(found: list[Alert]) -> list[Alert]:
    return [a for a in found if a.severity in (Severity.CRITICAL, Severity.WARNING)]


def _facility_name(state: FinancialState, facility_id: str) -> str:
    return next((f.name for f in state.facilities if f.id == facility_id), facility_id)


def _party(state: FinancialState, party_id: str) -> str:
    return next((c.name for c in state.counterparties if c.id == party_id), party_id)


def _past_due_sentence(ctx: NlContext, state: FinancialState, a: Alert) -> str:
    who = _party(state, a.inputs.get("counterparty_id", ""))
    amount = fmt_yuan(a.amount_fen or 0)
    rid = a.receivable_id or ""
    if a.commitment_id:  # the promised early payment did not arrive
        promised, due = a.inputs.get("promised_day", "?"), a.inputs.get("due_day", "?")
        return t(ctx, f"The early payment {who} promised on {rid} for day {promised} did not arrive; {amount} is "
                      f"outstanding and back on its due day, day {due}.",
                 f"{who} 承诺在第 {promised} 天提前支付的 {rid} 款项未到账；{amount} 仍未收到，已回到原到期日（第 {due} 天）。")
    return t(ctx, f"{who}'s {amount} on {rid} was due on day {a.day} and has not arrived.",
             f"{who} 的 {rid} 款项 {amount} 应于第 {a.day} 天到账，至今未到。")


def _op_clause(ctx: NlContext, state: FinancialState, op: Operation) -> tuple[str, str, str, str]:
    """(plan-step kind, step status, plan-step text, spoken clause) for one cure operation."""
    if isinstance(op, SubmitInvoiceForFinancing):
        fac = _facility_name(state, op.facility_id)
        amount = fmt_yuan(op.advance_fen)
        return (op.kind, "PROPOSED",
                t(ctx, f"Submit {op.receivable_id} to {op.facility_id} for a {amount} advance",
                  f"将 {op.receivable_id} 提交 {op.facility_id} 融资，预付 {amount}"),
                t(ctx, f"finance {amount} of invoice {op.receivable_id} on {fac} now",
                  f"立即以发票 {op.receivable_id} 在 {fac} 融资 {amount}"))
    if isinstance(op, DrawFacility):
        fac = _facility_name(state, op.facility_id)
        amount = fmt_yuan(op.amount_fen)
        return (op.kind, "PROPOSED", t(ctx, f"Draw {amount} on {op.facility_id}", f"从 {op.facility_id} 提款 {amount}"),
                t(ctx, f"draw {amount} on {fac} now", f"立即从 {fac} 提款 {amount}"))
    assert isinstance(op, ApplyForFacility)
    fac = _facility_name(state, op.facility_id)
    return (op.kind, "PENDING_APPROVAL",
            t(ctx, f"Apply for {op.facility_id} (needs the owner's approval)", f"申请 {op.facility_id}（需业主批准）"),
            t(ctx, f"apply for {fac} (needs your approval)", f"申请 {fac}（需您批准）"))


def alerts_turn(ctx: NlContext) -> tuple[Turn, bool]:
    """(the turn, whether anything needs the owner). Reads only; sets a pending plan when the first reserve-breach
    alert has a cure the agent may submit."""
    state, mandate = ctx.state(), ctx.mandate()
    try:
        found = alerts(state, mandate, ctx.store, ctx.day)
    except EngineError:
        return Turn(intent=Intent.SHOW_ALERTS, reply=t(
            ctx, "I could not project the books just now, so I cannot say what needs you.",
            "暂时无法预测账目，无法判断有什么需要您处理。")), False
    news = _news(found)
    if not news:
        return Turn(intent=Intent.SHOW_ALERTS, reply=t(ctx, f"Nothing needs you today (day {ctx.day}).",
                                                       f"今天（第 {ctx.day} 天）没有需要您处理的事项。")), False

    past_due = [a for a in news if a.kind == AlertKind.RECEIVABLE_PAST_DUE][:MAX_PAST_DUE]
    breach = next((a for a in news if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)
    shown = {a.id for a in past_due} | ({breach.id} if breach else set())
    rest = [a for a in news if a.id not in shown]

    parts = [t(ctx, f"Day {ctx.day}.", f"第 {ctx.day} 天。")]
    parts += [_past_due_sentence(ctx, state, a) for a in past_due]
    steps = Steps()
    pending: PendingPlan | None = None
    if breach is not None:
        parts.append(t(ctx, f"On current books cash falls {fmt_yuan(breach.amount_fen or 0)} below your "
                            f"{fmt_yuan(mandate.min_cash_fen)} floor on day {breach.day}.",
                       f"按现有账目，第 {breach.day} 天现金将比 {fmt_yuan(mandate.min_cash_fen)} 的储备线低 "
                       f"{fmt_yuan(breach.amount_fen or 0)}。"))
        ops = cure_operations(breach, day=ctx.day, mandate_version=mandate.version,
                              state_version=state.state_version) if breach.actionable else []
        if ops:
            clauses = []
            for op in ops:
                kind, status, text, clause = _op_clause(ctx, state, op)
                steps.add(kind, text, status)
                clauses.append(clause)
            parts.append(t(ctx, "I can " + " and ".join(clauses) + ". Go ahead?",
                           "我可以" + "，并".join(clauses) + "。要执行吗？"))
            pending = PendingPlan(Intent.SHOW_ALERTS, Slots(), steps.items, {"alert_id": breach.id})
        else:
            parts.append(t(ctx, "No committed facility can cover it, so there is nothing I can do on my own; "
                                "this needs your decision.",
                           "没有已承诺的额度可以覆盖，我无法自行处理；需要您来决定。"))
    if rest:
        titles = "; ".join(a.title for a in rest[:MAX_TITLES]) + ("…" if len(rest) > MAX_TITLES else "")
        all_warn = all(a.severity == Severity.WARNING for a in rest)
        more = bool(past_due or breach)
        noun_en = ("warning" if all_warn else "alert") + ("" if len(rest) == 1 else "s")
        parts.append(t(ctx, f"{len(rest)} {'more ' if more else ''}{noun_en}: {titles}.",
                       f"另有 {len(rest)} 项{'警告' if all_warn else '提醒'}：{titles}。") if more else
                     t(ctx, f"{len(rest)} {noun_en}: {titles}.", f"{len(rest)} 项{'警告' if all_warn else '提醒'}：{titles}。"))
    return Turn(intent=Intent.SHOW_ALERTS, reply=" ".join(parts), plan=steps.items, awaiting=pending is not None,
                pending=pending), True


def alerts_intent(ctx: NlContext) -> Turn:
    return alerts_turn(ctx)[0]


def confirm_cure(ctx: NlContext, pending: PendingPlan) -> Turn:
    """The owner's direct "go ahead" on a pending alert cure. The alerts are recomputed first; the cure runs only if
    the alert is still there, and only as the operations `cure_operations` builds from its current suggestion."""
    state, mandate = ctx.state(), ctx.mandate()
    alert_id = str(pending.data.get("alert_id", ""))
    try:
        found = alerts(state, mandate, ctx.store, ctx.day)
    except EngineError:
        return Turn(intent=Intent.SHOW_ALERTS, clear_pending=True, reply=t(
            ctx, "I could not project the books just now, so nothing was executed.", "暂时无法预测账目，未执行任何操作。"))
    alert = next((a for a in found if a.id == alert_id), None)
    gone = Turn(intent=Intent.SHOW_ALERTS, clear_pending=True, reply=t(
        ctx, "That is no longer needed: the alert has cleared since I raised it. Nothing was executed.",
        "已无需处理：该提醒在我提出之后已经解除。未执行任何操作。"))
    if alert is None:
        return gone
    ops = cure_operations(alert, day=ctx.day, mandate_version=mandate.version, state_version=state.state_version)
    if not ops:
        return gone
    steps = Steps()
    results: list[OperationResult] = []
    for op in ops:
        _kind, _status, text, _clause = _op_clause(ctx, state, op)
        r = ctx.execute(op)
        results.append(r)
        steps.result(op.kind, text, r)
        if r.status not in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL):
            break
    lines = []
    for r in results:
        if r.status == OperationStatus.PENDING_APPROVAL:
            ref = f" ({r.approval_id})" if r.approval_id else ""
            lines.append(t(ctx, f"{r.message} It waits for your approval{ref}; I have not done it.",
                           f"{r.message} 它在等您批准{ref}；我尚未执行。"))
        else:
            lines.append(r.message)
    try:
        after = alerts(ctx.state(), ctx.mandate(), ctx.store, ctx.day)
    except EngineError:
        after = None
    if after is not None:
        cleared = all(a.id != alert_id for a in after)
        lines.append(t(ctx, "The reserve alert is now cleared." if cleared else "The alert is still open.",
                       "储备线提醒已解除。" if cleared else "该提醒仍未解除。"))
    return Turn(intent=Intent.SHOW_ALERTS, reply=" ".join(lines), plan=steps.items, clear_pending=True)


__all__ = ["alerts_intent", "alerts_turn", "confirm_cure"]
