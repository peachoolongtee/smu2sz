"""Funding intents: FUND_GAP, REPAY_FACILITY, ACCELERATE_RECEIPT (the EX12 goal) and SHOW_STATUS.

Gaps come from the conservative trajectory (INVARIANT 11); the funding plan is the router's committed
plan carried by the verifier's verdict on the status quo; operations are built from that plan.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from app.counterparties import BuyerKernel
from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    CounterProposal,
    DrawFacility,
    Duration,
    DurationKind,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    OperationStatus,
    Outcome,
    RepayFacility,
    Repayment,
)
from app.domain.money import BP_DENOM, Ratio, fmt_pct, fmt_yuan
from app.financial import project
from app.financial.lots import ensure_lots, landed
from app.funding import NoPermanentSourceError, break_even_discount
from app.funding.search import Search
from app.nl import landing, quoting
from app.nl.context import NlContext
from app.nl.models import Intent, Slots
from app.nl.offers import buyer_options, owner_doc_for, verdict_line
from app.nl.pipeline import (
    Steps,
    accept,
    committed_plan,
    counter_line,
    funding_ops,
    package_offer,
    run_negotiation,
    sent_outside,
    span_of,
    status_quo_offer,
    t,
)
from app.nl.plans import (
    run_legs,
    runnable_alternative,
    runnable_legs,
    signature,
    unrunnable_note,
)
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn, ask
from app.verifier import OwnerConstraints, VerdictBundle

STEP_BP = 5


@dataclass(frozen=True)
class Gap:
    start: int
    end: int
    low_fen: int
    low_day: int
    shortfall_fen: int


def gaps(state: FinancialState, floor_fen: int, horizon: int, live: Sequence[Obligation] = (),
         from_day: int = 0) -> list[Gap]:
    """Maximal runs of days whose conservative closing cash is below the floor, on current books: `live`
    are the obligations of the commitments in force (`ctx.books(state).obligations`)."""
    traj = project(state, list(live), [], Mode.CONSERVATIVE, horizon, floor_fen)
    out: list[Gap] = []
    run: list = []
    for d in [*traj.days, None]:
        if d is not None and d.day < from_day:
            continue
        if d is not None and d.closing_fen < floor_fen:
            run.append(d)
            continue
        if run:
            low = min(run, key=lambda p: (p.closing_fen, p.day))
            out.append(Gap(run[0].day, run[-1].day, low.closing_fen, low.day, floor_fen - low.closing_fen))
            run = []
    return out


def gap_label(ctx: NlContext, g: Gap) -> str:
    return t(ctx, f"days {g.start}–{g.end}, short {fmt_yuan(g.shortfall_fen)} at the low on day {g.low_day}",
             f"第 {g.start}–{g.end} 天，最低点（第 {g.low_day} 天）缺 {fmt_yuan(g.shortfall_fen)}")


def through_gap(state: FinancialState, g: Gap) -> FinancialState:
    """A hypothetical state whose outflows after gap `g` are dropped, so the router funds up to it only."""
    flows = [f for f in state.flows if not (f.amount_fen < 0 and f.day > g.end)]
    return state.model_copy(update={"flows": flows})


# ---------------------------------------------------------------- FUND_GAP


def fund_gap(ctx: NlContext, slots: Slots, *, execute: bool = True) -> Turn:
    state, mandate = ctx.state(), ctx.mandate()
    steps = Steps()
    if slots.amount_fen is not None and slots.facility_id is not None:
        return _direct_draw(ctx, slots, steps, execute=execute)
    found = gaps(state, mandate.min_cash_fen, mandate.horizon_days, ctx.books(state).obligations)
    if not found:
        steps.add("VERIFY", t(ctx, "No projected day falls below the reserve; nothing to fund",
                              "预测期内没有低于储备线的日子，无需融资"), "INFO")
        return Turn(intent=Intent.FUND_GAP, reply=t(ctx, "There is no projected cash gap to fund.",
                                                    "目前没有需要融资的资金缺口。"), plan=steps.items)
    if len(found) > 1 and slots.gap_index is None:
        options = [(str(i), gap_label(ctx, g), i) for i, g in enumerate(found, 1)]
        options.append((str(len(found) + 1), t(ctx, "all of them", "全部"), 99))
        return ask(Intent.FUND_GAP, "gap_index",
                   t(ctx, f"There are {len(found)} projected cash gaps. Which should I fund?",
                     f"预测有 {len(found)} 个资金缺口，要为哪个融资？"), options, slots)
    idx = slots.gap_index or 1
    chosen = found[min(idx, len(found)) - 1] if idx != 99 else found[-1]
    variant = through_gap(state, chosen) if chosen is not found[-1] else state
    b = ctx.evaluate(status_quo_offer(ctx, variant, label=f"SQ{idx}"), state=variant, remember=False)
    steps.add("VERIFY", t(ctx, f"Gap {gap_label(ctx, chosen)}. ", f"缺口：{gap_label(ctx, chosen)}。")
              + verdict_line(ctx, b.verdict), "DONE")
    plan = committed_plan(b)
    if plan is None:
        return Turn(intent=Intent.FUND_GAP, verdict=b.verdict, plan=steps.items, clear_pending=True,
                    reply=t(ctx, "No admissible committed plan covers this gap; nothing executed. The owner must "
                                 "decide (e.g. apply for a facility, a Tier-2 action).",
                            "没有可行的已承诺融资方案覆盖该缺口，未执行任何操作。需由业主决定。"))
    blocked = ""
    if not plan.executable_now:
        # a plan the executor would refuse today is never offered for a go-ahead: say what it waits for, store nothing
        alt = runnable_alternative(b)
        why = unrunnable_note(ctx, plan)
        if alt is None:
            funding_ops(ctx, steps, plan, status="SKIPPED")
            return Turn(intent=Intent.FUND_GAP, verdict=b.verdict, plan=steps.items, clear_pending=True, reply=t(
                ctx, f"The cheapest committed plan is {plan.label}, need {fmt_yuan(plan.need_fen)}. {why} "
                     f"Nothing was stored and nothing was executed.",
                f"最低成本的已承诺方案是 {plan.label}，需求 {fmt_yuan(plan.need_fen)}。{why}未保存任何操作，也未执行任何操作。"))
        blocked = t(ctx, f"The cheapest plan, {plan.label}, cannot run today. {why} ",
                    f"最低成本的方案 {plan.label} 今天无法执行。{why}") + t(
            ctx, "The best plan that can run today:", "今天可以执行的最佳方案：")
        plan = alt
    legs, flagged = runnable_legs(ctx, plan)
    head = (blocked + " " if blocked else "") + t(
        ctx, f"Funding plan (committed facilities only): {plan.label}, need {fmt_yuan(plan.need_fen)}.",
        f"融资方案（仅已承诺额度）：{plan.label}，需求 {fmt_yuan(plan.need_fen)}。")
    if not execute:
        funding_ops(ctx, steps, plan)
        when = landing.line(ctx, legs, executed=False)
        pending = PendingPlan(Intent.FUND_GAP, slots, steps.items, {"actions": list(plan.actions)})
        pending.bind(ctx, legs, plan.total_cost_fen)
        pending.data["needs_owner"] = bool(flagged)  # as shown: a leg above the borrowing ceiling waits for the owner's approval
        if legs:
            quoting.stash(pending, lambda: quoting.of_plan(ctx, legs, plan=plan))
        return Turn(intent=Intent.FUND_GAP,
                    reply=head + (" " + when if when else "") + (" " + flagged if flagged else "")
                    + t(ctx, " Reply 'go ahead' to execute.", " 回复“执行”以执行。"),
                    plan=steps.items, verdict=b.verdict, awaiting=True, pending=pending)
    lines, _ok = run_legs(ctx, steps, legs)  # the same leg runner as a confirmed plan
    return Turn(intent=Intent.FUND_GAP, reply=" ".join([head, *lines]), plan=steps.items, verdict=b.verdict,
                clear_pending=True)


def _quoted(ctx: NlContext, pending: PendingPlan, *, alert_kind: str = "OPERATION") -> PendingPlan:
    """A plan of bare operations (a direct draw, a repayment) with the quote of what it shows kept beside it."""
    quoting.stash(pending, lambda: quoting.of_plan(ctx, pending.ops, alert_kind=alert_kind))
    return pending


def _direct_draw(ctx: NlContext, slots: Slots, steps: Steps, *, execute: bool) -> Turn:
    assert slots.facility_id is not None and slots.amount_fen is not None
    b = ctx.evaluate(status_quo_offer(ctx, ctx.state()), remember=False)
    steps.add("VERIFY", verdict_line(ctx, b.verdict), "DONE")
    desc = t(ctx, f"Draw {fmt_yuan(slots.amount_fen)} on {slots.facility_id}",
             f"从 {slots.facility_id} 提款 {fmt_yuan(slots.amount_fen)}")
    if b.verdict.outcome in (Outcome.REJECT, Outcome.NO_VERDICT):
        steps.add("DRAW_FACILITY", desc, "SKIPPED")
        return Turn(intent=Intent.FUND_GAP, reply=t(ctx, "The verifier does not allow new operations now: ",
                                                    "验证器当前不允许新操作：") + b.verdict.summary,
                    plan=steps.items, verdict=b.verdict)
    if not execute:
        steps.add("DRAW_FACILITY", desc)
        draw = DrawFacility(**ctx.base("DRAW_FACILITY"), facility_id=slots.facility_id, amount_fen=slots.amount_fen)
        when = landing.leg_clause(ctx, draw, executed=False)
        return Turn(intent=Intent.FUND_GAP,
                    reply=desc + (f" ({when})" if when else "") + t(ctx, ". Reply 'go ahead' to execute.", "。回复“执行”以执行。"),
                    plan=steps.items, verdict=b.verdict, awaiting=True,
                    pending=_quoted(ctx, PendingPlan(Intent.FUND_GAP, slots, steps.items).bind(ctx, [draw])))
    draw = DrawFacility(**ctx.base("DRAW_FACILITY"), facility_id=slots.facility_id, amount_fen=slots.amount_fen)
    r = ctx.execute(draw)
    steps.result("DRAW_FACILITY", desc, r)
    note = landing.executor_note(ctx, draw, r.message) if r.status == OperationStatus.EXECUTED else ""
    return Turn(intent=Intent.FUND_GAP, reply=r.message + (f" ({note})" if note else ""), plan=steps.items,
                verdict=b.verdict, clear_pending=True)


# ---------------------------------------------------------------- REPAY_FACILITY


def _repay_lows(ctx: NlContext, state: FinancialState, facility_id: str, amount: int) -> tuple[VerdictBundle, int, int]:
    """(the verdict after repaying, lowest projected cash now, lowest projected cash after repaying `amount`)."""
    after = state.model_copy(update={
        "cash_fen": state.cash_fen - amount,
        "facilities": [f.model_copy(update={"drawn_fen": f.drawn_fen - amount}) if f.id == facility_id else f
                       for f in state.facilities]})
    b_now = ctx.evaluate(status_quo_offer(ctx, state, "RPN"), remember=False)
    b_after = ctx.evaluate(status_quo_offer(ctx, after, "RPA"), state=after, remember=False)
    low_now = b_now.trajectory.min_cash_fen if b_now.trajectory else state.cash_fen
    low_after = b_after.trajectory.min_cash_fen if b_after.trajectory else after.cash_fen
    return b_after, low_now, low_after


def repay(ctx: NlContext, slots: Slots, *, execute: bool = True) -> Turn:
    state, mandate = ctx.state(), ctx.mandate()
    steps = Steps()
    drawn = [f for f in state.facilities if f.drawn_fen > 0]
    fac = next((f for f in state.facilities if f.id == slots.facility_id), None) if slots.facility_id else None
    if fac is None:
        bullet = [f for f in drawn if f.repayment == Repayment.BULLET]
        if len(bullet) > 1:
            return ask(Intent.REPAY_FACILITY, "facility_id", t(ctx, "Which facility should I repay?", "偿还哪一笔额度？"),
                       [(str(i), f"{f.name} ({f.id})", f.id) for i, f in enumerate(bullet, 1)], slots)
        fac = bullet[0] if bullet else None
    if fac is None or fac.drawn_fen == 0:
        return Turn(intent=Intent.REPAY_FACILITY, reply=t(ctx, "Nothing is drawn on a facility that can be repaid on demand.",
                                                          "没有可按需偿还的已提款额度。"))
    lots = ensure_lots(state).lots
    if fac.repayment != Repayment.BULLET:
        return Turn(intent=Intent.REPAY_FACILITY, reply=t(
            ctx, f"{fac.name} is repaid {fac.repayment.value.lower().replace('_', ' ')} (from the receivable), not on demand.",
            f"{fac.name} 按回款偿还，不能随时偿还。"))
    # only the balance whose cash has landed can be repaid (ADR-0010): the rest waits for its landing day
    on_hand = landed(lots, fac.id)
    transit = landing.not_repayable(ctx, fac.id)
    if on_hand <= 0:
        return Turn(intent=Intent.REPAY_FACILITY, facts={"repay": "nothing_landed", "facility_id": fac.id}, reply=t(
            ctx, "Nothing has landed on " + fac.name + " yet, so there is nothing to repay.",
            f"{fac.name} 上还没有资金到账，因此没有可偿还的金额。") + transit)
    amount = min(slots.amount_fen or on_hand, on_hand)
    # the reserve check: repaying must not push any projected day below the owner's floor
    b_after, low_now, low_after = _repay_lows(ctx, state, fac.id, amount)
    floor = mandate.min_cash_fen
    steps.add("VERIFY", t(ctx, f"Projected low after repaying: {fmt_yuan(low_after)} "
                          f"(now {fmt_yuan(low_now)}); reserve {fmt_yuan(floor)}",
                          f"还款后预测最低现金 {fmt_yuan(low_after)}（当前 {fmt_yuan(low_now)}）；储备 {fmt_yuan(floor)}"), "DONE")
    desc = t(ctx, f"Repay {fmt_yuan(amount)} on {fac.id}", f"偿还 {fac.id} {fmt_yuan(amount)}")
    if low_after < floor and low_after < low_now:
        safe = max(0, min(low_now - floor, amount))
        steps.add("REPAY_FACILITY", desc, "SKIPPED")
        hint = (t(ctx, f" The most I can repay now without breaching it is {fmt_yuan(safe)}.",
                  f" 目前在不跌破储备的前提下最多可偿还 {fmt_yuan(safe)}。") if safe > 0 else
                t(ctx, " Repay when the receivable pays (the plan's repayment day).", " 请在应收款到账后（计划还款日）再偿还。"))
        return Turn(intent=Intent.REPAY_FACILITY, plan=steps.items, verdict=b_after.verdict,
                    facts={"repay": "blocked", "facility_id": fac.id, "low_after_fen": low_after, "safe_fen": safe}, reply=t(
            ctx, f"Not repaid: it would take projected cash to {fmt_yuan(low_after)}, below the owner's reserve.",
            f"未偿还：还款会使预测现金降至 {fmt_yuan(low_after)}，低于储备线。") + hint + transit)
    if not execute:
        steps.add("REPAY_FACILITY", desc)
        repay_op = RepayFacility(**ctx.base("REPAY_FACILITY"), facility_id=fac.id, amount_fen=amount)
        return Turn(intent=Intent.REPAY_FACILITY, facts={"repay": "proposal", "facility_id": fac.id, "amount_fen": amount},
                    reply=desc + t(ctx, ". Reply 'go ahead' to execute.", "。回复“执行”。") + transit,
                    plan=steps.items, awaiting=True,
                    pending=_quoted(ctx, PendingPlan(Intent.REPAY_FACILITY, slots, steps.items).bind(ctx, [repay_op]),
                                    alert_kind="FACILITY_REPAYABLE"))
    r = ctx.execute(RepayFacility(**ctx.base("REPAY_FACILITY"), facility_id=fac.id, amount_fen=amount))
    steps.result("REPAY_FACILITY", desc, r)
    return Turn(intent=Intent.REPAY_FACILITY, reply=r.message + transit, plan=steps.items, verdict=b_after.verdict,
                clear_pending=True)


# ---------------------------------------------------------------- re-pricing a stored plan (A10)


def reprice_fund_gap(ctx: NlContext, pending: PendingPlan) -> str | None:
    """None when the stored draws and advances are still feasible on today's books at no more than the quoted cost
    (the router's own search evaluates exactly those actions), else one sentence on what changed."""
    state, mandate = ctx.state(), ctx.mandate()
    slots = pending.slots
    if slots.amount_fen is not None and slots.facility_id is not None:  # a direct draw: no gap, no quoted cost
        b = ctx.evaluate(status_quo_offer(ctx, state), remember=False)
        if b.verdict.outcome in (Outcome.REJECT, Outcome.NO_VERDICT):
            return t(ctx, "the verifier does not allow new operations now", "验证器当前不允许新操作")
        return None
    found = gaps(state, mandate.min_cash_fen, mandate.horizon_days, ctx.books(state).obligations)
    if not found:
        return t(ctx, "no projected day falls below your reserve any more", "预测期内已没有低于储备线的日子")
    idx = slots.gap_index or 1
    chosen = found[min(idx, len(found)) - 1] if idx != 99 else found[-1]
    variant = through_gap(state, chosen) if chosen is not found[-1] else state
    return reprice_actions(ctx, variant, pending)


def reprice_actions(ctx: NlContext, state: FinancialState, pending: PendingPlan) -> str | None:
    """Evaluate the plan's stored router actions on `state` with the router's own search."""
    ev = Search(state, list(ctx.books(state).obligations), ctx.mandate(), "COMMITTED").evaluate(
        list(pending.data["actions"]))
    if not ev.admissible:
        return t(ctx, "the books changed and those operations no longer keep cash above your reserve and within "
                      "your limits", "账目已变化，这些操作不再能使现金保持在储备线之上并符合您的限额")
    if pending.quoted_cost_fen is not None and ev.cost is not None and ev.cost > pending.quoted_cost_fen:
        return t(ctx, f"the books changed and those operations would now cost {fmt_yuan(ev.cost)}, more than the "
                      f"{fmt_yuan(pending.quoted_cost_fen)} I quoted",
                 f"账目已变化，这些操作现在需 {fmt_yuan(ev.cost)}，高于我报价的 {fmt_yuan(pending.quoted_cost_fen)}")
    return None


def reprice_repay(ctx: NlContext, pending: PendingPlan) -> str | None:
    """None when repaying the stored amount still keeps projected cash above the reserve (the check the proposal made)."""
    op = pending.ops[0]
    fac = next((f for f in ctx.state().facilities if f.id == op.facility_id), None)
    if fac is None or landed(ensure_lots(ctx.state()).lots, op.facility_id) < op.amount_fen:
        return t(ctx, "the books changed and that amount is no longer drawn on the facility",
                 "账目已变化，该额度上已没有这笔提款")
    _b, low_now, low_after = _repay_lows(ctx, ctx.state(), op.facility_id, op.amount_fen)
    if low_after < ctx.mandate().min_cash_fen and low_after < low_now:
        return t(ctx, f"the books changed and repaying it would now take projected cash to {fmt_yuan(low_after)}, "
                      f"below your reserve", f"账目已变化，现在还款会使预测现金降至 {fmt_yuan(low_after)}，低于您的储备线")
    return None


# ---------------------------------------------------------------- ACCELERATE_RECEIPT (EX12)


def largest_step_below(limit: Fraction) -> int:
    k = -(-limit * BP_DENOM // STEP_BP) - 1
    return max(0, int(k) * STEP_BP)


def accelerate(ctx: NlContext, slots: Slots, text: str, *, amended: bool = False) -> Turn:
    """Goal -> plan: an early-pay counter at or below the break-even-derived rate with zero forward
    concessions; if the buyer refuses, the router's committed plan (invoice financing + line) instead.
    It only proposes: the plan stores the counter and every operation that may follow it, and a confirmation sends
    exactly those (`run_accelerate`)."""
    state, mandate = ctx.state(), ctx.mandate()
    buyers_with_open = sorted({r.counterparty_id for r in state.receivables if r.status == "OPEN"})
    cp = slots.counterparty_id or ctx.session.counterparty_id
    if cp is None:
        if len(buyers_with_open) != 1:
            return ask(Intent.ACCELERATE_RECEIPT, "counterparty_id",
                       t(ctx, "Which buyer's invoice should be paid early?", "要提前收哪位买家的款？"),
                       buyer_options(ctx), slots)
        cp = buyers_with_open[0]
    rcvs = [r for r in state.receivables if r.counterparty_id == cp and r.status == "OPEN" and r.due_day > ctx.day]
    if not rcvs:
        return Turn(intent=Intent.ACCELERATE_RECEIPT, clear_pending=True,
                    reply=t(ctx, f"{cp} has no open invoice to accelerate.", f"{cp} 没有可提前收款的未结发票。"))
    if len(rcvs) > 1 and slots.receivable_id is None:
        return ask(Intent.ACCELERATE_RECEIPT, "receivable_id", t(ctx, "Which invoice?", "哪张发票？"),
                   [(str(i), f"{r.id} {fmt_yuan(r.face_fen)} due day {r.due_day}", r.id) for i, r in enumerate(rcvs, 1)],
                   slots)
    rcv = next((r for r in rcvs if r.id == slots.receivable_id), rcvs[0])
    steps = Steps()
    sq = ctx.evaluate(status_quo_offer(ctx, state), remember=False)
    fallback = committed_plan(sq)
    if_cond = t(ctx, "if the buyer refuses (fallback)", "若买方拒绝（后备方案）")

    if slots.use_financing:  # correction: invoice financing instead of the early-pay counter
        steps.add("VERIFY", verdict_line(ctx, sq.verdict), "DONE")
        if fallback is None:
            return Turn(intent=Intent.ACCELERATE_RECEIPT, plan=steps.items, verdict=sq.verdict, clear_pending=True,
                        reply=t(ctx, "No admissible committed financing plan; nothing to do.", "没有可行的已承诺融资方案。"))
        head = t(ctx, f"Plan: finance {rcv.id} instead of asking {cp} for early payment: {fallback.label}.",
                 f"方案：以 {rcv.id} 发票融资代替向 {cp} 提前收款：{fallback.label}。")
        legs, flagged = runnable_legs(ctx, fallback)
        if not fallback.executable_now:  # never offered for a go-ahead: nothing is stored
            funding_ops(ctx, steps, fallback, status="SKIPPED")
            return Turn(intent=Intent.ACCELERATE_RECEIPT, amended=amended, verdict=sq.verdict, plan=steps.items,
                        clear_pending=True, reply=head + " " + flagged + t(ctx, " Nothing was stored and nothing was "
                                                                          "executed.", "未保存任何操作，也未执行任何操作。"))
        funding_ops(ctx, steps, fallback)
        when = landing.line(ctx, legs, executed=False)
        pending = PendingPlan(Intent.ACCELERATE_RECEIPT, slots, steps.items, {"actions": list(fallback.actions)})
        pending.bind(ctx, legs, fallback.total_cost_fen)
        if legs:
            quoting.stash(pending, lambda: quoting.of_plan(ctx, legs, plan=fallback))
        return Turn(intent=Intent.ACCELERATE_RECEIPT, amended=amended, verdict=sq.verdict, plan=steps.items,
                    awaiting=True, pending=pending,
                    reply=head + (" " + when if when else "") + (" " + flagged if flagged else "")
                    + t(ctx, " Reply 'go ahead' to execute (Tier 1).", " 回复“执行”（一级权限）。"))

    try:
        be_ratio, _ = break_even_discount(state, mandate)
    except NoPermanentSourceError:
        return Turn(intent=Intent.ACCELERATE_RECEIPT, clear_pending=True,
                    reply=t(ctx, "No committed source can price early payment; nothing proposed.", "无法为提前收款定价。"))
    cap = largest_step_below(be_ratio.value)
    if mandate.max_immediate_discount_bp is not None:
        cap = min(cap, mandate.max_immediate_discount_bp)
    if slots.rate_bp is not None and (slots.rate_bp > cap or slots.rate_bp <= 0):
        # never loosen: a correction above the break-even-derived cap is refused and the plan is unchanged
        prior = ctx.session.pending_plan
        return Turn(intent=Intent.ACCELERATE_RECEIPT, amended=False, awaiting=prior is not None,
                    plan=prior.steps if prior else [],
                    reply=t(ctx, f"I can't use {fmt_pct(Fraction(slots.rate_bp, BP_DENOM))}: early payment above "
                                 f"{fmt_pct(Fraction(cap, BP_DENOM))} costs more than invoice financing (break-even "
                                 f"{fmt_pct(be_ratio.value)}). The plan is unchanged.",
                            f"不能使用 {fmt_pct(Fraction(slots.rate_bp, BP_DENOM))}：高于 {fmt_pct(Fraction(cap, BP_DENOM))} "
                            f"的提前付款折扣比发票融资更贵（盈亏平衡 {fmt_pct(be_ratio.value)}）。方案不变。"))
    # The buyer's standing early-pay offer on the invoice (or, without one, the first rate at the
    # break-even, which the owner would never give); the owner's goal caps early pay at `limit` with
    # zero forward concessions. The verifier applies the goal itself: COUNTER with its own counters.
    standing = next((f for f in state.facilities if f.kind == FacilityKind.BUYER_EARLY_PAY and f.lender_id == cp
                     and f.status == FacilityStatus.COMMITTED), None)
    ask_bp = standing.rate_bp if standing is not None else cap + STEP_BP
    limit = min(cap, slots.rate_bp) if slots.rate_bp is not None else cap
    goal = _goal_offer(ctx, text, cp, rcv.id, rcv.face_fen, ask_bp)
    b = ctx.evaluate(goal, owner_constraints=OwnerConstraints(max_early_pay_bp=limit, zero_forward_concessions=True))
    v = b.verdict
    zero = v.counters if v.outcome == Outcome.COUNTER else []
    steps.add("VERIFY", t(ctx, f"Break-even discount {fmt_pct(be_ratio.value)} (d/(1−d) < marginal cost of funds "
                               f"for 30 days); counter cap {fmt_pct(Fraction(cap, BP_DENOM))}; forward concessions ¥0.00",
                          f"盈亏平衡折扣 {fmt_pct(be_ratio.value)}；反报价上限 {fmt_pct(Fraction(cap, BP_DENOM))}；远期让步 ¥0.00"),
              "DONE")
    if not zero:
        steps.add("VERIFY", verdict_line(ctx, v), "DONE")
        when = flagged = ""
        if fallback is not None:
            funding_ops(ctx, steps, fallback, condition=if_cond, status="PROPOSED" if fallback.executable_now else "SKIPPED")
            legs, flagged = runnable_legs(ctx, fallback)
            when = landing.line(ctx, legs, executed=False)
        return Turn(intent=Intent.ACCELERATE_RECEIPT, plan=steps.items, verdict=v, clear_pending=False,
                    reply=t(ctx, "No early-pay counter fits the goal; the committed financing plan applies.",
                            "没有符合目标的提前付款反报价；适用已承诺融资方案。") + (" " + when if when else "")
                    + (" " + flagged if flagged else ""))
    counter = zero[0]
    gv = v
    steps.add("COUNTER_OFFER", counter_line(ctx, counter.label, counter.text), "PROPOSED")
    steps.add("NEGOTIATE", t(ctx, f"Bounded rounds with {cp}", f"与 {cp} 有限轮次谈判"))
    steps.add("ACCEPT_OFFER", t(ctx, "Record the commitment (nonce, expiry)", "记录承诺（随机数、到期日）"),
              condition=t(ctx, "if the buyer accepts", "若买方接受"))
    if fallback is not None:
        funding_ops(ctx, steps, fallback, condition=if_cond, status="PROPOSED" if fallback.executable_now else "SKIPPED")
    # The legs that may follow, built now so that the owner sees them and a go-ahead sends exactly these: the
    # remaining gap after the buyer accepts (the package projected as agreed), or the router's plan if it refuses.
    refuse_ops, refuse_note = runnable_legs(ctx, fallback)
    accept_plan = None
    offer = ctx.store.get_offer(gv.offer_id)
    if offer is not None:
        accept_plan = committed_plan(ctx.evaluate_accepted(package_offer(ctx, offer, counter)))
    accept_ops, accept_note = runnable_legs(ctx, accept_plan)
    if accept_plan is not None and (accept_ops or accept_note):
        funding_ops(ctx, steps, accept_plan,
                    condition=t(ctx, "if the buyer accepts: remaining gap after early settlement",
                                "若买方接受：提前结算后剩余缺口"),
                    status="PROPOSED" if accept_plan.executable_now else "SKIPPED")
    when_refuse = landing.line(ctx, refuse_ops, executed=False)
    when_accept = landing.line(ctx, accept_ops, executed=False)
    head = t(ctx, f"Plan (Tier 1): offer {cp} early settlement on up to "
                  f"{fmt_yuan(_face(counter))} of {rcv.id} at {fmt_pct(Fraction(_rate(counter), BP_DENOM))} "
                  f"(below the {fmt_pct(be_ratio.value)} break-even), terms unchanged, no rebate: ¥0.00 of forward "
                  f"concessions. If {cp} refuses: {fallback.label if fallback else 'no fallback needed'}."
                  + (f" If {cp} accepts, the rest of the gap: {accept_plan.label}." if accept_ops and accept_plan else ""),
             f"方案（一级权限）：向 {cp} 提议对 {rcv.id} 最多 {fmt_yuan(_face(counter))} 按 "
             f"{fmt_pct(Fraction(_rate(counter), BP_DENOM))} 提前结算（低于盈亏平衡 {fmt_pct(be_ratio.value)}），"
             f"账期不变、无返利：远期让步 ¥0.00。若对方拒绝：{_label_zh(fallback.label) if fallback else '无需后备'}。"
             + (f"若对方接受，其余缺口：{_label_zh(accept_plan.label)}。" if accept_ops and accept_plan else ""))
    head += (t(ctx, f" If {cp} refuses: {when_refuse}", f" 若 {cp} 拒绝：{when_refuse}") if when_refuse else "")
    head += (t(ctx, f" If {cp} refuses: {refuse_note}", f" 若 {cp} 拒绝：{refuse_note}") if refuse_note else "")
    head += (t(ctx, f" If {cp} accepts: {when_accept}", f" 若 {cp} 接受：{when_accept}") if when_accept else "")
    head += (t(ctx, f" If {cp} accepts: {accept_note}", f" 若 {cp} 接受：{accept_note}") if accept_note else "")
    data = {"verdict_id": gv.id, "counter_id": counter.id, "cp": cp, "accept_ops": accept_ops, "refuse_ops": refuse_ops,
            "verify": steps.items[0].description, "text": text, "terms": (_face(counter), _rate(counter)),
            "refuse_note": refuse_note, "accept_note": accept_note}
    pending = PendingPlan(Intent.ACCELERATE_RECEIPT, slots, steps.items, data).bind(ctx, [*accept_ops, *refuse_ops])
    return Turn(intent=Intent.ACCELERATE_RECEIPT, verdict=gv, plan=steps.items, awaiting=True, amended=amended,
                pending=pending,
                reply=head + t(ctx, " Reply 'go ahead' to run it, or correct me (e.g. 'make it 0.8%').",
                               " 回复“执行”运行，或直接修改（例如“改成 0.8%”）。"))


def run_accelerate(ctx: NlContext, pending: PendingPlan) -> Turn:
    """A confirmed early-pay plan: send the stored counter, run the bounded rounds, then the stored legs for the
    outcome (the remaining gap if the buyer accepts, the router's plan if it refuses). Nothing is re-planned."""
    d = pending.data
    gv = ctx.store.get_verdict(d["verdict_id"])
    counter = next((c for c in gv.counters if c.id == d["counter_id"]), None) if gv is not None else None
    if gv is None or counter is None:
        return Turn(intent=Intent.ACCELERATE_RECEIPT, clear_pending=True, reply=t(
            ctx, "That proposal is no longer on record, so nothing was executed.", "该方案已不在记录中，未执行任何操作。"))
    if (said := sent_outside(ctx, gv.offer_id)) is not None:  # the buyer has the owner's own counter: nothing is sent or run (OUT-1)
        return Turn(intent=Intent.ACCELERATE_RECEIPT, reply=said, verdict=gv, clear_pending=True)
    cp = d["cp"]
    run = Steps()
    run.add("VERIFY", d["verify"], "DONE")
    profile = pending.slots.buyer_profile or ctx.session.buyer_profile or cp
    try:
        BuyerKernel().max_rounds(profile)
    except Exception:  # noqa: BLE001 - an unknown simulated profile: negotiate with the counterparty's own
        profile = cp
    neg = run_negotiation(ctx, run, gv, [counter], profile)
    reply: list[str] = []
    if neg.accepted is not None:
        r = accept(ctx, run, gv, neg.accepted)
        reply.append(t(ctx, f"{cp} accepted {counter.label}: {counter.text}", f"{cp} 接受了 {counter_line(ctx, counter.label, counter.text)}"))
        if r is not None and r.status.value in ("EXECUTED", "PENDING_APPROVAL", "DUPLICATE") and d["accept_ops"]:
            lines, _ok = run_legs(ctx, run, d["accept_ops"], t(ctx, "remaining gap after early settlement", "提前结算后剩余缺口"))
            reply += lines
        elif d.get("accept_note"):  # the rest of the gap has a plan, but not one that can run today
            reply.append(d["accept_note"])
    elif d["refuse_ops"]:
        reply.append(t(ctx, f"{cp} refused.", f"{cp} 拒绝。"))
        lines, _ok = run_legs(ctx, run, d["refuse_ops"], t(ctx, "if the buyer refuses (fallback)", "若买方拒绝（后备方案）"))
        reply += lines
    elif d.get("refuse_note"):  # a plan exists, but not one that can run today: nothing was stored for it
        reply.append(t(ctx, f"{cp} refused. ", f"{cp} 拒绝。") + d["refuse_note"])
    else:
        reply.append(t(ctx, f"{cp} refused, and there is no gap to fund.", f"{cp} 拒绝，且无资金缺口。"))
    return Turn(intent=Intent.ACCELERATE_RECEIPT, reply="\n".join(reply), plan=run.items, verdict=gv,
                negotiation=neg.summary, clear_pending=True)


def reprice_accelerate(ctx: NlContext, pending: PendingPlan) -> tuple[str | None, Turn | None]:
    """(why the stored early-pay plan no longer holds or None, the fresh proposal built to find out). The books
    moved, so the plan is proposed again on them: it stands only if the counter (face and rate) and every leg that may
    follow it come out the same, and the stored financing, when that is the plan, is still feasible at its quote."""
    if pending.slots.use_financing:
        why = reprice_actions(ctx, ctx.state(), pending)
        return why, None
    fresh = accelerate(ctx, pending.slots, pending.data.get("text", ""))
    fp = fresh.pending
    if (fp is None or fp.data.get("terms") != pending.data.get("terms")
            or signature(fp.ops) != signature(pending.ops)):
        return (t(ctx, "the books changed and the early-payment plan I showed no longer comes out the same",
                  "账目已变化，我之前给出的提前收款方案已不再相同"), fresh)
    return None, fresh


def _goal_offer(ctx: NlContext, text: str, cp: str, receivable_id: str, face: int, rate_bp: int) -> CompiledOffer:
    """The buyer's standing early-pay offer on the target invoice, as a typed obligation. Its span is the
    owner's own words, so the verifier checks a real, grounded request."""
    doc = owner_doc_for(ctx, text)
    low = doc.text.lower()
    cue = next((w for w in ("paid early", "early", "提前", "早点") if w in low), None)
    start = low.index(cue) if cue else 0
    end = start + len(cue) if cue else len(doc.text)
    ob = Obligation(id=f"GOAL-{doc.doc_id}-O1", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id=cp,
                    rate_bp=rate_bp, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id=receivable_id,
                                                         amount_fen=face),
                    contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
                    spans=[span_of(doc, start, end)], confidence=1.0)
    oid = f"GOAL-{cp}-{receivable_id}-{rate_bp}-d{ctx.day}"
    return CompiledOffer(offer_id=oid, counterparty_id=cp, doc_ids=[doc.doc_id], received_day=ctx.day,
                         status=CompileStatus.COMPILED, obligations=[ob], compiler="nl-goal", prompt_version="nl-v1")


def _label_zh(label: str) -> str:
    """The router's plan label ("committed plan: ¥841.64 + ¥2,272.29 = ¥3,113.93") in Chinese, figures unchanged."""
    from app.api.engine_zh import translate

    return translate(label) or label


def _face(c: CounterProposal) -> int:
    return next((o.base.amount_fen or 0 for o in c.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT), 0)


def _rate(c: CounterProposal) -> int:
    return next((o.rate_bp or 0 for o in c.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT), 0)


# ---------------------------------------------------------------- SHOW_STATUS


def _x(x: Fraction) -> str:
    return Ratio.of(x).text


def status(ctx: NlContext) -> Turn:
    state, mandate = ctx.state(), ctx.mandate()
    floor = mandate.min_cash_fen
    live = ctx.books(state).obligations
    traj = project(state, list(live), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    found = gaps(state, floor, mandate.horizon_days, live, from_day=max(ctx.day, state.as_of_day))
    facts: dict = {"cash_fen": state.cash_fen, "floor_fen": floor,
                   "gaps": [(g.low_fen, g.low_day, g.shortfall_fen) for g in found],
                   "lowest": (traj.min_cash_fen, traj.min_cash_day)}
    lines = [t(ctx, f"Cash today (day {ctx.day}): {fmt_yuan(state.cash_fen)}. Reserve floor {fmt_yuan(floor)}.",
               f"今日（第 {ctx.day} 天）现金 {fmt_yuan(state.cash_fen)}，储备线 {fmt_yuan(floor)}。")]
    if found:
        lines.append(t(ctx, "Breach days (conservative): ", "低于储备的日子（保守口径）：")
                     + "; ".join(gap_label(ctx, g) for g in found) + ".")
    else:
        lines.append(t(ctx, f"No breach: lowest projected cash {fmt_yuan(traj.min_cash_fen)} on day {traj.min_cash_day}.",
                       f"无低于储备的日子：最低 {fmt_yuan(traj.min_cash_fen)}（第 {traj.min_cash_day} 天）。"))
    dscr = [m for m in traj.months if m.dscr is not None]
    lev = [m for m in traj.months if m.leverage is not None]
    if dscr:
        w = min(dscr, key=lambda m: m.dscr.value)  # type: ignore[union-attr]
        lim = Fraction(mandate.min_dscr_bp, BP_DENOM)
        head = _x(w.dscr.value - lim)  # type: ignore[union-attr]
        facts["dscr"] = (w.dscr.text, w.month, _x(lim))  # type: ignore[union-attr]
        lines.append(t(ctx, f"DSCR low {w.dscr.text}× in month {w.month} (min {_x(lim)}×, headroom {head}×).",  # type: ignore[union-attr]
                       f"DSCR 最低 {w.dscr.text}×（第 {w.month} 月），下限 {_x(lim)}×，余量 {head}×。"))  # type: ignore[union-attr]
    if lev:
        w = max(lev, key=lambda m: m.leverage.value)  # type: ignore[union-attr]
        lim = Fraction(mandate.max_leverage_bp, BP_DENOM)
        head = _x(lim - w.leverage.value)  # type: ignore[union-attr]
        facts["leverage"] = (w.leverage.text, w.month, _x(lim))  # type: ignore[union-attr]
        lines.append(t(ctx, f"Leverage high {w.leverage.text}× in month {w.month} (max {_x(lim)}×, headroom {head}×).",  # type: ignore[union-attr]
                       f"杠杆最高 {w.leverage.text}×（第 {w.month} 月），上限 {_x(lim)}×，余量 {head}×。"))  # type: ignore[union-attr]
    fc = sum(f.value_fen for f in state.forward_concessions)
    cap = mandate.max_aggregate_forward_concession_fen
    facts["concessions"] = (fc, cap)
    lines.append(t(ctx, f"Forward concessions {fmt_yuan(fc)} of {fmt_yuan(cap)} (headroom {fmt_yuan(cap - fc)}).",
                   f"远期让步 {fmt_yuan(fc)} / 上限 {fmt_yuan(cap)}（余量 {fmt_yuan(cap - fc)}）。"))
    drawn = [f for f in state.facilities if f.drawn_fen]
    facts["drawn"] = [(f.id, f.drawn_fen) for f in drawn]
    if drawn:
        lines.append(t(ctx, "Drawn: ", "已提款：") + ", ".join(f"{f.id} {fmt_yuan(f.drawn_fen)}" for f in drawn) + ".")
    pending = [a for a in ctx.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]
    if pending:
        lines.append(t(ctx, f"{len(pending)} operation(s) await owner approval: ", f"{len(pending)} 项操作待业主审批：")
                     + ", ".join(a.id for a in pending) + ".")
    facts["pending"] = [a.id for a in pending]
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(lines), facts={"status": facts})
