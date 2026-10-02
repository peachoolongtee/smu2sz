"""A confirmed plan sends the operations that were shown (audit finding A10, docs/FINANCIAL_SEMANTICS.md section 7).

A pending plan stores the typed operations the owner saw, the cost quoted for them and the books they were built on.
"Go ahead" never re-plans a goal:

- the day or the mandate version changed -> the plan is void: nothing runs and a fresh proposal is shown;
- the state version is unchanged -> the stored operations are sent as they are;
- the state version changed -> those same operations are re-priced on today's books with the engine the proposal
  used; if they are still feasible and cost no more than the quote they are sent, otherwise nothing runs, one sentence
  says what changed, and a fresh proposal is shown (it needs its own "go ahead").

The executor still decides tier and admission for every leg. A leg that is queued for the owner or refused ends the
run: the remaining legs are not sent, and the reply says which ones were not.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.models import (
    ApplyForFacility,
    DrawFacility,
    FundingActionKind,
    FundingPlan,
    GenerateBorrowerFile,
    OperationStatus,
    RepayFacility,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_yuan
from app.nl.context import NlContext
from app.nl.models import Intent
from app.nl.pipeline import Steps, t
from app.nl.turn import Turn

SETTLED = (OperationStatus.EXECUTED, OperationStatus.DUPLICATE)


def legs_from_plan(ctx: NlContext, plan: FundingPlan) -> list[Any]:
    """The router's committed plan as the typed Tier-1 operations a confirmation will send, in plan order. Early pay
    is a buyer's acceptance, not a funding operation, and repayments happen on their day: neither is a leg."""
    ops: list[Any] = []
    for a in plan.actions:
        if a.kind == FundingActionKind.DRAW:
            ops.append(DrawFacility(**ctx.base("DRAW_FACILITY"), facility_id=a.facility_id, amount_fen=a.amount_fen))
        elif a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
            ops.append(SubmitInvoiceForFinancing(**ctx.base("SUBMIT_INVOICE_FOR_FINANCING"), facility_id=a.facility_id,
                                                 receivable_id=a.receivable_id, advance_fen=a.amount_fen))
    return ops


def signature(ops: Sequence[Any]) -> list[tuple[str, str | None, str | None, int | None]]:
    """What the owner approves in an operation: its kind, facility, receivable and amount."""
    return [(o.kind, getattr(o, "facility_id", None), getattr(o, "receivable_id", None),
             getattr(o, "amount_fen", None) if hasattr(o, "amount_fen") else getattr(o, "advance_fen", None))
            for o in ops]


def plan_signature(plan: FundingPlan | None) -> list[tuple[str, str, str | None, int]] | None:
    """The router actions of a committed plan (kind, facility, receivable, amount); None for no plan."""
    if plan is None:
        return None
    return [(a.kind.value, a.facility_id, a.receivable_id, a.amount_fen) for a in plan.actions]


def describe(ctx: NlContext, op: Any) -> str:
    if isinstance(op, DrawFacility):
        return t(ctx, f"Draw {fmt_yuan(op.amount_fen)} on {op.facility_id}", f"从 {op.facility_id} 提款 {fmt_yuan(op.amount_fen)}")
    if isinstance(op, SubmitInvoiceForFinancing):
        return t(ctx, f"Submit {op.receivable_id} to {op.facility_id} for a {fmt_yuan(op.advance_fen)} advance",
                 f"将 {op.receivable_id} 提交 {op.facility_id} 融资，预付 {fmt_yuan(op.advance_fen)}")
    if isinstance(op, RepayFacility):
        return t(ctx, f"Repay {fmt_yuan(op.amount_fen)} on {op.facility_id}", f"偿还 {op.facility_id} {fmt_yuan(op.amount_fen)}")
    if isinstance(op, ApplyForFacility):
        return t(ctx, f"Apply for {op.facility_id}", f"申请 {op.facility_id}")
    if isinstance(op, GenerateBorrowerFile):
        return t(ctx, f"Prepare the borrower file for {op.facility_id}, {fmt_yuan(op.amount_fen)} (prepared, not sent)",
                 f"为 {op.facility_id} 准备借款人资料，{fmt_yuan(op.amount_fen)}（仅准备，不发送）")
    return str(op.kind)


def run_legs(ctx: NlContext, steps: Steps, ops: Sequence[Any], condition: str | None = None) -> tuple[list[str], bool]:
    """Send the stored operations in order and say how the executor answered each leg: (lines, whether every leg
    executed). The first leg that is not executed (queued for the owner, or refused) ends the run; the legs after it
    are not sent, and the lines name them."""
    lines: list[str] = []
    sent = 0
    ok = True
    for op in ops:
        r = ctx.execute(op)
        steps.result(op.kind, describe(ctx, op), r, condition)
        sent += 1
        if r.status in SETTLED:
            lines.append(t(ctx, f"{describe(ctx, op)}: done.", f"{describe(ctx, op)}：已执行。"))
            continue
        ok = False
        if r.status == OperationStatus.PENDING_APPROVAL:
            ref = f" ({r.approval_id})" if r.approval_id else ""
            lines.append(t(ctx, f"{describe(ctx, op)}: not done. It needs your approval{ref}; it is queued, not executed.",
                           f"{describe(ctx, op)}：尚未执行，需要您批准{ref}，已列入待批队列。"))
        else:
            lines.append(t(ctx, f"{describe(ctx, op)}: refused. {r.message}", f"{describe(ctx, op)}：被拒绝。{r.message}"))
        break
    rest = list(ops[sent:])
    for op in rest:
        steps.add(op.kind, describe(ctx, op), "SKIPPED", condition=condition)
    if rest:
        lines.insert(0, t(ctx, f"I stopped after step {sent} of {len(ops)}.", f"我在第 {sent} 步（共 {len(ops)} 步）后停止。"))
        lines.append(t(ctx, "Not sent: " + "; ".join(describe(ctx, o) for o in rest) + ". Nothing else was run.",
                       "未发送：" + "；".join(describe(ctx, o) for o in rest) + "。其余均未执行。"))
    return lines, ok


def send(ctx: NlContext, intent: Intent, ops: Sequence[Any], quoted_cost_fen: int | None = None) -> Turn:
    """The confirmed plan: its stored operations, sent as shown."""
    steps = Steps()
    lines, ok = run_legs(ctx, steps, ops)
    if ok:
        raised = sum((o.advance_fen if isinstance(o, SubmitInvoiceForFinancing) else o.amount_fen)
                     for o in ops if isinstance(o, DrawFacility | SubmitInvoiceForFinancing))
        if raised:
            lines.append(t(ctx, f"Raised {fmt_yuan(raised)} in total.", f"合计融得 {fmt_yuan(raised)}。"))
        if quoted_cost_fen is not None:
            lines.append(t(ctx, f"Cost as quoted: {fmt_yuan(quoted_cost_fen)}.",
                           f"费用与报价一致：{fmt_yuan(quoted_cost_fen)}。"))
    return Turn(intent=intent, reply=" ".join(lines), plan=steps.items, clear_pending=True)


def void_notice(ctx: NlContext, why: str) -> str:
    """The sentence in front of a fresh proposal: what changed, and that nothing ran."""
    return t(ctx, f"I did not run it: {why}. Nothing was executed; here is a fresh proposal.",
             f"我没有执行：{why}。未执行任何操作；以下是新的方案。")


def stale(ctx: NlContext, pending: Any) -> str | None:
    """Why the pending plan is void (the day or the mandate moved), or None when it may be considered."""
    if pending.day is None:
        return None
    if pending.day != ctx.day:
        return t(ctx, f"it was built on day {pending.day} and it is day {ctx.day} now",
                 f"该方案基于第 {pending.day} 天，现在已是第 {ctx.day} 天")
    if pending.mandate_version != ctx.mandate().version:
        return t(ctx, "your mandate changed after I proposed it", "在我提出方案之后，您的授权已变更")
    return None


def books_moved(ctx: NlContext, pending: Any) -> bool:
    return pending.state_version is not None and pending.state_version != ctx.state().state_version
