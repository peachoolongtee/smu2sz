"""Read-only answers for the questions the Business pages suggest (wayfinder #65, wave 4 part A).

Each answer is built from the Home read that the API layer lends the owner's chat (`OwnerReads.home`: the same
sentences and figures GET /home already writes) or from the verdict the page evaluated. Nothing here projects,
decides, books or executes; the amounts and distances are copied from those reads and only joined into sentences.
A read that cannot be made says so instead of guessing. Owner channel only: a counterparty turn never gets here.

  CHANGES          "what changed today?"          the log since the last visit, what it means for cash, what is left to do
  SHOW_STATUS      "what are we waiting for?", "when does the money arrive?"
  RECONCILE        "what is overdue?", "who should I chase first?"
  WHAT_IF          "what if I accept their original terms?", "what happens if this payment is late?"
  EXPLAIN          "why is Option A cheaper?", "why did FLOW choose this plan?"
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.models import Outcome, Verdict
from app.domain.money import fmt_yuan
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.models import Intent
from app.nl.pipeline import t
from app.nl.turn import Turn

MAX_EVENTS = 6

# ---------------------------------------------------------------- shared pieces


def _home(ctx: NlContext, since_day: int | None = None) -> dict[str, Any] | None:
    reads = ctx.reads
    return reads.home(ctx.lang, since_day) if reads is not None else None


def _unavailable(ctx: NlContext, intent: Intent) -> Turn:
    return Turn(intent=intent, reply=t(
        ctx, "I could not read your books just now, so I have not answered. Nothing was changed; please try again.",
        "我暂时无法读取您的账目，因此没有作答。没有任何更改，请稍后再试。"))


def _days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def _when(day: int, today: int, lang: str) -> str:
    """A day as a distance from today, for the one case the Home read does not already hold (a bound invoice)."""
    n = day - today
    if lang == "zh":
        return "今天" if n == 0 else (f"{n} 天后" if n > 0 else f"{-n} 天前")
    return "today" if n == 0 else (f"in {_days(n)}" if n > 0 else f"{_days(-n)} ago")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?。！？" else text + ("。" if re.search(r"[㐀-鿿]", text) else ".")


def _join(parts: list[str], zh: bool) -> str:
    return ("" if zh else " ").join(p for p in (_sentence(x) for x in parts) if p)


def _forecast(ctx: NlContext, h: dict[str, Any]) -> str:
    """Where the forecast stands, in the Home read's own words (its headline and note)."""
    return _join([str(h.get("headline") or ""), str(h.get("note") or "")], ctx.lang == "zh")


def _approval_line(ctx: NlContext, a: dict[str, Any]) -> str:
    bits = [str(a.get("headline") or a.get("what") or "")]
    if a.get("cost_display"):
        bits.append(t(ctx, f"It costs {a['cost_display']}.", f"费用 {a['cost_display']}。"))
    if a.get("lands_text"):
        bits.append(str(a["lands_text"]))
    if a.get("if_decline"):
        bits.append(t(ctx, f"If you decline, {a['if_decline'][:1].lower()}{a['if_decline'][1:]}", f"若您拒绝：{a['if_decline']}"))
    return _join(bits, ctx.lang == "zh")


def _status_of(ctx: NlContext, row: dict[str, Any]) -> str:
    kind = row.get("kind")
    if kind == "WAITING":
        return t(ctx, "Status: still waiting for your decision.", "状态：仍待您决定。")
    if kind == "LATE":
        left = row.get("remaining_display")
        return (t(ctx, f"Status: {left} is still to come.", f"状态：还有 {left} 未到。") if left
                else t(ctx, "Status: still unpaid.", "状态：仍未收到。"))
    if kind == "REFUSED":
        return t(ctx, "Status: refused, no money moved.", "状态：已被拒绝，没有资金变动。")
    return t(ctx, "Status: done.", "状态：已完成。")


def _unpaid_line(ctx: NlContext, r: dict[str, Any]) -> str:
    return t(ctx, f"Not yet paid: {r['invoice']}, due {r['due_when']}.", f"尚未收到：{r['invoice']}，{r['due_when']}到期。")


# ---------------------------------------------------------------- CHANGES


def changes(ctx: NlContext) -> Turn:
    """What changed since the owner's last visit (the page's marker) or, with none, today: each event in its business
    sentence with its status, what that means for cash, and what is left to do. Never a list of capabilities."""
    marker = ctx.binding.since_day if ctx.binding is not None else None
    h = _home(ctx, marker if marker is not None else ctx.day)
    if h is None:
        return _unavailable(ctx, Intent.CHANGES)
    away = h["day"] - marker if marker is not None else 0
    events: list[dict[str, Any]] = list(h.get("changes") or [])
    away_ = marker is not None and away > 0
    if not events:
        if marker is not None and away > 0:
            lead = t(ctx, f"Nothing changed since your last visit {_days(away)} ago; the forecast is unchanged: ",
                     f"自您上次访问（{away} 天前）以来没有变化；预测保持不变：")
        else:
            lead = t(ctx, "Nothing has changed today; the forecast is unchanged: ", "今天没有变化；预测保持不变：")
        return Turn(intent=Intent.CHANGES, reply=lead + _forecast(ctx, h))
    lines = [t(ctx, f"Since your last visit {_days(away)} ago:", f"自您上次访问（{away} 天前）以来：") if away_
             else t(ctx, "Today:", "今天：")]
    if away_:
        lines.append(t(ctx, f"- Time moved forward {_days(away)}, to today.", f"- 时间向前推进了 {away} 天，到今天。"))
    for row in events[:MAX_EVENTS]:
        lines.append(f"- {_sentence(str(row.get('event_text') or row.get('text') or ''))} {_status_of(ctx, row)}")
    if len(events) > MAX_EVENTS:
        lines.append(t(ctx, f"- {len(events) - MAX_EVENTS} more are on the Activity page.",
                       f"- 另有 {len(events) - MAX_EVENTS} 项见“动态”页面。"))
    lines.append(t(ctx, "What it means for your cash: ", "对您现金的影响：") + _forecast(ctx, h))
    todo = [_approval_line(ctx, a) for a in h.get("approvals") or []]
    todo += [_unpaid_line(ctx, r) for r in (h.get("receivables") or {}).get("past_due") or []]
    if todo:
        lines.append(t(ctx, "Still to do:", "还需处理："))
        lines += [f"- {x}" for x in todo]
    else:
        lines.append(t(ctx, "Nothing is waiting for you.", "目前没有需要您处理的事项。"))
    return Turn(intent=Intent.CHANGES, reply="\n".join(lines))


# ---------------------------------------------------------------- SHOW_STATUS reads


def waiting(ctx: NlContext) -> Turn:
    """What is open: decisions waiting for the owner, a buyer's promised payment, money on its way, invoices unpaid."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.SHOW_STATUS)
    r = h.get("receivables") or {}
    lines: list[str] = []
    for a in h.get("approvals") or []:
        lines.append(t(ctx, "Waiting for your decision: ", "等待您的决定：") + _approval_line(ctx, a))
    p = r.get("promised")
    if p:
        lines.append(t(ctx, f"Waiting for {p['buyer_name']} to pay {p['expected_display']} {p['when']}.",
                       f"等待{p['buyer_name']}{p['when']}支付 {p['expected_display']}。"))
    for lot in ((h.get("cash") or {}).get("in_transit") or {}).get("lots") or []:
        lines.append(t(ctx, f"Waiting for funding to land: {lot['headline']}.", f"等待资金到账：{lot['headline']}。"))
    lines += [t(ctx, "Waiting for payment: ", "等待付款：") + _unpaid_line(ctx, x) for x in r.get("past_due") or []]
    if not lines:
        lines.append(t(ctx, "Nothing is waiting on you or on anyone else right now.", "目前没有在等待您或其他方的事项。"))
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(lines))


def arrival(ctx: NlContext) -> Turn:
    """When money is due to land: funding in transit, what an approval would bring, a promised payment, the next invoice due."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.SHOW_STATUS)
    r = h.get("receivables") or {}
    lots = ((h.get("cash") or {}).get("in_transit") or {}).get("lots") or []
    approvals = [a for a in h.get("approvals") or [] if a.get("lands_text")]
    promised = r.get("promised")
    lines = [_sentence(str(lot["headline"])) for lot in lots]
    lines += [_join([str(a["headline"]), str(a["lands_text"])], ctx.lang == "zh") for a in approvals]
    if promised:
        lines.append(t(ctx, f"{promised['buyer_name']} has promised {promised['expected_display']} {promised['when']}.",
                       f"{promised['buyer_name']}承诺{promised['when']}支付 {promised['expected_display']}。"))
    if not (lots or approvals or promised):
        lines.append(t(ctx, "No funding is on its way.", "目前没有在途资金。"))
    nxt = r.get("next_receipt")
    if nxt:
        lines.append(t(ctx, f"The next payment due is {nxt['invoice']}, {nxt['due_when']}.",
                       f"下一笔到期的款项是{nxt['invoice']}，{nxt['due_when']}到期。"))
    elif not lines:
        lines.append(t(ctx, "No payment is due soon.", "近期没有到期的款项。"))
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(lines))


# ---------------------------------------------------------------- RECONCILE read (receivables)


def receivables(ctx: NlContext) -> Turn:
    """What is overdue, largest first: that is the one to chase first. Nothing is sent to anyone."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.RECONCILE)
    r = h.get("receivables") or {}
    late = sorted(r.get("past_due") or [], key=lambda x: (-int(x.get("face_fen") or 0), -int(x.get("days_late") or 0)))
    if not late:
        nxt = r.get("next_receipt")
        tail = (t(ctx, f" The next payment due is {nxt['invoice']}, {nxt['due_when']}.",
                  f"下一笔到期的款项是{nxt['invoice']}，{nxt['due_when']}到期。") if nxt else "")
        return Turn(intent=Intent.RECONCILE, reply=t(ctx, "Nothing is overdue.", "目前没有逾期款项。") + tail)
    first = late[0]
    lines = [t(ctx, f"{r['overdue_total_display']} is overdue across {len(late)} invoice{'' if len(late) == 1 else 's'} "
                    f"({r['open_total_display']} is open in all).",
               f"共有 {len(late)} 张发票逾期，合计 {r['overdue_total_display']}（未收总额 {r['open_total_display']}）。"),
             t(ctx, f"Chase {first['buyer_name']} first: {first['invoice']}, due {first['due_when']} "
                    f"({_days(int(first['days_late']))} late). It is the largest overdue amount.",
               f"请先催{first['buyer_name']}：{first['invoice']}，{first['due_when']}到期（已逾期 {first['days_late']} 天），"
               f"是逾期金额最大的一笔。")]
    lines += [t(ctx, f"Then: {x['invoice']}, due {x['due_when']}.", f"其次：{x['invoice']}，{x['due_when']}到期。") for x in late[1:4]]
    lines.append(t(ctx, "I have not contacted anyone.", "我没有联系任何人。"))
    return Turn(intent=Intent.RECONCILE, reply="\n".join(lines))


# ---------------------------------------------------------------- WHAT_IF reads


def late_payment(ctx: NlContext) -> Turn:
    """What a late payment means, from the forecast's own figures and no new projection: the payment, when the forecast
    counts it, the reserve and the lowest point ahead. FLOW does not re-run the forecast for a hypothetical delay."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.WHAT_IF)
    cash = h.get("cash") or {}
    r = h.get("receivables") or {}
    state = ctx.state()
    pay: dict[str, Any] | None = None
    bound = ctx.binding.invoice_id if ctx.binding is not None else None
    inv = next((x for x in state.receivables if x.id == bound and x.status != "SETTLED"), None)
    if inv is not None:
        buyer = next((c.name for c in state.counterparties if c.id == inv.counterparty_id), inv.counterparty_id)
        left = inv.face_fen - inv.settled_fen
        due = inv.issue_day + inv.terms_days
        pay = {"face_fen": left, "face_display": fmt_yuan(left), "due_day": due, "due_when": _when(due, h["day"], ctx.lang),
               "invoice": t(ctx, f"the {fmt_yuan(left)} invoice to {buyer}", f"开给{buyer}的 {fmt_yuan(left)} 发票")}
    else:
        pay = r.get("next_receipt")
    if pay is None:
        return Turn(intent=Intent.WHAT_IF, reply=t(
            ctx, "No payment is due, so there is nothing to be late. I have not changed anything.",
            "目前没有到期的款项，因此不存在延迟付款。我没有更改任何内容。"))
    if pay.get("due_day") is not None and pay["due_day"] < h["day"]:
        return Turn(intent=Intent.WHAT_IF, reply=t(
            ctx, f"{_cap(pay['invoice'])} is already late (due {pay['due_when']}). The forecast no longer counts on "
                 f"it. {_forecast(ctx, h)}",
            f"{pay['invoice']}已经逾期（{pay['due_when']}到期），预测已不再计入这笔款项。{_forecast(ctx, h)}"))
    which = t(ctx, "The payment in question" if inv is not None else "The next payment due", "所涉款项" if inv is not None else "下一笔到期款项")
    head = t(ctx, f"{which} is {pay['invoice']}, due {pay['due_when']}; the forecast counts it on that day. "
                  f"If it does not arrive, FLOW stops counting on it, checks your cash against your {cash.get('floor_short')} "
                  f"minimum and tells you what to do. I have not re-run the forecast for a late payment.",
             f"{which}是{pay['invoice']}，{pay['due_when']}到期，预测在当天计入这笔款项。若它没有到账，FLOW 会不再计入它，"
             f"对照您 {cash.get('floor_short')} 的最低现金储备重新检查，并告诉您该怎么办。我没有针对延迟付款重新做预测。")
    low_day, face, headroom, due_on = cash.get("lowest_day"), pay.get("face_fen"), cash.get("lowest_headroom_fen"), pay.get("due_day")
    low = t(ctx, f"Today's forecast bottoms out at {cash.get('lowest_short')} {cash.get('lowest_when')}.",
            f"当前预测的最低点是{cash.get('lowest_when')}的 {cash.get('lowest_short')}。")
    short = cash.get("lowest_headroom_short")
    verdict = ""
    if low_day is not None and face is not None and headroom is not None and due_on is not None:
        if headroom < 0:
            verdict = t(ctx, "Cash is already forecast to be below your minimum then, so a late payment would make that worse.",
                        "预测显示届时现金已低于最低储备，延迟付款会使情况更糟。")
        elif due_on > low_day:
            verdict = t(ctx, "That payment lands after the lowest point, so being late would not change the low.",
                        "这笔款项在最低点之后到账，延迟不会改变最低点。")
        elif face > headroom:
            verdict = t(ctx, f"That payment is bigger than the {short} of headroom you have at the lowest point, so if it "
                             f"had not arrived by then, cash would fall below your minimum {cash.get('lowest_when')}.",
                        f"这笔款项大于最低点处 {short} 的缓冲，若届时仍未到账，现金将在{cash.get('lowest_when')}跌破最低储备。")
        else:
            verdict = t(ctx, f"That payment is smaller than the {short} of headroom you have at the lowest point, so being "
                             f"late alone would not take cash below your minimum.",
                        f"这笔款项小于最低点处 {short} 的缓冲，仅凭延迟不会使现金跌破最低储备。")
    return Turn(intent=Intent.WHAT_IF, reply=_join([head, low, verdict], ctx.lang == "zh"))


def _violation_line(ctx: NlContext, v: Any) -> str:
    """A violation's own sentence (day numbers as distances from today), with its observed figure against its limit
    unless the sentence already says both."""
    base = ctx.reads.words(v.message, ctx.lang) if ctx.reads is not None else v.message
    said = all(x.lstrip("<>=≤≥ ") in base for x in (v.observed, v.limit) if x)
    if v.observed and v.limit and not said:
        base = f"{base} ({v.observed} against {v.limit})" if ctx.lang != "zh" else f"{base}（{v.observed}，限额 {v.limit}）"
    return base


def about(ctx: NlContext, v: Verdict) -> str:
    """The lead-in that names what an answer is about, when the page bound the deal: 'About the Foshan Home Retail Co.
    offer evaluated today: '. Empty when the verdict did not come from the page."""
    b = ctx.binding
    if b is None or b.verdict_id != v.id:
        return ""
    who = b.counterparty_name or t(ctx, "buyer's", "买方的")
    if b.received_day is None or b.received_day == ctx.day:
        when = t(ctx, "evaluated today", "今天评估")
    else:
        when = t(ctx, f"received {_when(b.received_day, ctx.day, 'en')}", f"{_when(b.received_day, ctx.day, 'zh')}收到")
    return t(ctx, f"About the {who} offer {when}: ", f"关于{who}的报价（{when}）：")


def accept_original(ctx: NlContext) -> Turn:
    """"What if I accept their original terms?": the verdict the page already holds on the offer as written, in words.
    Nothing is accepted, sent or booked."""
    vid = ctx.session.last_verdict_id
    v = ctx.store.get_verdict(vid) if vid else None
    if v is None:
        return Turn(intent=Intent.WHAT_IF, reply=t(
            ctx, "There is no evaluated offer to test yet. Open the offer on the Deals page, or evaluate one first; "
                 "nothing has been accepted.", "还没有已评估的报价可供测试。请先在“交易”页面打开报价或先评估一条报价；尚未接受任何内容。"))
    lead = about(ctx, v)
    cap = ctx.mandate().max_aggregate_forward_concession_fen
    if v.outcome == Outcome.ACCEPT:
        body = t(ctx, "FLOW would accept their original terms: they pass every check inside your limits.",
                 "FLOW 会接受其原始条款：它们通过了您授权范围内的所有检查。")
    elif v.outcome == Outcome.NEEDS_OWNER_APPROVAL:
        body = t(ctx, "Their original terms pass the checks but need your approval before anything is agreed.",
                 "其原始条款通过了检查，但需要您批准后才能达成。")
    elif v.outcome == Outcome.NO_VERDICT:
        body = t(ctx, "There is no verdict on their original terms: a term in the message was not clear enough to check.",
                 "对其原始条款没有结论：消息中有一项条款不够清晰，无法检查。")
    else:
        body = t(ctx, "FLOW would not accept their original terms as written.", "FLOW 不会按原样接受其原始条款。")
    lines = [lead + body]
    if v.outcome != Outcome.ACCEPT:
        lines += [f"- {_violation_line(ctx, x)}" for x in v.violations[:4]]
    if v.forward_concession_total_fen:
        lines.append(t(ctx, f"Forward concessions would total {fmt_yuan(v.forward_concession_total_fen)} against your "
                            f"{fmt_yuan(cap)} cap.", f"远期让步合计将达 {fmt_yuan(v.forward_concession_total_fen)}，您的上限为 {fmt_yuan(cap)}。"))
    if v.counters:
        lines.append(t(ctx, "What FLOW would offer instead: ", "FLOW 会改为提出：") + " ".join(f"{c.label}: {c.text}" for c in v.counters))
    lines.append(t(ctx, "Nothing has been accepted or sent.", "尚未接受或发送任何内容。"))
    return Turn(intent=Intent.WHAT_IF, reply="\n".join(lines), verdict=v)


# ---------------------------------------------------------------- EXPLAIN reads


def option(ctx: NlContext, v: Verdict, text: str) -> Turn:
    """"Why is Option A cheaper?": the counter's own price and reason, beside what their original terms would cost."""
    m = lx.OPTION_ASK.search(text)
    letter = next((g for g in (m.groups() if m else ()) if g), "").upper()
    counter = next((c for c in v.counters if letter and c.label.upper().endswith(letter)), v.counters[0] if v.counters else None)
    lead = about(ctx, v)
    if counter is None:
        return Turn(intent=Intent.EXPLAIN, verdict=v, reply=lead + t(
            ctx, "This verdict has no counter-offer, so there is no option to compare.", "此结论没有还价方案，因此没有可比较的选项。"))
    lines = [lead + f"{counter.label}: {counter.text}",
             t(ctx, f"It costs you {fmt_yuan(counter.supplier_cost_fen)} now.", f"它现在的成本为 {fmt_yuan(counter.supplier_cost_fen)}。"),
             t(ctx, "Why: ", "原因：") + counter.rationale]
    dearer = [x for x in v.violations if x.code.value in ("EARLY_PAY_DEARER_THAN_PLAN", "DISCOUNT_ABOVE_BREAK_EVEN")]
    if dearer:
        lines.append(t(ctx, "Their original terms, for comparison: ", "对比其原始条款：") + "; ".join(_violation_line(ctx, x) for x in dearer) + ".")
    lines.append(t(ctx, "Nothing has been sent.", "尚未发送任何内容。"))
    return Turn(intent=Intent.EXPLAIN, reply="\n".join(lines), verdict=v)


def plan_explain(ctx: NlContext) -> Turn:
    """"Why did FLOW choose this plan?": the Home read's recommended plan, its reason and its price."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.EXPLAIN)
    a = h.get("next_action")
    if not a:
        return Turn(intent=Intent.EXPLAIN, reply=t(ctx, "There is no funding plan to explain right now. ",
                                                   "目前没有需要说明的融资方案。") + _forecast(ctx, h))
    bits = [t(ctx, "FLOW's plan: ", "FLOW 的方案：") + str(a.get("title") or "")]
    if a.get("why"):
        bits.append(t(ctx, "Why: ", "原因：") + str(a["why"]))
    if a.get("cost_total_display"):
        lands = f" {a['lands_when']}" if a.get("lands_when") else ""
        bits.append(t(ctx, f"It costs {a['cost_total_display']} in all and the cash lands{lands}.",
                      f"总成本为 {a['cost_total_display']}，资金{a.get('lands_when') or ''}到账。"))
    if a.get("authority_text"):
        bits.append(str(a["authority_text"]))
    if a.get("if_nothing"):
        bits.append(t(ctx, "If you do nothing: ", "若不处理：") + str(a["if_nothing"]))
    if a.get("after"):
        bits.append(t(ctx, "After the plan: ", "执行方案后：") + str(a["after"]))
    ch = a.get("cheaper_option")
    if ch:
        bits.append(t(ctx, f"A cheaper option exists ({ch['cost_total_display']} in all) but it would need {ch['approvals']} "
                           f"separate approvals; this plan needs one.",
                      f"还有更便宜的方案（合计 {ch['cost_total_display']}），但需要 {ch['approvals']} 次单独批准；此方案只需一次。"))
    bits.append(t(ctx, "Nothing has been run.", "尚未执行任何操作。"))
    return Turn(intent=Intent.EXPLAIN, reply=_join(bits, ctx.lang == "zh"))


# ---------------------------------------------------------------- the one recovery


def recovery(ctx: NlContext) -> Turn:
    """An ordinary question FLOW has no read for: one way forward, not the list of everything it can do."""
    return Turn(intent=Intent.OUT_OF_SCOPE, reply=t(
        ctx, "I can answer questions about your cash, deals, approvals and what changed; try \"What changed today?\"",
        "我可以回答有关您的现金、交易、审批以及近期变化的问题；您可以试试问：“今天有什么变化？”"))
