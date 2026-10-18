"""Advice tool: what the owner should do now, most urgent first, from the same reads as the other tools (the reserve breach and
FLOW's plan, overdue customers, approvals, the covenants and the mandate). It advises; it never runs anything."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import cap, n_en
from app.nl.answers.metrics import money
from app.nl.router.tools.common import Spec, horizon_note, integer, obj, with_note, writer

_COUNT = ("One thing", "Two things", "Three things", "Four things", "Five things")


def general_advice(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    asked = slots.get("horizon_days")
    note = horizon_note(w, asked)
    days = min(asked or r.horizon, r.horizon)
    end = r.today + days
    res = w.fig("reserve", money(r.floor))
    fb, low, p = w.m(mx.first_breach(r)), w.m(mx.lowest_point(r)), w.m(mx.standing_plan(r))
    od = w.m(mx.overdue(r)).value
    ap = w.m(mx.approvals_pending(r)).value
    cov = w.m(mx.covenant_ratios(r))
    md = w.m(mx.mandate_limits_and_validity(r))
    items: list[str] = []
    planned = False
    if fb.value is not None and fb.value <= end:
        w.fig("first_breach_day", str(fb.value))
        when = (w.t("cash is already below your reserve", "现金已低于您的储备线") if fb.detail["today"]
                else w.t(f"cash falls below your {res} reserve on {w.on(fb.value)}", f"现金将在{w.on(fb.value)}低于您 {res} 的储备线"))
        lowest = w.t(f", lowest {low.display} on {w.on(low.day)}", f"，最低在{w.on(low.day)}降至 {low.display}")
        if p.value is not None:
            planned = True
            cost = w.fig("plan_cost", p.detail["cost"] or "")
            if not p.detail["restores_reserve"]:
                items.append(w.t(f"decide how to fund the gap: {when}{lowest}, and FLOW's best plan ({cost}) only keeps cash above zero",
                                 f"决定如何补上缺口：{when}{lowest}，FLOW 的最佳方案（{cost}）只能让现金保持在零以上"))
            else:
                auth = (w.t("with your approval", "需要您批准") if p.detail["needs_owner"]
                        else w.t("within your limits", "在您的授权内"))
                items.append(w.t(f"fund the gap: {when}{lowest}; FLOW's plan covers it for {cost}, {auth}, and waits for your go-ahead",
                                 f"补上缺口：{when}{lowest}；FLOW 的方案可用 {cost} 补上，{auth}，正等您同意"))
        else:
            items.append(w.t(f"decide how to fund the gap: {when}{lowest}, and no committed funding fixes it",
                             f"决定如何补上缺口：{when}{lowest}，而已承诺的融资都无法解决"))
    for x in od[:2]:
        items.append(w.t(f"chase {w.buyer(x['buyer_id'])} for {money(x['face_fen'])}, {n_en(x['days_late'], 'day', 'days')} late",
                         f"催收{w.buyer(x['buyer_id'])}的 {money(x['face_fen'])}，已逾期 {x['days_late']} 天"))
    if ap:
        items.append(w.t(f"decide on the {n_en(len(ap), 'approval', 'approvals')} waiting for you", f"处理等您审批的 {len(ap)} 项操作"))
    if not (cov.detail["dscr"] is None and cov.detail["lev"] is None) and not cov.value:
        items.append(w.t("talk to your lender: a loan covenant breaks in the forecast", "与贷款方沟通：预测中有贷款契约指标不达标"))
    d = md.detail
    if not md.value:
        items.append(w.t("sign a new mandate: yours is no longer valid, so FLOW only proposes and you decide",
                         "签署新的授权：您的授权已失效，FLOW 只能提建议，由您决定"))
    elif d["expires_day"] <= end:
        items.append(w.t(f"renew your mandate before it expires on {w.on(d['expires_day'])}", f"在授权于{w.on(d['expires_day'])}到期前续签"))
    w.fig("items", str(len(items)))
    if not items:
        lo = (w.t(f" (lowest {low.display} on {w.on(low.day)})", f"（最低为{w.on(low.day)}的 {low.display}）")
              if low.day is not None and low.day <= end else "")
        text = w.t(f"Nothing urgent over the next {days} days: cash stays at or above your {res} reserve{lo}, nothing is overdue, nothing "
                   f"waits for your approval and your loan covenants hold.",
                   f"未来 {days} 天没有紧急事项：现金不低于您 {res} 的最低现金储备{lo}，没有逾期款项，没有待您审批的操作，贷款契约指标都满足。")
        if fb.value is not None:
            text += w.t(f" Further out, cash falls below the reserve from {w.on(fb.value)}.", f"更远一些，现金将从{w.on(fb.value)}起低于储备线。")
        return with_note(note, w.reply("general_advice", text))
    count = _COUNT[len(items) - 1] if len(items) <= len(_COUNT) else f"{len(items)} things"
    text = w.t(f"{count} to do, most urgent first: " + "; ".join(f"{i + 1}) {x}" for i, x in enumerate(items)) + ".",
               f"有 {len(items)} 件事要做，按紧急程度：" + "；".join(f"{i + 1}）{x}" for i, x in enumerate(items)) + "。")
    if planned:
        text += w.t(" Nothing has run yet.", "目前尚未执行任何操作。")
    return with_note(note, w.reply("general_advice", cap(text) if not w.zh else text))


SPECS: tuple[Spec, ...] = (
    Spec("general_advice", "What the owner should do now, most urgent first: the cash gap and FLOW's plan, late customers, "
         "approvals, covenants and the mandate.",
         obj({"horizon_days": integer("How many days ahead the owner asks about; omit it for the whole forecast.", 1, 365)}),
         general_advice),
)
