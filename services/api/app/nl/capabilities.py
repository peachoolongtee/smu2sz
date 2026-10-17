"""Chat access to capabilities that are already built (tracker rows E1 and E2): the financing comparison, the
reconciliation, the covenant ratios, the capex case and the borrower file; and the nearest-capability reply that
replaces the flat "outside what I can do".

Every handler READS through the module function the HTTP route uses, on current books, and speaks the figures the
module formatted (`fmt_yuan`, the modules' own display strings); none re-implements a calculation.
BORROWER_FILE builds the file for the owner and returns its download id: a read-only action with its provenance in
the file, no operation and no approval. None of the five produces an operation, and all five disclose protected
figures, so they are for the owner (the owner token) only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from app.alerts import (
    AlertKind,
    OutstandingReceivable,
    PromiseStatus,
    alerts,
    covenant_limits,  # the covenant thresholds as the covenant alerts take them
    reconcile,
)
from app.api.presentation import buyer_of_receivable, invoice_words, party_name
from app.borrower_file import BorrowerFileError, build, remember
from app.capex import CapexDisabled, CapexRequest, CapexResult, CapexStructure, evaluate_capex
from app.capex.models import CHARGES_BASIS
from app.config import get_settings
from app.covenants import ratios_for, worst_dscr, worst_leverage
from app.domain.models import Mode, Violation
from app.domain.money import BP_DENOM, Ratio, bp, fmt_pct, fmt_yuan
from app.financial import EngineError, project
from app.funding import compare, menu_view, plan
from app.funding.models import ComparisonRow
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.funding import gap_label, gaps
from app.nl.models import Intent, Slots
from app.nl.pipeline import t
from app.nl.plans import ABOVE_CEILING, approval_sentences, unrunnable_sentences
from app.nl.turn import Turn, ask

OWNER_ONLY = (Intent.COMPARE_FINANCING, Intent.RECONCILE, Intent.SHOW_RATIOS, Intent.CAPEX, Intent.BORROWER_FILE,
              Intent.SHOW_DEAL)
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


def _row_line(ctx: NlContext, row: ComparisonRow) -> str:
    """An alternative the router priced and flagged, in words; '' for one that needs no one and can run today."""
    if row.cost_fen is None or not (row.needs_owner_approval or not row.executable_now):
        return ""
    en, zh = [], []
    if row.needs_owner_approval:
        rates = [m for m in ABOVE_CEILING.finditer(row.approval_reason)]
        en.append("needs your approval: " + row.approval_reason)
        zh.append("需要您批准：" + ("；".join(f"年化 {m['rate']}，高于 {m['cap']} 上限" for m in rates) or row.approval_reason))
    if not row.executable_now:
        en.append("cannot run today: it relies on an invoice that is not issued yet")
        zh.append("今天无法执行：它依赖一张尚未开出的发票")
    return t(ctx, f"Also priced: {row.label}, {row.cost_display}; " + "; ".join(en) + ".",
             f"另有测算：{_zh(ctx, row.label)}，{row.cost_display}；" + "；".join(zh) + "。")


def _zh(ctx: NlContext, text: str) -> str:
    """An engine sentence (a router label or note) in Chinese, in the owner's words when the owner's reads are lent to the
    turn (names for ids, distances from today), else through the translation layer; a sentence no template knows stays
    as written."""
    if ctx.reads is not None:
        return str(ctx.reads.words(text, "zh"))
    from app.api.engine_zh import translate

    return translate(text, [f.name for f in ctx.state().facilities]) or text


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
    cap = fmt_pct(bp(mandate.max_apr_bp))
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
        over = (t(ctx, f"; its rate alone is above your {cap} yearly ceiling, so any use of it needs your approval",
                  f"；其利率本身高于您 {cap} 的年度上限，任何使用都需要您批准") if r.needs_owner_approval else "")
        if not gap:
            lines.append(t(ctx, f"- {r.name}: {r.all_in_display} all-in a year, {cash}, up to {r.available_display}{over}.",
                           f"- {r.name}：综合年化 {r.all_in_display}，{cash}，可用 {r.available_display}{over}。"))
            continue
        cost = (t(ctx, f"{fmt_yuan(in_plan[r.facility_id])} for this gap", f"本次缺口成本 {fmt_yuan(in_plan[r.facility_id])}")
                if r.facility_id in in_plan else t(ctx, "not in the plan", "不在方案中"))
        why = ""
        if not r.committed:
            why = t(ctx, "; not relied on until it is committed", "；未承诺前不计入方案")
        elif not r.admissible_for_need and r.notes:
            why = t(ctx, f"; not used: {r.notes[0]}", f"；未采用：{_zh(ctx, r.notes[0])}")
        lines.append(t(ctx, f"- {r.name}: {r.all_in_display} all-in a year, {cost}, {cash}, {state_en}{why}{over}.",
                       f"- {r.name}：综合年化 {r.all_in_display}，{cost}，{cash}，{state_zh}{why}{over}。"))
    if gap:
        sel = next((c for c in rows if c.result.value == "SELECTED"), None)
        if committed.admissible and sel is not None:
            steps = "; ".join(c.label for c in committed.costs)
            lines.append(t(ctx, f"Selected committed plan: {steps}. Total cost {sel.cost_display}.",
                           f"选定的已承诺方案：{'；'.join(_zh(ctx, c.label) for c in committed.costs)}。总成本 {sel.cost_display}。"))
            if committed.needs_owner_approval:
                lines.append(t(ctx, "It needs your approval: ", "该方案需要您批准：") + " ".join(approval_sentences(ctx, committed)))
            if not committed.executable_now:
                lines.append(t(ctx, "It cannot run today: ", "该方案今天无法执行：") + " ".join(unrunnable_sentences(ctx, committed)))
            lines += [f"- {k}" for k in (_row_line(ctx, c) for c in rows if c is not sel) if k]
        else:
            lines.append(t(ctx, "No committed source can cover this gap on its own; the owner must decide.",
                           "没有已承诺的融资来源可以单独覆盖该缺口，需由业主决定。"))
        if committed.admissible and not committed.executable_now:
            lines.append(t(ctx, "Nothing was executed, and 'fund the gap' would not run this plan today.",
                           "未执行任何操作；今天回复“补足资金缺口”也不会执行该方案。"))
        elif committed.admissible and committed.needs_owner_approval:
            lines.append(t(ctx, "Nothing was executed. If you say 'fund the gap', the legs above your ceiling will wait "
                                "for your approval rather than run.",
                           "未执行任何操作。若您回复“补足资金缺口”，高于上限的步骤会等待您批准，而不会直接执行。"))
        else:
            lines.append(t(ctx, "Nothing was executed. Say 'fund the gap' to have me do it.",
                           "未执行任何操作。回复“补足资金缺口”，我来办理。"))
    return Turn(intent=Intent.COMPARE_FINANCING, reply="\n".join(lines))


# ---------------------------------------------------------------- RECONCILE


def _in_scope(ctx: NlContext, receivable_id: str | None, counterparty_id: str | None) -> bool:
    """Whether a reconciliation row belongs to the request's scope: its invoice when the scope names one, else its buyer. Everything when unscoped."""
    if ctx.scope_customer is None:
        return True
    ctx.scope_read = "filtered"
    if ctx.scope_invoice is not None:
        return receivable_id == ctx.scope_invoice
    return (counterparty_id or buyer_of_receivable(ctx.state(), receivable_id)) == ctx.scope_customer


def _business_when(day: int, today: int, lang: str) -> str:
    n = day - today
    if lang == "zh":
        return "今天" if n == 0 else (f"{n} 天后" if n > 0 else f"{-n} 天前")
    days = "1 day" if abs(n) == 1 else f"{abs(n)} days"
    return "today" if n == 0 else (f"in {days}" if n > 0 else f"{days} ago")


def reconcile_receipts(ctx: NlContext) -> Turn:
    """The receipts reconciliation: the scope's own rows when the request has a scope, and in Business mode in the owner's words (the buyer's
    name for an id, a distance from today for a day number, no status code)."""
    if not get_settings().features.alerts:
        return _off(ctx, Intent.RECONCILE, "FEATURE_ALERTS")
    from app.nl import business

    biz = business.active(ctx)
    zh = ctx.lang == "zh"
    state = ctx.state()
    rep = reconcile(ctx.store, day=ctx.day)
    receipts = [m for m in rep.receipts if _in_scope(ctx, m.receivable_id, m.counterparty_id)]
    promised = [p for p in rep.promised if _in_scope(ctx, p.receivable_id, p.counterparty_id)]
    out = sorted((o for o in rep.outstanding if _in_scope(ctx, o.receivable_id, o.counterparty_id)),
                 key=lambda o: (not o.past_due, o.due_day, o.receivable_id))
    scoped = ctx.scope_customer is not None
    matched, flagged = (len(receipts) - sum(1 for m in receipts if m.flagged), sum(1 for m in receipts if m.flagged)) if scoped \
        else (rep.matched, rep.flagged)
    received = sum(m.received_fen for m in receipts) if scoped else rep.received_total_fen
    expected = sum(m.expected_fen or 0 for m in receipts) if scoped else rep.expected_total_fen
    who = party_name(state, ctx.scope_customer) if scoped else ""

    def inv(receivable_id: str) -> str:
        return invoice_words(state, receivable_id, "zh" if zh else "en")

    sums = t(ctx, f"{matched} receipt(s) matched, {flagged} flagged; received {fmt_yuan(received)} of {fmt_yuan(expected)} expected.",
             f"{matched} 笔回款匹配，{flagged} 笔有异常；实收 {fmt_yuan(received)}，应收 {fmt_yuan(expected)}。")
    if biz:
        head = t(ctx, "Checked against today's books: ", "按今天的账目核对：") + sums
        if scoped:
            head = t(ctx, f"Checked against today's books for {who}: ", f"按今天的账目核对{who}：") + sums
    else:
        head = t(ctx, f"Reconciliation to day {rep.as_of_day}: ", f"截至第 {rep.as_of_day} 天对账：") + sums
    lines = [head]
    for m in [m for m in receipts if m.flagged][:MAX_FLAGGED]:
        ref = m.bank_reference
        if biz:
            detail = ctx.reads.words(m.detail, ctx.lang) if ctx.reads is not None else m.detail
            lines.append(t(ctx, f"- Flagged: {inv(m.receivable_id)}{f' (bank reference {ref})' if ref else ''}, {fmt_yuan(m.received_fen)} received. {detail}",
                           f"- 异常：{inv(m.receivable_id)}{f'（银行流水号 {ref}）' if ref else ''}，已收 {fmt_yuan(m.received_fen)}。{detail}"))
            continue
        lines.append(t(ctx, f"- Flagged: {m.receivable_id}{f' (bank ref {ref})' if ref else ''} {fmt_yuan(m.received_fen)}: "
                            f"{m.status.value}. {m.detail}",
                       f"- 异常：{m.receivable_id}{f'（银行流水号 {ref}）' if ref else ''} {fmt_yuan(m.received_fen)}："
                       f"{m.status.value}。{m.detail}"))
    if promised:
        counts = {s: sum(1 for p in promised if p.status == s) for s in PromiseStatus}
        words = {PromiseStatus.AWAITED: ("awaited", "等待中"), PromiseStatus.RECEIVED: ("received", "已收到"),
                 PromiseStatus.LAPSED: ("lapsed", "已逾期"), PromiseStatus.SETTLED_OTHERWISE: ("settled another way", "已另行结清")}
        if biz:
            en = ", ".join(f"{n} {words[s][0]}" for s, n in counts.items() if n)
            cn = "，".join(f"{n} 笔{words[s][1]}" for s, n in counts.items() if n)
        else:
            en = ", ".join(f"{s.value} {n}" for s, n in counts.items() if n)
            cn = "，".join(f"{s.value} {n}" for s, n in counts.items() if n)
        lines.append(t(ctx, f"Promised early payments: {en}.", f"承诺的提前付款：{cn}。"))
        for p in [p for p in promised if p.status == PromiseStatus.LAPSED]:
            if biz:
                detail = ctx.reads.words(p.detail, ctx.lang) if ctx.reads is not None else p.detail
                for_day_en = f" for {_business_when(p.promised_day, ctx.day, 'en')}" if p.promised_day is not None else ""
                for_day_zh = _business_when(p.promised_day, ctx.day, "zh") if p.promised_day is not None else ""
                lines.append(t(ctx, f"- Lapsed: {inv(p.receivable_id)}, {fmt_yuan(p.expected_fen)} promised{for_day_en}. {detail}",
                               f"- 已逾期：{inv(p.receivable_id)}，承诺{for_day_zh}支付 {fmt_yuan(p.expected_fen)}。{detail}"))
                continue
            lines.append(t(ctx, f"- Lapsed: {p.receivable_id} ({p.counterparty_id}), {fmt_yuan(p.expected_fen)} promised for "
                                f"day {p.promised_day}. {p.detail}",
                           f"- 已逾期：{p.receivable_id}（{p.counterparty_id}），承诺第 {p.promised_day} 天支付 "
                           f"{fmt_yuan(p.expected_fen)}。{p.detail}"))
    if out:
        more = len(out) - MAX_OUTSTANDING
        if biz:
            def one(o: OutstandingReceivable) -> tuple[str, str]:
                days = abs(o.due_day - ctx.day)
                if o.past_due:
                    return (f"{inv(o.receivable_id)}, {days} day{'' if days == 1 else 's'} overdue", f"{inv(o.receivable_id)}，已逾期 {days} 天")
                return (f"{inv(o.receivable_id)}, due {_business_when(o.due_day, ctx.day, 'en')}",
                        f"{inv(o.receivable_id)}，{_business_when(o.due_day, ctx.day, 'zh')}到期")
            rows = [one(o) for o in out[:MAX_OUTSTANDING]]
            shown, shown_zh = "; ".join(x[0] for x in rows), "；".join(x[1] for x in rows)
        else:
            shown = "; ".join(f"{o.receivable_id} ({o.counterparty_id}) {fmt_yuan(o.face_fen)} due day {o.due_day}"
                              + (" past due" if o.past_due else "") for o in out[:MAX_OUTSTANDING])
            shown_zh = "；".join(f"{o.receivable_id}（{o.counterparty_id}）{fmt_yuan(o.face_fen)}，第 {o.due_day} 天到期"
                                + ("，已逾期" if o.past_due else "") for o in out[:MAX_OUTSTANDING])
        lines.append(t(ctx, f"Outstanding receivables, past due first: {shown}" + (f" and {more} more" if more > 0 else "") + ".",
                       f"未收应收款（逾期优先）：{shown_zh}" + (f"，另有 {more} 笔" if more > 0 else "") + "。"))
    elif scoped:
        lines.append(t(ctx, f"{who} has no receivable outstanding.", f"{who}目前没有未收的应收款。").replace("..", "."))
    else:
        lines.append(t(ctx, "No receivable is outstanding.", "没有未收的应收款。"))
    lines.append(t(ctx, "The audit chain verifies." if rep.chain_valid else "The audit chain does NOT verify.",
                   "审计链校验通过。" if rep.chain_valid else "审计链校验未通过。"))
    return Turn(intent=Intent.RECONCILE, reply="\n".join(lines))


# ---------------------------------------------------------------- RECORD_FACT


def record_fact(ctx: NlContext, slots: Slots) -> Turn:
    """The owner states a new bill, invoice, delay, EBITDA figure or similar. Chat reads and writes nothing for it: the
    books change only through the owner's own entry, so the answer is plain that it is not recorded, what is needed
    and that the forecast is unchanged. No operation, no pending plan."""
    amount = f" ({fmt_yuan(slots.amount_fen)})" if slots.amount_fen else ""
    return Turn(intent=Intent.RECORD_FACT, reply=t(
        ctx,
        f"I cannot record that{amount}: I do not enter bills, invoices, payment delays or figures from chat, and I have "
        f"not recorded or run anything. The forecast is unchanged and does not include it. To have it counted, enter it "
        f"through the books yourself (who it is with, the amount and the day it is due, or the new figure); I will "
        f"then forecast from it and tell you what changes.",
        f"这一项我无法记录{amount}：我不会根据聊天内容录入账单、发票、延迟付款或财务数字，也没有记录或执行任何操作。"
        f"预测保持不变，不包含这一项。若要计入，请您自行通过账本录入（对象、金额和到期日，或新的数字）；"
        f"录入后我会据此重新预测并告诉您有什么变化。"))


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
    # The one definition (app.covenants.ratios) on the projection's month points, as the verifier and capex read it.
    if (wd := worst_dscr(traj.months)) is not None and (d := ratios_for(wd)[0]) is not None:
        head = d.value - dscr_limit
        inside &= head >= 0
        lines.append(t(ctx, f"Lowest DSCR {d.text}× in month {wd.month}, against the {_x(dscr_limit)}× minimum "
                            f"({dscr_src}): headroom {_x(head)}×.",
                       f"最低 DSCR {d.text}×（第 {wd.month} 月），下限 {_x(dscr_limit)}×（{dscr_src}）：余量 {_x(head)}×。"))
    if (wl := worst_leverage(traj.months)) is not None and (lv := ratios_for(wl)[1]) is not None:
        head = lev_limit - lv.value
        inside &= head >= 0
        lines.append(t(ctx, f"Highest leverage {lv.text}× in month {wl.month}, against the {_x(lev_limit)}× maximum "
                            f"({lev_src}): headroom {_x(head)}×.",
                       f"最高杠杆 {lv.text}×（第 {wl.month} 月），上限 {_x(lev_limit)}×（{lev_src}）：余量 {_x(head)}×。"))
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


def _structure_label_zh(s: CapexStructure) -> str:
    """A structure's name in Chinese, from its typed fields (the module writes its label in English)."""
    rate = fmt_pct(Fraction(s.rate_bp, BP_DENOM)) if s.rate_bp is not None else ""
    if s.kind == "CASH_LINE":
        return "现金加信用额度"
    what = "定期贷款" if s.kind == "LOAN" else "租赁"
    return f"{s.term_months} 个月{what}" + (f"，{rate}" if rate else "")


def _limit(text: str | None) -> str:
    return (text or "").lstrip("≥≤<> ").strip()


def _violation_zh(v: Violation) -> str:
    """A structure's first failed check in Chinese, from the violation's code and its own figures."""
    code = v.code.value
    if code == "RESERVE_BREACH":
        on = f"第 {v.day} 天" if v.day is not None else "期间"
        i = v.inputs
        if all(k in i for k in ("available_above_reserve", "line_available", "price", "min_cash")):  # paying from cash + line
            return (f"在 {i['min_cash']} 的最低现金储备之上只有 {i['available_above_reserve']} 可用（现金加 {i['line_available']} "
                    f"的信用额度），不足以支付 {i['price']} 的价款；{on}现金降至 {v.observed}")
        return f"{on}现金降至 {v.observed}，低于 {_limit(v.limit)} 的最低现金储备"
    if code == "DSCR_BREACH":
        on = f"第 {v.month} 个月" if v.month is not None else "期间"
        return f"{on}的偿债覆盖率（DSCR）为 {v.observed}，低于 {_limit(v.limit)} 的下限"
    if code == "LEVERAGE_BREACH":
        on = f"第 {v.month} 个月" if v.month is not None else "期间"
        return f"{on}的杠杆率为 {v.observed}，高于 {_limit(v.limit)} 的上限"
    if code == "CLEAN_DOWN_BREACH":
        return "信用额度无法按要求按期清零"
    return f"未通过检查（{code}）"


def _structure_line(ctx: NlContext, r: CapexResult, s: CapexStructure) -> str:
    tag = (t(ctx, "SELECTED", "选定") if s.id == r.selected_id
           else t(ctx, "passes", "通过") if s.feasible else t(ctx, "fails", "不通过"))
    figures = ""
    if s.min_dscr is not None:
        figures = t(ctx, f"min DSCR {s.min_dscr.text}×", f"最低 DSCR {s.min_dscr.text}×")
        if s.leverage is not None:
            figures += t(ctx, f", leverage {s.leverage.text}×", f"，杠杆 {s.leverage.text}×")
        figures += t(ctx, "; ", "；")
    if s.hypothetical:
        tag += t(ctx, " (illustration only: not the facility's real term, never applied for)",
                 "（仅为示例：并非该额度的实际期限，不会据此申请）")
    if ctx.lang == "zh":
        why = f"：{_violation_zh(s.violations[0])}" if not s.feasible and s.violations else ""
        return f"- {_structure_label_zh(s)}：{figures}{tag}{why}"
    why = f": {s.violations[0].message}" if not s.feasible and s.violations else ""
    return f"- {s.label}: {figures}{tag}{why}"


def _capex_words_zh(req: CapexRequest, r: CapexResult) -> tuple[str, str]:
    """(the owner's-estimate note, the recommendation) in Chinese, from the result's typed fields; the module writes both
    in English."""
    note = (f"业主的估计，系统未观察到：自第 {req.uplift_start_month} 个月至第 {req.life_months} 个月，"
            f"每月经营现金流增加 {fmt_yuan(req.monthly_uplift_fen)}。")
    hurdle = fmt_pct(Fraction(req.hurdle_bp, BP_DENOM))
    payback = f"第 {r.payback_month} 个月回本" if r.payback_month is not None else "使用期内无法回本"
    lines = [("按业主的估计值得投资" if r.worth_doing else "按业主的估计不值得投资")
             + f"：按 {hurdle} 折现，净现值 {fmt_yuan(r.npv_fen)}，{payback}。"]
    sel = next((s for s in r.structures if s.id == r.selected_id), None)
    if sel is not None:
        monthly = f"（每月 {fmt_yuan(sel.monthly_payment_fen)}）" if sel.monthly_payment_fen else ""
        charges = f"，为 {fmt_yuan(sel.charges_total_fen)}" if sel.charges_total_fen is not None else ""
        lines.append(f"建议采用{_structure_label_zh(sel)}{monthly}：在通过检查的结构中，其融资费用合计（利息加费用，未折现）最低{charges}。")
        cheaper = [s for s in r.structures if not s.feasible and not s.hypothetical and s.charges_total_fen is not None
                   and sel.charges_total_fen is not None and s.charges_total_fen < sel.charges_total_fen and s.violations]
        for s in cheaper:
            lines.append(f"费用更低的{_structure_label_zh(s)}未通过：{_violation_zh(s.violations[0])}。")
        if r.required_tier.value == "TIER_2":
            lines.append("新增融资属于二级操作：由代理提出建议，由业主提交申请。")
    else:
        lines.append("没有任何结构通过全部检查，因此不建议融资购置。")
    return note, "".join(lines)


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
    note, recommendation = _capex_words_zh(req, r) if ctx.lang == "zh" else (r.estimate_note, r.recommendation)
    lines = [t(ctx, f"{req.label}, {fmt_yuan(req.price_fen)}: NPV {fmt_yuan(r.npv_fen)} at "
                    f"{fmt_pct(Fraction(req.hurdle_bp, BP_DENOM))}, {payback}. ",
               f"{req.label}，{fmt_yuan(req.price_fen)}：按 {fmt_pct(Fraction(req.hurdle_bp, BP_DENOM))} 折现，"
               f"净现值 {fmt_yuan(r.npv_fen)}，{payback}。") + note]
    lines += [_structure_line(ctx, r, s) for s in r.structures]
    lines.append(recommendation)
    lines.append(t(ctx, f"Computed on day {r.as_of_day}. Structures are ranked on the {CHARGES_BASIS}; rates are "
                        f"nominal annual rates, and the uplift is your estimate, not an observed figure.",
                   f"按第 {r.as_of_day} 天的账目计算。结构按融资费用合计（利息加费用，未折现）排序；利率为名义年利率；"
                   f"增收为您的估计，并非实测数据。"))
    lines.append(t(ctx, "Nothing was applied for: evaluating changes nothing here; you apply on the Capex screen.",
                   "尚未提交任何申请：评估不会改动任何内容；申请请由您在资本支出页面提交。"))
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


def borrower_file(ctx: NlContext, slots: Slots, text: str) -> Turn:
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
    try:
        bf = remember(build(ctx.store, facility_id=fid, amount_fen=slots.amount_fen,
                            use_of_proceeds="owner request in chat", day=ctx.day))
    except BorrowerFileError as exc:
        return Turn(intent=Intent.BORROWER_FILE, clear_pending=True, reply=t(
            ctx, f"I cannot prepare that file: {exc}.", f"无法准备该资料：{exc}。"))
    p = bf.provenance
    return Turn(intent=Intent.BORROWER_FILE, clear_pending=True, reply=t(
        ctx, f"Prepared the borrower file {bf.file_id} for {fid}, {fmt_yuan(slots.amount_fen)}: generated on day "
             f"{p.generated_day}, state version {p.state_version}, mandate version {p.mandate_version}, evidence hash "
             f"{p.evidence_hash[:12]}. Download it at /borrower-file/{bf.file_id}.html (also .docx). It is prepared, "
             f"not sent: nothing was queued and nothing needs approval; you submit it to the lender yourself.",
        f"已准备借款人资料 {bf.file_id}，对应 {fid}，{fmt_yuan(slots.amount_fen)}：第 {p.generated_day} 天生成，"
        f"状态版本 {p.state_version}，授权版本 {p.mandate_version}，证据哈希 {p.evidence_hash[:12]}。"
        f"请在 /borrower-file/{bf.file_id}.html 下载（另有 .docx）。资料仅准备，不发送：没有排队任何操作，"
        f"也无需批准；由您自行提交给贷方。"))


# ---------------------------------------------------------------- SHOW_DEAL (brief 03)


def show_deal(ctx: NlContext, slots: Slots) -> Turn:
    """Where a buyer's deal stands: the owner-confirmed contract beside the live books (`app.deals`). Read-only: no
    operation, no pending plan, nothing recorded."""
    from app.deals import deal_reply, deal_summary

    if not get_settings().features.contracts:
        return _off(ctx, Intent.SHOW_DEAL, "FEATURE_CONTRACTS")
    state = ctx.state()
    buyers = [c for c in state.counterparties if c.role == "BUYER"]
    cp = slots.counterparty_id if any(c.id == slots.counterparty_id for c in buyers) else None
    if cp is None:
        confirmed = sorted({r.counterparty_id for r in ctx.store.contract_records()
                            if r.kind.value == "BUYER_CONTRACT" and r.status.value == "CONFIRMED"})
        if len(confirmed) == 1:
            cp = confirmed[0]
        else:
            return ask(Intent.SHOW_DEAL, "counterparty_id", t(ctx, "Which buyer's deal?", "哪位买家的交易？"),
                       [(str(i), c.name, c.id) for i, c in enumerate(buyers, 1)], slots)
    reply = deal_reply(deal_summary(ctx.store, cp, ctx.day), ctx.lang)
    # a name that ends in a full stop ("Foshan Home Retail Co.") at the end of a sentence takes no second one
    return Turn(intent=Intent.SHOW_DEAL, reply=re.sub(r"(?<=[A-Za-z])\.\.(?=\s|$|[)）])", ".", reply))


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
    Capability(Intent.SHOW_DEAL, "show where a deal stands (the signed contract and the money)", "查看交易进展（合同与回款）",
               "where are we with Foshan?", "跟佛山的合同进展如何？",
               ("deal", "contract", "agreement", "signed", "clause"), ("合同", "协议", "进展", "条款")),
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
    "show_deal",
    "show_ratios",
]
