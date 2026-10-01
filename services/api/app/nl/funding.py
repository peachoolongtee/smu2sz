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
    Outcome,
    RepayFacility,
    Repayment,
)
from app.domain.money import BP_DENOM, Ratio, fmt_pct, fmt_yuan
from app.financial import project
from app.funding import NoPermanentSourceError, break_even_discount
from app.nl.context import NlContext
from app.nl.models import Intent, Slots
from app.nl.offers import buyer_options, owner_doc_for, verdict_line
from app.nl.pipeline import (
    Steps,
    accept,
    committed_plan,
    funding_ops,
    package_offer,
    run_negotiation,
    span_of,
    status_quo_offer,
    t,
)
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn, ask
from app.verifier import OwnerConstraints

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
    funding_ops(ctx, steps, plan, execute=execute)
    head = t(ctx, f"Router plan (committed facilities only): {plan.label}, need {fmt_yuan(plan.need_fen)}.",
             f"融资路由方案（仅已承诺额度）：{plan.label}，需求 {fmt_yuan(plan.need_fen)}。")
    if not execute:
        return Turn(intent=Intent.FUND_GAP, reply=head + t(ctx, " Reply 'go ahead' to execute.", " 回复“执行”以执行。"),
                    plan=steps.items, verdict=b.verdict, awaiting=True,
                    pending=PendingPlan(Intent.FUND_GAP, slots, steps.items))
    return Turn(intent=Intent.FUND_GAP, reply=head, plan=steps.items, verdict=b.verdict, clear_pending=True)


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
        return Turn(intent=Intent.FUND_GAP, reply=desc + t(ctx, ". Reply 'go ahead' to execute.", "。回复“执行”以执行。"),
                    plan=steps.items, verdict=b.verdict, awaiting=True,
                    pending=PendingPlan(Intent.FUND_GAP, slots, steps.items))
    r = ctx.execute(DrawFacility(**ctx.base("DRAW_FACILITY"), facility_id=slots.facility_id,
                                 amount_fen=slots.amount_fen))
    steps.result("DRAW_FACILITY", desc, r)
    return Turn(intent=Intent.FUND_GAP, reply=r.message, plan=steps.items, verdict=b.verdict, clear_pending=True)


# ---------------------------------------------------------------- REPAY_FACILITY


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
    if fac.repayment != Repayment.BULLET:
        return Turn(intent=Intent.REPAY_FACILITY, reply=t(
            ctx, f"{fac.name} is repaid {fac.repayment.value.lower().replace('_', ' ')} (from the receivable), not on demand.",
            f"{fac.name} 按回款偿还，不能随时偿还。"))
    amount = min(slots.amount_fen or fac.drawn_fen, fac.drawn_fen)
    # the reserve check: repaying must not push any projected day below the owner's floor
    after = state.model_copy(update={
        "cash_fen": state.cash_fen - amount,
        "facilities": [f.model_copy(update={"drawn_fen": f.drawn_fen - amount}) if f.id == fac.id else f
                       for f in state.facilities]})
    b_now = ctx.evaluate(status_quo_offer(ctx, state, "RPN"), remember=False)
    b_after = ctx.evaluate(status_quo_offer(ctx, after, "RPA"), state=after, remember=False)
    low_now = b_now.trajectory.min_cash_fen if b_now.trajectory else state.cash_fen
    low_after = b_after.trajectory.min_cash_fen if b_after.trajectory else after.cash_fen
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
        return Turn(intent=Intent.REPAY_FACILITY, plan=steps.items, verdict=b_after.verdict, reply=t(
            ctx, f"Not repaid: it would take projected cash to {fmt_yuan(low_after)}, below the owner's reserve.",
            f"未偿还：还款会使预测现金降至 {fmt_yuan(low_after)}，低于储备线。") + hint)
    if not execute:
        steps.add("REPAY_FACILITY", desc)
        return Turn(intent=Intent.REPAY_FACILITY, reply=desc + t(ctx, ". Reply 'go ahead' to execute.", "。回复“执行”。"),
                    plan=steps.items, awaiting=True, pending=PendingPlan(Intent.REPAY_FACILITY, slots, steps.items))
    r = ctx.execute(RepayFacility(**ctx.base("REPAY_FACILITY"), facility_id=fac.id, amount_fen=amount))
    steps.result("REPAY_FACILITY", desc, r)
    return Turn(intent=Intent.REPAY_FACILITY, reply=r.message, plan=steps.items, verdict=b_after.verdict,
                clear_pending=True)


# ---------------------------------------------------------------- ACCELERATE_RECEIPT (EX12)


def largest_step_below(limit: Fraction) -> int:
    k = -(-limit * BP_DENOM // STEP_BP) - 1
    return max(0, int(k) * STEP_BP)


def accelerate(ctx: NlContext, slots: Slots, text: str, *, execute: bool = False, amended: bool = False) -> Turn:
    """Goal -> plan: an early-pay counter at or below the break-even-derived rate with zero forward
    concessions; if the buyer refuses, the router's committed plan (invoice financing + line) instead."""
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
        funding_ops(ctx, steps, fallback, execute=execute)
        head = t(ctx, f"Plan: finance {rcv.id} instead of asking {cp} for early payment: {fallback.label}.",
                 f"方案：以 {rcv.id} 发票融资代替向 {cp} 提前收款：{fallback.label}。")
        if not execute:
            return Turn(intent=Intent.ACCELERATE_RECEIPT, amended=amended, verdict=sq.verdict, plan=steps.items,
                        awaiting=True, pending=PendingPlan(Intent.ACCELERATE_RECEIPT, slots, steps.items),
                        reply=head + t(ctx, " Reply 'go ahead' to execute (Tier 1).", " 回复“执行”（一级权限）。"))
        return Turn(intent=Intent.ACCELERATE_RECEIPT, reply=head, plan=steps.items, verdict=sq.verdict,
                    clear_pending=True)

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
        if fallback is not None:
            funding_ops(ctx, steps, fallback, execute=execute, condition=if_cond)
        return Turn(intent=Intent.ACCELERATE_RECEIPT, plan=steps.items, verdict=v, clear_pending=execute,
                    reply=t(ctx, "No early-pay counter fits the goal; the committed financing plan applies.",
                            "没有符合目标的提前付款反报价；适用已承诺融资方案。"))
    counter = zero[0]
    gv = v
    steps.add("COUNTER_OFFER", f"{counter.label}: {counter.text}", "PROPOSED")
    steps.add("NEGOTIATE", t(ctx, f"Bounded rounds with {cp}", f"与 {cp} 有限轮次谈判"))
    steps.add("ACCEPT_OFFER", t(ctx, "Record the commitment (nonce, expiry)", "记录承诺（随机数、到期日）"),
              condition=t(ctx, "if the buyer accepts", "若买方接受"))
    if fallback is not None:
        funding_ops(ctx, steps, fallback, execute=False, condition=if_cond)
    if not execute:
        head = t(ctx, f"Plan (Tier 1): offer {cp} early settlement on up to "
                      f"{fmt_yuan(_face(counter))} of {rcv.id} at {fmt_pct(Fraction(_rate(counter), BP_DENOM))} "
                      f"(below the {fmt_pct(be_ratio.value)} break-even), terms unchanged, no rebate: ¥0.00 of forward "
                      f"concessions. If {cp} refuses: {fallback.label if fallback else 'no fallback needed'}.",
                 f"方案（一级权限）：向 {cp} 提议对 {rcv.id} 最多 {fmt_yuan(_face(counter))} 按 "
                 f"{fmt_pct(Fraction(_rate(counter), BP_DENOM))} 提前结算（低于盈亏平衡 {fmt_pct(be_ratio.value)}），"
                 f"账期不变、无返利：远期让步 ¥0.00。若对方拒绝：{fallback.label if fallback else '无需后备'}。")
        return Turn(intent=Intent.ACCELERATE_RECEIPT, verdict=gv, plan=steps.items, awaiting=True, amended=amended,
                    pending=PendingPlan(Intent.ACCELERATE_RECEIPT, slots, steps.items, {"verdict_id": gv.id}),
                    reply=head + t(ctx, " Reply 'go ahead' to run it, or correct me (e.g. 'make it 0.8%').",
                                   " 回复“执行”运行，或直接修改（例如“改成 0.8%”）。"))
    # execute: counter -> bounded rounds -> accept, or the fallback
    run = Steps()
    run.add("VERIFY", steps.items[0].description, "DONE")
    profile = slots.buyer_profile or ctx.session.buyer_profile or cp
    try:
        BuyerKernel().max_rounds(profile)
    except Exception:  # noqa: BLE001 - an unknown simulated profile: negotiate with the counterparty's own
        profile = cp
    neg = run_negotiation(ctx, run, gv, [counter], profile)
    reply: list[str] = []
    if neg.accepted is not None:
        r = accept(ctx, run, gv, neg.accepted)
        if r is not None and r.status.value in ("EXECUTED", "PENDING_APPROVAL", "DUPLICATE"):
            offer = ctx.store.get_offer(gv.offer_id)
            if offer is not None:
                plan = committed_plan(ctx.evaluate_accepted(package_offer(ctx, offer, neg.accepted)))
                if plan is not None:
                    funding_ops(ctx, run, plan, condition=t(ctx, "remaining gap after early settlement", "提前结算后剩余缺口"))
        reply.append(t(ctx, f"{cp} accepted {counter.label}: {counter.text}", f"{cp} 接受了 {counter.label}：{counter.text}"))
    else:
        if fallback is not None:
            funding_ops(ctx, run, fallback, condition=if_cond)
            reply.append(t(ctx, f"{cp} refused. Fallback executed: {fallback.label}.",
                           f"{cp} 拒绝。已执行后备方案：{fallback.label}。"))
        else:
            reply.append(t(ctx, f"{cp} refused, and there is no gap to fund.", f"{cp} 拒绝，且无资金缺口。"))
    return Turn(intent=Intent.ACCELERATE_RECEIPT, reply="\n".join(reply), plan=run.items, verdict=gv,
                negotiation=neg.summary, clear_pending=True)


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
        lines.append(t(ctx, f"DSCR low {w.dscr.text}× in month {w.month} (min {_x(lim)}×, headroom {head}×).",  # type: ignore[union-attr]
                       f"DSCR 最低 {w.dscr.text}×（第 {w.month} 月），下限 {_x(lim)}×，余量 {head}×。"))  # type: ignore[union-attr]
    if lev:
        w = max(lev, key=lambda m: m.leverage.value)  # type: ignore[union-attr]
        lim = Fraction(mandate.max_leverage_bp, BP_DENOM)
        head = _x(lim - w.leverage.value)  # type: ignore[union-attr]
        lines.append(t(ctx, f"Leverage high {w.leverage.text}× in month {w.month} (max {_x(lim)}×, headroom {head}×).",  # type: ignore[union-attr]
                       f"杠杆最高 {w.leverage.text}×（第 {w.month} 月），上限 {_x(lim)}×，余量 {head}×。"))  # type: ignore[union-attr]
    fc = sum(f.value_fen for f in state.forward_concessions)
    cap = mandate.max_aggregate_forward_concession_fen
    lines.append(t(ctx, f"Forward concessions {fmt_yuan(fc)} of {fmt_yuan(cap)} (headroom {fmt_yuan(cap - fc)}).",
                   f"远期让步 {fmt_yuan(fc)} / 上限 {fmt_yuan(cap)}（余量 {fmt_yuan(cap - fc)}）。"))
    drawn = [f for f in state.facilities if f.drawn_fen]
    if drawn:
        lines.append(t(ctx, "Drawn: ", "已提款：") + ", ".join(f"{f.id} {fmt_yuan(f.drawn_fen)}" for f in drawn) + ".")
    pending = [a for a in ctx.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]
    if pending:
        lines.append(t(ctx, f"{len(pending)} operation(s) await owner approval: ", f"{len(pending)} 项操作待业主审批：")
                     + ", ".join(a.id for a in pending) + ".")
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(lines))
