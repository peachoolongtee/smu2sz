"""The owner's chat in Business words (wayfinder #65 Wave 7, F28 and the design review): template strings only.

On an owner turn asked in Business mode (`POST /nl?mode=business`) the verdict, the funding plan and the confirmed run are said without
ids (FAC-IF, RCV-A, BUYER-1), tier words or reason codes: one outcome line, the plan in a few lines (amount, estimated cost, arrival) and
the confirm words. The raw replies stay as they are for the Demo and the audit; every figure here is read from the verdict, the typed
operations the plan will send and the cost the plan quoted, never computed. Nothing here evaluates, decides or executes: the same turn
ran, and only its `reply` is re-said.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.api.presentation import business_action, funding_lines, option_label, party_name, plural
from app.domain.models import DrawFacility, OperationStatus, SubmitInvoiceForFinancing
from app.domain.money import fmt_yuan
from app.nl import landing
from app.nl.context import NlContext
from app.nl.models import Intent
from app.nl.turn import Turn


def _t(ctx: NlContext, en: str, zh: str) -> str:
    return zh if ctx.lang == "zh" else en


def active(ctx: NlContext) -> bool:
    """Business mode: an owner turn whose request asked for it."""
    return ctx.owner_authenticated and ctx.reads is not None and bool(getattr(ctx.reads, "business", False))


def confirm_words(ctx: NlContext) -> str:
    return _t(ctx, 'Reply "Yes, run it" to run it.', "回复“好，执行”即可执行。")


_LAST_AMOUNT = re.compile(r"(¥[\d,]+\.\d{2})(?!.*¥)")


def _cost_of(label: str | None) -> int | None:
    """The total in a plan's label ("committed plan: ¥841.64 + ¥2,272.29 = ¥3,113.93" -> 311393): the router's own figure."""
    m = _LAST_AMOUNT.search(label or "")
    return round(float(m.group(1)[1:].replace(",", "")) * 100) if m else None


def _legs(ctx: NlContext, ops: Sequence[Any]) -> list[tuple[str, str | None, int, int | None]]:
    out: list[tuple[str, str | None, int, int | None]] = []
    for o in ops:
        if isinstance(o, DrawFacility):
            out.append(("DRAW", o.facility_id, o.amount_fen, landing.landing_day(ctx, o, executed=False)))
        elif isinstance(o, SubmitInvoiceForFinancing):
            out.append(("FINANCE_INVOICE", o.facility_id, o.advance_fen, landing.landing_day(ctx, o, executed=False)))
    return out


def _plan_sentences(ctx: NlContext, ops: Sequence[Any], cost_fen: int | None, *, past: bool = False) -> list[str]:
    return funding_lines(ctx.state(), _legs(ctx, ops), cost_fen, ctx.day, ctx.lang, past=past)


def _say(ctx: NlContext, lines: Sequence[str]) -> str:
    """Lines as one sentence: "Draws ¥1 today; requests ¥2, arriving in 3 days; estimated cost ¥3."."""
    if ctx.lang == "zh":
        return "；".join(lines) + "。"
    return "; ".join([lines[0], *(x[:1].lower() + x[1:] for x in lines[1:])]) + "." if lines else ""


def _months(ctx: NlContext) -> int:
    return max(1, round(ctx.mandate().forward_concession_horizon_days * 12 / 365))


def _whole(fen: int) -> str:
    text = fmt_yuan(fen)
    return text.removesuffix(".00")


def outcome_line(ctx: NlContext, v: Any) -> str:
    """"FLOW recommends a counter: the offer's future concessions cost ¥28,326.92 over the next 12 months, above your ¥5,000 limit.":
    the verdict's recommendation and the first thing in the way, in the owner's words."""
    action = business_action(v.outcome.value, len(v.counters))
    lead = {"accept": _t(ctx, "FLOW recommends accepting", "FLOW 建议接受"), "counter": _t(ctx, "FLOW recommends a counter", "FLOW 建议还价"),
            "decline": _t(ctx, "FLOW recommends declining", "FLOW 建议拒绝"),
            "needs_owner": _t(ctx, "This needs your approval", "这需要您批准"),
            "cannot": _t(ctx, "FLOW cannot decide this yet", "FLOW 暂时无法决定")}[action]
    first = v.violations[0] if v.violations else None
    if first is None:
        return lead + _t(ctx, ": the terms are within your limits.", "：条款在您的限额内。")
    code = first.code.value
    if code == "AGG_CONCESSION_EXCEEDED":
        cap = ctx.mandate().max_aggregate_forward_concession_fen
        return lead + _t(ctx, f": the offer's future concessions cost {fmt_yuan(v.forward_concession_total_fen)} over the next "
                              f"{_months(ctx)} months, above your {_whole(cap)} limit.",
                         f"：此报价的未来让步在未来 {_months(ctx)} 个月内共需 {fmt_yuan(v.forward_concession_total_fen)}，"
                         f"高于您 {_whole(cap)} 的上限。")
    if code == "RESERVE_BREACH":
        when = landing_when(ctx, first.day)
        cure = (_t(ctx, f" Funding to cover it would cost about {fmt_yuan(first.cure_cost_fen)}.",
                   f"为此融资约需 {fmt_yuan(first.cure_cost_fen)}。") if first.curable and first.cure_cost_fen else "")
        return lead + _t(ctx, f": cash would fall below your minimum {when}.{cure}", f"：现金将在{when}低于您的最低现金储备。{cure}")
    from app.api.presentation import business_text

    words = business_text(ctx.state(), first.message, ctx.day, ctx.lang) or first.message
    return lead + "：" + words.rstrip(".") + "。" if ctx.lang == "zh" else lead + ": " + words.rstrip(".") + "."


def landing_when(ctx: NlContext, day: int | None) -> str:
    from app.api.presentation import when_text

    return when_text(day, ctx.day, ctx.lang) if day is not None else ""


def _gate(ctx: NlContext, noted: bool) -> str:
    return _t(ctx, " Some of this needs your approval before it runs; it would wait in your approvals.",
              "其中一部分需要您批准后才会执行，会先放在待批事项中。") if noted else ""


def evaluate_reply(ctx: NlContext, turn: Turn) -> str | None:
    """The verdict on an offer with counters: the outcome line, what funding would follow each way, and the confirm words."""
    v, pending = turn.verdict, turn.pending
    if v is None or pending is None or pending.intent != Intent.NEGOTIATE:
        return None
    data = pending.data
    offer = ctx.store.get_offer(v.offer_id)
    who = party_name(ctx.state(), offer.counterparty_id) if offer is not None else _t(ctx, "the buyer", "买方")
    lines = [outcome_line(ctx, v)]
    first = v.counters[0].label if v.counters else None
    if first and data.get("accept_ops", {}).get(first):
        label = option_label(first, ctx.lang)
        body = _say(ctx, _plan_sentences(ctx, data["accept_ops"][first], _cost_of(data.get("accept_labels", {}).get(first))))
        lines.append(_t(ctx, f"If the buyer accepts {label}, the rest of the gap is funded: {body[:1].lower() + body[1:]}",
                        f"若买方接受{label}，其余缺口的融资：{body}"))
    if data.get("refuse_ops"):
        body = _say(ctx, _plan_sentences(ctx, data["refuse_ops"], _cost_of(data.get("refuse_label"))))
        lines.append(_t(ctx, f"If the buyer refuses, the gap is funded another way: {body[:1].lower() + body[1:]}",
                        f"若买方拒绝，缺口改用其他方式融资：{body}"))
    noted = bool(data.get("refuse_note") or any(data.get("accept_notes", {}).values()))
    names = [option_label(c.label, ctx.lang) for c in v.counters]
    stop = "" if who.endswith(".") else "."
    send = _t(ctx, f'Reply "Yes, run it" to send {" and ".join(names)} to {who}{stop} Nothing is sent before that.',
              f"回复“好，执行”即可向{who}发送{'、'.join(names)}；在此之前不会发送任何内容。")
    return "\n".join(lines) + _gate(ctx, noted) + "\n" + send


def plan_reply(ctx: NlContext, turn: Turn) -> str | None:
    """A funding plan waiting for the owner's yes: the amount, the estimated cost, the legs with their arrival, the confirm words."""
    pending = turn.pending
    legs = _legs(ctx, pending.ops) if pending is not None else []
    if pending is None or not legs:
        return None
    total = sum(a for _k, _f, a, _d in legs)
    cost = f"，预计成本 {fmt_yuan(pending.quoted_cost_fen)}" if pending.quoted_cost_fen is not None and ctx.lang == "zh" else (
        f", estimated cost {fmt_yuan(pending.quoted_cost_fen)}" if pending.quoted_cost_fen is not None else "")
    head = _t(ctx, f"FLOW's plan: {fmt_yuan(total)} of funding{cost}.", f"FLOW 的方案：融资 {fmt_yuan(total)}{cost}。")
    body = _say(ctx, _plan_sentences(ctx, pending.ops, None))
    noted = "approval" in turn.reply.lower() or "批准" in turn.reply
    return f"{head} {body}{_gate(ctx, noted)} {confirm_words(ctx)}" if ctx.lang != "zh" else f"{head}{body}{_gate(ctx, noted)}{confirm_words(ctx)}"


def done_reply(ctx: NlContext, turn: Turn) -> str | None:
    """A confirmed funding plan that ran in full: what was done, with the arrival and the quoted cost."""
    sent = [o for o in ctx.sent if landing.is_funding(o)]
    if not sent or len(ctx.results) < len(ctx.sent) or any(r.status != OperationStatus.EXECUTED for r in ctx.results):
        return None
    quoted = re.search(r"Cost as quoted: (¥[\d,]+\.\d{2})|费用与报价一致：(¥[\d,]+\.\d{2})", turn.reply)
    cost = (quoted.group(1) or quoted.group(2)) if quoted else None
    legs = [(k, f, a, landing.landing_day(ctx, o, executed=True)) for o in sent
            for k, f, a, _d in _legs(ctx, [o])]
    body = _say(ctx, funding_lines(ctx.state(), legs, None, ctx.day, ctx.lang, past=True))
    tail = _t(ctx, f" Cost as quoted {cost}." if cost else "", f"报价成本 {cost}。" if cost else "")
    return _t(ctx, f"Done. {body}{tail}", f"已完成。{body}{tail}")


def negotiated_reply(ctx: NlContext, turn: Turn) -> str | None:
    """The counters were sent and the simulated buyer answered: who accepted what, and the funding that ran, in a few lines."""
    neg, v = turn.negotiation, turn.verdict
    if neg is None or v is None or not ctx.results or any(r.status != OperationStatus.EXECUTED for r in ctx.results):
        return None
    offer = ctx.store.get_offer(v.offer_id)
    who = party_name(ctx.state(), offer.counterparty_id) if offer is not None else _t(ctx, "The buyer", "买方")
    funding = [o for o in ctx.sent if landing.is_funding(o)]
    legs = [(k, f, a, landing.landing_day(ctx, o, executed=True)) for o in funding for k, f, a, _d in _legs(ctx, [o])]
    ran = _say(ctx, funding_lines(ctx.state(), legs, None, ctx.day, ctx.lang, past=True)) if legs else ""
    if neg.get("outcome") == "ACCEPT":
        label = option_label(neg.get("accepted_counter"), ctx.lang)
        head = _t(ctx, f"{who} accepted {label} and the agreement is recorded.", f"{who}接受了{label}，协议已记录。")
    elif neg.get("outcome") == "NO_DEAL" and legs:
        head = _t(ctx, f"{who} did not accept, so the gap was funded another way.", f"{who}未接受，缺口已改用其他方式融资。")
    else:
        return None
    return f"{head} {ran}" if ctx.lang != "zh" and ran else (head + ran)


def rewrite(ctx: NlContext, turn: Turn) -> Turn:
    """Say the owner's reply in Business words when the turn asked for them; any other turn is returned as it is."""
    if not active(ctx) or turn.guarded:
        return turn
    reply: str | None = None
    if turn.intent == Intent.EVALUATE_OFFER and turn.awaiting:
        reply = evaluate_reply(ctx, turn)
    elif turn.intent == Intent.FUND_GAP and turn.awaiting:
        reply = plan_reply(ctx, turn)
    elif turn.intent == Intent.FUND_GAP and turn.clear_pending:
        reply = done_reply(ctx, turn)
    elif turn.intent == Intent.NEGOTIATE and turn.clear_pending:
        reply = negotiated_reply(ctx, turn)
    if reply is not None:
        turn.reply = plural(reply)
    return turn
