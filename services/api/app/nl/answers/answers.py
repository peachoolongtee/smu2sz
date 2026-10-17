"""Read-only answers to the owner's top 30 questions (research/owner-questions BASELINE section 4), in English and Chinese.

`answer(question, lang, ctx)` matches the question deterministically (the bank's wordings and their paraphrases are the
spec) to one of the 30, reads the metrics it needs (`app.nl.answers.metrics`) and writes one server sentence that leads
with the yes/no or the figure, then the reason, with the basis on its own line. It returns None for anything else (an
instruction, an offer, a question outside the 30), so the caller can route it or refuse it honestly.

Owner channel only: the answers carry protected values (the reserve, the caps, the limits). The caller sends only the
owner's own turns here. Nothing here writes: no store call other than reads, no executor, no verdict stored, no session
changed. No id or contract reference code appears in a sentence; buyers and facilities are said by name (en) or by what
they are (zh, where the books hold only English names).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from app.domain.models import FlowKind
from app.domain.money import bp, fmt_pct
from app.nl import lexicon as lx
from app.nl.answers import metrics as mx
from app.nl.answers.metrics import Event, Metric, Reading, money, ratio_x


@dataclass(frozen=True)
class AnswerReply:
    text: str
    metric_ids: list[str]
    figures: dict[str, str]
    basis: str
    question_id: str = ""
    lang: str = "en"
    extra: dict[str, Any] = field(default_factory=dict, compare=False)


# ================================================================ words


class W:
    """One answer's writer: the language, the reading, and the metrics and figures the sentence used."""

    def __init__(self, r: Reading, lang: str) -> None:
        self.r = r
        self.zh = lang == "zh"
        self.lang = "zh" if self.zh else "en"
        self.used: list[str] = []
        self.figures: dict[str, str] = {}

    def t(self, en: str, zh: str) -> str:
        return zh if self.zh else en

    def m(self, metric: Metric) -> Metric:
        if metric.id not in self.used:
            self.used.append(metric.id)
        return metric

    def fig(self, key: str, value: str) -> str:
        self.figures[key] = value
        return value

    # ------------------------------------------------------------ days, names

    def on(self, day: int | None) -> str:
        """"day 12" (with "in 8 days" after it once the clock has moved); "today" for today."""
        if day is None:
            return ""
        today = self.r.today
        n = day - today
        if n == 0:
            return self.t(f"day {day} (today)", f"第 {day} 天（今天）")
        if today == 0:
            return self.t(f"day {day}", f"第 {day} 天")
        rel = self.t(f"in {n} days" if n > 0 else f"{-n} days ago", f"{n} 天后" if n > 0 else f"{-n} 天前")
        return self.t(f"day {day} ({rel})", f"第 {day} 天（{rel}）")

    def day(self, day: int | None) -> str:
        """"day 12" alone, for inside parentheses."""
        return self.t(f"day {day}", f"第 {day} 天") if day is not None else ""

    def buyer(self, buyer_id: str | None) -> str:
        state = self.r.state
        c = next((x for x in state.counterparties if x.id == buyer_id), None)
        if c is None:
            return self.t("a customer", "一位客户")
        if not self.zh:
            return c.name
        alias = next((n for n in lx.counterparty_aliases(state).get(c.id, ()) if not n.isascii()), None)
        return alias or self.t(c.name, "该客户")

    def buyer_s(self, buyer_id: str | None) -> str:
        name = self.buyer(buyer_id)
        return name if self.zh else (name + "'" if name.endswith("s") else name + "'s")

    def facility(self, kind: str | None, name: str = "") -> str:
        words = {
            "CREDIT_LINE": ("the credit line", "银行信用额度"), "INVOICE_FINANCING": ("invoice financing", "发票融资"),
            "BUYER_EARLY_PAY": ("the buyer's early payment", "买家提前付款"),
            "GOV_GUARANTEED_LOAN": ("the government-guaranteed loan", "政府担保贷款"),
            "EQUIPMENT_TERM_LOAN": ("the equipment term loan", "设备定期贷款"), "EQUIPMENT_LEASE": ("the equipment lease", "设备租赁"),
            "BANK_ACCEPTANCE_BILL": ("bank acceptance bill discounting", "银票贴现"), "EQUITY": ("equity", "股权融资"),
        }
        en, zh = words.get(kind or "", (name or "a facility", "一项融资"))
        return self.t(en, zh)

    def outflow(self, e: Event) -> str:
        """An outflow by what it is: the books' own label in English, its kind in Chinese."""
        if not self.zh:
            return e.label if e.kind != FlowKind.DEBT_SERVICE.value else f"{e.label} payment"
        return {"PAYROLL": "工资", "SUPPLIER": "供应商付款", "OPERATING": "经营支出", "CAPEX": "设备款",
                "DEBT_SERVICE": loan_zh(e.label) + "还款"}.get(e.kind, "其他支出")

    def loan(self, label: str) -> str:
        return self.t(lower_first(label), loan_zh(label))

    def end(self, text: str) -> str:
        text = re.sub(r"\.\.(?=\s|$)", ".", text.strip())
        return re.sub(r"\s+", " ", text) if not self.zh else text.replace(" 。", "。")

    def reply(self, qid: str, text: str, basis: str | None = None) -> AnswerReply:
        basis = basis or self.basis()
        return AnswerReply(text=self.end(text), metric_ids=list(self.used), figures=dict(self.figures), basis=basis,
                           question_id=qid, lang=self.lang)

    def basis(self, what: str = "forecast") -> str:
        d = self.r.today
        if what == "mandate":
            return self.t(f"Your signed mandate (version {self.r.mandate.version}), day {d}",
                          f"您签署的授权（第 {self.r.mandate.version} 版），第 {d} 天")
        if what == "log":
            return self.t(f"The operations log and approvals queue, day {d}", f"操作日志与审批队列，第 {d} 天")
        if what == "hypothetical":
            return self.t(f"Hypothetical: conservative forecast of a copy of today's books, nothing changed, day {d}",
                          f"假设分析：对今日账目副本的保守预测，未做任何更改，第 {d} 天")
        if what == "books":
            return self.t(f"Today's books, day {d}", f"今日账目，第 {d} 天")
        return self.t(f"Conservative forecast, today's books, day {d}", f"基于今日账目的保守预测，第 {d} 天")


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if len(text) > 1 and text[0].isupper() and text[1].islower() else text


def loan_zh(label: str) -> str:
    return "现有设备贷款" if "equipment" in label.lower() else "现有贷款"


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def pct0(x: Fraction) -> str:
    return fmt_pct(x, 0)


def n_en(n: int, one: str, many: str) -> str:
    return f"one {one}" if n == 1 else f"{n} {many}"


# ================================================================ shared clauses


def plan_clause(w: W) -> str:
    """What FLOW's plan does for the breach: covers it (within the limits or with the owner's approval), only keeps cash above
    zero, or there is none."""
    p = w.m(mx.standing_plan(w.r))
    if p.value is None:
        return w.t("No committed funding can fix it, so it needs your decision.", "已承诺的融资都无法解决，需要您来决定。")
    cost = w.fig("plan_cost", p.detail["cost"] or "")
    if not p.detail["restores_reserve"]:
        return w.t(f"No committed funding restores the reserve; FLOW's best plan ({cost}) keeps cash above zero and needs your "
                   f"decision.", f"已承诺的融资无法恢复储备线；FLOW 的最佳方案（{cost}）可让现金保持在零以上，需要您来决定。")
    if p.detail["needs_owner"]:
        return w.t(f"FLOW's plan covers it for {cost}, with your approval", f"FLOW 的方案可用 {cost} 补上，需要您批准")
    return w.t(f"FLOW's plan covers it for {cost}", f"FLOW 的方案可用 {cost} 补上")


def covenant_sentence(w: W) -> str:
    c = w.m(mx.covenant_ratios(w.r))
    if c.detail["dscr"] is None and c.detail["lev"] is None:
        return ""
    return (w.t("Your loan covenants hold.", "您的贷款契约指标都满足。") if c.value
            else w.t("But a loan covenant breaks in the forecast.", "但预测中有贷款契约指标不达标。"))


def covenant_clause(w: W) -> str:
    c = w.m(mx.covenant_ratios(w.r))
    if c.detail["dscr"] is None and c.detail["lev"] is None:
        return ""
    return (w.t("and your loan covenants hold.", "且您的贷款契约指标都满足。") if c.value
            else w.t("but a loan covenant breaks in the forecast.", "但预测中有贷款契约指标不达标。"))


def joined(w: W, parts: list[str]) -> str:
    if not parts:
        return ""
    if w.zh:
        return "、".join(parts)
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


# ================================================================ liquidity


def a_safe(w: W, q: str) -> AnswerReply:
    r = w.r
    fb, low, need = w.m(mx.first_breach(r)), w.m(mx.lowest_point(r)), w.m(mx.funding_need(r))
    res = w.fig("reserve", money(r.floor))
    lo = w.fig("lowest", low.display)
    if fb.value is None:
        w.fig("answer", "yes")
        return w.reply("LIQ-01", w.t(
            f"Yes: on today's books cash stays at or above your {res} reserve for the next {r.horizon} days; the lowest point is "
            f"{lo} on {w.on(low.day)}. " + covenant_sentence(w),
            f"安全：按今日账目，未来 {r.horizon} 天现金都不低于您 {res} 的最低现金储备；最低点是{w.on(low.day)}的 {lo}。"
            + covenant_sentence(w)))
    w.fig("answer", "no")
    w.fig("first_breach_day", str(fb.value))
    short = w.fig("need", need.display)
    if fb.detail["today"]:
        lead = w.t(f"No: cash is already below your {res} reserve today ({money(r.state.cash_fen)}), and the lowest point ahead is "
                   f"{lo} on {w.on(low.day)}, {short} short of the reserve.",
                   f"不安全：今天现金（{money(r.state.cash_fen)}）已低于您 {res} 的最低现金储备，之后最低在{w.on(low.day)}降至 {lo}，"
                   f"比储备低 {short}。")
    else:
        lead = w.t(f"Not on today's books: without new funding, cash falls below your {res} reserve from {w.on(fb.value)}, lowest "
                   f"{lo} on {w.on(low.day)} ({short} short of the reserve).",
                   f"按今日账目并不安全：若不新增融资，现金将从{w.on(fb.value)}起低于您 {res} 的最低现金储备，最低在{w.on(low.day)}"
                   f"降至 {lo}（比储备低 {short}）。")
    plan = plan_clause(w)
    tail = (plan if plan.endswith((".", "。")) else
            plan + w.t(", ", "，") + covenant_clause(w) if covenant_clause(w) else plan + w.t(".", "。"))
    return w.reply("LIQ-01", lead + w.t(" ", "") + tail)


def a_runway(w: W, q: str) -> AnswerReply:
    r = w.r
    fb, neg = w.m(mx.first_breach(r)), w.m(mx.first_negative_cash_day(r))
    w.m(mx.runway_days(r))
    res = w.fig("reserve", money(r.floor))
    if neg.value is not None:
        w.fig("zero_day", str(neg.value))
        zero = w.t(f" Cash itself goes below zero on {w.on(neg.value)}, to {neg.detail['closing']}, unless you fund the gap.",
                   f"若不补上缺口，现金本身将在{w.on(neg.value)}跌破零，降至 {neg.detail['closing']}。")
    else:
        zero = w.t(" Cash itself stays above zero.", "现金本身始终在零以上。")
    if fb.value is None:
        return w.reply("LIQ-03", w.t(
            f"Longer than the forecast: cash stays at or above your {res} reserve for all {r.horizon} days.",
            f"超过预测期：未来 {r.horizon} 天现金都不低于您 {res} 的最低现金储备。"))
    if fb.detail["today"]:
        return w.reply("LIQ-03", w.t(f"None: cash is already below your {res} reserve today.",
                                     f"已经没有：今天现金已低于您 {res} 的最低现金储备。") + zero)
    n = w.fig("runway_days", str(fb.value - r.today))
    return w.reply("LIQ-03", w.t(
        f"{n} days to your reserve: cash falls to {fb.detail['closing']} on {w.on(fb.value)}, below your {res} reserve.",
        f"距离跌破储备线还有 {n} 天：现金将在{w.on(fb.value)}降至 {fb.detail['closing']}，低于您 {res} 的最低现金储备。") + zero)


def a_lowest(w: W, q: str) -> AnswerReply:
    r = w.r
    low = w.m(mx.lowest_point(r))
    lo = w.fig("lowest", low.display)
    w.fig("lowest_day", str(low.day))
    outs = [e for e in r.events(low.day or 0, low.day or 0) if e.amount_fen < 0]
    rec = next((e for e in r.events((low.day or 0) + 1, r.today + r.horizon) if e.amount_fen > 0), None)
    text = w.t(f"{lo} on {w.on(low.day)}", f"最低为{w.on(low.day)}的 {lo}")
    if outs:
        text += w.t(", the day of " + joined(w, [f"the {lower_first(w.outflow(e))} of {money(-e.amount_fen)}" for e in outs]),
                    "，当天要支付" + joined(w, [f"{w.outflow(e)} {money(-e.amount_fen)}" for e in outs]))
    if rec is not None:
        text += w.t(f"; it recovers on {w.on(rec.day)} when {w.buyer(rec.counterparty_id)} pays {money(rec.amount_fen)}.",
                    f"；{w.on(rec.day)}{w.buyer(rec.counterparty_id)}付款 {money(rec.amount_fen)} 后回升。")
    else:
        text += w.t(".", "。")
    if low.value is not None and low.value < r.floor:
        text += w.t(f" That is {money(r.floor - low.value)} below your {money(r.floor)} reserve.",
                    f"比您 {money(r.floor)} 的最低现金储备低 {money(r.floor - low.value)}。")
    return w.reply("LIQ-04", text)


def a_breach(w: W, q: str) -> AnswerReply:
    r = w.r
    fb = w.m(mx.first_breach(r))
    res = w.fig("reserve", money(r.floor))
    if fb.value is None:
        low = w.m(mx.lowest_point(r))
        return w.reply("LIQ-05", w.t(
            f"Never in the {r.horizon}-day forecast: cash stays at or above your {res} reserve; the closest it comes is {low.display} "
            f"on {w.on(low.day)}.",
            f"预测的 {r.horizon} 天内不会：现金始终不低于您 {res} 的最低现金储备；最接近的一天是{w.on(low.day)}，为 {low.display}。"))
    w.fig("first_breach_day", str(fb.value))
    closing, short = w.fig("first_breach_cash", fb.detail["closing"]), fb.detail["short"]
    if fb.detail["today"]:
        return w.reply("LIQ-05", w.t(f"Already: cash is {closing} today, {short} below your {res} reserve.",
                                     f"已经跌破：今天现金为 {closing}，比您 {res} 的最低现金储备低 {short}。"))
    return w.reply("LIQ-05", w.t(f"On {w.on(fb.value)}: cash closes at {closing}, {short} below your {res} reserve.",
                                 f"{w.on(fb.value)}：当天现金收于 {closing}，比您 {res} 的最低现金储备低 {short}。"))


def a_spend(w: W, q: str) -> AnswerReply:
    r = w.r
    head, low = w.m(mx.headroom_today(r)), w.m(mx.lowest_point(r))
    w.m(mx.funding_need(r))
    res = w.fig("reserve", money(r.floor))
    lowh = (low.value or 0) - r.floor
    if head.value <= 0:
        w.fig("safe_spend", money(0))
        return w.reply("LIQ-06", w.t(
            f"Nothing: cash is already {money(-head.value)} below your {res} reserve today." if head.value < 0
            else f"Nothing: cash is exactly at your {res} reserve today.",
            f"一分都不能花：今天现金已比您 {res} 的最低现金储备低 {money(-head.value)}。" if head.value < 0
            else f"一分都不能花：今天现金正好等于您 {res} 的最低现金储备。"))
    if lowh > 0:
        safe = w.fig("safe_spend", money(lowh))
        return w.reply("LIQ-06", w.t(
            f"Up to {safe}: that keeps cash at or above your {res} reserve through the lowest point, {low.display} on {w.on(low.day)}.",
            f"最多 {safe}：这样现金在最低点（{w.on(low.day)}的 {low.display}）也不会低于您 {res} 的最低现金储备。"))
    w.fig("safe_spend", money(0))
    hd = w.fig("headroom_today", head.display)
    if lowh == 0:
        return w.reply("LIQ-06", w.t(
            f"Nothing safely. {hd} is above your reserve today, but the forecast already sits exactly on your {res} reserve on "
            f"{w.on(low.day)}, so any spend takes you below it.",
            f"没有可安全动用的钱。今天现金比储备线高 {hd}，但预测显示{w.on(low.day)}现金正好落在您 {res} 的储备线上，任何支出都会跌破它。"))
    short = w.fig("need", money(-lowh))
    return w.reply("LIQ-06", w.t(
        f"Nothing safely. {hd} is above your reserve today, but the forecast is already {short} short of your {res} reserve on "
        f"{w.on(low.day)}, and any spend widens that gap.",
        f"没有可安全动用的钱。今天现金比储备线高 {hd}，但预测显示{w.on(low.day)}现金已比您 {res} 的最低现金储备低 {short}，"
        f"任何支出都会扩大缺口。"))


def a_payments(w: W, q: str) -> AnswerReply:
    r = w.r
    m = w.m(mx.upcoming_outflows(r))
    outs: list[Event] = m.value
    window = m.detail["window_days"]
    if not outs:
        return w.reply("LIQ-09", w.t(f"None: no payment is scheduled in the next {window} days.",
                                     f"没有：未来 {window} 天没有计划中的付款。"))
    total = w.fig("total", money(m.detail["total_fen"]))
    for i, e in enumerate(outs[:8]):
        w.fig(f"payment_{i + 1}", f"{money(-e.amount_fen)} day {e.day}")
    items = [w.t(f"{w.outflow(e)} {money(-e.amount_fen)} on {w.on(e.day)}", f"{w.on(e.day)}{w.outflow(e)} {money(-e.amount_fen)}")
             for e in outs[:8]]
    more = len(outs) - len(items)
    tail = w.t(f"; and {more} more", f"；另有 {more} 笔") if more > 0 else ""
    return w.reply("LIQ-09", w.t(
        f"{cap(n_en(len(outs), 'payment', 'payments'))} in the next {window} days, {total} in all: " + "; ".join(items) + tail + ".",
        f"未来 {window} 天共有 {len(outs)} 笔支出，合计 {total}：" + "；".join(items) + tail + "。"))


def a_payroll(w: W, q: str) -> AnswerReply:
    r = w.r
    pc = w.m(mx.payroll_cover(r))
    res = w.fig("reserve", money(r.floor))
    if pc.value is None:
        return w.reply("LIQ-10", w.t(
            f"No payroll is scheduled in the {r.horizon}-day forecast; the books hold payroll only as scheduled totals.",
            f"预测的 {r.horizon} 天内没有安排发工资；账目中的工资只记录计划总额。"))
    amt, day = w.fig("payroll", pc.display), pc.day
    w.fig("payroll_day", str(day))
    closing, before = pc.detail["closing_fen"], pc.detail["before_fen"]
    if closing >= r.floor:
        w.fig("answer", "yes")
        return w.reply("LIQ-10", w.t(
            f"Yes: the {money(before)} you will have covers the {amt} payroll on {w.on(day)}, and leaves {money(closing)}, at or above "
            f"your {res} reserve.",
            f"够：届时的 {money(before)} 足以支付{w.on(day)}的 {amt} 工资，发完后剩 {money(closing)}，不低于您 {res} 的最低现金储备。"))
    if closing >= 0:
        w.fig("answer", "yes")
        p = w.m(mx.standing_plan(r))
        fix = (w.t(f" FLOW's plan fixes that for {p.detail['cost']}.", f"FLOW 的方案可用 {p.detail['cost']} 解决。")
               if p.value is not None and p.detail["restores_reserve"] else "")
        return w.reply("LIQ-10", w.t(
            f"Yes: the {money(before)} you will have covers the {amt} payroll on {w.on(day)}, but it leaves {money(closing)}, "
            f"{money(r.floor - closing)} below your {res} reserve." + fix,
            f"够发：届时的 {money(before)} 足以支付{w.on(day)}的 {amt} 工资，但发完后只剩 {money(closing)}，比您 {res} 的最低现金储备低 "
            f"{money(r.floor - closing)}。" + fix))
    w.fig("answer", "no")
    return w.reply("LIQ-10", w.t(
        f"No, not on today's books: after the {amt} payroll on {w.on(day)}, cash would be {money(closing)}. ",
        f"按今日账目不够：{w.on(day)}支付 {amt} 工资后，现金将为 {money(closing)}。") + plan_clause(w)
        + ("" if plan_clause(w).endswith((".", "。")) else w.t(".", "。")))


def a_why(w: W, q: str) -> AnswerReply:
    r = w.r
    d = w.m(mx.cash_drivers(r))
    if d.value["outflows"] == [] and d.value["receipt"] is None:
        return w.reply("LIQ-14", w.t(
            f"You are not forecast to be short: cash stays at or above your {money(r.floor)} reserve for the next {r.horizon} days.",
            f"预测显示现金不会不够：未来 {r.horizon} 天现金都不低于您 {money(r.floor)} 的最低现金储备。"))
    outs: list[Event] = d.value["outflows"]
    rec: Event | None = d.value["receipt"]
    for i, e in enumerate(outs):
        w.fig(f"driver_{i + 1}", f"{money(-e.amount_fen)} day {e.day}")
    if rec is not None:
        w.fig("next_receipt", f"{money(rec.amount_fen)} day {rec.day}")
    due = joined(w, [w.t(f"{lower_first(w.outflow(e))} of {money(-e.amount_fen)} falls due on {w.on(e.day)}",
                         f"{w.on(e.day)}要支付{w.outflow(e)} {money(-e.amount_fen)}") for e in outs])
    if rec is not None:
        tail = w.t(f", before the next receipt: {w.buyer_s(rec.counterparty_id)} {money(rec.amount_fen)} lands only on {w.on(rec.day)}.",
                   f"，而下一笔收款——{w.buyer(rec.counterparty_id)}的 {money(rec.amount_fen)}——要到{w.on(rec.day)}才到账。")
    else:
        tail = w.t(", and no receipt is forecast to cover it.", "，而预测期内没有收款能弥补。")
    return w.reply("LIQ-14", w.t("Because " + due + tail, "因为" + due + tail))


def a_need(w: W, q: str) -> AnswerReply:
    r = w.r
    need = w.m(mx.funding_need(r))
    if not need.value:
        return w.reply("LIQ-15", w.t(f"Nothing: cash stays at or above your {money(r.floor)} reserve for the next {r.horizon} days.",
                                     f"不需要：未来 {r.horizon} 天现金都不低于您 {money(r.floor)} 的最低现金储备。"))
    gaps = w.m(mx.gap_windows(r)).value
    amt = w.fig("need", need.display)
    span = ""
    if gaps:
        g0 = gaps[0]
        span = w.t(f", needed from {w.on(g0['start'])} to {w.on(g0['end'])}", f"，缺口从{w.on(g0['start'])}持续到{w.on(g0['end'])}")
        if len(gaps) > 1:
            span += w.t(f" (and {len(gaps) - 1} later gap{'s' if len(gaps) > 2 else ''})", f"（之后另有 {len(gaps) - 1} 段缺口）")
    p = w.m(mx.standing_plan(r))
    if p.value is None:
        tail = w.t("; no committed funding covers it, so it needs your decision.", "；已承诺的融资无法覆盖，需要您来决定。")
    elif not p.detail["restores_reserve"]:
        tail = w.t(f"; no committed funding restores the reserve, and FLOW's best plan ({p.detail['cost']}) only keeps cash above zero.",
                   f"；已承诺的融资无法恢复储备线，FLOW 的最佳方案（{p.detail['cost']}）只能让现金保持在零以上。")
    else:
        tail = w.t(f"; FLOW's cheapest committed plan covers it for {w.fig('plan_cost', p.detail['cost'])}.",
                   f"；FLOW 用已承诺额度的最便宜方案可用 {w.fig('plan_cost', p.detail['cost'])} 补上。")
    return w.reply("LIQ-15", w.t(f"{amt}{span}{tail}", f"需要 {amt}{span}{tail}"))


# ================================================================ funding


def legs_words(w: W, legs: list[dict[str, Any]], *, with_cost: bool = True) -> list[str]:
    out: list[str] = []
    for leg in legs:
        amt, cost, kind = money(leg["amount_fen"]), leg["cost"], leg["operation_kind"]
        fac = w.facility(leg["facility_kind"], leg["facility"])
        lands = leg["lands_day"]
        when = (w.t("today", "今天") if lands is None or lands <= w.r.today else w.t(f"cash on {w.day(lands)}", f"{w.day(lands)}到账"))
        if kind == "DRAW_FACILITY":
            out.append(w.t(f"draw {amt} on {fac} {when}" + (f" ({cost})" if with_cost and cost else ""),
                           f"{when}从{fac}提款 {amt}" + (f"（{cost}）" if with_cost and cost else "")))
        elif kind == "SUBMIT_INVOICE_FOR_FINANCING":
            extra = ", ".join(x for x in (cost if with_cost else "", when) if x)
            out.append(w.t(f"finance {amt} of {w.buyer_s(leg['buyer_id'])} invoice ({extra})",
                           f"以{w.buyer(leg['buyer_id'])}的发票融资 {amt}（{'，'.join(x for x in (cost if with_cost else '', when) if x)}）"))
        elif kind == "REPAY_FACILITY":
            out.append(w.t(f"repay {amt} of {fac}", f"偿还{fac} {amt}"))
        elif kind == "APPLY_FOR_FACILITY":
            out.append(w.t(f"apply for {fac} ({amt})", f"申请{fac}（{amt}）"))
        else:
            out.append(w.t(f"use {fac} for {amt}", f"使用{fac} {amt}"))
    return out


def a_recommend(w: W, q: str) -> AnswerReply:
    r = w.r
    p = w.m(mx.standing_plan(r))
    fb = w.m(mx.first_breach(r))
    if p.value is None:
        a = r.action
        if a is not None and a.get("kind") == "FACILITY_REPAYABLE":
            repay = [{"operation_kind": x["operation_kind"], "facility_kind": mx.facility_kind(r.state, x["facility_id"]),
                      "facility": x["facility_name"], "buyer_id": None, "amount_fen": x["amount_fen"] or 0, "cost": None,
                      "lands_day": None} for x in a["legs"]]
            return w.reply("FUN-02", w.t("FLOW suggests you " + joined(w, legs_words(w, repay, with_cost=False))
                                         + ": your cash can afford it, and it stops the interest. Nothing has run yet.",
                                         "FLOW 建议" + joined(w, legs_words(w, repay, with_cost=False))
                                         + "：您的现金足以负担，且可停止计息。目前尚未执行任何操作。"))
        if fb.value is not None:
            return w.reply("FUN-02", w.t(
                f"Your cash goes below your {money(r.floor)} reserve on {w.on(fb.value)} and no committed funding fixes it: it needs "
                f"your decision, for example a new facility.",
                f"现金将在{w.on(fb.value)}低于您 {money(r.floor)} 的最低现金储备，而已承诺的融资都无法解决：需要您来决定，例如申请新的融资额度。"))
        return w.reply("FUN-02", w.t(
            f"Nothing needs doing about cash: it stays at or above your {money(r.floor)} reserve for the next {r.horizon} days.",
            f"现金方面无需采取行动：未来 {r.horizon} 天现金都不低于您 {money(r.floor)} 的最低现金储备。"))
    cost = w.fig("plan_cost", p.detail["cost"] or "")
    for i, leg in enumerate(p.value):
        w.fig(f"leg_{i + 1}", money(leg["amount_fen"]))
    legs = legs_words(w, p.value)
    auth = (w.t("and it needs your approval", "需要您批准") if p.detail["needs_owner"]
            else w.t("within your limits, so no approval is needed", "在您的授权内，无需批准"))
    lead = "" if p.detail["restores_reserve"] else w.t(
        "No committed funding restores your reserve; the best FLOW can do is: ", "已承诺的融资无法恢复储备线；FLOW 能做的最好安排是：")
    return w.reply("FUN-02", w.t(
        lead + cap(joined(w, legs)) if not lead else lead + joined(w, legs), lead + "，并".join(legs)) + w.t(
        f": {cost} in total, {auth}. Nothing has run yet.", f"：合计 {cost}，{auth}。目前尚未执行任何操作。"))


def a_plan_cost(w: W, q: str) -> AnswerReply:
    r = w.r
    p = w.m(mx.standing_plan(r))
    if p.value is None:
        fb = w.m(mx.first_breach(r))
        return w.reply("FUN-04", w.t(
            "There is no committed plan to price: no committed funding covers the gap." if fb.value is not None
            else "Nothing: no funding is needed on today's books.",
            "没有可报价的已承诺方案：已承诺的融资都无法覆盖缺口。" if fb.value is not None else "不需要花钱：按今日账目无需融资。"))
    cost = w.fig("plan_cost", p.detail["cost"] or "")
    unpriced = [leg for leg in p.value if not leg["cost"] and leg["operation_kind"] == "DRAW_FACILITY"]
    if unpriced and len([leg for leg in p.value if leg["cost"]]) == 1:
        priced = next(leg for leg in p.value if leg["cost"])
        names = joined(w, [w.facility(leg["facility_kind"], leg["facility"]) for leg in unpriced])
        return w.reply("FUN-04", w.t(
            f"{cost}, for {w.facility(priced['facility_kind'], priced['facility'])}. Interest on the {names.removeprefix('the ')} draw is "
            f"not included: it runs only while the balance stays drawn.",
            f"{cost}，用于{w.facility(priced['facility_kind'], priced['facility'])}。不含{names}提款的利息：利息只在余额未还期间产生。"))
    parts = [w.t(f"{leg['cost']} for {w.facility(leg['facility_kind'], leg['facility'])}",
                 f"{w.facility(leg['facility_kind'], leg['facility'])} {leg['cost']}") for leg in p.value if leg["cost"]]
    for i, leg in enumerate(p.value):
        if leg["cost"]:
            w.fig(f"leg_cost_{i + 1}", leg["cost"])
    return w.reply("FUN-04", w.t(f"{cost}: " + joined(w, parts) + ".", f"{cost}：其中" + "，".join(parts) + "。"))


# ================================================================ debt


def a_total_debt(w: W, q: str) -> AnswerReply:
    r = w.r
    total, pos = w.m(mx.total_debt(r)), w.m(mx.debt_positions(r))
    if not total.value:
        return w.reply("DEBT-01", w.t("None: the books hold no loan and nothing is drawn on your facilities.",
                                      "没有负债：账目中没有贷款，各融资额度也没有提款。"))
    amt = w.fig("total_debt", total.display)
    loans = [x for x in pos.value if x["kind"] == "LOAN"]
    facs = [x for x in pos.value if x["kind"] == "FACILITY"]
    if len(pos.value) == 1 and loans:
        x = loans[0]
        text = w.t(f"{amt}, all of it the {w.loan(x['label'])} ({money(x['monthly_fen'])} a month).",
                   f"{amt}，全部是{w.loan(x['label'])}（每月还 {money(x['monthly_fen'])}）。")
    else:
        parts = [w.t(f"the {w.loan(x['label'])} {money(x['principal_fen'])}", f"{w.loan(x['label'])} {money(x['principal_fen'])}")
                 for x in loans]
        parts += [w.t(f"{w.facility(x['facility_kind'], x['label'])} {money(x['principal_fen'])}"
                      + (f" ({x['lender']})" if x["lender"] else ""),
                      f"{w.facility(x['facility_kind'], x['label'])} {money(x['principal_fen'])}") for x in facs]
        text = w.t(f"{amt}: " + joined(w, parts) + ".", f"{amt}：" + "，".join(parts) + "。")
    if not facs:
        text += w.t(" Nothing is drawn on your credit line or invoice financing.", "信用额度和发票融资都没有提款。")
    unknown = [x for x in loans if x["lender"] is None]
    if unknown:
        text += w.t(f" The books do not record who lent the {joined(w, [w.loan(x['label']) for x in unknown])}.",
                    f"账目中没有记录{joined(w, [w.loan(x['label']) for x in unknown])}的贷款方。")
    return w.reply("DEBT-01", text, w.basis("books"))


def a_clear_debts(w: W, q: str) -> AnswerReply:
    r = w.r
    p, pos = w.m(mx.payoff_all(r)), w.m(mx.debt_positions(r))
    w.m(mx.total_debt(r))
    d = p.detail
    total = w.fig("total_debt", money(d["total_fen"]))
    res = w.fig("reserve", money(r.floor))
    if not d["total_fen"]:
        return w.reply("DEBT-04", w.t("There is nothing to clear: the books hold no loan and nothing is drawn.",
                                      "没有需要偿还的债务：账目中没有贷款，也没有提款。"))
    after = money(d["cash_after_fen"])
    low = (w.t(f" (lowest {money(d['low_fen'])} on {w.on(d['low_day'])})", f"（最低在{w.on(d['low_day'])}为 {money(d['low_fen'])}）")
           if d["low_fen"] is not None else "")
    if p.value:
        w.fig("answer", "yes")
        text = w.t(f"Yes: repaying all {total} today leaves {after}, and cash stays at or above your {res} reserve over the forecast{low}.",
                   f"可以：今天还清全部 {total} 后剩 {after}，预测期内现金都不低于您 {res} 的最低现金储备{low}。")
    else:
        w.fig("answer", "no")
        gap = money(r.floor - d["cash_after_fen"])
        head = money(d["headroom_fen"])
        text = w.t(f"No. Repaying all {total} today would leave cash at {after}, {gap} below your {res} reserve"
                   + (f", and the forecast would fall to {money(d['low_fen'])} on {w.on(d['low_day'])}"
                      if d["low_fen"] is not None and d["low_fen"] < d["cash_after_fen"] else "")
                   + (f"; you have {head} above your reserve today." if d["headroom_fen"] > 0
                      else f"; cash is already {money(-d['headroom_fen'])} below your reserve today." if d["headroom_fen"] < 0
                      else "; cash is exactly at your reserve today."),
                   f"不能。今天还清全部 {total} 后现金将为 {after}，比您 {res} 的最低现金储备低 {gap}"
                   + (f"，预测还会在{w.on(d['low_day'])}降至 {money(d['low_fen'])}"
                      if d["low_fen"] is not None and d["low_fen"] < d["cash_after_fen"] else "")
                   + (f"；您今天比储备线只多 {head}。" if d["headroom_fen"] > 0
                      else f"；今天现金已比储备线低 {money(-d['headroom_fen'])}。" if d["headroom_fen"] < 0 else "；今天现金正好等于储备线。"))
    for x in pos.value:
        if x["kind"] == "LOAN":
            sched = (w.t(f", next on {w.on(x['next_day'])}", f"，下一笔在{w.on(x['next_day'])}") if x["next_day"] is not None else "")
            text += w.t(f" The {w.loan(x['label'])} ({money(x['principal_fen'])}) is repaid on schedule, {money(x['monthly_fen'])} a "
                        f"month{sched}; the books do not say whether it can be repaid early.",
                        f"{w.loan(x['label'])}（{money(x['principal_fen'])}）按计划每月还 {money(x['monthly_fen'])}{sched}；账目没有记录它能否提前还清。")
        elif x["repayable_on_demand"]:
            text += w.t(f" The {money(x['principal_fen'])} on {w.facility(x['facility_kind'], x['label'])} can be repaid now.",
                        f"{w.facility(x['facility_kind'], x['label'])}的 {money(x['principal_fen'])} 可以随时偿还。")
        else:
            text += w.t(f" The {money(x['principal_fen'])} of {w.facility(x['facility_kind'], x['label'])} is repaid when the invoice is paid.",
                        f"{w.facility(x['facility_kind'], x['label'])}的 {money(x['principal_fen'])} 在发票回款时偿还。")
    return w.reply("DEBT-04", text, w.basis("hypothetical"))


def a_borrow_more(w: W, q: str) -> AnswerReply:
    r = w.r
    u = w.m(mx.undrawn_committed(r))
    later = u.detail["not_applied"]
    rows = u.value
    if not rows:
        text = w.t("Nothing more on committed terms: every committed facility is fully drawn.", "按已承诺的额度已无法再借：已承诺的额度都已用完。")
    else:
        total = w.fig("undrawn_total", u.display)
        parts = []
        for x in rows:
            w.fig(f"undrawn_{x['facility_kind'].lower()}", money(x["available_fen"]))
            when = (w.t("cash the same day", "当天到账") if x["days"] == 0 else w.t(f"cash in {x['days']} days", f"{x['days']} 天到账"))
            parts.append(w.t(f"{w.facility(x['facility_kind'], x['name'])} {money(x['available_fen'])} ({x['all_in']} a year all-in, {when})",
                             f"{w.facility(x['facility_kind'], x['name'])} {money(x['available_fen'])}（综合年化 {x['all_in']}，{when}）"))
        text = w.t(f"{total} committed and unused: " + "; ".join(parts) + ".", f"已承诺但未使用的额度共 {total}：" + "；".join(parts) + "。")
        cap_ = w.m(mx.invoice_financing_capacity(r))
        if cap_.value and any(x["facility_kind"] == "INVOICE_FINANCING" for x in rows):
            w.fig("invoice_capacity", cap_.display)
            text += w.t(f" Invoice financing advances {cap_.detail['advance_rate']} of an invoice, so {cap_.display} on "
                        f"{w.buyer_s(cap_.detail['buyer_id'])} open invoice.",
                        f"发票融资按发票金额的 {cap_.detail['advance_rate']} 放款，{w.buyer(cap_.detail['buyer_id'])}的未结发票可融 {cap_.display}。")
    full = u.detail["fully_drawn"]
    if full:
        text += w.t(" Fully drawn: " + joined(w, [w.facility(x["facility_kind"], x["name"]) for x in full]) + ".",
                    "已用完：" + "、".join(w.facility(x["facility_kind"], x["name"]) for x in full) + "。")
    if later:
        names = [w.t(f"{w.facility(x['facility_kind'], x['name'])} {money(x['limit_fen'])}",
                     f"{w.facility(x['facility_kind'], x['name'])} {money(x['limit_fen'])}") for x in later]
        text += w.t(" Not applied for yet, so counted as zero: " + joined(w, names) + ".",
                    "尚未申请、因此按零计算：" + "、".join(names) + "。")
    return w.reply("DEBT-06", text, w.basis("books"))


def a_next_loan_payment(w: W, q: str) -> AnswerReply:
    r = w.r
    n = w.m(mx.next_debt_payment(r))
    if n.value is None:
        return w.reply("DEBT-08", w.t(f"No loan payment is scheduled in the {r.horizon}-day forecast.",
                                      f"预测的 {r.horizon} 天内没有贷款还款。"), w.basis("books"))
    amt = w.fig("next_payment", n.display)
    w.fig("next_payment_day", str(n.day))
    interest = n.detail["interest_fen"]
    tail = w.t(f" ({money(interest)} of it interest)", f"（其中利息 {money(interest)}）") if interest else ""
    return w.reply("DEBT-08", w.t(f"{amt} on the {w.loan(n.detail['label'])} on {w.on(n.day)}{tail}.",
                                  f"{w.on(n.day)}，{w.loan(n.detail['label'])}还款 {amt}{tail}。"), w.basis("books"))


def a_debt_cost(w: W, q: str) -> AnswerReply:
    r = w.r
    ds, fees = w.m(mx.debt_service_month(r)), w.m(mx.projected_interest_fees(r))
    pos = w.m(mx.debt_positions(r))
    if not ds.value:
        return w.reply("DEBT-03", w.t("Nothing: no debt service falls due in the first month of the forecast.",
                                      "不需要：预测的第一个月没有还本付息。"))
    amt = w.fig("debt_service_month", ds.display)
    loans = [x for x in pos.value if x["kind"] == "LOAN"]
    what = ""
    if loans:
        x = loans[0]
        rate = fmt_pct(bp(x["rate_bp"]))
        what = w.t(f": the {w.loan(x['label'])}'s scheduled payment, at the {rate} rate the books record",
                   f"：即{w.loan(x['label'])}的计划还款，账目记录的利率为 {rate}")
    f = w.fig("interest_fees", fees.display)
    return w.reply("DEBT-03", w.t(f"{amt} a month of debt service{what}. Interest and fees on your facilities over the forecast: {f}.",
                                  f"每月还本付息 {amt}{what}。预测期内各融资额度的利息和费用合计 {f}。"))


# ================================================================ customers


def a_owes_most(w: W, q: str) -> AnswerReply:
    r = w.r
    rows = w.m(mx.receivables_by_customer(r)).value
    top = rows[0] if rows else None
    if top is None or not top["owed_fen"]:
        return w.reply("CUS-01", w.t("Nobody owes you anything right now.", "目前没有客户欠您款项。"), w.basis("books"))
    name = w.buyer(top["buyer_id"])
    w.fig("buyer", name)
    owed = w.fig("owed", money(top["owed_fen"]))
    n = top["invoices"]
    due = (w.t(f", due on {w.on(top['next_due_day'])}", f"，{w.on(top['next_due_day'])}到期") if n == 1 else "")
    share = (w.t("; that is everything you are owed", "；这就是您应收的全部款项") if top["share"] == 1
             else w.t(f", {pct0(top['share'])} of what you are owed", f"，占您应收账款的 {pct0(top['share'])}"))
    text = w.t(f"{name}: {owed} on {n_en(n, 'invoice', 'invoices')}{due}{share}.", f"{name}：{n} 张发票共 {owed}{due}{share}。")
    if top["overdue_fen"]:
        text += w.t(f" {money(top['overdue_fen'])} of it is overdue.", f"其中 {money(top['overdue_fen'])} 已逾期。")
    zero = [w.buyer(x["buyer_id"]) for x in rows if not x["owed_fen"]]
    if zero:
        text += w.t(f" {joined(w, zero)} {'owes' if len(zero) == 1 else 'owe'} nothing.", f"{'、'.join(zero)}目前不欠款。")
    return w.reply("CUS-01", text, w.basis("books"))


def a_late(w: W, q: str) -> AnswerReply:
    r = w.r
    od = w.m(mx.overdue(r))
    if not od.value:
        nx = w.m(mx.next_receipt(r))
        tail = (w.t(f"; the next payment due is {w.buyer_s(nx.detail['buyer_id'])} {nx.display} on {w.on(nx.day)}.",
                    f"；下一笔到期的是{w.buyer(nx.detail['buyer_id'])}的 {nx.display}，{w.on(nx.day)}到期。")
                if nx.value is not None else w.t(" and nothing else is due.", "，也没有其他到期款项。"))
        w.fig("overdue", money(0))
        return w.reply("CUS-03", w.t("Nobody. Nothing is overdue" + tail, "没有。目前没有逾期款项" + tail), w.basis("books"))
    first = od.value[0]
    w.fig("overdue", od.display)
    name = w.fig("buyer", w.buyer(first["buyer_id"]))
    text = w.t(f"{name}: {money(first['face_fen'])}, {n_en(first['days_late'], 'day', 'days')} late (due on {w.day(first['due_day'])}). "
               f"Chase them first.",
               f"{name}：{money(first['face_fen'])}，已逾期 {first['days_late']} 天（{w.day(first['due_day'])}到期），请先催收。")
    for x in od.value[1:4]:
        text += w.t(f" Then {w.buyer(x['buyer_id'])}: {money(x['face_fen'])}, {n_en(x['days_late'], 'day', 'days')} late.",
                    f"其次是{w.buyer(x['buyer_id'])}：{money(x['face_fen'])}，已逾期 {x['days_late']} 天。")
    text += w.t(" I have not contacted anyone.", "我没有联系任何人。")
    return w.reply("CUS-03", text, w.basis("books"))


def a_dependence(w: W, q: str) -> AnswerReply:
    r = w.r
    rows = w.m(mx.receivables_by_customer(r)).value
    rec = w.m(mx.recurring_billing(r)).value
    named = lx.find_counterparty(q, r.state)
    top = next((x for x in rows if x["buyer_id"] in named), rows[0] if rows else None)
    if top is None or not top["owed_fen"]:
        return w.reply("CUS-05", w.t("Nobody owes you anything right now, so no customer holds a share of your receivables.",
                                     "目前没有客户欠款，因此没有客户占有应收账款的份额。"), w.basis("books"))
    total = sum(x["owed_fen"] for x in rows)
    name, share = w.buyer(top["buyer_id"]), w.fig("share", pct0(top["share"]))
    text = w.t(f"{share}: {name} accounts for {share} of what you are owed ({money(top['owed_fen'])} of {money(total)})",
               f"{share}：{name}占您应收账款的 {share}（{money(total)} 中的 {money(top['owed_fen'])}）")
    per_day = {x["buyer_id"]: Fraction(x["face_fen"], x["every_days"]) for x in rec if x["every_days"]}
    mine = [x for x in rec if x["buyer_id"] == top["buyer_id"]]
    if per_day and mine:
        rshare = w.fig("recurring_share", pct0(per_day.get(top["buyer_id"], Fraction(0)) / sum(per_day.values())))
        x = mine[0]
        text += w.t(f" and {rshare} of your recurring invoicing ({money(x['face_fen'])} every {x['every_days']} days).",
                    f"，占定期开票的 {rshare}（每 {x['every_days']} 天 {money(x['face_fen'])}）。")
    else:
        text += w.t(".", "。")
    return w.reply("CUS-05", text, w.basis("books"))


def _days_asked(q: str) -> int | None:
    found = lx.days(q)
    if found:
        return found[0].value
    low = lx.norm(q)
    for pat, n in ((r"\bhalf a month\b|半个月", 15), (r"\b(?:a|one) month\b|一个月|1个月", 30), (r"\btwo months\b|两个月|2个月", 60),
                   (r"\btwo weeks\b|两周|两个星期", 14), (r"\b(?:a|one) week\b|一周|一个星期", 7)):
        if re.search(pat, low):
            return n
    return None


def _buyer_asked(r: Reading, q: str) -> str | None:
    named = lx.find_counterparty(q, r.state)
    if named:
        return named[0]
    holders = sorted({x.counterparty_id for x in mx.unpaid(r.state)})
    return holders[0] if len(holders) == 1 else None


def a_late_what_if(w: W, q: str) -> AnswerReply | None:
    r = w.r
    n, buyer = _days_asked(q), _buyer_asked(r, q)
    if n is None or buyer is None:
        return None
    name = w.buyer(buyer)
    li = w.m(mx.late_payment_impact(r, buyer, n))
    if li.value is None:
        late = li.detail.get("already_late_fen") or 0
        if late:
            return w.reply("CUS-07", w.t(
                f"{name} has no invoice still to come: the {money(late)} it owes is already overdue, and the forecast no longer counts on it. "
                f"I have not changed anything.",
                f"{name}没有尚未到期的发票：所欠的 {money(late)} 已经逾期，预测已不再计入。我没有更改任何内容。"), w.basis("hypothetical"))
        return w.reply("CUS-07", w.t(f"{name} has no unpaid invoice, so there is nothing to be late. I have not changed anything.",
                                     f"{name}目前没有未付发票，因此不存在延迟付款。我没有更改任何内容。"), w.basis("hypothetical"))
    d = li.detail
    w.m(mx.lowest_point(r))
    w.fig("lowest", li.display)
    w.fig("lowest_day", str(li.day))
    w.fig("need", money(d["need_fen"]))
    inv = money(d["invoice_fen"])
    head = w.t(f"If {name} pays its {inv} invoice {n} days late ({w.day(d['new_due_day'])} instead of {w.day(d['due_day'])}), ",
               f"如果{name}的 {inv} 发票晚 {n} 天付款（{w.day(d['new_due_day'])}而不是{w.day(d['due_day'])}），")
    if (li.value, li.day) != (d["base_low_fen"], d["base_low_day"]):
        low = w.t(f"your lowest cash moves from {money(d['base_low_fen'])} on {w.on(d['base_low_day'])} to {li.display} on {w.on(li.day)}",
                  f"现金最低点将从{w.on(d['base_low_day'])}的 {money(d['base_low_fen'])} 变为{w.on(li.day)}的 {li.display}")
    else:
        low = w.t(f"your lowest cash stays {li.display} on {w.on(li.day)}", f"现金最低点仍是{w.on(li.day)}的 {li.display}")
    parts = [low]
    if d["last_below_day"] is not None and d["last_below_day"] != d["base_last_below_day"]:
        parts.append(w.t(f"but cash stays below your {money(r.floor)} reserve until {w.on(d['last_below_day'])}"
                         + (f" instead of {w.on(d['base_last_below_day'])}" if d["base_last_below_day"] is not None else ""),
                         f"但现金低于您 {money(r.floor)} 储备线的时间将持续到{w.on(d['last_below_day'])}"
                         + (f"，而不是{w.on(d['base_last_below_day'])}" if d["base_last_below_day"] is not None else "")))
    if not d["need_fen"]:
        parts.append(w.t(f"and cash stays at or above your {money(r.floor)} reserve throughout", f"现金始终不低于您 {money(r.floor)} 的储备线"))
    if d["need_fen"] != d["base_need_fen"]:
        parts.append(w.t(f"and the amount needed to stay at your reserve goes from {money(d['base_need_fen'])} to {money(d['need_fen'])}",
                         f"维持储备线所需的资金从 {money(d['base_need_fen'])} 变为 {money(d['need_fen'])}"))
    text = head + (", " if not w.zh else "，").join(parts) + w.t(".", "。")
    base = w.m(mx.standing_plan(r))
    if d["need_fen"]:
        if d["plan_ok"] and d["plan_cost"]:
            w.fig("plan_cost", d["plan_cost"])
            was = (w.t(f" (today's plan: {base.detail['cost']})", f"（当前方案为 {base.detail['cost']}）") if base.value is not None else "")
            text += w.t(f" FLOW's cheapest committed plan would then cost {d['plan_cost']}{was}.",
                        f"届时 FLOW 用已承诺额度的最便宜方案需要 {d['plan_cost']}{was}。")
        else:
            text += w.t(" No committed plan would cover that; it would need your decision.", "已承诺的融资无法覆盖，需要您来决定。")
    if d["already_late_fen"]:
        text += w.t(f" {name} also has {money(d['already_late_fen'])} overdue, which the forecast no longer counts.",
                    f"{name}另有 {money(d['already_late_fen'])} 已逾期，预测已不再计入。")
    text += w.t(" This is a projection on a copy of your books; nothing was changed.", "这是对账目副本的预测，没有更改任何内容。")
    return w.reply("CUS-07", text, w.basis("hypothetical"))


def a_early_pay(w: W, q: str) -> AnswerReply | None:
    r = w.r
    be = w.m(mx.break_even(r))
    if be.value is None:
        return None
    buyer = _buyer_asked(r, q)
    offer = next((f for f in r.state.facilities if f.kind.value == "BUYER_EARLY_PAY" and (buyer is None or f.lender_id == buyer)), None)
    asked = lx.rates(q)
    rate_bp = asked[0].value if asked else (offer.rate_bp if offer is not None else None)
    if rate_bp is None:
        return None
    rate, b = w.fig("rate", fmt_pct(bp(rate_bp))), w.fig("break_even", be.display)
    full = None
    if offer is not None and rate_bp == offer.rate_bp:
        rows = w.m(mx.alternatives_priced(r)).value
        full = next((x for x in rows if x["key"] == "full_discount"), None)
    p = w.m(mx.standing_plan(r))
    if Fraction(rate_bp, 10_000) > be.value:
        w.fig("answer", "no")
        text = w.t(f"No. {rate} is above your {b} break-even, so your own funding is cheaper",
                   f"不划算。{rate} 高于您 {b} 的盈亏平衡点，自己融资更便宜")
        if full is not None and full["cost_fen"] is not None and p.value is not None:
            fc = w.fig("full_discount_cost", money(full["cost_fen"]))
            text += w.t(f": discounting the whole invoice costs {fc}, against {p.detail['cost']} for FLOW's plan.",
                        f"：整张发票贴现要花 {fc}，而 FLOW 的方案只需 {p.detail['cost']}。")
        elif p.value is None and w.m(mx.first_breach(r)).value is None:
            text += w.t(", and you have no funding need on today's books.", "，而且按今日账目您并没有融资需求。")
        else:
            text += w.t(".", "。")
    else:
        w.fig("answer", "yes")
        text = w.t(f"Yes on price: {rate} is at or below your {b} break-even, so it is cheaper than your own marginal funding.",
                   f"按价格划算：{rate} 不高于您 {b} 的盈亏平衡点，比您自己的边际融资更便宜。")
        if p.value is None and w.m(mx.first_breach(r)).value is None:
            text += w.t(" But you have no funding need on today's books, so the discount buys nothing.",
                        "但按今日账目您并没有融资需求，这笔折扣换不来任何好处。")
    return w.reply("CUS-08", text)


# ================================================================ deals and approvals


def approval_words(w: W, x: dict[str, Any]) -> str:
    kind, amt = x.get("kind") or "", x.get("amount_fen")
    fac = w.facility(x.get("facility_kind"))
    a = money(amt) if isinstance(amt, int) else ""
    words = {
        "DRAW_FACILITY": (f"a {a} draw on {fac}", f"从{fac}提款 {a}"),
        "SUBMIT_INVOICE_FOR_FINANCING": (f"invoice financing of {a}", f"发票融资 {a}"),
        "APPLY_FOR_FACILITY": (f"an application for {fac}" + (f" ({a})" if a else ""), f"申请{fac}" + (f"（{a}）" if a else "")),
        "REPAY_FACILITY": (f"a {a} repayment of {fac}", f"偿还{fac} {a}"),
        "ACCEPT_OFFER": ("accepting a customer's offer", "接受一位客户的报价"),
        "RECORD_COMMITMENT": ("recording an agreement with a customer", "记录与客户的协议"),
        "RECEIVE_PAYMENT": (f"a reported receipt of {a}", f"一笔被报告的收款 {a}"),
        "COMMIT_PURCHASE": ("an equipment purchase", "一笔设备采购"),
    }
    en, zh = words.get(kind, ("one other operation", "另一项操作"))
    return w.t(en, zh)


def a_waiting(w: W, q: str) -> AnswerReply:
    r = w.r
    ww = w.m(mx.what_waits(r))
    fb, p = w.m(mx.first_breach(r)), w.m(mx.standing_plan(r))
    ap = w.m(mx.approvals_pending(r)).value
    od = w.m(mx.overdue(r)).value
    items: list[str] = []
    if fb.value is not None:
        when = (w.t("your cash is already below your reserve", "现金已低于您的储备线") if fb.detail["today"]
                else w.t(f"your cash goes below your reserve on {w.on(fb.value)}", f"现金将在{w.on(fb.value)}低于您的储备线"))
        if p.value is not None:
            auth = w.t("within your limits", "在您的授权内") if not p.detail["needs_owner"] else w.t("it needs your approval", "需要您批准")
            if not p.detail["restores_reserve"]:
                auth += w.t(", and it only keeps cash above zero", "，且只能让现金保持在零以上")
            amount = money(p.detail["receive_fen"]) if p.detail["receive_fen"] else ""
            items.append(w.t(f"{when}, and FLOW's {amount} plan ({p.detail['cost']}, {auth}) waits for your go-ahead",
                             f"{when}，FLOW 的 {amount} 方案（{p.detail['cost']}，{auth}）正等您同意"))
        else:
            items.append(w.t(f"{when} and no committed funding fixes it: that needs your decision",
                             f"{when}，而已承诺的融资都无法解决，需要您来决定"))
        w.fig("first_breach_day", str(fb.value))
    if ap:
        items.append(w.t(f"{n_en(len(ap), 'approval waits', 'approvals wait')} for you: " + joined(w, [approval_words(w, x) for x in ap]),
                         f"{len(ap)} 项操作等您审批：" + "、".join(approval_words(w, x) for x in ap)))
    for x in od[:2]:
        items.append(w.t(f"{w.buyer_s(x['buyer_id'])} {money(x['face_fen'])} is {n_en(x['days_late'], 'day', 'days')} late",
                         f"{w.buyer(x['buyer_id'])}的 {money(x['face_fen'])} 已逾期 {x['days_late']} 天"))
    deals = ww.value["deal_rows"]
    if deals:
        items.append(w.t(f"{n_en(deals, 'customer item needs', 'customer items need')} you on the Deals page",
                         f"“交易”页面有 {deals} 项客户事项需要您处理"))
    w.fig("items", str(len(items)))
    w.fig("approvals_pending", str(len(ap)))
    if not items:
        text = w.t("Nothing is waiting for you: no plan to approve, no approval pending, nothing overdue.",
                   "目前没有需要您处理的事项：没有待批准的方案、没有待审批的操作，也没有逾期款项。")
        return w.reply("DEAL-01", text)
    count = ["One thing", "Two things", "Three things", "Four things"][len(items) - 1] if len(items) <= 4 else f"{len(items)} things"
    text = w.t(f"{count}: " + "; ".join(items) + ".", f"有 {len(items)} 件事：" + "；".join(items) + "。")
    neg = []
    if not ap:
        neg.append(w.t("no approvals are pending", "没有待审批的操作"))
    if ww.detail["queue_read"] and not deals:
        neg.append(w.t("no deal needs you", "也没有需要您处理的交易"))
    if neg:
        text += w.t(" " + cap(" and ".join(neg)) + ".", "，".join(neg) + "。")
    return w.reply("DEAL-01", text, w.basis("log") if not fb.value else None)


def a_approvals(w: W, q: str) -> AnswerReply:
    ap = w.m(mx.approvals_pending(w.r)).value
    w.fig("approvals_pending", str(len(ap)))
    if not ap:
        w.fig("answer", "no")
        return w.reply("DEAL-02", w.t("No. Nothing is waiting for your approval.", "没有。目前没有待审批的操作。"), w.basis("log"))
    w.fig("answer", "yes")
    return w.reply("DEAL-02", w.t(
        f"Yes, {len(ap)}: " + "; ".join(approval_words(w, x) for x in ap) + ". Approve or reject each on the Approvals page.",
        f"有，共 {len(ap)} 项：" + "；".join(approval_words(w, x) for x in ap) + "。请在审批页面逐项批准或拒绝。"), w.basis("log"))


def a_terms_cost(w: W, q: str) -> AnswerReply | None:
    r = w.r
    found = lx.days(q)
    if not found:
        return None
    n = found[0].value
    buyer = _buyer_asked(r, q)
    name = w.buyer(buyer)
    c = w.m(mx.terms_extension_cost(r, buyer, n))
    if c.value is None:
        return w.reply("DEAL-09", w.t(
            f"I could not price {n}-day terms for {name} on today's books: the what-if needs a recurring invoice of theirs and an open, "
            f"unfinanced invoice to apply them to, and the books hold none. Nothing was changed.",
            f"按今日账目，我无法为{name}测算 {n} 天账期的成本：假设分析需要该客户的定期发票和一张未融资的未结发票，而账目中没有。没有更改任何内容。"),
            w.basis("hypothetical"))
    d = c.detail
    h = r.mandate.forward_concession_horizon_days
    span = w.t(f"the next {h // 365 * 12} months" if h % 365 == 0 else f"the next {h} days",
               f"未来 {h // 365 * 12} 个月" if h % 365 == 0 else f"未来 {h} 天")
    total = w.fig("concession_cost", c.display)
    capf = money(int(d["cap_fen"] or 0))
    text = w.t(f"{total} in forward concessions over {span} of {name} invoices, " + (f"above your {capf} limit" if d["over_cap"]
                                                                                   else f"within your {capf} limit"),
               f"{span}{name}的发票共产生远期让步 {total}，" + (f"超过您 {capf} 的上限" if d["over_cap"] else f"在您 {capf} 的上限内"))
    if d["breach_day"] is not None:
        w.fig("breach_day", str(d["breach_day"]))
        text += w.t(f", and cash would fall below your reserve on {w.on(d['breach_day'])}",
                    f"，且现金将在{w.on(d['breach_day'])}低于您的储备线")
    outcome = d["outcome"]
    if outcome == "ACCEPT":
        text += w.t("; FLOW could accept it within your limits.", "；FLOW 可在您的授权内接受。")
    elif outcome == "NEEDS_OWNER_APPROVAL":
        text += w.t("; it would need your approval.", "；需要您批准。")
    elif d["counters"]:
        text += w.t("; FLOW would counter rather than accept.", "；FLOW 会提出还价，而不是直接接受。")
    else:
        text += w.t("; FLOW would decline it.", "；FLOW 会拒绝。")
    text += w.t(" Nothing was booked or sent.", "没有记账，也没有发送任何内容。")
    return w.reply("DEAL-09", text, w.basis("hypothetical"))


# ================================================================ covenants, capex


def a_covenants(w: W, q: str) -> AnswerReply:
    c = w.m(mx.covenant_ratios(w.r))
    d = c.detail
    if d["dscr"] is None and d["lev"] is None:
        return w.reply("COV-01", w.t("There is nothing to test: no projected month carries debt service or debt.",
                                     "没有可检验的指标：预测期内没有债务或还本付息。"))
    parts_en, parts_zh = [], []
    if d["dscr"] is not None:
        dv, dl, dh = w.fig("dscr", ratio_x(d["dscr"]) + "×"), ratio_x(d["dscr_limit"]) + "×", ratio_x(d["dscr_head"]) + "×"
        parts_en.append(f"lowest DSCR {dv} against the {dl} minimum ({dh} headroom)")
        parts_zh.append(f"偿债覆盖率最低 {dv}，下限 {dl}（余量 {dh}）")
    if d["lev"] is not None:
        lv, ll, lh = w.fig("leverage", ratio_x(d["lev"]) + "×"), ratio_x(d["lev_limit"]) + "×", ratio_x(d["lev_head"]) + "×"
        parts_en.append(f"highest leverage {lv} against the {ll} maximum ({lh} headroom)")
        parts_zh.append(f"杠杆率最高 {lv}，上限 {ll}（余量 {lh}）")
    cd = (w.t("; the credit line's clean-down is at risk", "；信用额度的清零要求有风险") if d["clean_down_alert"]
          else w.t("; no clean-down alert", "；信用额度清零要求没有预警"))
    w.fig("answer", "yes" if c.value else "no")
    if c.value:
        text = w.t("Yes. Every projected month is inside the covenants: " + " and ".join(parts_en) + cd + ".",
                   "满足。预测的每个月都在契约范围内：" + "；".join(parts_zh) + cd + "。")
    else:
        text = w.t("No. A projected month breaches a covenant: " + " and ".join(parts_en) + cd + ".",
                   "不满足。有预测月份违反契约：" + "；".join(parts_zh) + cd + "。")
    return w.reply("COV-01", text)


def a_breakpoints(w: W, q: str) -> AnswerReply:
    b = w.m(mx.covenant_breakpoints(w.r))
    w.m(mx.ebitda_month(w.r))
    v, d = b.value, b.detail
    ds_max, debt_max = v["debt_service_max_fen"], v["debt_max_fen"]
    dsm, dbm = w.fig("debt_service_max", money(ds_max)), w.fig("debt_max", money(debt_max))
    dsn, dbn = money(d["debt_service_now_fen"]), money(d["debt_now_fen"])
    p1 = pct0(Fraction(d["debt_service_now_fen"], ds_max)) if ds_max else "—"
    p2 = pct0(Fraction(d["debt_now_fen"], debt_max)) if debt_max else "—"
    return w.reply("COV-05", w.t(
        f"Monthly debt service above {dsm} (now {dsn}) breaks the DSCR covenant; total debt above {dbm} (now {dbn}) breaks the "
        f"leverage covenant. You are at {p1} and {p2} of those limits, on monthly EBITDA of {money(w.r.state.monthly_ebitda_fen)}.",
        f"每月还本付息超过 {dsm}（目前 {dsn}）会违反偿债覆盖率契约；总负债超过 {dbm}（目前 {dbn}）会违反杠杆率契约。目前分别处于上限的 "
        f"{p1} 和 {p2}，按每月息税折旧摊销前利润 {money(w.r.state.monthly_ebitda_fen)} 计算。"))


def a_capex(w: W, q: str) -> AnswerReply:
    from app.capex import CapexRequest

    r = w.r
    cx = w.m(mx.capex_case(r))
    req = CapexRequest()
    basis = w.t(f"The capex case on file ({req.label}), today's books, day {r.today}",
                f"已录入的设备方案（{money(req.price_fen)}），今日账目，第 {r.today} 天")
    if cx.detail.get("disabled"):
        return w.reply("CAP-01", w.t("Capex evaluation is switched off here, so I cannot say.", "这里未开启设备投资评估，因此无法回答。"), basis)
    if cx.value is None and not cx.detail:
        return w.reply("CAP-01", w.t("I could not project the books just now, so I cannot evaluate the purchase.",
                                     "暂时无法预测账目，无法评估这笔购置。"), basis)
    d = cx.detail
    price = w.fig("price", money(d["price_fen"]))
    npv = money(d["npv_fen"])
    worth = (w.t(f"the machine is worth doing on your estimate (NPV {npv} at {d['hurdle']}", f"按您的估计这台设备值得投资（按 {d['hurdle']} 折现，净现值 {npv}")
             if d["npv_fen"] > 0 else
             w.t(f"the machine is not worth doing on your estimate (NPV {npv} at {d['hurdle']}", f"按您的估计这台设备不值得投资（按 {d['hurdle']} 折现，净现值 {npv}"))
    worth += (w.t(f", payback in month {d['payback_month']})", f"，第 {d['payback_month']} 个月回本）") if d["payback_month"] is not None
              else w.t(", no payback within its life)", "，使用期内无法回本）"))
    sel = d["selected"]
    if d["cash_feasible"] and sel is not None and sel.kind == "CASH_LINE":
        w.fig("answer", "yes")
        return w.reply("CAP-01", w.t(f"Yes, from cash: paying the {price} from cash and the credit line keeps your reserve, and {worth}.",
                                     f"买得起，可直接用现金：用现金和信用额度支付 {price} 仍能守住储备线，且{worth}。"), basis)
    if sel is None:
        w.fig("answer", "no")
        return w.reply("CAP-01", w.t(f"No: neither cash nor any financing structure passes your limits for the {price} machine; {worth}.",
                                     f"买不起：{price} 的设备无论用现金还是任何融资结构都无法满足您的限额；{worth}。"), basis)
    w.fig("answer", "yes")
    rate = fmt_pct(bp(sel.rate_bp)) if sel.rate_bp is not None else ""
    monthly = money(sel.monthly_payment_fen) if sel.monthly_payment_fen else ""
    w.fig("structure_monthly", monthly)
    kind_en = {"LEASE": "lease", "LOAN": "term loan"}.get(sel.kind, "financing")
    kind_zh = {"LEASE": "设备租赁", "LOAN": "定期贷款"}.get(sel.kind, "融资")
    what = w.t(f"the {sel.term_months}-month {kind_en} ({monthly} a month, {rate})", f"{sel.term_months} 个月{kind_zh}（每月 {monthly}，年利率 {rate}）")
    return w.reply("CAP-01", w.t(
        f"Only financed. Paying the {price} from cash and the credit line would break your {money(r.floor)} reserve. "
        f"{cap(what)} passes every limit, and {worth}. Nothing was applied for: you apply on the Capex screen.",
        f"只能融资购买。用现金和信用额度支付 {price} 会跌破您 {money(r.floor)} 的最低现金储备。{what}满足所有限额，且{worth}。"
        f"尚未提交任何申请：申请请由您在资本支出页面提交。"), basis)


# ================================================================ activity and mandate


def op_words(w: W, kind: str, amount: int, op: Any) -> str:
    a = money(abs(amount)) if amount else ""
    fac = w.facility(mx.facility_kind(w.r.state, getattr(op, "facility_id", None)))
    buyer = mx.buyer_of(w.r.books.state, getattr(op, "receivable_id", None))
    words = {
        "DRAW_FACILITY": (f"drew {a} on {fac}", f"从{fac}提款 {a}"),
        "SUBMIT_INVOICE_FOR_FINANCING": (f"financed {a} of {w.buyer_s(buyer)} invoice", f"以{w.buyer(buyer)}的发票融资 {a}"),
        "REPAY_FACILITY": (f"repaid {a} on {fac}", f"偿还{fac} {a}"),
        "RECEIVE_PAYMENT": (f"recorded a receipt of {a}", f"记录一笔收款 {a}"),
        "ADVANCE_CLOCK": (f"moved the clock forward to day {getattr(op, 'to_day', '') or w.r.today}", "将日期向前推进"),
        "ACCEPT_OFFER": ("accepted a customer's offer", "接受了一位客户的报价"),
        "COUNTER_OFFER": ("sent a counter-offer", "发出了还价"),
        "REJECT_OFFER": ("declined an offer", "拒绝了一份报价"),
        "RECORD_COMMITMENT": ("recorded an agreement", "记录了一项协议"),
        "APPLY_FOR_FACILITY": (f"applied for {fac}", f"申请了{fac}"),
    }
    en, zh = words.get(kind, ("ran one other operation", "执行了另一项操作"))
    return w.t(en, zh)


def a_activity(w: W, q: str) -> AnswerReply:
    a = w.m(mx.activity_since(w.r))
    d = a.detail
    chain = (w.t("the log's chain verifies", "日志的哈希链校验通过") if d["chain_valid"]
             else w.t("the log's chain does NOT verify", "日志的哈希链校验未通过"))
    w.fig("operations", str(a.value))
    w.fig("refused", str(d["refused"]))
    if not a.value and not d["refused"] and not d["queued"]:
        return w.reply("ACT-01", w.t(
            f"Nothing yet: no operation has run in the last {mx.RECENT_DAYS} days, nothing was refused"
            + ("" if d["security_events"] else ", no security event was logged") + f", and {chain}.",
            f"还没有：最近 {mx.RECENT_DAYS} 天没有执行任何操作，也没有被拒绝的操作"
            + ("" if d["security_events"] else "，没有安全事件") + f"，{chain}。"), w.basis("log"))
    ran = [op_words(w, kind, amount, op) for kind, amount, op in d["ran"]]
    text = w.t(f"{cap(n_en(a.value, 'operation', 'operations'))} in the last {mx.RECENT_DAYS} days: " + "; ".join(ran) + ".",
               f"最近 {mx.RECENT_DAYS} 天执行了 {a.value} 项操作：" + "；".join(ran) + "。") if ran else ""
    text += w.t(f" {d['refused']} refused, {d['queued']} waiting for your approval, {d['security_events']} security events; {chain}.",
                f"被拒绝 {d['refused']} 项，待您审批 {d['queued']} 项，安全事件 {d['security_events']} 起；{chain}。")
    return w.reply("ACT-01", text, w.basis("log"))


def _mandate_problem(w: W, d: dict[str, Any]) -> str:
    codes = d["problems"]
    if "MANDATE_REVOKED" in codes:
        return w.t("revoked", "已被撤销")
    if "MANDATE_EXPIRED" in codes:
        return w.t(f"expired on day {d['expires_day']}", f"已于第 {d['expires_day']} 天到期")
    return w.t("not validly signed", "签名无效")


def a_autonomy(w: W, q: str) -> AnswerReply:
    m = w.m(mx.mandate_limits_and_validity(w.r))
    d = m.detail
    if not m.value:
        return w.reply("MAN-01", w.t(f"Nothing on its own right now: your mandate is {_mandate_problem(w, d)}, so FLOW only proposes and "
                                     f"you decide.", f"目前不能自主做任何事：您的授权{_mandate_problem(w, d)}，因此 FLOW 只提建议，由您决定。"),
                       w.basis("mandate"))
    apr, res, disc = w.fig("max_apr", d["max_apr"]), w.fig("reserve", money(d["reserve_fen"])), w.fig("max_discount", d["max_discount"])
    capf, t2 = w.fig("concession_cap", money(d["concession_cap_fen"])), w.fig("tier2", money(d["tier2_fen"]))
    new = (w.t("a new facility", "新的融资额度") if d["allow_new_borrowing"] else w.t("new borrowing (which your mandate does not allow)", "新增借款（您的授权不允许）"))
    return w.reply("MAN-01", w.t(
        f"Inside your signed mandate (valid to day {d['expires_day']}), FLOW may use your committed facilities at up to {apr} a year "
        f"while keeping {res} in cash, give early-payment discounts up to {disc} and future concessions up to {capf} in all. "
        f"A single commitment above {t2}, {new} or a rate above {apr} needs you; guarantees, collateral, equity and changes to "
        f"the mandate are never FLOW's to do.",
        f"在您签署的授权内（有效至第 {d['expires_day']} 天），FLOW 可以使用已承诺的融资额度，年化成本不超过 {apr}，同时保持现金不低于 "
        f"{res}；可给予不超过 {disc} 的提前付款折扣，远期让步合计不超过 {capf}。单笔超过 {t2} 的承诺、{new}或年化成本超过 {apr} 的融资需要您批准；"
        f"个人担保、抵押、股权和修改授权，FLOW 永远不能做。"), w.basis("mandate"))


def a_needs_approval(w: W, q: str) -> AnswerReply:
    m = w.m(mx.mandate_limits_and_validity(w.r))
    d = m.detail
    ap = w.m(mx.approvals_pending(w.r)).value
    apr, res, disc = w.fig("max_apr", d["max_apr"]), w.fig("reserve", money(d["reserve_fen"])), w.fig("max_discount", d["max_discount"])
    capf, t2 = w.fig("concession_cap", money(d["concession_cap_fen"])), w.fig("tier2", money(d["tier2_fen"]))
    lead = "" if m.value else w.t(f"Everything, for now: your mandate is {_mandate_problem(w, d)}. Once it is valid again: ",
                                  f"目前所有事项都需要：您的授权{_mandate_problem(w, d)}。授权恢复有效后：")
    now = (w.t(f" Right now {n_en(len(ap), 'approval waits', 'approvals wait')} for you.", f"目前有 {len(ap)} 项操作等您审批。") if ap
           else w.t(" Right now nothing is waiting for your approval.", "目前没有待您审批的操作。"))
    return w.reply("MAN-02", lead + w.t(
        f"A single commitment above {t2}, funding that costs more than {apr} a year, applying for a new facility or buying "
        f"equipment, longer payment terms or any promise to a customer beyond an early-payment discount, and a receipt someone "
        f"else reports. Offers that would break your {res} reserve, the {capf} concession cap, the {disc} discount limit or a "
        f"covenant are declined or countered, not sent to you; guarantees, collateral, equity and mandate changes are never "
        f"FLOW's to do.",
        f"单笔超过 {t2} 的承诺、年化成本超过 {apr} 的融资、申请新的融资额度或购买设备、延长账期或在提前付款折扣之外对客户作出的任何承诺，"
        f"以及他人报告的收款。会跌破您 {res} 储备线、超过 {capf} 让步上限、超过 {disc} 折扣上限或违反契约的报价，FLOW 会拒绝或还价，不会交给您；"
        f"个人担保、抵押、股权和修改授权，FLOW 永远不能做。") + now, w.basis("mandate"))


# ================================================================ the matcher


def _p(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.IGNORECASE)


Handler = Callable[[W, str], AnswerReply | None]

# In order: the first question whose pattern matches answers. Specific questions (a what-if, a named offer, a breakpoint) come
# before the general ones whose words they share ("pays late" before "who is late", "debt service can we carry" before "debt
# service", "payroll" before "is cash enough").
QUESTIONS: tuple[tuple[str, re.Pattern[str], Handler], ...] = (
    ("CUS-07", _p(r"\b(?:what if|what happens if|what would happen if|suppose|if)\b.{0,60}\b(?:pays?|paid|payment|invoice|receipt|money)"
                  r"\b.{0,40}\b(?:late|slips?|slipped|delayed|later|overdue)\b",
                  r"\b(?:what if|what happens if|suppose)\b.{0,60}\b(?:slips?|delayed?)\b",
                  r"(?:如果|假如|要是|万一).{0,20}(?:晚|延迟|推迟|拖延).{0,12}(?:付|到|回款|收款|付款)",
                  r"(?:款|付款|回款|发票).{0,6}(?:晚|延迟|推迟).{0,10}(?:会怎|怎么样|会如何|影响)"), a_late_what_if),
    ("DEAL-09", _p(r"\b(?:cost|costs|cost us|price|expensive)\b.{0,60}\b(?:give|giving|extend(?:ing)?|offer(?:ing)?|move|moving|terms)\b.{0,40}"
                   r"\b\d{1,3}[- ]?days?\b",
                   r"\b(?:give|giving|extend(?:ing)?|move|moving)\b.{0,40}\b\d{1,3}[- ]?days?\b.{0,40}\b(?:cost|costs|price)\b",
                   r"(?:账期|延到|延长到|给).{0,12}\d{1,3}\s*天.{0,16}(?:多少钱|成本|代价|花多少|要花)",
                   r"\d{1,3}\s*天账期.{0,12}(?:多少钱|成本|代价|花)"), a_terms_cost),
    ("CUS-08", _p(r"\b(?:should we|shall we|do we|would you|is it|is the|is that|is this|worth)\b.{0,60}\b(?:early[- ]pay(?:ment)?|pay(?:s|ing)? "
                  r"early|early settlement)\b",
                  r"\bearly[- ]pay(?:ment)?\b.{0,60}\b(?:worth it|a good deal|worth taking|should we)\b",
                  r"提前(?:付款|结算|还款折扣).{0,16}(?:划算|值不值|值得|要不要|该不该|能不能接受)",
                  r"(?:接受|要不要接受).{0,10}提前付款.{0,8}(?:值|划算|吗)"), a_early_pay),
    ("COV-05", _p(r"\bwhat (?:would|could|will|might) (?:break|breach|trip|violate)\b.{0,30}\bcovenants?\b",
                  r"\bhow much (?:more )?(?:debt service|debt)\b.{0,30}\b(?:can we|could we)\b.{0,10}\b(?:carry|afford|take on|handle)\b",
                  r"\bcovenant\b.{0,20}\b(?:break ?points?|limits? on debt)\b",
                  r"什么情况.{0,8}违反.{0,4}契约", r"会让我们违反", r"还本付息.{0,6}最多", r"最多.{0,6}还本付息"), a_breakpoints),
    ("COV-01", _p(r"\b(?:are we|is the company|we)\b.{0,20}\b(?:inside|within|compliant|in compliance|meeting|breaching|in breach)\b.{0,30}"
                  r"\bcovenants?\b",
                  r"\bcovenants?\b.{0,20}\b(?:ok|okay|fine|met|hold|holding|passing|compliant)\b",
                  r"\b(?:do we|are we) (?:meet|pass|comply with)\b.{0,20}\bcovenants?\b",
                  r"(?:满足|符合|达标|违反).{0,10}(?:贷款)?契约.{0,4}(?:吗|么|没有)", r"契约.{0,8}(?:达标|满足|符合).{0,4}(?:吗|么)",
                  r"契约指标都达标"), a_covenants),
    ("LIQ-10", _p(r"\b(?:make|meet|cover|covered|afford|pay)\b.{0,20}\b(?:payroll|wages|salaries)\b",
                  r"\b(?:payroll|wages|salaries)\b.{0,20}\b(?:covered|ok|okay|safe|enough|afford)\b",
                  r"\benough\b.{0,20}\b(?:payroll|wages|salaries)\b",
                  r"(?:工资|薪水|薪资|发薪).{0,10}(?:够|发得出|发不出|能发|付得起)", r"(?:够|能).{0,6}(?:发工资|发薪)"), a_payroll),
    ("LIQ-14", _p(r"\bwhy\b.{0,40}\b(?:short|gap|run out|running out|low|tight|below|shortfall)\b",
                  r"\bwhat(?:'s| is)? (?:causing|driving|behind)\b.{0,30}\b(?:gap|short|shortfall|cash)\b",
                  r"为什么.{0,12}(?:不够|缺钱|紧张|短缺|跌破|缺口)", r"(?:缺口|不够|缺钱).{0,10}(?:怎么造成|是怎么|原因|为什么|怎么来的)"), a_why),
    ("FUN-04", _p(r"\b(?:what(?:'s| is| would be)?|how much)\b.{0,30}\b(?:cost|costs|price)\b.{0,20}\b(?:of )?(?:the |flow'?s |your )?"
                  r"(?:plan|fix(?:ing)? (?:the|this) gap|fund(?:ing)? (?:the|this) gap|clos(?:e|ing) (?:the|this) gap)\b",
                  r"\bhow much (?:would|does|will) (?:flow'?s |the |your )?plan cost\b", r"\bplan\b.{0,10}\bcost\b\?",
                  r"(?:方案|补上缺口|补缺口|填补缺口|补上这个缺口).{0,10}(?:多少钱|成本|花多少|费用)"), a_plan_cost),
    ("FUN-02", _p(r"\bwhat (?:does flow|do you|would you|would flow|does the system) (?:recommend|suggest|advise)\b",
                  r"\bwhat should (?:i|we) do\b", r"\b(?:your|flow'?s) (?:recommendation|advice|suggestion)\b",
                  r"\bwhat do you recommend\b",
                  r"(?:建议|推荐).{0,12}(?:怎么|如何|什么)", r"你建议", r"我(?:们)?(?:该|应该)怎么(?:做|办)"), a_recommend),
    ("DEBT-06", _p(r"\bhow much (?:more )?(?:can|could) we borrow\b", r"\bborrowing (?:headroom|capacity|room|power)\b", r"\bundrawn\b",
                   r"\bunused\b.{0,20}\b(?:facilit|credit|lines?)\b", r"\bhow much credit\b.{0,20}\bleft\b",
                   r"还能借", r"能借多少", r"额度还剩", r"还剩多少额度", r"授信.{0,6}剩", r"可用额度"), a_borrow_more),
    ("LIQ-15", _p(r"\bhow (?:much|big)\b.{0,40}\b(?:raise|short(?:fall)?|gap)\b", r"\bhow much (?:money |funding |cash )?do we need\b",
                  r"(?:融|筹)多少", r"需要融", r"缺口(?:有)?多大", r"缺多少", r"差多少钱", r"缺口是多少"), a_need),
    ("LIQ-03", _p(r"\brunway\b", r"\bhow long\b.{0,30}\b(?:cash|money)\b.{0,20}\blast\b", r"\bhow many days\b.{0,30}\b(?:run out|last)\b",
                  r"\bwhen (?:do|will) we run out\b",
                  r"能撑多久", r"撑几天", r"撑多久", r"跑道", r"还能撑"), a_runway),
    ("LIQ-04", _p(r"\blowest\b.{0,30}\bcash\b", r"\bcash\b.{0,30}\blowest\b", r"\bworst cash\b", r"\bworst (?:point|day)\b",
                  r"\bhow low\b.{0,20}\bcash\b",
                  r"最低.{0,6}(?:多少|哪天|哪一天|降到|是多少)", r"哪天.{0,4}现金最紧张", r"现金最紧张"), a_lowest),
    ("LIQ-06", _p(r"\bhow much (?:money )?can (?:i|we) spend\b", r"\bwhat can (?:i|we) spend\b", r"\bfree cash\b", r"\bspare cash\b",
                  r"\bspend\b.{0,30}\bwithout\b", r"\bhow much (?:money )?can (?:i|we) (?:use|take out)\b",
                  r"(?:能花|能动用|可以花|可动用|能用|可以动用)多少", r"最多能花"), a_spend),
    ("LIQ-05", _p(r"\b(?:drop|fall|go|dip|slip)s? below\b.{0,30}\breserve\b", r"\bbreach\b.{0,20}\breserve\b",
                  r"\breserve\b.{0,20}\bbreach", r"\bbelow (?:the |our |my )?(?:minimum )?(?:cash )?reserve\b",
                  r"跌破.{0,8}(?:储备|最低现金)", r"低于.{0,6}储备"), a_breach),
    ("DEBT-08", _p(r"\bnext\b.{0,20}\b(?:loan|debt|bank)\b.{0,10}\b(?:payment|repayment|instal?ment)\b",
                   r"\bwhen\b.{0,20}\b(?:next )?pay (?:the|our) (?:bank|lender|loan)\b", r"\bnext (?:loan|debt) (?:payment|repayment)\b",
                   r"(?:下一笔|下次|下一次).{0,6}(?:还款|还贷|贷款)", r"还贷是哪天", r"哪天还贷"), a_next_loan_payment),
    ("LIQ-09", _p(r"\b(?:payments?|bills?|outflows?|expenses?|outgoings?)\b.{0,30}\b(?:coming up|due|ahead|soon|upcoming)\b",
                  r"\bwhat(?:'s| is)? going out\b", r"\bupcoming (?:payments?|bills?|outflows?)\b",
                  r"大额支出", r"要付哪些", r"哪些支出", r"近期.{0,4}(?:要付|付款|支出)", r"接下来.{0,6}(?:支出|付款|要付)"), a_payments),
    ("DEBT-04", _p(r"\b(?:can|could) we\b.{0,20}\b(?:clear|pay off|pay back|repay|settle)\b.{0,20}\b(?:debts?|loans?|borrowing)\b",
                   r"(?:能|可以|能不能).{0,6}(?:还清|清偿|偿清|还完|结清)"), a_clear_debts),
    ("DEBT-03", _p(r"\bdebt service\b", r"\b(?:debt|loans?)\b.{0,30}\b(?:each|a|per|every) month\b", r"\bmonthly\b.{0,20}\b(?:debt|loan|repayments?)\b",
                   r"每(?:个)?月.{0,8}(?:还本付息|还款|还贷|要付多少|付多少)", r"还本付息多少", r"月供"), a_debt_cost),
    ("DEBT-01", _p(r"\bhow much (?:debt|do we owe)\b", r"\btotal debt\b", r"\bwhat do we owe\b", r"\bhow much\b.{0,20}\bowe (?:the )?(?:banks?|lenders?)\b",
                   r"\bhow much (?:are we|is the company) in debt\b",
                   r"我们.{0,4}欠多少", r"欠(?:银行|贷款方|金融机构).{0,2}多少",r"欠多少债", r"负债多少", r"总负债", r"债务(?:总额|有多少|是多少)"), a_total_debt),
    ("CUS-01", _p(r"\bwho owes\b", r"\bwhich (?:customer|client|buyer)s? owes?\b", r"\bowes us the most\b",
                  r"谁欠", r"哪个客户欠", r"欠款最多", r"欠我们最多"), a_owes_most),
    ("CUS-03", _p(r"\bwho(?:'s| is)? (?:paying |pays )?late\b", r"\b(?:customers?|clients?|buyers?|invoices?)\b.{0,20}\b(?:overdue|past due|late)\b",
                  r"\bwho should (?:i|we) chase\b", r"\bwho (?:do|should) (?:i|we) chase\b", r"\banything overdue\b", r"\bwhat(?:'s| is) overdue\b",
                  r"拖欠", r"逾期", r"催谁", r"先催"), a_late),
    ("CUS-05", _p(r"\bdependen(?:t|ce|cy)\b", r"\bconcentrat", r"\bshare of (?:our )?(?:receivables|revenue|sales|invoic)",
                  r"\brel(?:y|iant) on\b.{0,20}\b(?:one|a single|single)\b",
                  r"依赖", r"占.{0,8}(?:比例|比重|多少)", r"集中度"), a_dependence),
    ("MAN-02", _p(r"\bwhat (?:needs|requires|will need) my (?:approval|sign[- ]?off|ok|okay|permission)\b",
                  r"\bwhen do you (?:have|need) to ask me\b", r"\bask me first\b", r"\bwhat do i (?:have|need) to approve\b",
                  r"哪些(?:事情|事|操作|情况).{0,6}需要我批准", r"什么情况下.{0,10}(?:问我|批准|请示)", r"必须先问我"), a_needs_approval),
    ("DEAL-02", _p(r"\bapprovals? (?:pending|waiting|queued|outstanding)\b", r"\bpending approvals?\b", r"\banything (?:for me )?to approve\b",
                   r"\bany(?:thing)? (?:waiting )?for (?:my )?approval\b", r"\bawaiting (?:my )?approval\b",
                   r"待审批", r"有需要我批准的", r"有.{0,6}要我批准.{0,4}(?:吗|么)", r"待批准", r"等我批准"), a_approvals),
    ("DEAL-01", _p(r"\bwhat(?:'s| is)? waiting (?:for|on) me\b", r"\bwhat needs my (?:decision|attention)\b",
                   r"\banything (?:for me )?to (?:look at|do|decide)\b", r"\bwhat do i need to (?:do|decide)\b", r"\bmy to-?do\b",
                   r"在等我", r"需要我(?:决定|处理)", r"等我处理"), a_waiting),
    ("LIQ-01", _p(r"\bare we (?:safe|ok(?:ay)?|fine|alright|all right)\b", r"\b(?:is|are) (?:our|the) cash(?: position)? (?:safe|ok(?:ay)?|fine|enough)\b",
                  r"\bok(?:ay)? (?:for|on) cash\b", r"\bis the company safe\b", r"\bdo we have enough (?:cash|money)\b",
                  r"安全吗", r"够不够", r"资金安全", r"现金够吗", r"钱够吗", r"够用吗"), a_safe),
    ("CAP-01", _p(r"\bafford\b.{0,30}\b(?:machine|equipment|die[- ]cutting|line|capex|purchase|investment)\b",
                  r"\b(?:should|can) we (?:buy|purchase)\b.{0,30}\b(?:machine|equipment|die[- ]cutting)\b",
                  r"买得起", r"(?:设备|模切线).{0,8}(?:能买|可以买|该买|买不买)"), a_capex),
    ("ACT-01", _p(r"\bwhat (?:did|has|have) (?:flow|you) (?:do|done)\b", r"\b(?:your|flow'?s) recent (?:actions|activity|operations)\b",
                  r"\bwhat have you (?:been )?do(?:ne|ing)\b", r"\brecent actions\b",
                  r"(?:flow|你).{0,6}(?:做了什么|做了哪些|干了什么|最近.{0,4}操作)", r"最近做了"), a_activity),
    ("MAN-01", _p(r"\bwhat can (?:flow|you) do without me\b", r"\b(?:allowed|permitted|authori[sz]ed) to do\b.{0,20}\b(?:own|without)\b",
                  r"\bwhat are you allowed to do\b", r"\bwithin your (?:authority|mandate)\b", r"\bwhat can you do on your own\b",
                  r"不经过我", r"自己能做", r"无需我", r"不用问我", r"权限范围", r"授权范围内"), a_autonomy),
)

# An instruction is not a question: "draw ¥50,000 on the line", "repay the line", "go ahead", "accept Foshan's offer". These never
# get a read answer, whatever words they share with one.
_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:draw|repay|pay off|pay back|fund|finance|send|accept|reject|approve|decline|counter|offer|negotiate|record|"
    r"book|apply|transfer|move|go ahead|run it|execute|cancel|confirm|sign|pledge|issue|change|set|give)\b"
    r"|^\s*(?:请)?(?:提款|还款|偿还|融资|发送|接受|拒绝|批准|还价|记录|执行|取消|确认|签|抵押|修改|转账|申请|给)",
    re.IGNORECASE)
_QUESTION = re.compile(r"[?？]|\b(?:what|how|when|who|which|why|can|could|should|is|are|do|does|did|will|would|any)\b|吗|么|呢|多少|哪|什么|怎么|为什么|能不能|是否|几",
                       re.IGNORECASE)


def _normal(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("’", "'").replace("‘", "'").strip().lower()


def match(question: str) -> tuple[str, Handler] | None:
    """The one top-30 question this text asks (its id and its answer), or None."""
    q = _normal(question)
    if not q or len(q) > 400:
        return None
    if _COMMAND.search(q) and not re.search(r"[?？]|吗|么|呢|多少|哪|什么|怎么|几", q):
        return None
    if not _QUESTION.search(q) and not q.startswith(("show me", "tell me", "list")):
        return None
    for qid, pattern, handler in QUESTIONS:
        if pattern.search(q):
            return qid, handler
    return None


def answer(question: str, lang: str, ctx: Any) -> AnswerReply | None:
    """The answer to one of the owner's top 30 questions, in `lang` (en or zh), from the books `ctx` holds (the turn's `NlContext`, or
    any object with `store`, `day`, `owner_key_hex` and optionally `reads`). None when the text is not one of them. Read-only."""
    found = match(question)
    if found is None:
        return None
    _qid, handler = found
    w = W(Reading.of(ctx), "zh" if lang == "zh" else "en")
    return handler(w, question)


def question_ids() -> list[str]:
    return [qid for qid, _, _ in QUESTIONS]


__all__ = ["AnswerReply", "answer", "match", "question_ids"]

