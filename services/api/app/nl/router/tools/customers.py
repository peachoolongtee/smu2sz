"""Customer tools: who owes the most, what is overdue, what each customer owes, how concentrated the receivables are, one
customer's summary, and three what-ifs (a late payment, an early-payment offer, longer terms). A customer slot is the
owner's own words; it is resolved here against the registry and never comes from, or goes to, the model as a registry name."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.domain.money import bp, fmt_pct
from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import W, a_dependence, a_late, a_owes_most, n_en, pct0
from app.nl.answers.metrics import money
from app.nl.router.tools.common import (
    Resolved,
    Spec,
    ask_which_customer,
    customer,
    integer,
    obj,
    resolve_customer,
    writer,
)


def _customer(w: W, tool: str, said: str | None) -> tuple[str | None, AnswerReply | None]:
    res: Resolved = resolve_customer(w.r, said)
    if res.buyer_id is None:
        return None, ask_which_customer(w, tool, res)
    return res.buyer_id, None


def who_owes_most(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_owes_most(writer(ctx, lang), "")


def overdue(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_late(writer(ctx, lang), "")


def receivables_by_customer(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    total = w.m(mx.receivables_total(r))
    rows = w.m(mx.receivables_by_customer(r)).value
    if not total.value:
        return w.reply("CUS-02", w.t("Nothing: nobody owes you anything right now.", "没有：目前没有客户欠您款项。"), w.basis("books"))
    amt = w.fig("receivables_total", total.display)
    parts = []
    for x in rows:
        name = w.buyer(x["buyer_id"])
        if not x["owed_fen"]:
            parts.append(w.t(f"{name} nothing", f"{name}不欠款"))
            continue
        due = (w.t(f", next due on {w.on(x['next_due_day'])}", f"，最近一张{w.on(x['next_due_day'])}到期")
               if x["next_due_day"] is not None else "")
        late = (w.t(f", {money(x['overdue_fen'])} of it overdue", f"，其中 {money(x['overdue_fen'])} 已逾期") if x["overdue_fen"] else "")
        parts.append(w.t(f"{name} {money(x['owed_fen'])} on {n_en(x['invoices'], 'invoice', 'invoices')}{due}{late}",
                         f"{name} {money(x['owed_fen'])}（{x['invoices']} 张发票{due}{late}）"))
    return w.reply("CUS-02", w.t(f"{amt} owed to you in all: " + "; ".join(parts) + ".", f"应收账款合计 {amt}：" + "；".join(parts) + "。"),
                   w.basis("books"))


def concentration(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    said = slots.get("customer")
    if not said:
        return a_dependence(w, "")
    buyer, ask = _customer(w, "concentration", said)
    if ask is not None:
        return ask
    rows = w.m(mx.receivables_by_customer(w.r)).value
    mine = next((x for x in rows if x["buyer_id"] == buyer), None)
    total = sum(x["owed_fen"] for x in rows)
    name = w.buyer(buyer)
    if not total:
        return w.reply("CUS-05", w.t("Nobody owes you anything right now, so no customer holds a share of your receivables.",
                                     "目前没有客户欠款，因此没有客户占有应收账款的份额。"), w.basis("books"))
    owed = mine["owed_fen"] if mine else 0
    share = w.fig("share", pct0(Fraction(owed, total)))
    text = w.t(f"{share}: {name} accounts for {share} of what you are owed ({money(owed)} of {money(total)}).",
               f"{share}：{name}占您应收账款的 {share}（{money(total)} 中的 {money(owed)}）。")
    rec = w.m(mx.recurring_billing(w.r)).value
    per_day = {x["buyer_id"]: Fraction(x["face_fen"], x["every_days"]) for x in rec if x["every_days"]}
    if per_day:
        rshare = w.fig("recurring_share", pct0(per_day.get(buyer or "", Fraction(0)) / sum(per_day.values())))
        text += w.t(f" Of your recurring invoicing, {rshare} is to {name}.", f"在定期开票中，{name}占 {rshare}。")
    return w.reply("CUS-05", text, w.basis("books"))


def customer_summary(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    buyer, ask = _customer(w, "customer_summary", slots.get("customer"))
    if ask is not None:
        return ask
    name = w.buyer(buyer)
    w.fig("customer", name)
    rows = w.m(mx.receivables_by_customer(r)).value
    x = next((v for v in rows if v["buyer_id"] == buyer), None)
    late = [o for o in w.m(mx.overdue(r)).value if o["buyer_id"] == buyer]
    if x is None or not x["owed_fen"]:
        text = w.t(f"{name} owes you nothing right now.", f"{name}目前不欠您款项。")
    else:
        owed = w.fig("owed", money(x["owed_fen"]))
        due = (w.t(f", next due on {w.on(x['next_due_day'])}", f"，最近一张{w.on(x['next_due_day'])}到期")
               if x["next_due_day"] is not None else "")
        text = w.t(f"{name} owes you {owed} on {n_en(x['invoices'], 'invoice', 'invoices')}{due}; that is {pct0(x['share'])} of what "
                   f"you are owed.",
                   f"{name}欠您 {owed}（{x['invoices']} 张发票{due}），占您应收账款的 {pct0(x['share'])}。")
    if late:
        worst = max(late, key=lambda o: o["days_late"])
        w.fig("overdue", money(sum(o["face_fen"] for o in late)))
        text += w.t(f" {money(sum(o['face_fen'] for o in late))} of it is overdue, the oldest {n_en(worst['days_late'], 'day', 'days')} "
                    f"late.", f"其中 {money(sum(o['face_fen'] for o in late))} 已逾期，最久的已逾期 {worst['days_late']} 天。")
    rec = [v for v in w.m(mx.recurring_billing(r)).value if v["buyer_id"] == buyer]
    for v in rec[:1]:
        text += w.t(f" You invoice them {money(v['face_fen'])} every {v['every_days']} days on {v['terms_days']}-day terms.",
                    f"您每 {v['every_days']} 天向其开票 {money(v['face_fen'])}，账期 {v['terms_days']} 天。")
    terms = next((v for v in w.m(mx.terms_by_customer(r)).value if v["buyer_id"] == buyer), None)
    if terms is not None and not rec:
        text += w.t(f" Their invoices are on {terms['terms_days']}-day terms.", f"其发票账期为 {terms['terms_days']} 天。")
    if terms is not None:
        text += (w.t(" Their contract is confirmed in FLOW.", "其合同已在 FLOW 中确认。") if terms["contract_confirmed"]
                 else w.t(" No contract with them is confirmed in FLOW.", "FLOW 中尚无与其确认的合同。"))
    offer = next((f for f in r.state.facilities if f.kind.value == "BUYER_EARLY_PAY" and f.lender_id == buyer), None)
    if offer is not None and offer.rate_bp:
        text += w.t(f" They offer to pay early for a {fmt_pct(bp(offer.rate_bp))} discount.",
                    f"其提出以 {fmt_pct(bp(offer.rate_bp))} 的折扣提前付款。")
    return w.reply("customer_summary", text, w.basis("books"))


def late_payment_whatif(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    buyer, ask = _customer(w, "late_payment_whatif", slots.get("customer"))
    if ask is not None:
        return ask
    n = int(slots["days_late"])
    name = w.buyer(buyer)
    li = w.m(mx.late_payment_impact(r, buyer or "", n))
    if li.value is None:
        already = li.detail.get("already_late_fen") or 0
        if already:
            return w.reply("CUS-07", w.t(
                f"{name} has no invoice still to come: the {money(already)} it owes is already overdue, and the forecast no longer counts "
                f"on it. I have not changed anything.",
                f"{name}没有尚未到期的发票：所欠的 {money(already)} 已经逾期，预测已不再计入。我没有更改任何内容。"), w.basis("hypothetical"))
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
    text = head + w.t(", ", "，").join(parts) + w.t(".", "。")
    end = r.today + r.horizon
    if d["new_due_day"] > end:
        text += w.t(f" Day {d['new_due_day']} is past the end of FLOW's {r.horizon}-day forecast (day {end}), so the forecast no longer "
                    f"counts that payment at all.",
                    f"第 {d['new_due_day']} 天已超出 FLOW {r.horizon} 天预测的终点（第 {end} 天），因此预测完全不再计入这笔回款。")
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


def early_pay_offer(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    buyer: str | None = None
    if slots.get("customer"):
        buyer, ask = _customer(w, "early_pay_offer", slots["customer"])
        if ask is not None:
            return ask
    be = w.m(mx.break_even(r))
    offer = next((f for f in r.state.facilities if f.kind.value == "BUYER_EARLY_PAY" and (buyer is None or f.lender_id == buyer)), None)
    rate_bp = slots.get("rate_bp") or (offer.rate_bp if offer is not None else None)
    if be.value is None:
        return w.reply("CUS-08", w.t("I cannot price it: there is no committed funding to compare an early-payment discount with.",
                                     "无法判断：没有已承诺的融资可与提前付款折扣比较。"))
    b = w.fig("break_even", be.display)
    if rate_bp is None:
        who = w.t(f" from {w.buyer(buyer)}", f"{w.buyer(buyer)}的") if buyer else ""
        return w.reply("CUS-08", w.t(f"There is no early-payment offer{who} on your books. Any discount at or below your {b} break-even "
                                     f"is cheaper than your own funding.",
                                     f"账目中没有{who}提前付款报价。任何不高于您 {b} 盈亏平衡点的折扣都比自己融资便宜。"))
    rate = w.fig("rate", fmt_pct(bp(rate_bp)))
    full = None
    if offer is not None and rate_bp == offer.rate_bp:
        full = next((x for x in w.m(mx.alternatives_priced(r)).value if x["key"] == "full_discount"), None)
    p = w.m(mx.standing_plan(r))
    no_need = p.value is None and w.m(mx.first_breach(r)).value is None
    if Fraction(rate_bp, 10_000) > be.value:
        w.fig("answer", "no")
        text = w.t(f"No. {rate} is above your {b} break-even, so your own funding is cheaper", f"不划算。{rate} 高于您 {b} 的盈亏平衡点，自己融资更便宜")
        if full is not None and full["cost_fen"] is not None and p.value is not None:
            fc = w.fig("full_discount_cost", money(full["cost_fen"]))
            text += w.t(f": discounting the whole invoice costs {fc}, against {p.detail['cost']} for FLOW's plan.",
                        f"：整张发票贴现要花 {fc}，而 FLOW 的方案只需 {p.detail['cost']}。")
        elif no_need:
            text += w.t(", and you have no funding need on today's books.", "，而且按今日账目您并没有融资需求。")
        else:
            text += w.t(".", "。")
    else:
        w.fig("answer", "yes")
        text = w.t(f"Yes on price: {rate} is at or below your {b} break-even, so it is cheaper than your own marginal funding.",
                   f"按价格划算：{rate} 不高于您 {b} 的盈亏平衡点，比您自己的边际融资更便宜。")
        if no_need:
            text += w.t(" But you have no funding need on today's books, so the discount buys nothing.",
                        "但按今日账目您并没有融资需求，这笔折扣换不来任何好处。")
    return w.reply("CUS-08", text)


def terms_extension_cost(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    buyer, ask = _customer(w, "terms_extension_cost", slots.get("customer"))
    if ask is not None:
        return ask
    n = int(slots["days"])
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
    text = w.t(f"{total} in forward concessions over {span} of {name} invoices on {n}-day terms, "
               + (f"above your {capf} limit" if d["over_cap"] else f"within your {capf} limit"),
               f"{span}{name}的发票共产生远期让步 {total}（按 {n} 天账期），" + (f"超过您 {capf} 的上限" if d["over_cap"] else f"在您 {capf} 的上限内"))
    if d["breach_day"] is not None:
        w.fig("breach_day", str(d["breach_day"]))
        text += w.t(f", and cash would fall below your reserve on {w.on(d['breach_day'])}", f"，且现金将在{w.on(d['breach_day'])}低于您的储备线")
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


SPECS: tuple[Spec, ...] = (
    Spec("who_owes_most", "Which customer owes the company the most, and how much.", obj(), who_owes_most),
    Spec("overdue", "Which customers are paying late and should be chased first.", obj(), overdue),
    Spec("receivables_by_customer", "What each customer owes, in all and customer by customer.", obj(), receivables_by_customer),
    Spec("concentration", "How dependent the company is on one customer: a customer's share of what is owed.",
         obj({"customer": customer(required=False)}), concentration),
    Spec("customer_summary", "Everything the books hold on one customer: what they owe, when it is due, what is late, their "
         "terms and any early-payment offer.", obj({"customer": customer()}, ["customer"]), customer_summary),
    Spec("late_payment_whatif", "What happens to cash if one customer pays a number of days late (a projection; nothing changes).",
         obj({"customer": customer(), "days_late": integer("How many days late the customer pays.", 1, 180)},
             ["customer", "days_late"]), late_payment_whatif),
    Spec("early_pay_offer", "Whether taking a customer's early-payment discount is worth it against the break-even rate.",
         obj({"customer": customer(required=False),
              "rate_bp": integer("The discount rate the owner names, in basis points (one percent is one hundred); omit it to use "
                                 "the offer on file.", 1, 500)}), early_pay_offer),
    Spec("terms_extension_cost", "What giving a customer longer payment terms would cost in concessions, and whether FLOW could "
         "accept it (a what-if; nothing is sent).",
         obj({"customer": customer(), "days": integer("The payment terms in days the customer would get.", 1, 180)},
             ["customer", "days"]), terms_extension_cost),
)
