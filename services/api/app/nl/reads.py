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

from app.api.presentation import buyer_of_receivable, invoice_words, party_name
from app.domain.models import Outcome, Verdict
from app.domain.money import fmt_yuan
from app.financial.lots import ensure_lots
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


def _said(ctx: NlContext, text: str) -> str:
    """An engine sentence in Business words (names for ids, distances from today, no status codes), as the Business pages say it."""
    return ctx.reads.words(text, ctx.lang) if ctx.reads is not None else text


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


# ---------------------------------------------------------------- the request's scope (a customer, an invoice, a negotiation)
#
# A read that lists per-customer rows keeps the scope's own rows and says it kept them (`ctx.scope_read = "filtered"`); a company-wide read
# says so (`"company"`), and the service then answers in the company scope instead of pretending to a narrower one.


def _scoped(ctx: NlContext) -> bool:
    return ctx.scope_customer is not None


def _who(ctx: NlContext) -> str:
    """The scope's buyer, said as the books name it."""
    return party_name(ctx.state(), ctx.scope_customer)


def _end(text: str) -> str:
    """One full stop at the end: a buyer's name that ends in "Co." takes no second."""
    return text.replace("..", ".") if text.endswith("..") else text


def _row_buyer(ctx: NlContext, row: dict[str, Any]) -> str | None:
    return row.get("buyer_id") or buyer_of_receivable(ctx.state(), row.get("receivable_id"))


def _mine(ctx: NlContext, row: dict[str, Any]) -> bool:
    """Whether a Home-read row belongs to the request's scope: its invoice when the scope names one, else its buyer. Everything when unscoped."""
    if not _scoped(ctx):
        return True
    ctx.scope_read = "filtered"
    if ctx.scope_invoice is not None and row.get("receivable_id"):
        return bool(row["receivable_id"] == ctx.scope_invoice)
    return _row_buyer(ctx, row) == ctx.scope_customer


def _mine_approval(ctx: NlContext, a: dict[str, Any]) -> bool:
    if not _scoped(ctx):
        return True
    ctx.scope_read = "filtered"
    return a.get("buyer_name") == _who(ctx)


def _mine_lots(ctx: NlContext, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The funding in transit that is against the scope's invoices (the Home read's rows are in the order of the unsettled lots)."""
    if not _scoped(ctx):
        return rows
    ctx.scope_read = "filtered"
    lots = sorted((x for x in ensure_lots(ctx.state()).lots if not x.settled), key=lambda x: (x.arrival_day, x.id))
    if len(lots) != len(rows):
        return []
    return [row for row, lot in zip(rows, lots, strict=True)
            if lot.receivable_id and (lot.receivable_id == ctx.scope_invoice if ctx.scope_invoice is not None
                                      else buyer_of_receivable(ctx.state(), lot.receivable_id) == ctx.scope_customer)]


def _next_due(ctx: NlContext, r: dict[str, Any], *, late_ok: bool = False) -> dict[str, Any] | None:
    """The next payment due: the company's, or the scope's own (its invoice, or its buyer's earliest unpaid invoice not yet due; with `late_ok`
    an invoice already late when it has none ahead)."""
    if not _scoped(ctx):
        return r.get("next_receipt")
    ctx.scope_read = "filtered"
    state = ctx.state()
    mine = [x for x in state.receivables if x.status != "SETTLED" and x.face_fen > x.settled_fen
            and (x.id == ctx.scope_invoice if ctx.scope_invoice is not None else x.counterparty_id == ctx.scope_customer)]
    ahead = [x for x in mine if x.issue_day + x.terms_days >= ctx.day]
    mine = ahead or (mine if late_ok else [])
    if not mine:
        return None
    first = min(mine, key=lambda x: (x.issue_day + x.terms_days, x.id))
    due = first.issue_day + first.terms_days
    return {"receivable_id": first.id, "invoice": invoice_words(state, first.id, ctx.lang), "due_day": due,
            "due_when": _when(due, ctx.day, ctx.lang), "face_fen": first.face_fen - first.settled_fen}


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
        lines.append(f"- {_sentence(_said(ctx, str(row.get('event_text') or row.get('text') or '')))} {_status_of(ctx, row)}")
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


_NUMBER_WORDS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")


def _count(n: int) -> str:
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else str(n)


def _lower_first(text: str) -> str:
    """"Rebate" -> "rebate", but "EBITDA" and a name stay as written."""
    return text[:1].lower() + text[1:] if len(text) > 1 and text[0].isupper() and text[1].islower() else text


def _topic(row: dict[str, Any]) -> str:
    """What a queue row is about in a word or two ("Rebate"): its `topic_text`, else the part of its subject after the customer."""
    return str(row.get("topic_text") or str(row.get("subject_text") or "").partition(" · ")[2]).strip()


def _queue_mine(ctx: NlContext, row: dict[str, Any]) -> bool:
    """Whether a Deals-queue row belongs to the request's scope: its invoice when the scope names one and the row has one, else its customer."""
    if not _scoped(ctx):
        return True
    ctx.scope_read = "filtered"
    if ctx.scope_invoice is not None and row.get("invoice_id"):
        return bool(row["invoice_id"] == ctx.scope_invoice)
    return bool(row.get("customer_id") == ctx.scope_customer)


def _queue_parts(ctx: NlContext, who: str, rows: list[dict[str, Any]]) -> list[str]:
    """The sentences' clauses for one customer's queue rows: what needs the owner, then what waits on the buyer or on FLOW's own funding."""
    zh = ctx.lang == "zh"
    parts: list[str] = []
    replies = [r for r in rows if r["kind"] == "DECISION"]
    if len(replies) == 1:
        topic = _topic(replies[0])
        parts.append(t(ctx, f"a reply to {who}{f' about the {_lower_first(topic)}' if topic else ''} needs you",
                       f"{who}{f'关于{topic}' if topic else ''}的答复需要您处理"))
    elif replies:
        parts.append(t(ctx, f"{_count(len(replies)).lower()} replies to {who} need you", f"{who}有 {len(replies)} 项答复需要您处理"))
    if any(r["kind"] == "SETUP" for r in rows):
        parts.append(t(ctx, f"{who}'s contract needs your review", f"{who}的合同需要您审核"))
    clarifying = [r for r in rows if r["kind"] == "BUYER_REPLY"]
    if len(clarifying) == 1:
        topic = _topic(clarifying[0])
        parts.append(t(ctx, f"FLOW is waiting for {who}'s clarification{f' on the {_lower_first(topic)}' if topic else ''}",
                       f"FLOW 正在等待{who}{f'就{topic}' if topic else ''}作出澄清"))
    elif clarifying:
        parts.append(t(ctx, f"FLOW is waiting for {who}'s clarification on {len(clarifying)} offers",
                       f"FLOW 正在等待{who}就 {len(clarifying)} 项报价作出澄清"))
    for r in rows:
        if r["kind"] == "PROMISE":
            status = _lower_first(str(r.get("status_text") or "")).replace(" · ", "，" if zh else ", ")
            parts.append(t(ctx, f"{who}'s promised payment is {status}", f"{who}承诺的付款：{status}"))
    return parts


def waiting(ctx: NlContext) -> Turn:
    """What is open. The replies that need the owner and what waits on the buyer are the Deals queue's own rows (app/api/worklist.py `queue`), said
    per customer ("Three replies to Foshan need you; FLOW is waiting for Foshan's clarification on the rebate."): a customer's own for a scope,
    every customer's company-wide. Beside them, from the Home read: the approvals waiting for the owner (the company plan's too, which the queue
    leaves to the alert), the funding in transit and the invoices still unpaid."""
    h = _home(ctx)
    q = ctx.reads.queue(ctx.lang) if ctx.reads is not None else None
    if h is None or q is None:
        return _unavailable(ctx, Intent.SHOW_STATUS)
    r = h.get("receivables") or {}
    zh = ctx.lang == "zh"
    rows = [x for tier in ("needs_you", "waiting", "agreements") for x in q.get(tier) or []
            if x["kind"] in ("DECISION", "SETUP", "BUYER_REPLY", "PROMISE") and _queue_mine(ctx, x)]
    by_customer: dict[str, list[dict[str, Any]]] = {}
    for x in rows:
        by_customer.setdefault(str(x["customer_id"]), []).append(x)
    lines: list[str] = []
    for a in h.get("approvals") or []:
        if _mine_approval(ctx, a):
            lines.append(t(ctx, "Waiting for your decision: ", "等待您的决定：") + _approval_line(ctx, a))
    for cid, group in by_customer.items():
        parts = _queue_parts(ctx, group[0].get("customer_short") or party_name(ctx.state(), cid), group)
        if parts:
            lines.append(_sentence(("；" if zh else "; ").join([_cap(parts[0]), *parts[1:]])))
    for lot in _mine_lots(ctx, ((h.get("cash") or {}).get("in_transit") or {}).get("lots") or []):
        lines.append(t(ctx, f"Waiting for funding to land: {lot['headline']}.", f"等待资金到账：{lot['headline']}。"))
    lines += [t(ctx, "Waiting for payment: ", "等待付款：") + _unpaid_line(ctx, x) for x in r.get("past_due") or [] if _mine(ctx, x)]
    if not lines:
        lines.append(_end(t(ctx, f"Nothing is waiting on you or on {_who(ctx)} right now.", f"目前没有在等待您或{_who(ctx)}的事项。"))
                     if _scoped(ctx) else t(ctx, "Nothing is waiting on you or on anyone else right now.", "目前没有在等待您或其他方的事项。"))
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(lines))


def owed(ctx: NlContext) -> Turn:
    """"Who owes us money?": what each customer still owes, largest first, with how much of it is overdue and when the next payment is due, from the
    books' unpaid invoices; the scope's own customer (or invoice) when the request has one. A promised early payment is said beside the customer
    that made it. Nothing is sent to anyone."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.SHOW_STATUS)
    state = ctx.state()
    zh = ctx.lang == "zh"
    unpaid = [x for x in state.receivables if x.status != "SETTLED" and x.face_fen > x.settled_fen
              and _mine(ctx, {"receivable_id": x.id, "buyer_id": x.counterparty_id})]
    if not unpaid:
        return Turn(intent=Intent.SHOW_STATUS, reply=_end(
            t(ctx, f"{_who(ctx)} owes you nothing right now.", f"{_who(ctx)}目前不欠您款项。") if _scoped(ctx)
            else t(ctx, "Nobody owes you anything right now.", "目前没有客户欠您款项。")))
    by_buyer: dict[str, list[Any]] = {}
    for x in unpaid:
        by_buyer.setdefault(x.counterparty_id, []).append(x)
    promised = (h.get("receivables") or {}).get("promised")
    rows = []
    for cid, invoices in by_buyer.items():
        total = sum(x.face_fen - x.settled_fen for x in invoices)
        late = [x for x in invoices if x.issue_day + x.terms_days < ctx.day]
        ahead = sorted((x for x in invoices if x.issue_day + x.terms_days >= ctx.day), key=lambda x: (x.issue_day + x.terms_days, x.id))
        late_fen = sum(x.face_fen - x.settled_fen for x in late)
        n = len(invoices)
        name = party_name(state, cid)
        bits = [t(ctx, f"{name} owes {fmt_yuan(total)} on {n} invoice{'' if n == 1 else 's'}",
                  f"{name}欠 {fmt_yuan(total)}，共 {n} 张发票")]
        if late:
            oldest = min(late, key=lambda x: (x.issue_day + x.terms_days, x.id))
            days = ctx.day - (oldest.issue_day + oldest.terms_days)
            bits.append(t(ctx, f"{fmt_yuan(late_fen)} of it is overdue, the oldest by {_days(days)}",
                          f"其中 {fmt_yuan(late_fen)} 已逾期，最久的逾期 {days} 天"))
        if ahead:
            due = ahead[0].issue_day + ahead[0].terms_days
            bits.append(t(ctx, f"the next payment is due {_when(due, ctx.day, 'en')}", f"下一笔{_when(due, ctx.day, 'zh')}到期"))
        if promised and promised.get("when") and buyer_of_receivable(state, promised.get("receivable_id")) == cid:
            bits.append(t(ctx, f"{promised['buyer_name']} has promised {promised['expected_display']} {promised['when']}",
                          f"{promised['buyer_name']}承诺{promised['when']}支付 {promised['expected_display']}"))
        rows.append((-late_fen, -total, cid, _sentence(("，" if zh else ", ").join(bits))))
    rows.sort()
    grand = sum(x.face_fen - x.settled_fen for x in unpaid)
    if _scoped(ctx):
        return Turn(intent=Intent.SHOW_STATUS, reply="\n".join(r[3] for r in rows))
    lead = t(ctx, f"{fmt_yuan(grand)} is owed to you across {len(rows)} customer{'' if len(rows) == 1 else 's'}.",
             f"共有 {len(rows)} 位客户欠您款项，合计 {fmt_yuan(grand)}。")
    return Turn(intent=Intent.SHOW_STATUS, reply="\n".join([lead, *(f"- {r[3]}" for r in rows)]))


def arrival(ctx: NlContext) -> Turn:
    """When money is due to land: funding in transit, what an approval would bring, a promised payment, the next invoice due."""
    h = _home(ctx)
    if h is None:
        return _unavailable(ctx, Intent.SHOW_STATUS)
    r = h.get("receivables") or {}
    lots = _mine_lots(ctx, ((h.get("cash") or {}).get("in_transit") or {}).get("lots") or [])
    approvals = [a for a in h.get("approvals") or [] if a.get("lands_text") and _mine_approval(ctx, a)]
    promised = r.get("promised") if r.get("promised") and _mine(ctx, r["promised"]) else None
    lines = [_sentence(str(lot["headline"])) for lot in lots]
    lines += [_join([str(a["headline"]), str(a["lands_text"])], ctx.lang == "zh") for a in approvals]
    if promised:
        lines.append(t(ctx, f"{promised['buyer_name']} has promised {promised['expected_display']} {promised['when']}.",
                       f"{promised['buyer_name']}承诺{promised['when']}支付 {promised['expected_display']}。"))
    if not (lots or approvals or promised):
        lines.append(_end(t(ctx, f"No funding is on its way for {_who(ctx)}.", f"目前没有与{_who(ctx)}相关的在途资金。")) if _scoped(ctx)
                     else t(ctx, "No funding is on its way.", "目前没有在途资金。"))
    nxt = _next_due(ctx, r)
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
    late = sorted((x for x in r.get("past_due") or [] if _mine(ctx, x)),
                  key=lambda x: (-int(x.get("face_fen") or 0), -int(x.get("days_late") or 0)))
    if not late:
        nxt = _next_due(ctx, r)
        tail = (t(ctx, f" The next payment due is {nxt['invoice']}, {nxt['due_when']}.",
                  f"下一笔到期的款项是{nxt['invoice']}，{nxt['due_when']}到期。") if nxt else "")
        none = (_end(t(ctx, f"Nothing is overdue from {_who(ctx)}.", f"{_who(ctx)}目前没有逾期款项。")) if _scoped(ctx)
                else t(ctx, "Nothing is overdue.", "目前没有逾期款项。"))
        return Turn(intent=Intent.RECONCILE, reply=none + tail)
    first = late[0]
    total = fmt_yuan(sum(int(x.get("face_fen") or 0) for x in late)) if _scoped(ctx) else r["overdue_total_display"]
    lines = [t(ctx, f"{total} is overdue across {len(late)} invoice{'' if len(late) == 1 else 's'}"
                    + ("." if _scoped(ctx) else f" ({r['open_total_display']} is open in all)."),
               f"共有 {len(late)} 张发票逾期，合计 {total}" + ("。" if _scoped(ctx) else f"（未收总额 {r['open_total_display']}）。")),
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
    if inv is None and _scoped(ctx):  # a customer's late payment is about its own next unpaid invoice, never the company's
        nxt = _next_due(ctx, r, late_ok=True)
        inv = next((x for x in state.receivables if nxt is not None and x.id == nxt["receivable_id"]), None)
        if inv is None:
            return Turn(intent=Intent.WHAT_IF, reply=t(
                ctx, f"No payment is due from {_who(ctx)}, so there is nothing to be late. I have not changed anything.",
                f"{_who(ctx)}目前没有到期的款项，因此不存在延迟付款。我没有更改任何内容。"))
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
