"""Debt and funding tools: FLOW's plan, its cost, the priced alternatives, the debt (in all and by facility), clearing it,
what can still be borrowed, the next loan payment and the monthly debt service."""

from __future__ import annotations

import re
from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import (
    W,
    a_borrow_more,
    a_clear_debts,
    a_debt_cost,
    a_next_loan_payment,
    a_plan_cost,
    a_recommend,
    a_total_debt,
    joined,
)
from app.nl.answers.metrics import money
from app.nl.router.tools.common import Spec, obj, writer


def funding_plan(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_recommend(writer(ctx, lang), "")


def plan_cost(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_plan_cost(writer(ctx, lang), "")


# The router's comparison rows (`funding.router.compare`), said by what they are: their labels are English only.
_OPTION = {
    "router_optimum": ("FLOW's plan", "FLOW 的方案"),
    "full_discount": ("taking early payment on the whole invoice", "整张发票接受提前付款"),
    "line_partial_early_pay": ("the credit line plus early payment on part of the invoice", "信用额度加部分发票提前付款"),
    "line_guaranteed_loan": ("the credit line plus the government-guaranteed loan", "信用额度加政府担保贷款"),
    "line_only": ("the credit line alone", "仅用信用额度"),
}
_WHY_NOT = {
    "RESERVE_BREACH": ("cash would still fall below your reserve", "现金仍会低于储备线"),
    "UNCOMMITTED_FACILITY": ("a facility in it is not committed yet", "其中有额度尚未获批"),
    "LEAD_TIME_TOO_LONG": ("the cash would arrive too late", "资金到账太晚"),
}
_RATE = re.compile(r"\b\d+(?:\.\d+)?%")


def _option(w: W, row: dict[str, Any]) -> str:
    en, zh = _OPTION.get(row["key"], ("another way", "另一种方式"))
    rate = _RATE.search(row.get("label") or "")
    if rate and row["key"] in ("full_discount", "line_partial_early_pay"):
        en, zh = en + f" at {rate.group(0)}", zh + f"（折扣 {rate.group(0)}）"
    return w.t(en, zh)


def _why_not(w: W, row: dict[str, Any]) -> str:
    parts = list(dict.fromkeys(w.t(*_WHY_NOT.get(c, ("it breaks one of your limits", "不满足您的某项限额"))) for c in row["reasons"]))
    return joined(w, parts) if parts else w.t("it breaks one of your limits", "不满足您的某项限额")


def compare_financing(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    rows = w.m(mx.alternatives_priced(r)).value
    fb = w.m(mx.first_breach(r))
    basis = w.t(f"FLOW's comparison of the ways to fund the gap, today's books, day {r.today}",
                f"FLOW 对各种补缺口方式的比较，今日账目，第 {r.today} 天")
    if not rows:
        if fb.value is None:
            return w.reply("FUN-03", w.t("Nothing to compare: no funding is needed on today's books.",
                                         "没有需要比较的：按今日账目无需融资。"), basis)
        return w.reply("FUN-03", w.t("I could not price the ways to fund the gap just now.", "暂时无法为补缺口的各种方式报价。"), basis)
    ok = sorted((x for x in rows if x["result"] in ("SELECTED", "ADMISSIBLE") and x["cost_fen"] is not None),
                key=lambda x: (x["result"] != "SELECTED", x["cost_fen"]))
    bad = [x for x in rows if x not in ok]
    if ok:
        best = ok[0]
        cost = w.fig("best_cost", money(best["cost_fen"]))
        cheapest = best["cost_fen"] == min(x["cost_fen"] for x in ok)
        lead = (w.t(f"{cap_(_option(w, best))} is the cheapest way that keeps your reserve: {cost}.",
                    f"{_option(w, best)}是守住储备线最便宜的方式：{cost}。") if cheapest
                else w.t(f"{cap_(_option(w, best))} is FLOW's choice: {cost}.", f"{_option(w, best)}是 FLOW 的选择：{cost}。"))
        for i, x in enumerate(ok[1:]):
            w.fig(f"alternative_{i + 1}", money(x["cost_fen"]))
        others = [w.t(f"{_option(w, x)} for {money(x['cost_fen'])}", f"{_option(w, x)}需 {money(x['cost_fen'])}") for x in ok[1:]]
        text = lead + (w.t(" Other ways that work: " + "; ".join(others) + ".", "其他可行方式：" + "；".join(others) + "。")
                       if others else "")
    else:
        text = w.t("None of the ways FLOW can price keeps your reserve.", "FLOW 能报价的方式都无法守住储备线。")
    if bad:
        text += w.t(" Not possible: " + "; ".join(f"{_option(w, x)} ({_why_not(w, x)})" for x in bad) + ".",
                    "不可行：" + "；".join(f"{_option(w, x)}（{_why_not(w, x)}）" for x in bad) + "。")
    return w.reply("FUN-03", text + w.t(" Nothing has run yet.", "目前尚未执行任何操作。"), basis)


def cap_(text: str) -> str:
    return text[:1].upper() + text[1:]


def total_debt(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_total_debt(writer(ctx, lang), "")


def debt_by_facility(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    total, pos = w.m(mx.total_debt(r)), w.m(mx.debt_positions(r))
    w.m(mx.drawn_by_facility(r))
    amt = w.fig("total_debt", total.display)
    loans = [x for x in pos.value if x["kind"] == "LOAN"]
    parts = [w.t(f"the {w.loan(x['label'])} {money(x['principal_fen'])} ({money(x['monthly_fen'])} a month)",
                 f"{w.loan(x['label'])} {money(x['principal_fen'])}（每月还 {money(x['monthly_fen'])}）") for x in loans]
    drawn, empty = [], []
    for f in r.state.facilities:  # the committed borrowing facilities (a buyer's early payment is a discount, not borrowing)
        if f.status.value != "COMMITTED" or f.limit_fen <= 0 or not f.counts_in_leverage:
            continue
        name = w.facility(f.kind.value, f.name)
        if f.drawn_fen > 0:
            w.fig(f"drawn_{f.kind.value.lower()}", money(f.drawn_fen))
            drawn.append(w.t(f"{name} {money(f.drawn_fen)} drawn of {money(f.limit_fen)}", f"{name}已提款 {money(f.drawn_fen)}（额度 {money(f.limit_fen)}）"))
        else:
            empty.append(w.t(f"{name} ({money(f.limit_fen)})", f"{name}（额度 {money(f.limit_fen)}）"))
    parts += drawn
    if not total.value:
        text = w.t("None: the books hold no loan and nothing is drawn on your facilities.", "没有负债：账目中没有贷款，各融资额度也没有提款。")
    else:
        text = w.t(f"{amt} in all: " + joined(w, parts) + ".", f"合计 {amt}：" + "，".join(parts) + "。")
    if empty and total.value:
        text += w.t(" Nothing is drawn on " + joined(w, empty).replace(" and ", " or ") + ".", "未提款：" + "、".join(empty) + "。")
    return w.reply("DEBT-02", text, w.basis("books"))


def repay_all_today(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_clear_debts(writer(ctx, lang), "")


def borrowing_headroom(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_borrow_more(writer(ctx, lang), "")


def next_loan_payment(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_next_loan_payment(writer(ctx, lang), "")


def debt_service(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_debt_cost(writer(ctx, lang), "")


SPECS: tuple[Spec, ...] = (
    Spec("funding_plan", "What FLOW recommends doing about cash: its funding plan, each step, the cost and whether it needs the "
         "owner's approval.", obj(), funding_plan),
    Spec("plan_cost", "What FLOW's funding plan costs, in all and by step.", obj(), plan_cost),
    Spec("compare_financing", "The ways to fund the cash gap compared on cost, the cheapest that keeps the reserve first, and why "
         "the others do not work.", obj(), compare_financing),
    Spec("total_debt", "How much debt the company has in all, and what it is.", obj(), total_debt),
    Spec("debt_by_facility", "The debt loan by loan and facility by facility: what is drawn and what is not.", obj(),
         debt_by_facility),
    Spec("repay_all_today", "Whether all the debt could be repaid today without breaking the reserve.", obj(), repay_all_today),
    Spec("borrowing_headroom", "How much more can be borrowed on committed facilities, at what cost and how fast.", obj(),
         borrowing_headroom),
    Spec("next_loan_payment", "When the next loan payment is due and how much it is.", obj(), next_loan_payment),
    Spec("debt_service", "What the debt costs each month: the scheduled debt service and the interest and fees ahead.", obj(),
         debt_service),
)
