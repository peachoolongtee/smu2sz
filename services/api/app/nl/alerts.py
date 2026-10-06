"""SHOW_ALERTS: the agent tells the owner the one thing that needs them, proposes the mandate-bounded cure, and runs
it on the owner's "go ahead" (tracker row C4).

The message is built from `app.alerts.alerts()` (the conservative trajectory of current books); the cure is the
alert's own typed suggestion, turned into operations by `cure_operations` and sent to the executor as the agent,
exactly as POST /alerts/{id}/act does. Nothing here executes on its own: the plan is pending until a direct
"go ahead" (the same guard as every other plan), and the executor still decides every tier.
"""

from __future__ import annotations

import json

from app.alerts import Alert, AlertKind, Severity, SuggestedAction, alerts, cure_operations
from app.domain.models import (
    ApplyForFacility,
    DrawFacility,
    FinancialState,
    Mandate,
    Operation,
    OperationResult,
    OperationStatus,
    RepayFacility,
    SubmitInvoiceForFinancing,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.financial import EngineError
from app.funding.recommend import cost_lines_by_leg, plan_operations, recommend
from app.nl import landing
from app.nl.context import NlContext
from app.nl.models import Intent, Slots
from app.nl.pipeline import Steps, t
from app.nl.plans import books_moved, describe, signature, stale, void_notice
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


def _suggestion(alert: Alert | None, op: Operation) -> tuple[SuggestedAction | None, int | None]:
    """The alert's priced suggestion that `cure_operations` turned into `op`, and the day its cost falls due."""
    if alert is None:
        return None, None
    for i, s in enumerate(alert.suggested):
        if (s.operation_kind == op.kind and s.facility_id == getattr(op, "facility_id", None)
                and s.receivable_id == getattr(op, "receivable_id", None)):
            end = alert.inputs.get(f"cure_end_day_{i}")
            return s, int(end) if end else None
    return None, None


def _quoted_cost(alert: Alert, ops: list[Operation]) -> int | None:
    """The total cost the alert's own pricing puts on the cure it proposes; None when any leg has no stated cost."""
    priced = [_suggestion(alert, op)[0] for op in ops]
    if not priced or any(sg is None or sg.cost_fen is None for sg in priced):
        return None
    return sum(sg.cost_fen for sg in priced if sg is not None and sg.cost_fen is not None)


def _cost_clause(ctx: NlContext, op: Operation, s: SuggestedAction | None, end: int | None) -> str:
    """Cost words appended to a cure's spoken clause; empty when the engine priced nothing."""
    if s is None or s.cost_fen is None:
        return ""
    cost = fmt_yuan(s.cost_fen)
    if s.annual_rate is None or s.cost_days is None or end is None:
        return t(ctx, f"; it will cost {cost}", f"；费用 {cost}")
    rate = fmt_pct(s.annual_rate.value, 1)
    if isinstance(op, SubmitInvoiceForFinancing):
        return t(ctx, f"; it will cost {cost} by day {end}, which is {rate} a year for those {s.cost_days} days",
                 f"；到第 {end} 天费用为 {cost}，相当于这 {s.cost_days} 天的年化 {rate}")
    return t(ctx, f"; {cost} interest to day {end} ({rate} a year)", f"；到第 {end} 天利息 {cost}（年化 {rate}）")


def _cap_sentence(ctx: NlContext, mandate: Mandate, op: Operation) -> str:
    """Above the ceiling the agent may not borrow alone: the executor queues the cure for the owner's approval."""
    cap = fmt_pct(bp(mandate.max_apr_bp))
    queue_en = ("so it needs your approval: if you say go ahead I will queue it for you to approve, and it does not "
                "run until you do.")
    queue_zh = "所以需要您批准：您确认后我会把它放入待批队列，您批准之前不会执行。"
    if isinstance(op, SubmitInvoiceForFinancing):
        return t(ctx, f" That is above your {cap} yearly ceiling for funding (invoice financing is billed in whole "
                      f"30-day periods), {queue_en}",
                 f"这高于您 {cap} 的年度融资成本上限（发票融资按整 30 天计费），{queue_zh}")
    return t(ctx, f" That is above your {cap} yearly ceiling for funding, {queue_en}",
             f"这高于您 {cap} 的年度融资成本上限，{queue_zh}")


def _if_approved(ctx: NlContext, op: Operation) -> str:
    """For a queued draw or advance on a facility with a lead time: when its cash would land if it ran today."""
    if not landing.is_funding(op):
        return ""
    day = landing.landing_day(ctx, op, executed=False)
    if day <= op.day:
        return ""
    return t(ctx, f" Once it runs, the cash lands after the lead time: day {day} if that is today.",
             f" 执行后资金经提前期到账：若今天执行，则第 {day} 天到账。")


def _queued_sentence(ctx: NlContext, mandate: Mandate, s: SuggestedAction | None, end: int | None,
                     approval_id: str | None, op: Operation | None = None) -> str:
    """After "go ahead": what the cure costs, why it did not run, and how to approve it."""
    cap = fmt_pct(bp(mandate.max_apr_bp))
    ref = approval_id or "its approval id"
    cost_en = cost_zh = ""
    if s is not None and s.cost_fen is not None and s.annual_rate is not None and s.cost_days is not None and end:
        cost, rate = fmt_yuan(s.cost_fen), fmt_pct(s.annual_rate.value, 1)
        cost_en = f"It costs {cost} by day {end}, which is {rate} a year for those {s.cost_days} days. "
        cost_zh = f"到第 {end} 天费用为 {cost}，相当于这 {s.cost_days} 天的年化 {rate}。"
    return t(ctx, f"{cost_en}That is above your {cap} ceiling, so it needs your approval. I have not run it: it is "
                  f"queued as {ref}. Say \"approve {ref}\" or use the approval card.",
             f"{cost_zh}这高于您 {cap} 的上限，需要您批准。我尚未执行：已列入待批队列，编号 {ref}。"
             f"请说“批准 {ref}”或使用审批卡。") + (_if_approved(ctx, op) if op is not None else "")


def _when(ctx: NlContext, op: Operation, zh: bool = False) -> str:
    """" (requested today, cash lands on day 37)" after a proposed draw or advance whose cash is not in today."""
    c = landing.leg_clause(ctx, op, executed=False)
    return (f"（{c}）" if zh else f" ({c})") if c else ""


def _op_clause(ctx: NlContext, state: FinancialState, op: Operation) -> tuple[str, str, str, str]:
    """(plan-step kind, step status, plan-step text, spoken clause) for one cure operation."""
    if isinstance(op, SubmitInvoiceForFinancing):
        fac = _facility_name(state, op.facility_id)
        amount = fmt_yuan(op.advance_fen)
        return (op.kind, "PROPOSED",
                t(ctx, f"Submit {op.receivable_id} to {op.facility_id} for a {amount} advance",
                  f"将 {op.receivable_id} 提交 {op.facility_id} 融资，预付 {amount}"),
                t(ctx, f"finance {amount} of invoice {op.receivable_id} on {fac} now{_when(ctx, op)}",
                  f"立即以发票 {op.receivable_id} 在 {fac} 融资 {amount}{_when(ctx, op, zh=True)}"))
    if isinstance(op, DrawFacility):
        fac = _facility_name(state, op.facility_id)
        amount = fmt_yuan(op.amount_fen)
        return (op.kind, "PROPOSED", t(ctx, f"Draw {amount} on {op.facility_id}", f"从 {op.facility_id} 提款 {amount}"),
                t(ctx, f"draw {amount} on {fac} now{_when(ctx, op)}", f"立即从 {fac} 提款 {amount}{_when(ctx, op, zh=True)}"))
    if isinstance(op, RepayFacility):
        fac = _facility_name(state, op.facility_id)
        amount = fmt_yuan(op.amount_fen)
        return (op.kind, "PROPOSED", t(ctx, f"Repay {amount} on {op.facility_id}", f"向 {op.facility_id} 还款 {amount}"),
                t(ctx, f"repay {amount} on {fac} now", f"立即向 {fac} 还款 {amount}"))
    assert isinstance(op, ApplyForFacility)
    fac = _facility_name(state, op.facility_id)
    return (op.kind, "PENDING_APPROVAL",
            t(ctx, f"Apply for {op.facility_id} (needs the owner's approval)", f"申请 {op.facility_id}（需业主批准）"),
            t(ctx, f"apply for {fac} (needs your approval)", f"申请 {fac}（需您批准）"))


def _plan_line(plan_costs: dict | None, op: Operation):
    """The router's cost line for a leg of the recommended plan (None for an alert-cure operation)."""
    if not plan_costs:
        return None
    amount = getattr(op, "advance_fen", None) if isinstance(op, SubmitInvoiceForFinancing) else getattr(op, "amount_fen", None)
    return plan_costs.get((op.kind, op.facility_id, getattr(op, "receivable_id", None), amount))


def _plan_cost_clause(ctx: NlContext, line, action_repay_day: int | None) -> str:
    """Cost words for a plan leg, from the router's cost line: the amount, and for a line draw the repayment day
    the estimate assumes (the first receipt that can repay it)."""
    cost = fmt_yuan(line.fen)
    if action_repay_day is not None:
        return t(ctx, f"; about {cost} interest if it is repaid on day {action_repay_day} as expected",
                 f"；若如预期在第 {action_repay_day} 天还款，利息约 {cost}")
    return t(ctx, f"; it will cost {cost}", f"；费用 {cost}")


def _waiting_sentence(ctx: NlContext, state: FinancialState, mandate: Mandate, alert: Alert,
                      ops: list[Operation], plan_costs: dict | None = None) -> str | None:
    """The cure of this alert is already in the owner's approval queue (a pending approval whose operation id starts
    `alert:<alert id>:`): say that it waits, its cost and rate, and how to approve it. None when nothing is queued."""
    queued = [a for a in ctx.store.approvals()
              if str(getattr(a.status, "value", a.status)) == "PENDING" and (a.op_id or "").startswith(f"alert:{alert.id}:")]
    if not queued:
        return None
    rec = queued[0]
    try:
        body = json.loads(rec.op_json)
    except ValueError:
        body = {}
    op = next((o for o in ops if o.kind == body.get("kind") and getattr(o, "facility_id", None) == body.get("facility_id")
               and getattr(o, "receivable_id", None) == body.get("receivable_id")), None)
    what_en = what_zh = ""
    cost_en = cost_zh = ""
    if op is not None:
        _kind, _status, _text, clause = _op_clause(ctx, state, op)
        what_en, what_zh = f" to {clause}", f"：{clause}"
        line = _plan_line(plan_costs, op)
        sg, end = (None, None) if line is not None else _suggestion(alert, op)
        if line is not None:
            cost_en = f" It costs {fmt_yuan(line.fen)}" + (f", above your {fmt_pct(bp(mandate.max_apr_bp))} ceiling" if line.needs_owner_approval else "") + "."
            cost_zh = f"费用 {fmt_yuan(line.fen)}" + (f"，高于您 {fmt_pct(bp(mandate.max_apr_bp))} 的上限" if line.needs_owner_approval else "") + "。"
        elif sg is not None and sg.cost_fen is not None and sg.annual_rate is not None and sg.cost_days is not None and end:
            cap = fmt_pct(bp(mandate.max_apr_bp))
            cost, rate = fmt_yuan(sg.cost_fen), fmt_pct(sg.annual_rate.value, 1)
            over_en = f", above your {cap} ceiling" if sg.above_apr_cap else ""
            over_zh = f"，高于您 {cap} 的上限" if sg.above_apr_cap else ""
            cost_en = f" It costs {cost} by day {end}, which is {rate} a year for those {sg.cost_days} days{over_en}."
            cost_zh = f"到第 {end} 天费用为 {cost}，相当于这 {sg.cost_days} 天的年化 {rate}{over_zh}。"
    return t(ctx, f"The cure is already waiting for your approval ({rec.id}){what_en}.{cost_en} I have not run it. To approve "
                  f"it, say \"approve {rec.id}\" or use the approval card.",
             f"处理方案已在等待您批准（{rec.id}）{what_zh}。{cost_zh}我尚未执行。要批准，请说“批准 {rec.id}”或使用审批卡。")


def _mandate_sentence(ctx: NlContext, a: Alert) -> str:
    """The mandate that expires soon, or has: the agent cannot renew it, the owner signs a new one offline."""
    day = a.inputs.get("expires_day", "?")
    if a.severity == Severity.CRITICAL:
        return t(ctx, f"Your mandate expired on day {day}, so I can no longer act until you sign a new one. Renewal is "
                      f"an offline step for you.",
                 f"您的授权已于第 {day} 天到期，在您签署新授权之前我无法再执行任何操作。续期需要您线下完成。")
    left = a.inputs.get("days_left", "?")
    return t(ctx, f"Your mandate expires on day {day}, in {left} day(s); after that I can no longer act. Renewal is an "
                  f"offline step for you.",
             f"您的授权将在第 {day} 天到期（还有 {left} 天）；之后我将无法执行任何操作。续期需要您线下完成。")


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
    repay = None if breach else next((a for a in news if a.kind == AlertKind.FACILITY_REPAYABLE), None)
    shown |= {repay.id} if repay else set()
    mand = next((a for a in news if a.kind == AlertKind.MANDATE_EXPIRING), None)
    shown |= {mand.id} if mand else set()
    rest = [a for a in news if a.id not in shown]

    parts = [t(ctx, f"Day {ctx.day}.", f"第 {ctx.day} 天。")]
    parts += [_past_due_sentence(ctx, state, a) for a in past_due]
    if mand is not None:
        parts.append(_mandate_sentence(ctx, mand))
    rest_sentence: list[str] = []
    if rest:  # the other alerts, in one line, before the question so that the question ends the message
        titles = "; ".join(a.title for a in rest[:MAX_TITLES]) + ("…" if len(rest) > MAX_TITLES else "")
        all_warn = all(a.severity == Severity.WARNING for a in rest)
        more = bool(past_due or breach)
        noun_en = ("warning" if all_warn else "alert") + ("" if len(rest) == 1 else "s")
        noun_zh = "警告" if all_warn else "提醒"
        rest_sentence.append(t(ctx, f"{len(rest)} {'more ' if more else ''}{noun_en}: {titles}.",
                               f"{'另有 ' if more else ''}{len(rest)} 项{noun_zh}：{titles}。"))
    steps = Steps()
    pending: PendingPlan | None = None
    if breach is None:
        parts += rest_sentence
        ops = cure_operations(repay, day=ctx.day, mandate_version=mandate.version,
                              state_version=state.state_version) if repay and repay.actionable else []
        if repay and ops:  # the books can repay a drawn credit line today: one sentence, then the proposal
            for op in ops:
                kind, status, text, _clause = _op_clause(ctx, state, op)
                steps.add(kind, text, status)
            fac = _facility_name(state, repay.inputs.get("facility_id", ""))
            amount = fmt_yuan(repay.amount_fen or 0)
            low, low_day = repay.inputs.get("lowest_closing", "?"), repay.inputs.get("lowest_day", "?")
            interest = repay.inputs.get("interest_due", "?")
            parts.append(t(ctx, f"The {amount} drawn on {fac} can be repaid today: cash stays above your floor "
                                f"(lowest {low} on day {low_day}). Interest to date {interest}. I can repay it now. "
                                f"Go ahead?",
                           f"{fac} 已提取的 {amount} 今天可以还清：现金仍高于您的储备线（最低 {low}，第 {low_day} 天）。"
                           f"截至今日利息 {interest}。我现在就可以还款。要执行吗？"))
            pending = PendingPlan(Intent.SHOW_ALERTS, Slots(), steps.items, {"alert_id": repay.id}).bind(
                ctx, ops, _quoted_cost(repay, ops))
    else:
        zero_day = breach.inputs.get("zero_day")
        if zero_day is not None:  # no plan restores the reserve; cash itself goes below zero
            parts.append(t(ctx, f"On current books cash goes below zero on day {zero_day}, and falls "
                                f"{fmt_yuan(breach.amount_fen or 0)} below your {fmt_yuan(mandate.min_cash_fen)} floor on day "
                                f"{breach.day}.",
                           f"按现有账目，第 {zero_day} 天现金将降到零以下，第 {breach.day} 天比 "
                           f"{fmt_yuan(mandate.min_cash_fen)} 的储备线低 {fmt_yuan(breach.amount_fen or 0)}。"))
        else:
            parts.append(t(ctx, f"On current books cash falls {fmt_yuan(breach.amount_fen or 0)} below your "
                                f"{fmt_yuan(mandate.min_cash_fen)} floor on day {breach.day}.",
                           f"按现有账目，第 {breach.day} 天现金将比 {fmt_yuan(mandate.min_cash_fen)} 的储备线低 "
                           f"{fmt_yuan(breach.amount_fen or 0)}。"))
        parts += rest_sentence
        # The plan proposed is the recommendation the home shows (app.funding.recommend): the router's cheapest
        # runnable plan priced all-in, else the alert's own cure. Both bind "go ahead" to the exact legs spoken.
        plan = None
        plan_costs: dict = {}
        cheaper = None
        if breach.actionable and breach.inputs.get("cure_restores_reserve") != "false":
            books = ctx.books(state)
            cure_approvals = sum(1 for sg in breach.suggested if sg.above_apr_cap)
            rec = recommend(books.state, books.with_([]), mandate, cure_exists=bool(breach.suggested),
                            cure_approvals=cure_approvals)
            plan, cheaper = rec.plan, rec.cheaper
        if plan is not None:
            ops = plan_operations(breach.id, plan, day=ctx.day, mandate_version=mandate.version,
                                  state_version=state.state_version)
            plan_costs = cost_lines_by_leg(plan)
        else:
            ops = cure_operations(breach, day=ctx.day, mandate_version=mandate.version,
                                  state_version=state.state_version) if breach.actionable else []
        waiting = _waiting_sentence(ctx, state, mandate, breach, ops, plan_costs)
        if waiting is not None:  # already queued: nothing to propose, nothing stored, no second approval
            parts.append(waiting)
        elif ops:
            clauses = []
            over_cap: Operation | None = None
            for i, op in enumerate(ops):
                kind, status, text, clause = _op_clause(ctx, state, op)
                steps.add(kind, text, status)
                line = _plan_line(plan_costs, op)
                if line is not None and plan is not None:
                    clauses.append(clause + _plan_cost_clause(ctx, line, plan.actions[i].repay_day))
                    if line.needs_owner_approval and over_cap is None:
                        over_cap = op
                else:
                    sg, end = _suggestion(breach, op)
                    clauses.append(clause + _cost_clause(ctx, op, sg, end))
                    if sg is not None and sg.above_apr_cap and over_cap is None:
                        over_cap = op
            cap = _cap_sentence(ctx, mandate, over_cap) if over_cap is not None else ""
            if cheaper is not None:
                n = sum(1 for cl in cheaper.costs if cl.needs_owner_approval)
                cap += t(ctx, f" A cheaper plan exists, {fmt_yuan(cheaper.total_cost_fen)} in all, but it would need {n} "
                              f"separate approvals; this one needs one.",
                         f" 还有更便宜的方案（合计 {fmt_yuan(cheaper.total_cost_fen)}），但需要 {n} 次单独批准；此方案只需一次。")
            if "cure_restores_reserve" in breach.inputs:  # the zero-floor fallback: say what it does not do
                cap += t(ctx, f" This keeps cash at or above zero but does not restore your reserve: it stays "
                              f"{breach.inputs.get('residual_shortfall', '?')} short, which needs your decision.",
                         f" 这只能让现金保持在零以上，并不能恢复储备线：仍差 "
                         f"{breach.inputs.get('residual_shortfall', '?')}，需要您来决定。")
            if plan is not None:
                together = (t(ctx, f" Together they cost about {fmt_yuan(plan.total_cost_fen)} in all.",
                              f"合计费用约 {fmt_yuan(plan.total_cost_fen)}。") if len(ops) > 1 else "")
            else:
                together = (t(ctx, f" Together they cost {breach.inputs['cure_cost']}.",
                              f"合计费用 {breach.inputs['cure_cost']}。") if len(ops) > 1 and "cure_cost" in breach.inputs else "")
            parts.append(t(ctx, "I can " + " and ".join(clauses) + "." + together + cap + " Go ahead?",
                           "我可以" + "，并".join(clauses) + "。" + together + cap + "要执行吗？"))
            pending = PendingPlan(Intent.SHOW_ALERTS, Slots(), steps.items, {"alert_id": breach.id}).bind(
                ctx, ops, plan.total_cost_fen if plan is not None else _quoted_cost(breach, ops))
        else:
            parts.append(t(ctx, "No committed facility can cover it, so there is nothing I can do on my own; "
                                "this needs your decision.",
                           "没有已承诺的额度可以覆盖，我无法自行处理；需要您来决定。"))
    return Turn(intent=Intent.SHOW_ALERTS, reply=" ".join(parts), plan=steps.items, awaiting=pending is not None,
                pending=pending), True


def alerts_intent(ctx: NlContext) -> Turn:
    return alerts_turn(ctx)[0]


def _void(ctx: NlContext, why: str, fresh: Turn | None = None) -> Turn:
    """Nothing ran: say why, and raise the alert again on today's books (its cure needs its own go-ahead)."""
    fresh = fresh or alerts_turn(ctx)[0]
    fresh.reply = void_notice(ctx, why) + " " + fresh.reply
    fresh.clear_pending = True
    return fresh


def confirm_cure(ctx: NlContext, pending: PendingPlan) -> Turn:
    """The owner's direct "go ahead" on a pending alert cure. It sends the operations that were shown. If the day or
    the mandate changed the cure is void and the alert is raised again; if the books moved, the cure is re-derived
    only to check it: the stored operations run if the alert still calls for exactly them at no more than the quoted
    cost, otherwise nothing runs and the new cure is proposed."""
    state, mandate = ctx.state(), ctx.mandate()
    alert_id = str(pending.data.get("alert_id", ""))
    why = stale(ctx, pending)
    if why is not None:
        return _void(ctx, why)
    try:
        found = alerts(state, mandate, ctx.store, ctx.day)
    except EngineError:
        return Turn(intent=Intent.SHOW_ALERTS, clear_pending=True, reply=t(
            ctx, "I could not project the books just now, so nothing was executed.", "暂时无法预测账目，未执行任何操作。"))
    alert = next((a for a in found if a.id == alert_id), None)
    gone = Turn(intent=Intent.SHOW_ALERTS, clear_pending=True, reply=t(
        ctx, "That is no longer needed: the alert has cleared since I raised it. Nothing was executed.",
        "已无需处理：该提醒在我提出之后已经解除。未执行任何操作。"))
    ops = list(pending.ops)
    if alert is None:  # the alert I raised is gone; if something else needs the owner now, that is a new proposal
        fresh, _has_news = alerts_turn(ctx)
        if fresh.pending is not None or any(a.severity == Severity.CRITICAL for a in found):
            # something critical needs the owner, but it is not what was raised: it is said again, with its own go-ahead
            return _void(ctx, t(ctx, "the books changed and what needs you is no longer what I raised",
                                "账目已变化，需要您处理的事项已不再是我之前提出的"), fresh)
        return gone
    if not ops:
        return gone
    if books_moved(ctx, pending):
        now = cure_operations(alert, day=ctx.day, mandate_version=mandate.version, state_version=state.state_version)
        cost = _quoted_cost(alert, now)
        quoted = pending.quoted_cost_fen
        if signature(now) != signature(ops):
            return _void(ctx, t(ctx, "the books changed and the cure would now be different from the one I showed",
                                "账目已变化，现在的处理方案与我之前给出的不同"))
        if quoted is not None and (cost is None or cost > quoted):
            return _void(ctx, t(ctx, f"the books changed and the cure would now cost "
                                     f"{fmt_yuan(cost) if cost is not None else 'more'}, above the {fmt_yuan(quoted)} I quoted",
                                f"账目已变化，该处理现在费用为 {fmt_yuan(cost) if cost is not None else '更高'}，高于我报价的 "
                                f"{fmt_yuan(quoted)}"))
    steps = Steps()
    results: list[OperationResult] = []
    for op in ops:  # exactly the operations that were shown, in order
        _kind, _status, text, _clause = _op_clause(ctx, state, op)
        r = ctx.execute(op)
        results.append(r)
        steps.result(op.kind, text, r)
        if r.status != OperationStatus.EXECUTED and not (r.status == OperationStatus.DUPLICATE and r.approval_id is None):
            break  # queued for the owner or refused: the legs after it are not sent
    unsent = ops[len(results):]
    for op in unsent:
        steps.add(op.kind, _op_clause(ctx, state, op)[2], "SKIPPED")
    lines = []
    for op, r in zip(ops, results, strict=False):
        sg, end = _suggestion(alert, op)
        waits = r.status == OperationStatus.PENDING_APPROVAL or (
            r.status == OperationStatus.DUPLICATE and r.approval_id is not None)
        if waits and sg is not None and sg.above_apr_cap and isinstance(op, DrawFacility | SubmitInvoiceForFinancing):
            lines.append(_queued_sentence(ctx, mandate, sg, end, r.approval_id, op))
        elif r.status == OperationStatus.PENDING_APPROVAL:
            ref = f" ({r.approval_id})" if r.approval_id else ""
            lines.append(t(ctx, f"{r.message} It waits for your approval{ref}; I have not done it.",
                           f"{r.message} 它在等您批准{ref}；我尚未执行。") + _if_approved(ctx, op))
        else:
            note = landing.executor_note(ctx, op, r.message) if r.status == OperationStatus.EXECUTED else ""
            lines.append(r.message + (f" ({note})" if note else ""))
    if unsent:
        lines.append(t(ctx, "Not sent: " + "; ".join(describe(ctx, o) for o in unsent) + ". Nothing else was run.",
                       "未发送：" + "；".join(describe(ctx, o) for o in unsent) + "。其余均未执行。"))
    try:
        after = alerts(ctx.state(), ctx.mandate(), ctx.store, ctx.day)
    except EngineError:
        after = None
    if after is not None:
        cleared = all(a.id != alert_id for a in after)
        repaid = alert.kind == AlertKind.FACILITY_REPAYABLE
        lines.append(t(ctx, ("The repayment alert" if repaid else "The reserve alert") + " is now cleared."
                       if cleared else "The alert is still open.",
                       ("还款提醒已解除。" if repaid else "储备线提醒已解除。") if cleared else "该提醒仍未解除。"))
    return Turn(intent=Intent.SHOW_ALERTS, reply=" ".join(lines), plan=steps.items, clear_pending=True)


__all__ = ["alerts_intent", "alerts_turn", "confirm_cure"]
