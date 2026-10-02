"""Chat access to capabilities that are already built (tracker rows E1 and E2): the financing comparison, the
reconciliation, the covenant ratios, the capex case and the borrower file; and the nearest-capability reply that
replaces the flat "outside what I can do".

Every handler READS through the module function the HTTP route uses, on current books, and speaks the figures the
module formatted (`fmt_yuan`, the modules' own display strings); none re-implements a calculation. Only
BORROWER_FILE produces an operation: a typed GenerateBorrowerFile, proposed first and sent to the executor on the
owner's direct "go ahead"; the executor decides the tier. All five disclose protected figures, so they are for the
owner (the owner token) only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from app.alerts import (
    AlertKind,
    PromiseStatus,
    alerts,
    covenant_limits,  # the covenant thresholds as the covenant alerts take them
    reconcile,
)
from app.borrower_file import BorrowerFileError, build
from app.capex import CapexDisabled, CapexRequest, CapexResult, CapexStructure, evaluate_capex
from app.capex.models import CHARGES_BASIS
from app.config import get_settings
from app.domain.models import GenerateBorrowerFile, Mode, OperationStatus
from app.domain.money import BP_DENOM, Ratio, fmt_pct, fmt_yuan
from app.financial import EngineError, project
from app.funding import compare, menu_view, plan
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.funding import gap_label, gaps
from app.nl.models import Intent, Slots
from app.nl.pipeline import Steps, t
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn, ask

OWNER_ONLY = (Intent.COMPARE_FINANCING, Intent.RECONCILE, Intent.SHOW_RATIOS, Intent.CAPEX, Intent.BORROWER_FILE)
MAX_FLAGGED = 5
MAX_OUTSTANDING = 5


def needs_sign_in(ctx: NlContext, intent: Intent) -> Turn:
    """The agent key alone: the intent is kept, nothing is read, disclosed or logged."""
    return Turn(intent=intent, reply=t(ctx, "This needs the owner's sign-in.", "这需要业主登录。"))


def _off(ctx: NlContext, intent: Intent, feature: str) -> Turn:
    return Turn(intent=intent, reply=t(ctx, f"That feature is switched off ({feature}).",
                                       f"该功能已关闭（{feature}）。"))


def _x(r: Fraction) -> str:
    return Ratio.of(r).text


# ---------------------------------------------------------------- COMPARE_FINANCING


def compare_financing(ctx: NlContext) -> Turn:
    if not get_settings().features.debt_desk:
        return _off(ctx, Intent.COMPARE_FINANCING, "FEATURE_DEBT_DESK")
    state, mandate = ctx.state(), ctx.mandate()
    books = ctx.books(state)
    try:
        committed = plan(books.state, books.with_([]), mandate)
        rows = compare(books.state, books.with_([]), mandate)
    except EngineError:
        return Turn(intent=Intent.COMPARE_FINANCING, reply=t(
            ctx, "I could not project the books just now, so I cannot compare the options.",
            "暂时无法预测账目，无法比较融资方案。"))
    menu = [r for r in menu_view(state, mandate, need_fen=committed.need_fen or None) if r.status.value != "REFERENCE_ONLY"]
    in_plan = {c.facility_id: c.fen for c in committed.costs if c.facility_id}
    lines: list[str] = []
    gap = committed.need_fen > 0
    if gap:
        found = gaps(state, mandate.min_cash_fen, mandate.horizon_days, books.obligations,
                     from_day=max(ctx.day, state.as_of_day))
        lines.append(t(ctx, f"Gap to fund: {fmt_yuan(committed.need_fen)}"
                            + (f" ({'; '.join(gap_label(ctx, g) for g in found)})" if found else "") + ".",
                       f"需要融资的缺口：{fmt_yuan(committed.need_fen)}"
                       + (f"（{'；'.join(gap_label(ctx, g) for g in found)}）" if found else "") + "。"))
    else:
        lines.append(t(ctx, "There is no projected cash gap today, so nothing needs funding. The committed sources:",
                       "目前没有预测的资金缺口，无需融资。已承诺的融资来源："))
    for r in menu:
        if not gap and not r.committed:
            continue
        cash = (t(ctx, "cash same day", "当天到账") if r.time_to_cash_days == 0
                else t(ctx, f"cash in {r.time_to_cash_days} day{'' if r.time_to_cash_days == 1 else 's'}",
                                f"{r.time_to_cash_days} 天到账"))
        state_en = "committed" if r.committed else r.status.value.lower().replace("_", " ")
        state_zh = "已承诺" if r.committed else {"NOT_APPLIED": "未申请", "PENDING": "审批中"}.get(r.status.value, state_en)
        if not gap:
            lines.append(t(ctx, f"- {r.name}: {r.all_in_display} all-in a year, {cash}, up to {r.available_display}.",
                           f"- {r.name}：综合年化 {r.all_in_display}，{cash}，可用 {r.available_display}。"))
            continue
        cost = (t(ctx, f"{fmt_yuan(in_plan[r.facility_id])} for this gap", f"本次缺口成本 {fmt_yuan(in_plan[r.facility_id])}")
                if r.facility_id in in_plan else t(ctx, "not in the plan", "不在方案中"))
        why = ""
        if not r.committed:
            why = t(ctx, "; not relied on until it is committed", "；未承诺前不计入方案")
        elif not r.admissible_for_need and r.notes:
            why = t(ctx, f"; not used: {r.notes[0]}", f"；未采用：{r.notes[0]}")
        lines.append(t(ctx, f"- {r.name}: {r.all_in_display} all-in a year, {cost}, {cash}, {state_en}{why}.",
                       f"- {r.name}：综合年化 {r.all_in_display}，{cost}，{cash}，{state_zh}{why}。"))
    if gap:
        sel = next((c for c in rows if c.result.value == "SELECTED"), None)
        if committed.admissible and sel is not None:
            steps = "; ".join(c.label for c in committed.costs)
            lines.append(t(ctx, f"Selected committed plan: {steps}. Total cost {sel.cost_display}.",
                           f"选定的已承诺方案：{steps}。总成本 {sel.cost_display}。"))
        else:
            lines.append(t(ctx, "No committed source can cover this gap on its own; the owner must decide.",
                           "没有已承诺的融资来源可以单独覆盖该缺口，需由业主决定。"))
        lines.append(t(ctx, "Nothing was executed. Say 'fund the gap' to have me do it.",
                       "未执行任何操作。回复“补足资金缺口”，我来办理。"))
    return Turn(intent=Intent.COMPARE_FINANCING, reply="\n".join(lines))


# ---------------------------------------------------------------- RECONCILE


def reconcile_receipts(ctx: NlContext) -> Turn:
    if not get_settings().features.alerts:
        return _off(ctx, Intent.RECONCILE, "FEATURE_ALERTS")
    rep = reconcile(ctx.store, day=ctx.day)
    lines = [t(ctx, f"Reconciliation to day {rep.as_of_day}: {rep.matched} receipt(s) matched, {rep.flagged} flagged; "
                    f"received {fmt_yuan(rep.received_total_fen)} of {fmt_yuan(rep.expected_total_fen)} expected.",
               f"截至第 {rep.as_of_day} 天对账：{rep.matched} 笔回款匹配，{rep.flagged} 笔有异常；"
               f"实收 {fmt_yuan(rep.received_total_fen)}，应收 {fmt_yuan(rep.expected_total_fen)}。")]
    for m in [m for m in rep.receipts if m.flagged][:MAX_FLAGGED]:
        lines.append(t(ctx, f"- Flagged: {m.receivable_id} {fmt_yuan(m.received_fen)}: {m.status.value}. {m.detail}",
                       f"- 异常：{m.receivable_id} {fmt_yuan(m.received_fen)}：{m.status.value}。{m.detail}"))
    if rep.promised:
        counts = {s: sum(1 for p in rep.promised if p.status == s) for s in PromiseStatus}
        lines.append(t(ctx, "Promised early payments: " + ", ".join(f"{s.value} {n}" for s, n in counts.items() if n) + ".",
                       "承诺的提前付款：" + "，".join(f"{s.value} {n}" for s, n in counts.items() if n) + "。"))
        for p in [p for p in rep.promised if p.status == PromiseStatus.LAPSED]:
            lines.append(t(ctx, f"- Lapsed: {p.receivable_id} ({p.counterparty_id}), {fmt_yuan(p.expected_fen)} promised for "
                                f"day {p.promised_day}. {p.detail}",
                           f"- 已逾期：{p.receivable_id}（{p.counterparty_id}），承诺第 {p.promised_day} 天支付 "
                           f"{fmt_yuan(p.expected_fen)}。{p.detail}"))
    out = sorted(rep.outstanding, key=lambda o: (not o.past_due, o.due_day, o.receivable_id))
    if out:
        shown = "; ".join(
            f"{o.receivable_id} ({o.counterparty_id}) {fmt_yuan(o.face_fen)} due day {o.due_day}"
            + (" past due" if o.past_due else "") for o in out[:MAX_OUTSTANDING])
        shown_zh = "；".join(
            f"{o.receivable_id}（{o.counterparty_id}）{fmt_yuan(o.face_fen)}，第 {o.due_day} 天到期"
            + ("，已逾期" if o.past_due else "") for o in out[:MAX_OUTSTANDING])
        more = len(out) - MAX_OUTSTANDING
        lines.append(t(ctx, f"Outstanding receivables, past due first: {shown}" + (f" and {more} more" if more > 0 else "") + ".",
                       f"未收应收款（逾期优先）：{shown_zh}" + (f"，另有 {more} 笔" if more > 0 else "") + "。"))
    else:
        lines.append(t(ctx, "No receivable is outstanding.", "没有未收的应收款。"))
    lines.append(t(ctx, "The audit chain verifies." if rep.chain_valid else "The audit chain does NOT verify.",
                   "审计链校验通过。" if rep.chain_valid else "审计链校验未通过。"))
    return Turn(intent=Intent.RECONCILE, reply="\n".join(lines))


# ---------------------------------------------------------------- SHOW_RATIOS


def show_ratios(ctx: NlContext) -> Turn:
    state, mandate = ctx.state(), ctx.mandate()
    books = ctx.books(state)
    try:
        traj = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, mandate.horizon_days,
                       mandate.min_cash_fen)
    except EngineError:
        return Turn(intent=Intent.SHOW_RATIOS, reply=t(ctx, "I could not project the books just now, so I cannot "
                                                            "show the ratios.", "暂时无法预测账目，无法显示指标。"))
    dscr_limits, lev_limits = covenant_limits(books.state, mandate)
    dscr_limit, dscr_src = max(dscr_limits, key=lambda z: z[0])
    lev_limit, lev_src = min(lev_limits, key=lambda z: z[0])
    lines: list[str] = []
    inside = True
    dscr = [m for m in traj.months if m.dscr is not None]
    lev = [m for m in traj.months if m.leverage is not None]
    if dscr:
        w = min(dscr, key=lambda m: m.dscr.value)  # type: ignore[union-attr]
        head = w.dscr.value - dscr_limit  # type: ignore[union-attr]
        inside &= head >= 0
        lines.append(t(ctx, f"Lowest DSCR {w.dscr.text}× in month {w.month}, against the {_x(dscr_limit)}× minimum "  # type: ignore[union-attr]
                            f"({dscr_src}): headroom {_x(head)}×.",
                       f"最低 DSCR {w.dscr.text}×（第 {w.month} 月），下限 {_x(dscr_limit)}×（{dscr_src}）：余量 {_x(head)}×。"))  # type: ignore[union-attr]
    if lev:
        w = max(lev, key=lambda m: m.leverage.value)  # type: ignore[union-attr]
        head = lev_limit - w.leverage.value  # type: ignore[union-attr]
        inside &= head >= 0
        lines.append(t(ctx, f"Highest leverage {w.leverage.text}× in month {w.month}, against the {_x(lev_limit)}× maximum "  # type: ignore[union-attr]
                            f"({lev_src}): headroom {_x(head)}×.",
                       f"最高杠杆 {w.leverage.text}×（第 {w.month} 月），上限 {_x(lev_limit)}×（{lev_src}）：余量 {_x(head)}×。"))  # type: ignore[union-attr]
    if not lines:
        lines.append(t(ctx, "No month of the projection carries debt service or debt, so there is no ratio to show.",
                       "预测期内没有债务或还本付息，没有可显示的指标。"))
    else:
        lines.append(t(ctx, "Every projected month is inside the covenants." if inside
                       else "A projected month breaches a covenant.",
                       "预测的每个月都在契约范围内。" if inside else "有预测月份违反契约。"))
    try:
        cd = [a for a in alerts(state, mandate, ctx.store, ctx.day) if a.kind == AlertKind.CLEAN_DOWN_AT_RISK]
    except EngineError:
        cd = []
    lines.append(cd[0].detail if cd else t(ctx, "Clean-down of the credit line: no alert raised.",
                                           "信用额度的清零要求：没有预警。"))
    return Turn(intent=Intent.SHOW_RATIOS, reply="\n".join(lines))


# ---------------------------------------------------------------- CAPEX


def _structure_line(ctx: NlContext, r: CapexResult, s: CapexStructure) -> str:
    tag = (t(ctx, "SELECTED", "选定") if s.id == r.selected_id
           else t(ctx, "passes", "通过") if s.feasible else t(ctx, "fails", "不通过"))
    figures = ""
    if s.min_dscr is not None:
        figures = t(ctx, f"min DSCR {s.min_dscr.text}×", f"最低 DSCR {s.min_dscr.text}×")
        if s.leverage is not None:
            figures += t(ctx, f", leverage {s.leverage.text}×", f"，杠杆 {s.leverage.text}×")
        figures += "; "
    if s.hypothetical:
        tag += t(ctx, " (illustration only: not the facility's real term, never applied for)",
                 "（仅为示例：并非该额度的实际期限，不会据此申请）")
    why = f": {s.violations[0].message}" if not s.feasible and s.violations else ""
    return f"- {s.label}: {figures}{tag}{why}"


def capex_intent(ctx: NlContext, slots: Slots) -> Turn:
    req = CapexRequest()  # POST /capex/evaluate with no body: the spec's case
    if slots.amount_fen is not None and slots.amount_fen != req.price_fen:
        return Turn(intent=Intent.CAPEX, reply=t(
            ctx, f"The capex case I hold is {req.label}, {fmt_yuan(req.price_fen)}; I will not guess at "
                 f"{fmt_yuan(slots.amount_fen)}. Ask about that one, or enter the other machine's price, uplift and "
                 f"life on the Capex screen.",
            f"我手上的资本支出方案是 {req.label}，{fmt_yuan(req.price_fen)}；我不会猜测 {fmt_yuan(slots.amount_fen)}。"
            f"请就该方案提问，或在资本支出页面录入其他设备的价格、增收和使用年限。"))
    state, mandate = ctx.state(), ctx.mandate()
    try:
        r = evaluate_capex(req, state, mandate, commitments=ctx.store.commitments())
    except CapexDisabled:
        return _off(ctx, Intent.CAPEX, "FEATURE_CAPEX")
    except EngineError:
        return Turn(intent=Intent.CAPEX, reply=t(ctx, "I could not project the books just now, so I cannot evaluate "
                                                      "the purchase.", "暂时无法预测账目，无法评估这笔购置。"))
    payback = (t(ctx, f"payback in month {r.payback_month}", f"第 {r.payback_month} 个月回本")
               if r.payback_month is not None else t(ctx, "no payback within its life", "使用期内无法回本"))
    lines = [t(ctx, f"{req.label}, {fmt_yuan(req.price_fen)}: NPV {fmt_yuan(r.npv_fen)} at "
                    f"{fmt_pct(Fraction(req.hurdle_bp, BP_DENOM))}, {payback}. ",
               f"{req.label}，{fmt_yuan(req.price_fen)}：按 {fmt_pct(Fraction(req.hurdle_bp, BP_DENOM))} 折现，"
               f"净现值 {fmt_yuan(r.npv_fen)}，{payback}。") + r.estimate_note]
    lines += [_structure_line(ctx, r, s) for s in r.structures]
    lines.append(r.recommendation)
    lines.append(t(ctx, f"Computed on day {r.as_of_day}. Structures are ranked on the {CHARGES_BASIS}; rates are "
                        f"nominal annual rates, and the uplift is your estimate, not an observed figure.",
                   f"按第 {r.as_of_day} 天的账目计算。结构按融资费用合计（利息加费用，未折现）排序；利率为名义年利率；"
                   f"增收为您的估计，并非实测数据。"))
    lines.append(t(ctx, "Nothing was applied for: the application needs the Capex screen and your approval.",
                   "尚未提交任何申请：申请需在资本支出页面进行，并经您批准。"))
    return Turn(intent=Intent.CAPEX, reply="\n".join(lines))


# ---------------------------------------------------------------- BORROWER_FILE

_FACILITY_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EQUIPMENT_TERM_LOAN", lx._re(r"term loan", r"equipment loan", r"设备贷款", r"设备定期")),
    ("EQUIPMENT_LEASE", lx._re(r"\blease\b", r"租赁")),
    ("GOV_GUARANTEED_LOAN", lx._re(r"guaranteed", r"government", r"政府担保", r"担保贷款")),
)


def _named_facility(slots: Slots, text: str, state_facilities: list) -> str | None:
    ids = {f.id for f in state_facilities}
    if slots.facility_id in ids:
        return slots.facility_id
    low = text.lower()
    for f in state_facilities:
        if f.id.lower() in low:
            return f.id
    for kind, pat in _FACILITY_CUES:
        if pat.search(text):
            found = [f.id for f in state_facilities if f.kind.value == kind]
            if len(found) == 1:
                return found[0]
    return None


def _probe(ctx: NlContext, facility_id: str, amount_fen: int) -> str | None:
    """None when the borrower file module accepts the facility and amount, else its own reason."""
    try:
        build(ctx.store, facility_id=facility_id, amount_fen=amount_fen, use_of_proceeds="owner request in chat",
              day=ctx.day)
    except BorrowerFileError as exc:
        return str(exc)
    return None


def borrower_file(ctx: NlContext, slots: Slots, text: str, *, execute: bool) -> Turn:
    if not get_settings().features.borrower_file:
        return _off(ctx, Intent.BORROWER_FILE, "FEATURE_BORROWER_FILE")
    state = ctx.state()
    fid = _named_facility(slots, text, state.facilities)
    if fid is None:
        ok = [f for f in state.facilities if f.owner_approved and _probe(ctx, f.id, 1) is None]
        if not ok:
            return Turn(intent=Intent.BORROWER_FILE, reply=t(
                ctx, "No facility on the owner-approved menu can take a borrower file.",
                "没有业主批准的融资菜单中的额度可以生成借款人资料。"))
        if len(ok) > 1:
            return ask(Intent.BORROWER_FILE, "facility_id",
                       t(ctx, "Which facility is the borrower file for?", "借款人资料针对哪一项融资？"),
                       [(str(i), f"{f.name} ({f.id})", f.id) for i, f in enumerate(ok, 1)], slots)
        fid = ok[0].id
    fac = next(f for f in state.facilities if f.id == fid)
    if slots.amount_fen is None:
        return Turn(intent=Intent.BORROWER_FILE, reply=t(
            ctx, f"How much is the file for? For example: 'prepare the borrower file for {fid}, "
                 f"{fmt_yuan(max(fac.limit_fen - fac.drawn_fen, 0))}'.",
            f"资料对应多少金额？例如：“准备 {fid} 的借款人资料，{fmt_yuan(max(fac.limit_fen - fac.drawn_fen, 0))}”。"))
    reason = _probe(ctx, fid, slots.amount_fen)
    if reason is not None:
        return Turn(intent=Intent.BORROWER_FILE, clear_pending=True, reply=t(
            ctx, f"I cannot prepare that file: {reason}.", f"无法准备该资料：{reason}。"))
    desc = t(ctx, f"Prepare the borrower file for {fid}, {fmt_yuan(slots.amount_fen)} (prepared, not sent)",
             f"为 {fid} 准备借款人资料，{fmt_yuan(slots.amount_fen)}（仅准备，不发送）")
    steps = Steps()
    if not execute:
        steps.add("GENERATE_BORROWER_FILE", desc)
        pend = slots.model_copy(update={"facility_id": fid})
        return Turn(intent=Intent.BORROWER_FILE, plan=steps.items, awaiting=True,
                    pending=PendingPlan(Intent.BORROWER_FILE, pend, steps.items),
                    reply=desc + t(ctx, ". It needs your approval and nothing is sent to a lender. Reply 'go ahead' "
                                        "to request it.", "。需要您的批准，且不会发送给任何贷方。回复“执行”提出申请。"))
    r = ctx.execute(GenerateBorrowerFile(**ctx.base("GENERATE_BORROWER_FILE"), facility_id=fid,
                                         amount_fen=slots.amount_fen))
    steps.result("GENERATE_BORROWER_FILE", desc, r)
    if r.status == OperationStatus.PENDING_APPROVAL:
        ref = f" ({r.approval_id})" if r.approval_id else ""
        said = r.message.rstrip(". ")
        reply = t(ctx, f"{said}. It waits for your approval{ref}; the file is prepared, not sent.",
                  f"{said}。它在等您批准{ref}；资料仅准备，不会发送。")
    else:
        reply = r.message
    return Turn(intent=Intent.BORROWER_FILE, reply=reply, plan=steps.items, clear_pending=True)


# ---------------------------------------------------------------- the nearest capability (E2)


@dataclass(frozen=True)
class Capability:
    intent: Intent
    en: str
    zh: str
    example_en: str
    example_zh: str
    kw_en: tuple[str, ...]
    kw_zh: tuple[str, ...]


CAPABILITY_TABLE: tuple[Capability, ...] = (
    Capability(Intent.EVALUATE_OFFER, "evaluate a buyer's offer", "评估买家报价", "evaluate EX01", "评估 EX01",
               ("offer", "buyer", "deal", "discount", "terms", "rebate", "contract", "quote", "price"),
               ("报价", "买家", "折扣", "返点", "条款", "合同")),
    Capability(Intent.NEGOTIATE, "negotiate with a buyer", "与买家谈判", "negotiate with Foshan", "跟佛山谈判",
               ("negotiate", "counter", "haggle", "bargain"), ("谈判", "还价", "议价", "砍价")),
    Capability(Intent.ACCELERATE_RECEIPT, "get an invoice paid early", "提前收款", "get Foshan to pay early", "让佛山提前付款",
               ("paid", "early", "invoice", "receipt", "collect", "collection", "customer"),
               ("回款", "收款", "提前", "发票")),
    Capability(Intent.FUND_GAP, "fund a projected cash gap", "为资金缺口融资", "fund the gap", "补足资金缺口",
               ("fund", "gap", "shortfall", "borrow", "draw", "cash", "payroll", "money", "short", "loan"),
               ("缺口", "资金", "借钱", "融资", "提款", "工资")),
    Capability(Intent.REPAY_FACILITY, "repay a facility", "偿还额度", "repay the credit line", "偿还授信额度",
               ("repay", "pay back", "debt", "line", "facility"), ("还款", "偿还", "还清")),
    Capability(Intent.SHOW_STATUS, "show cash status", "查看现金状况", "how are we doing", "现金状况怎么样",
               ("status", "balance", "position", "forecast", "bank", "cash", "receivables"),
               ("现金", "余额", "状况", "预测", "应收")),
    Capability(Intent.SHOW_ALERTS, "show what needs you (alerts)", "查看需要您处理的提醒", "any alerts?", "有什么提醒",
               ("alert", "alerts", "warning", "news", "attention", "notify"), ("提醒", "预警", "告警")),
    Capability(Intent.EXPLAIN, "explain a verdict", "解释结论", "why was it rejected?", "为什么被拒绝？",
               ("explain", "why", "reason", "verdict", "rejected"), ("为什么", "解释", "原因")),
    Capability(Intent.WHAT_IF, "run a what-if", "做假设分析", "what if we accept 1.5%?", "如果接受1.5%会怎样？",
               ("what if", "suppose", "scenario", "hypothetical", "simulate"), ("如果", "假设", "会怎样")),
    Capability(Intent.APPROVE, "approve or reject a pending operation", "批准或驳回待审批操作", "approve the pending one", "批准待审批的操作",
               ("approve", "reject", "approval", "queue", "pending", "decline"), ("批准", "审批", "驳回")),
    Capability(Intent.COMPARE_FINANCING, "compare financing options", "比较融资方案", "which financing option is cheapest?", "哪种融资最便宜？",
               ("financing", "funding", "loan", "cheapest", "interest", "rate", "option", "options", "source", "sources"),
               ("融资", "贷款", "利率", "最便宜")),
    Capability(Intent.RECONCILE, "reconcile receipts", "核对回款", "reconcile this month", "对账",
               ("reconcile", "reconciliation", "receipts", "payment", "payments", "paid", "missing", "ledger"),
               ("对账", "回款", "核对")),
    Capability(Intent.SHOW_RATIOS, "show the covenant ratios (DSCR, leverage)", "查看契约指标（DSCR、杠杆）", "what is our DSCR?", "偿债覆盖率是多少？",
               ("dscr", "leverage", "covenant", "covenants", "ratio", "ratios", "coverage", "headroom"),
               ("杠杆", "契约", "覆盖率")),
    Capability(Intent.CAPEX, "evaluate an equipment purchase", "评估设备购置", "should I buy the machine?", "买这台设备划算吗？",
               ("machine", "equipment", "capex", "purchase", "buy", "invest", "npv", "payback"),
               ("设备", "机器", "购置")),
    Capability(Intent.BORROWER_FILE, "prepare a borrower file", "准备借款人资料", "prepare the borrower file", "准备借款人资料",
               ("borrower", "lender", "file", "pack", "application", "dossier"), ("借款人", "资料", "申请")),
)


def _score(cap: Capability, low: str, raw: str) -> int:
    en = sum(1 for k in cap.kw_en if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?:e?s)?(?![a-z0-9])", low))
    return en + sum(1 for k in cap.kw_zh if k in raw)


def closest_capability(text: str) -> Capability | None:
    """The capability whose keywords overlap the text most (the first in the table on a tie), or None."""
    low, raw = lx.norm(text), text
    best = max(CAPABILITY_TABLE, key=lambda c: _score(c, low, raw))
    return best if _score(best, low, raw) > 0 else None


def nearest_reply(ctx: NlContext, text: str, capabilities_en: str, capabilities_zh: str) -> Turn:
    cap = closest_capability(text)
    if cap is not None:
        reply = t(ctx, f"I can't do that. The closest thing I can do is {cap.en}: try \"{cap.example_en}\".",
                  f"这个我做不了。我最接近能做的是{cap.zh}，您可以试试说：“{cap.example_zh}”。")
    else:
        reply = t(ctx, "I can't do that. " + capabilities_en, "这个我做不了。" + capabilities_zh)
    return Turn(intent=Intent.OUT_OF_SCOPE, reply=reply)


__all__ = [
    "CAPABILITY_TABLE",
    "OWNER_ONLY",
    "borrower_file",
    "capex_intent",
    "closest_capability",
    "compare_financing",
    "nearest_reply",
    "needs_sign_in",
    "reconcile_receipts",
    "show_ratios",
]
