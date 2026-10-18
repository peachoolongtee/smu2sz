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

import re
from collections.abc import Sequence
from typing import Any

from app.domain.models import (
    ApplyForFacility,
    DrawFacility,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    OperationStatus,
    RepayFacility,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_yuan
from app.nl import landing
from app.nl.context import NlContext
from app.nl.models import Intent
from app.nl.pipeline import Steps, t
from app.nl.turn import Turn

SETTLED = (OperationStatus.EXECUTED, OperationStatus.DUPLICATE)

# The router's own reasons (`app.funding.rates.approval_reason`, `Search.unrunnable`), read only to say them in the
# owner's language; a reason that does not read like these is quoted as the router wrote it.
ABOVE_CEILING = re.compile(r"effective annual cost (?P<rate>\S+) is above the mandate's (?P<cap>\S+) ceiling")
UNISSUED = re.compile(r"(?P<rid>\S+) is not an invoice the executor can finance today(?:; it is issued on day (?P<day>-?\d+))?")
NO_OPERATION_ZH = {"needs the buyer's agreement to pay early": "需要买方同意提前付款",
                   "needs a bill in hand": "需要手中持有票据"}


def legs_from_plan(ctx: NlContext, plan: FundingPlan) -> list[Any]:
    """The router's committed plan as the typed Tier-1 operations a confirmation will send, in plan order (repayments
    happen on their day and are not legs). Early pay is a buyer's acceptance and a bill discount needs a bill in hand:
    no operation runs either, so a plan holding one has no legs at all (ValueError) rather than losing that leg
    silently; `runnable_legs` says why it cannot run today instead."""
    ops: list[Any] = []
    for a in plan.actions:
        if a.kind == FundingActionKind.DRAW:
            ops.append(DrawFacility(**ctx.base("DRAW_FACILITY"), facility_id=a.facility_id, amount_fen=a.amount_fen))
        elif a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
            ops.append(SubmitInvoiceForFinancing(**ctx.base("SUBMIT_INVOICE_FOR_FINANCING"), facility_id=a.facility_id,
                                                 receivable_id=a.receivable_id, advance_fen=a.amount_fen))
        else:
            raise ValueError(f"{a.kind.value} on {a.facility_id} is not an operation the executor can run")
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


# ---------------------------------------------------------------- what the router flags on a plan, in words


def _is_leg(a: FundingAction) -> bool:
    return a.kind == FundingActionKind.DRAW or (a.kind == FundingActionKind.FINANCE_INVOICE and bool(a.receivable_id))


def _leg_name(ctx: NlContext, plan: FundingPlan, i: int) -> str:
    """The plan's i-th action as the step the owner sees (the cost lines run in the actions' order)."""
    a = plan.actions[i]
    if a.kind == FundingActionKind.DRAW:
        return t(ctx, f"Draw {fmt_yuan(a.amount_fen)} on {a.facility_id}", f"从 {a.facility_id} 提款 {fmt_yuan(a.amount_fen)}")
    if a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
        return t(ctx, f"Submit {a.receivable_id} to {a.facility_id} for a {fmt_yuan(a.amount_fen)} advance",
                 f"将 {a.receivable_id} 提交 {a.facility_id} 融资，预付 {fmt_yuan(a.amount_fen)}")
    return plan.costs[i].label if i < len(plan.costs) else a.kind.value


def approval_sentences(ctx: NlContext, plan: FundingPlan) -> list[str]:
    """One plain sentence per leg above the mandate's ceiling: its cost, its yearly rate and the ceiling. The numbers
    are the router's (the cost line and the reason it wrote); the sentence only says them."""
    out: list[str] = []
    aligned = len(plan.costs) == len(plan.actions)
    for i, cl in enumerate(plan.costs):
        if not cl.needs_owner_approval:
            continue
        name = _leg_name(ctx, plan, i) if aligned else cl.label
        m = ABOVE_CEILING.search(cl.approval_reason)
        if m is None:
            out.append(t(ctx, f"{name}: {cl.approval_reason}.", f"{name}：{cl.approval_reason}。"))
            continue
        cost, rate, cap = fmt_yuan(cl.fen), m["rate"], m["cap"]
        out.append(t(ctx, f"{name} costs {cost}, which is {rate} a year, above your {cap} yearly ceiling for what I may "
                          f"borrow alone.",
                     f"{name}：费用 {cost}，年化 {rate}，高于您 {cap} 的年度融资成本上限（我可自行借款的范围）。"))
    return out


def approval_note(ctx: NlContext, plan: FundingPlan) -> str:
    """For a plan the executor will queue: which legs are above the ceiling and what a go-ahead then does (the first
    such leg waits for the owner as APR-nnnnnn and the legs after it are not sent). '' when no leg needs the owner."""
    if not plan.needs_owner_approval:
        return ""
    sentences = approval_sentences(ctx, plan) or [t(ctx, f"{plan.approval_reason}.", f"{plan.approval_reason}。")]
    aligned = len(plan.costs) == len(plan.actions)
    legs = [i for i, a in enumerate(plan.actions) if _is_leg(a)]
    first = next((i for i, cl in enumerate(plan.costs) if cl.needs_owner_approval and i in legs), None)
    tail = ""
    if first is not None and aligned:
        name = _leg_name(ctx, plan, first)
        later = any(i > first for i in legs)
        tail = t(ctx, f" After you say go ahead, \"{name}\" will wait for your approval (APR-…) rather than run"
                      + (", and I will not send the steps after it" if later else "") + ".",
                 f" 您回复“执行”后，“{name}”不会直接执行，而是等待您批准（APR-…）"
                 + ("，其后的步骤也不会发送" if later else "") + "。")
    elif first is None:
        tail = t(ctx, " It needs your approval before it can go ahead.", " 该方案需要您批准后才能进行。")
    return " ".join(sentences) + tail


def unrunnable_sentences(ctx: NlContext, plan: FundingPlan) -> list[str]:
    """One plain sentence per leg the executor would refuse today: what it is waiting for."""
    out: list[str] = []
    aligned = len(plan.costs) == len(plan.actions)
    for i, cl in enumerate(plan.costs):
        if cl.executable_now:
            continue
        name = _leg_name(ctx, plan, i) if aligned else cl.label
        m = UNISSUED.search(cl.not_executable_reason)
        if m is None and cl.not_executable_reason in NO_OPERATION_ZH:
            out.append(t(ctx, f"{name}: {cl.not_executable_reason}; no operation of mine can do that.",
                         f"{name}：{NO_OPERATION_ZH[cl.not_executable_reason]}，我无法通过任何操作完成。"))
            continue
        if m is None:
            out.append(t(ctx, f"{name}: {cl.not_executable_reason}.", f"{name}：{cl.not_executable_reason}。"))
            continue
        rid, day = m["rid"], m["day"]
        out.append(t(ctx, f"{name}: {rid} is not an invoice I can finance today"
                          + (f"; it is issued on day {day}" if day else "") + ".",
                     f"{name}：{rid} 目前还不能用来融资" + (f"，它将于第 {day} 天开出" if day else "") + "。"))
    return out


def unrunnable_note(ctx: NlContext, plan: FundingPlan) -> str:
    """For a plan that cannot run today: what it is waiting for, and that it is not offered. '' when it can run."""
    if plan.executable_now:
        return ""
    sentences = unrunnable_sentences(ctx, plan) or [
        t(ctx, f"{plan.not_executable_reason}.", f"{plan.not_executable_reason}。")]
    return (t(ctx, "It cannot run today: ", "该方案今天无法执行：") + " ".join(sentences)
            + t(ctx, " I will not offer it for a go-ahead; ask me again once it can run.",
                " 我不会把它作为可执行的方案提出；等它可以执行时请再问我。"))


def runnable_legs(ctx: NlContext, plan: FundingPlan | None) -> tuple[list[Any], str]:
    """(the legs a go-ahead may send for this plan, the words about what the router flagged on it). A plan that cannot
    run today yields no legs and the reason; a plan that needs the owner yields its legs and the approval sentences."""
    if plan is None:
        return [], ""
    if not plan.executable_now:
        return [], unrunnable_note(ctx, plan)
    if not all(_is_leg(a) for a in plan.actions):  # the router flags these; never drop one if it did not
        return [], (t(ctx, "It cannot run today: it relies on a step no operation can run (a buyer paying early or a "
                           "bill discount).", "该方案今天无法执行：它依赖无法通过操作执行的步骤（买方提前付款或票据贴现）。")
                    + t(ctx, " I will not offer it for a go-ahead; ask me again once it can run.",
                        " 我不会把它作为可执行的方案提出；等它可以执行时请再问我。"))
    return legs_from_plan(ctx, plan), approval_note(ctx, plan)


def runnable_alternative(bundle: Any) -> FundingPlan | None:
    """A plan that can run today among those the verdict carries (the router ranks every plan that can run before
    one that cannot, so when its best cannot run it holds no other admissible plan: usually None)."""
    for p in (bundle.plan_committed, bundle.verdict.plan):
        if p is not None and p.admissible and p.basis == "COMMITTED" and p.executable_now and p.actions:
            return p
    return None


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
    return str(op.kind)


def run_legs(ctx: NlContext, steps: Steps, ops: Sequence[Any], condition: str | None = None) -> tuple[list[str], bool]:
    """Send the stored operations in order and say how the executor answered each leg: (lines, whether every leg
    executed). The first leg that is not executed (queued for the owner, or refused) ends the run; the legs after it
    are not sent, and the lines name them. A draw or advance whose cash has not landed says when it lands; when every
    leg executed, one closing line separates the cash that is in now from the cash still to land."""
    lines: list[str] = []
    sent = 0
    ok = True
    done: list[Any] = []
    for op in ops:
        r = ctx.execute(op)
        steps.result(op.kind, describe(ctx, op), r, condition)
        sent += 1
        if r.status in SETTLED:
            done.append(op)
            when = landing.leg_clause(ctx, op, executed=True)
            lines.append(t(ctx, f"{describe(ctx, op)}: done" + (f"; {when}." if when else "."),
                           f"{describe(ctx, op)}：已执行" + (f"；{when}。" if when else "。")))
            if isinstance(op, RepayFacility) and (left := landing.not_repayable(ctx, op.facility_id)):
                lines[-1] += left  # what is still on the facility and has not landed
            continue
        ok = False
        if r.status == OperationStatus.PENDING_APPROVAL:
            ref = f" ({r.approval_id})" if r.approval_id else ""
            how = (t(ctx, f" To approve it, say \"approve {r.approval_id}\" or use the approval card.",
                     f"要批准，请说“批准 {r.approval_id}”或使用审批卡。")
                   if r.approval_id else t(ctx, " To approve it, name its approval id in the queue.",
                                           "要批准，请说出待批队列中的审批编号。"))
            lines.append(t(ctx, f"{describe(ctx, op)}: not done. It needs your approval{ref}; it is queued, not executed."
                                f"{how}",
                           f"{describe(ctx, op)}：尚未执行，需要您批准{ref}，已列入待批队列。{how}"))
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
    if ok and (total := landing.line(ctx, done, executed=True)):
        lines.append(total)
    if not ok:
        # the plan did not fund what it set out to: say how much is not in place (the stopped step and every step after it),
        # and what already ran, so "funded" is never inferred from a part-run plan
        left = sum(getattr(o, "amount_fen", None) or getattr(o, "advance_fen", 0) or 0
                   for o in ops if o not in done and isinstance(o, DrawFacility | SubmitInvoiceForFinancing))
        if left:
            lines.append(t(ctx, f"Still to arrange: {fmt_yuan(left)} of the funding is not in place; the gap is not fully funded.",
                           f"仍需安排：{fmt_yuan(left)} 的融资尚未到位，资金缺口尚未完全补足。"))
        if done and (ran := landing.line(ctx, done, executed=True)):
            lines.append(ran)  # cash in now vs cash still to land, for the steps that ran
    return lines, ok


def send(ctx: NlContext, intent: Intent, ops: Sequence[Any], quoted_cost_fen: int | None = None) -> Turn:
    """The confirmed plan: its stored operations, sent as shown."""
    steps = Steps()
    lines, ok = run_legs(ctx, steps, ops)
    if ok and quoted_cost_fen is not None:
        lines.append(t(ctx, f"Cost as quoted: {fmt_yuan(quoted_cost_fen)}.", f"费用与报价一致：{fmt_yuan(quoted_cost_fen)}。"))
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
