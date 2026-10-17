"""Liquidity tools: cash today, whether it stays safe, the runway, the lowest point, the first breach, cash on a day, the
payments and receipts ahead, payroll, what can be spent, why cash is short, and how much is needed."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import (
    W,
    a_breach,
    a_lowest,
    a_need,
    a_payroll,
    a_runway,
    a_safe,
    a_spend,
    a_why,
    cap,
    n_en,
)
from app.nl.answers.metrics import Event, money
from app.nl.router.tools.common import Spec, flag, horizon_note, integer, obj, with_note, writer

HORIZON = integer("How many days ahead the owner asks about; omit it for the whole forecast.", 1, 365)


def cash_position(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    cash, res, head, transit = w.m(mx.cash_today(r)), w.m(mx.reserve(r)), w.m(mx.headroom_today(r)), w.m(mx.in_transit(r))
    c, rv = w.fig("cash", cash.display), w.fig("reserve", res.display)
    w.fig("headroom", head.display)
    if head.value > 0:
        rel = w.t(f"{money(head.value)} above your {rv} reserve", f"比您 {rv} 的最低现金储备高 {money(head.value)}")
    elif head.value < 0:
        rel = w.t(f"{money(-head.value)} below your {rv} reserve", f"比您 {rv} 的最低现金储备低 {money(-head.value)}")
    else:
        rel = w.t(f"exactly at your {rv} reserve", f"正好等于您 {rv} 的最低现金储备")
    text = w.t(f"{c} in cash today, {rel}.", f"今天现金 {c}，{rel}。")
    if transit.detail["total_fen"]:
        text += w.t(f" Another {transit.display} is on its way and not yet in the bank.", f"另有 {transit.display} 正在到账途中，尚未入账。")
    return w.reply("LIQ-02", text, w.basis("books"))


def cash_safety(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    asked = slots.get("horizon_days")
    if asked is None or asked >= r.horizon:
        return with_note(horizon_note(w, asked), a_safe(w, ""))
    fb = w.m(mx.first_breach(r))
    end = r.today + asked
    if fb.value is not None and fb.value <= end:
        return a_safe(w, "")
    low = w.m(mx.lowest_point(r))
    window = min((d for d in r.ahead if d.day <= end), key=lambda d: (d.closing_fen, d.day))
    res = w.fig("reserve", money(r.floor))
    lo = w.fig("lowest_in_window", money(window.closing_fen))
    w.fig("answer", "yes")
    text = w.t(f"Yes: for the next {asked} days cash stays at or above your {res} reserve; the lowest in that time is {lo} on "
               f"{w.on(window.day)}.",
               f"安全：未来 {asked} 天现金都不低于您 {res} 的最低现金储备；这段时间的最低点是{w.on(window.day)}的 {lo}。")
    if fb.value is not None:
        w.fig("first_breach_day", str(fb.value))
        text += w.t(f" After that it falls below the reserve from {w.on(fb.value)}, lowest {low.display} on {w.on(low.day)}.",
                    f"但之后现金将从{w.on(fb.value)}起低于储备线，最低在{w.on(low.day)}降至 {low.display}。")
    return w.reply("LIQ-01", text)


def runway(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_runway(writer(ctx, lang), "")


def lowest_point(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_lowest(writer(ctx, lang), "")


def first_breach(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_breach(writer(ctx, lang), "")


def cash_on_day(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    n = int(slots["day"])
    target = r.today + n if slots.get("relative") else n
    last = r.traj.days[-1].day if r.traj.days else r.today
    res = money(r.floor)
    if target < r.today:
        cash = w.m(mx.cash_today(r))
        w.fig("cash", cash.display)
        return w.reply("LIQ-11", w.t(f"Day {target} has already passed: today is day {r.today}, and cash today is {cash.display}.",
                                     f"第 {target} 天已经过去：今天是第 {r.today} 天，今天现金 {cash.display}。"), w.basis("books"))
    note = ""
    if target > last:
        note = w.t(f"FLOW's forecast runs to day {last}, so day {target} is beyond it; this is the forecast's last day. ",
                   f"FLOW 的预测只到第 {last} 天，第 {target} 天超出了预测期；以下是预测最后一天的数字。")
        target = last
    m = w.m(mx.cash_on(r, target))
    if m.value is None:
        return w.reply("LIQ-11", w.t("I could not read that day from the forecast.", "无法从预测中读到那一天。"))
    amt = w.fig("cash_on_day", m.display)
    w.fig("day", str(target))
    if m.value >= r.floor:
        rel = w.t(f"{money(m.value - r.floor)} above your {res} reserve", f"比您 {res} 的最低现金储备高 {money(m.value - r.floor)}")
    else:
        rel = w.t(f"{money(r.floor - m.value)} below your {res} reserve", f"比您 {res} 的最低现金储备低 {money(r.floor - m.value)}")
    text = w.t(f"{amt} on {w.on(target)}, {rel}, if nothing new is done.", f"{w.on(target)}现金为 {amt}，{rel}（不采取新措施的情况下）。")
    reply = w.reply("LIQ-11", text)
    return with_note(note, reply) if note else reply


def _window(w: W, asked: int | None, default: int | None) -> tuple[int, str, bool]:
    """The window of days [today, today + window) to read, the note when the owner asked beyond the forecast, and whether the
    window is the whole forecast (`default` None: the whole forecast unless the owner asked for fewer days)."""
    r = w.r
    if asked is None and default is None:
        return r.horizon + 1, "", True
    days = asked if asked is not None else int(default or 0)
    if days > r.horizon:
        return r.horizon + 1, horizon_note(w, days), True  # [today, today + horizon]: every day the forecast holds
    return days, "", False


def _span(w: W, window: int, capped: bool) -> tuple[str, str]:
    """("in the next 60 days", "未来 60 天"), or "until the forecast ends on day 120" when capped."""
    r = w.r
    if capped:
        end = r.today + r.horizon
        return f"until the forecast ends on day {end}", f"到预测结束的第 {end} 天为止"
    return f"in the next {window} days", f"未来 {window} 天"


def upcoming_payments(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    window, note, whole = _window(w, slots.get("window_days"), mx.UPCOMING_DAYS)
    m = w.m(mx.upcoming_outflows(w.r, window))
    outs: list[Event] = m.value
    en_span, zh_span = _span(w, window, whole)
    if not outs:
        return with_note(note, w.reply("LIQ-09", w.t(f"None: no payment is scheduled {en_span}.", f"没有：{zh_span}没有计划中的付款。")))
    total = w.fig("total", money(m.detail["total_fen"]))
    for i, e in enumerate(outs[:8]):
        w.fig(f"payment_{i + 1}", f"{money(-e.amount_fen)} day {e.day}")
    items = [w.t(f"{w.outflow(e)} {money(-e.amount_fen)} on {w.on(e.day)}", f"{w.on(e.day)}{w.outflow(e)} {money(-e.amount_fen)}")
             for e in outs[:8]]
    more = len(outs) - len(items)
    tail = w.t(f"; and {more} more", f"；另有 {more} 笔") if more > 0 else ""
    return with_note(note, w.reply("LIQ-09", w.t(
        f"{cap(n_en(len(outs), 'payment', 'payments'))} {en_span}, {total} in all: " + "; ".join(items) + tail + ".",
        f"{zh_span}共有 {len(outs)} 笔支出，合计 {total}：" + "；".join(items) + tail + "。")))


def upcoming_receipts(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    window, note, whole = _window(w, slots.get("window_days"), None)
    m = w.m(mx.upcoming_inflows(r, window - 1))  # upcoming_inflows reads [today, today + n] inclusive
    ins: list[Event] = m.value
    en_span, zh_span = _span(w, window, whole)
    od = w.m(mx.overdue(r))
    late = (w.t(f" {od.display} overdue is not counted: the forecast no longer counts on it.", f"已逾期的 {od.display} 未计入：预测已不再计入。")
            if od.value else "")
    if not ins:
        return with_note(note, w.reply("LIQ-13", w.t(f"None: no receipt is expected {en_span}.", f"没有：{zh_span}没有预计的收款。") + late))
    total = w.fig("total", m.display)
    for i, e in enumerate(ins[:8]):
        w.fig(f"receipt_{i + 1}", f"{money(e.amount_fen)} day {e.day}")
    items = [w.t(f"{w.buyer(e.counterparty_id)} {money(e.amount_fen)} on {w.on(e.day)}",
                 f"{w.on(e.day)}{w.buyer(e.counterparty_id)} {money(e.amount_fen)}") for e in ins[:8]]
    more = len(ins) - len(items)
    tail = w.t(f"; and {more} more", f"；另有 {more} 笔") if more > 0 else ""
    return with_note(note, w.reply("LIQ-13", w.t(
        f"{total} expected {en_span}, {n_en(len(ins), 'receipt', 'receipts')}: " + "; ".join(items) + tail + "." + late,
        f"{zh_span}预计收款 {len(ins)} 笔，合计 {total}：" + "；".join(items) + tail + "。" + late)))


def payroll_cover(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_payroll(writer(ctx, lang), "")


def safe_to_spend(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_spend(writer(ctx, lang), "")


def why_short(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_why(writer(ctx, lang), "")


def funding_need(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_need(writer(ctx, lang), "")


WINDOW = integer("How many days ahead the owner asks about; omit it for the default window.", 1, 365)

SPECS: tuple[Spec, ...] = (
    Spec("cash_position", "How much cash the company has today, against the minimum cash reserve.", obj(), cash_position),
    Spec("cash_safety", "Whether cash stays at or above the minimum cash reserve (are we safe, do we have enough cash), over the "
         "whole forecast or the next few days asked about.", obj({"horizon_days": HORIZON}), cash_safety),
    Spec("runway", "How many days until cash falls below the reserve, and when it goes below zero.", obj(), runway),
    Spec("lowest_point", "The lowest cash will go in the forecast, on which day, and why.", obj(), lowest_point),
    Spec("first_breach", "When cash first drops below the minimum cash reserve.", obj(), first_breach),
    Spec("cash_on_day", "The forecast cash on one day: a day number as FLOW counts days, or a number of days from today.",
         obj({"day": integer("The day the owner asks about: the day number, or the number of days from today when relative.", 0, 365),
              "relative": flag("True when the owner said 'in N days' rather than 'day N'.")}, ["day"]), cash_on_day),
    Spec("upcoming_payments", "The payments going out in the coming days (payroll, suppliers, loan payments), with the total.",
         obj({"window_days": WINDOW}), upcoming_payments),
    Spec("upcoming_receipts", "The money expected to come in over the coming days, from which customers, with the total.",
         obj({"window_days": WINDOW}), upcoming_receipts),
    Spec("payroll_cover", "Whether the next payroll can be paid, and what it leaves against the reserve.", obj(), payroll_cover),
    Spec("safe_to_spend", "How much can be spent today without breaking the reserve at the forecast's lowest point.", obj(),
         safe_to_spend),
    Spec("why_short", "Why cash is going to be short: the payments that cause the gap and the receipt that ends it.", obj(),
         why_short),
    Spec("funding_need", "How much money is needed to stay at the reserve, over which days, and what FLOW's plan costs.", obj(),
         funding_need),
)
