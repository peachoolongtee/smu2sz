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

from app.api.presentation import (
    business_action,
    facility_name,
    funding_lines,
    invoice_words,
    leg_words,
    option_label,
    party_name,
    plural,
)
from app.domain.models import (
    ApplyForFacility,
    DrawFacility,
    OperationStatus,
    RepayFacility,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_yuan
from app.financial.lots import ensure_lots, first_unsettled
from app.nl import landing
from app.nl.context import NlContext
from app.nl.models import Clarification, ClarifyOption, Intent
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


def _legs(ctx: NlContext, ops: Sequence[Any], *, executed: bool = False) -> list[tuple[str, str | None, int, int | None]]:
    out: list[tuple[str, str | None, int, int | None]] = []
    for o in ops:
        if isinstance(o, DrawFacility):
            out.append(("DRAW", o.facility_id, o.amount_fen, landing.landing_day(ctx, o, executed=executed)))
        elif isinstance(o, SubmitInvoiceForFinancing):
            out.append(("FINANCE_INVOICE", o.facility_id, o.advance_fen, landing.landing_day(ctx, o, executed=executed)))
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


def _reason(ctx: NlContext, v: Any, x: Any) -> str:
    """One thing in the way of a verdict, in the owner's words and without the capital or the full stop."""
    code = x.code.value
    if code == "AGG_CONCESSION_EXCEEDED":
        cap = ctx.mandate().max_aggregate_forward_concession_fen
        return _t(ctx, f"the offer's future concessions cost {fmt_yuan(v.forward_concession_total_fen)} over the next {_months(ctx)} months, "
                       f"above your {_whole(cap)} limit",
                  f"此报价的未来让步在未来 {_months(ctx)} 个月内共需 {fmt_yuan(v.forward_concession_total_fen)}，高于您 {_whole(cap)} 的上限")
    if code == "RESERVE_BREACH":
        when = landing_when(ctx, x.day)
        return _t(ctx, f"cash would fall below your minimum {when}", f"现金将在{when}低于您的最低现金储备")
    from app.api.presentation import business_text

    words = business_text(ctx.state(), x.message, ctx.day, ctx.lang) or x.message
    return words.rstrip(".。")


def explain_reply(ctx: NlContext, turn: Turn) -> str | None:
    """"Why are we countering this?": the outcome in one line (every reason the verdict names that has a plain wording) and the
    recommended response in one line, nothing else."""
    v = turn.verdict
    if v is None:
        return None
    action = business_action(v.outcome.value, len(v.counters))
    lead = outcome_lead(ctx, action)
    known = [x for x in v.violations if x.code.value in ("AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH")] or list(v.violations[:1])
    reasons = [_reason(ctx, v, x) for x in known]
    if reasons:
        joined = _t(ctx, ", and ", "，并且").join(reasons)
        line = lead + _t(ctx, ": ", "：") + joined + _t(ctx, ".", "。")
    else:
        line = lead + _t(ctx, ": the terms are within your limits.", "：条款在您的限额内。")
    label = option_label(v.counters[0].label, ctx.lang) if v.counters else ""
    response = {"accept": _t(ctx, "accept the offer", "接受报价"),
                "counter": _t(ctx, f"send {label} to the buyer", f"向买方发送{label}"),
                "decline": _t(ctx, "decline the offer", "拒绝报价"),
                "needs_owner": _t(ctx, "ask for your approval first", "先征得您的批准"),
                "cannot": _t(ctx, "wait: FLOW cannot decide this yet", "等待：FLOW 暂时无法决定")}[action]
    return line + "\n" + _t(ctx, f"Recommended response: {response}.", f"建议的回应：{response}。")


_RAW_VOICE = re.compile(r"\bVerdict [A-Z]|\bTIER_\d|\b[A-Z][A-Z_]{5,}\b")


def outcome_lead(ctx: NlContext, action: str) -> str:
    return {"accept": _t(ctx, "FLOW recommends accepting", "FLOW 建议接受"), "counter": _t(ctx, "FLOW recommends a counter", "FLOW 建议还价"),
            "decline": _t(ctx, "FLOW recommends declining", "FLOW 建议拒绝"),
            "needs_owner": _t(ctx, "This needs your approval", "这需要您批准"),
            "cannot": _t(ctx, "FLOW cannot decide this yet", "FLOW 暂时无法决定")}[action]


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


# ---------------------------------------------------------------- alert cures, repayments, approvals and the status read (map #65 debt, ticket #83)
# The same rule as above: the turn that ran said its reply in the engine's words; these say it again without ids, tier words or codes. The
# figures are the ones the turn carried (`Turn.facts`, the plan that was shown, the operations that were sent and what the executor answered);
# the approval id stays in a parenthesis where the owner's next "yes" needs it (`service._remember_shown` finds it there).

_VOID_LEADS = ("I did not run it:", "我没有执行：")
_IDS = re.compile(r"\b(?:FAC-[A-Z]+|RCV-[A-Z]+|RI:\S+|BUYER-\d+)\b")


def _void_line(ctx: NlContext) -> str:
    """The notice in front of a fresh proposal, without the engine's reason: nothing ran, and the plan below is the one on today's books."""
    return _t(ctx, "Nothing was run: the books changed since I proposed it. Here is a fresh proposal.",
              "未执行任何操作：自我提出方案以来账目已变化。以下是新的方案。")


def approve_words(ctx: NlContext) -> str:
    """The words that approve what this session just showed. "Yes, run it" confirms a plan; an approval that waits in the queue is decided
    only by the word approve (`consent.bare_verdict`: "approve it" binds to the one item just shown) or by its id. "Yes, do it" does not
    approve it, so a retried "go ahead" cannot approve the leg the first one queued."""
    return _t(ctx, 'Reply "Approve it" to approve it.', "回复“批准”即可批准。")


def _join(ctx: NlContext, *parts: str) -> str:
    """Sentences as one reply: spaced in English, run together in Chinese."""
    return (" " if ctx.lang != "zh" else "").join(p for p in parts if p)


def _fac(ctx: NlContext, facility_id: str | None) -> str:
    return facility_name(ctx.state(), facility_id)


def _op_sentences(ctx: NlContext, ops: Sequence[Any], *, past: bool = False, executed: bool = False) -> list[str]:
    """One short sentence per operation, in order, without the cost: "Draws ¥1 on the Bank credit line today", "Repays ¥2 on the Bank
    credit line today". A draw or an advance says when its cash arrives; a repayment and an application are said by their own words."""
    out: list[str] = []
    for o in ops:
        if isinstance(o, DrawFacility | SubmitInvoiceForFinancing):
            out += funding_lines(ctx.state(), _legs(ctx, [o], executed=executed), None, ctx.day, ctx.lang, past=past)
        elif isinstance(o, RepayFacility):
            fac, money = _fac(ctx, o.facility_id), fmt_yuan(o.amount_fen)
            out.append(_t(ctx, f"{'Repaid' if past else 'Repays'} {money} on the {fac}" + ("" if past else " today"),
                          f"{'已' if past else '今天'}向{fac}还款 {money}"))
        elif isinstance(o, ApplyForFacility):
            fac, money = _fac(ctx, o.facility_id), fmt_yuan(o.amount_fen)
            out.append(_t(ctx, f"{'Applied' if past else 'Applies'} for {money} on the {fac}", f"{'已' if past else ''}申请{fac} {money}"))
    return out


def _cost_line(ctx: NlContext, cost_fen: int | None) -> str:
    return _t(ctx, f"Estimated cost {fmt_yuan(cost_fen)}", f"预计成本 {fmt_yuan(cost_fen)}") if cost_fen is not None else ""


def _body(ctx: NlContext, sentences: Sequence[str]) -> str:
    """The sentences as one, with its full stop."""
    return _say(ctx, [x for x in sentences if x])


def _list(ctx: NlContext, sentences: Sequence[str]) -> str:
    """The sentences as one phrase to embed in another sentence: no full stop."""
    return _body(ctx, sentences).rstrip(".。")


def _outcome(ctx: NlContext, f: dict[str, Any]) -> str:
    """The alert in one line: what is wrong with the owner's cash, or what can be repaid."""
    if f.get("cure") == "repay":
        money, fac = fmt_yuan(f.get("amount_fen") or 0), _fac(ctx, f.get("facility_id"))
        return _t(ctx, f"The {money} drawn on the {fac} can be repaid today, and cash stays above your minimum.",
                  f"{fac}已提取的 {money} 今天可以还清，现金仍高于您的最低现金储备。")
    if f.get("zero_day") is not None:
        when = landing_when(ctx, f["zero_day"])
        return _t(ctx, f"Cash would go below zero {when}.", f"现金将在{when}降到零以下。")
    short, when = fmt_yuan(f.get("shortfall_fen") or 0), landing_when(ctx, f.get("day"))
    return _t(ctx, f"Cash would fall {short} below your minimum {when}.", f"现金将在{when}比您的最低现金储备低 {short}。")


def _plan_head(ctx: NlContext, ops: Sequence[Any], cost_fen: int | None) -> str:
    """"FLOW's plan: ¥405,000.00 of funding, estimated cost ¥3,113.93." for borrowing; "FLOW's plan:" alone for a repayment."""
    legs = _legs(ctx, ops)
    if not legs:
        return _t(ctx, "FLOW's plan:", "FLOW 的方案：")
    total = sum(a for _k, _f, a, _d in legs)
    cost = (_t(ctx, f", estimated cost {fmt_yuan(cost_fen)}", f"，预计成本 {fmt_yuan(cost_fen)}") if cost_fen is not None else "")
    return _t(ctx, f"FLOW's plan: {fmt_yuan(total)} of funding{cost}.", f"FLOW 的方案：融资 {fmt_yuan(total)}{cost}。")


def _proposal(ctx: NlContext, outcome: str, ops: Sequence[Any], cost_fen: int | None, *, noted: bool, tail: str = "") -> str:
    plan = _join(ctx, _plan_head(ctx, ops, cost_fen), _body(ctx, _op_sentences(ctx, ops)))
    return _join(ctx, outcome, plan + _gate(ctx, noted) + tail, confirm_words(ctx))


def alerts_reply(ctx: NlContext, turn: Turn) -> str | None:
    """"What needs me today?" with a cure to propose, a cure already waiting for the owner, or a cure that just ran."""
    f = turn.facts
    if not f:
        return _scrub(ctx, turn.reply)
    pending = turn.pending
    if turn.awaiting and pending is not None and pending.ops:
        residual = "" if f.get("restores", True) else _t(
            ctx, " This does not restore your minimum in full; the rest needs your decision.",
            "这不能完全恢复您的最低现金储备，其余部分需要您来决定。")
        return _proposal(ctx, _outcome(ctx, f), pending.ops, pending.quoted_cost_fen, noted=bool(f.get("needs_owner")), tail=residual)
    if f.get("waiting"):
        op, cost = f.get("waiting_op"), f.get("waiting_cost_fen")
        what = _list(ctx, _op_sentences(ctx, [op]) + ([_cost_line(ctx, cost)] if cost is not None else [])) if op is not None else ""
        return _join(ctx, _outcome(ctx, f),
                     _t(ctx, f"The plan is already waiting for your approval ({f['waiting']})" + (f": {what[:1].lower() + what[1:]}" if what else "")
                        + ". Nothing has run yet.", f"该方案已在等待您批准（{f['waiting']}）" + (f"：{what}" if what else "") + "。尚未执行。"),
                     approve_words(ctx))
    if ctx.sent and "cure" in f:
        return _cure_run(ctx, turn)
    if f.get("no_cure"):
        return _join(ctx, _outcome(ctx, f), _t(ctx, "No committed facility can cover it, so FLOW cannot fix it on its own; this needs your decision.",
                                               "没有已承诺的额度可以覆盖，FLOW 无法自行处理；需要您来决定。"))
    return _summary(ctx, f)


def _summary(ctx: NlContext, f: dict[str, Any]) -> str | None:
    """What needs the owner when there is no cure to propose: the invoices that did not arrive, the mandate, and the other alerts' titles."""
    parts: list[str] = []
    state = ctx.state()
    for d in f.get("past_due") or []:
        inv, money = invoice_words(state, d["receivable_id"], ctx.lang), fmt_yuan(d["amount_fen"])
        if d["early_pay"]:
            promised, due = landing_when(ctx, d["promised_day"]), landing_when(ctx, d["original_due_day"])
            parts.append(_t(ctx, f"The early payment promised on {inv} for {promised} did not arrive; {money} is outstanding and back on its "
                                 f"original due date ({due}).",
                            f"{inv}的提前付款承诺（{promised}）未兑现；{money} 仍未收到，已回到原到期日（{due}）。"))
        else:
            parts.append(_t(ctx, f"{money} on {inv} was due {landing_when(ctx, d['due_day'])} and has not arrived.",
                            f"{inv}的 {money} 应于{landing_when(ctx, d['due_day'])}到账，至今未到。"))
    m = f.get("mandate")
    if m is not None:
        when = landing_when(ctx, m["expires_day"])
        parts.append(_t(ctx, f"Your mandate {'expired' if m['critical'] else 'expires'} {when}, so FLOW can no longer act until you sign a new one. "
                             "Renewal is an offline step for you." if m["critical"] else
                        f"Your mandate expires {when}; after that FLOW can no longer act. Renewal is an offline step for you.",
                        f"您的授权已于{when}到期，在您签署新授权之前 FLOW 无法再执行任何操作。续期需要您线下完成。" if m["critical"] else
                        f"您的授权将在{when}到期；之后 FLOW 将无法执行任何操作。续期需要您线下完成。"))
    others = [(ctx.reads.words(x, ctx.lang) if ctx.reads is not None else x) for x in f.get("others") or []]
    if others:
        n = len(others) + int(f.get("more") or 0)
        parts.append(_t(ctx, f"{n} more {'warning' if n == 1 else 'warnings'}: " + "; ".join(x.rstrip('.') for x in others) + ".",
                        f"另有 {n} 项提醒：" + "；".join(x.rstrip("。") for x in others) + "。"))
    return _join(ctx, *parts) or None


def _scrub(ctx: NlContext, text: str) -> str | None:
    """A reply with no structured figures behind it (past-due invoices, an expiring mandate) that still names an invoice or a facility by
    id: said through the same Business wording the pages use (names for ids, distances from today)."""
    if ctx.reads is None or not _IDS.search(text):
        return None
    return ctx.reads.words(text, ctx.lang) or None

def _cure_run(ctx: NlContext, turn: Turn) -> str | None:
    """The owner said go ahead on an alert's cure: what ran, what waits for the owner (with its approval id in a parenthesis), what was refused."""
    f = turn.facts
    plan = ctx.session.pending_plan  # the confirmed plan: the session drops it once the turn is over
    sent, results = list(ctx.sent), list(ctx.results)
    if not sent or len(sent) != len(results):
        return None
    mine = plan is not None and plan.intent == turn.intent
    quoted = plan.quoted_cost_fen if mine and plan is not None else None
    whole = list(plan.ops) if mine and plan is not None else sent
    ran = [o for o, r in zip(sent, results, strict=True) if r.status == OperationStatus.EXECUTED
           or (r.status == OperationStatus.DUPLICATE and r.approval_id is None)]
    stuck = next(((o, r) for o, r in zip(sent, results, strict=True) if o not in ran), None)
    unsent = [o for o in whole if o not in sent]
    done = _list(ctx, _op_sentences(ctx, ran, past=True, executed=True)) if ran else ""
    cleared = f.get("cleared")
    if stuck is None and not unsent:
        repay = f.get("cure") == "repay"
        what = _t(ctx, "Interest as quoted", "利息与报价一致：") if repay else _t(ctx, "Cost as quoted", "报价成本 ")
        cost = (f" {what} {fmt_yuan(quoted)}." if ctx.lang != "zh" else f"{what}{fmt_yuan(quoted)}。") if quoted is not None else ""
        end = (_t(ctx, " That covers the shortfall.", "缺口已补上。") if cleared and not repay else
               _t(ctx, " The line is repaid.", "该额度已还清。") if cleared else
               _t(ctx, " The shortfall is not fully covered yet.", "缺口尚未完全补上。") if cleared is False and not repay else "")
        return _t(ctx, f"Done. {done}.{cost}{end}", f"已完成。{done}。{cost}{end}")
    parts: list[str] = [_t(ctx, f"Done so far: {done}.", f"目前已完成：{done}。")] if done else []
    if stuck is not None:
        o, r = stuck
        what = _list(ctx, _op_sentences(ctx, [o]))
        if r.status == OperationStatus.PENDING_APPROVAL or (r.status == OperationStatus.DUPLICATE and r.approval_id):
            whole_plan = len(whole) > 1  # the quote is the plan's total, not this leg's
            est = (_t(ctx, f" The plan's estimated cost is {fmt_yuan(quoted)} in all." if whole_plan else f" Estimated cost {fmt_yuan(quoted)}.",
                      f"整个方案的预计成本为 {fmt_yuan(quoted)}。" if whole_plan else f"预计成本 {fmt_yuan(quoted)}。")
                   if quoted is not None else "")
            parts.append(_t(ctx, f"This needs your approval before it runs ({r.approval_id}): {what[:1].lower() + what[1:]}.{est}"
                                 f" I have not run it.", f"这需要您批准后才会执行（{r.approval_id}）：{what}。{est}我尚未执行。"))
            tail = approve_words(ctx)
        else:
            reason = _reason_of(ctx, r.message)
            parts.append(_t(ctx, f"I could not run it: {reason}. Nothing else was run.", f"未能执行：{reason}。其余均未执行。"))
            tail = ""
    else:
        tail = ""
    if unsent and stuck is not None:
        left = _list(ctx, _op_sentences(ctx, unsent))
        parts.append(_t(ctx, f"Not sent: {left[:1].lower() + left[1:]}.", f"未发送：{left}。"))
    return _join(ctx, *parts, tail)


def _reason_of(ctx: NlContext, message: str) -> str:
    """Why the executor refused, in the owner's words: its sentence through the Business wording, without "Refused:" or the full stop."""
    said = (ctx.reads.words(message, ctx.lang) if ctx.reads is not None else message) or message
    for lead in ("Refused: ", "已拒绝："):
        said = said.removeprefix(lead)
    return said.rstrip(".。")


def _in_transit(ctx: NlContext, facility_id: str) -> str:
    """What is on a facility but has not landed (it cannot be repaid before it does), in the owner's words; empty when all has landed."""
    lots = ensure_lots(ctx.state()).lots
    first = first_unsettled(lots, facility_id)
    if first is None:
        return ""
    fen = sum(lot.remaining_fen for lot in lots if lot.facility_id == facility_id and not lot.settled)
    fac, when = _fac(ctx, facility_id), landing_when(ctx, first.arrival_day)
    return _t(ctx, f"A further {fmt_yuan(fen)} on the {fac} arrives {when} and cannot be repaid before then.",
              f"{fac}另有 {fmt_yuan(fen)} 将在{when}到账，到账前不能偿还。")


def repay_reply(ctx: NlContext, turn: Turn) -> str | None:
    """A repayment proposed, blocked or run."""
    f = turn.facts
    pending = turn.pending
    kind = f.get("repay")
    fac = _fac(ctx, f.get("facility_id"))
    transit = _in_transit(ctx, f["facility_id"]) if f.get("facility_id") else ""
    if kind == "proposal" and turn.awaiting and pending is not None:
        money = fmt_yuan(f.get("amount_fen") or 0)
        outcome = _t(ctx, f"You can repay {money} on the {fac} today, and cash stays above your minimum.",
                     f"您今天可以向{fac}还款 {money}，现金仍高于最低现金储备。")
        return _join(ctx, outcome, _plan_head(ctx, pending.ops, None), _body(ctx, _op_sentences(ctx, pending.ops)), transit,
                     confirm_words(ctx))
    if kind == "blocked":
        low, safe = fmt_yuan(f.get("low_after_fen") or 0), f.get("safe_fen") or 0
        hint = (_t(ctx, f"The most I can repay now without going below it is {fmt_yuan(safe)}.", f"目前在不低于它的前提下最多可偿还 {fmt_yuan(safe)}。")
                if safe > 0 else _t(ctx, "Repay when the receivable pays.", "请在应收款到账后再偿还。"))
        return _join(ctx, _t(ctx, f"I have not repaid anything: that would take cash to {low}, below your minimum.",
                             f"我没有还款：这会使现金降到 {low}，低于您的最低现金储备。"), hint, transit)
    if kind == "nothing_landed":
        return _join(ctx, _t(ctx, f"Nothing has arrived on the {fac} yet, so there is nothing to repay.", f"{fac}上还没有资金到账，因此没有可偿还的金额。"), transit)
    sent = [o for o in ctx.sent if isinstance(o, RepayFacility)]
    if not sent or len(ctx.results) != len(ctx.sent):
        return None
    op, r = sent[0], ctx.results[ctx.sent.index(sent[0])]
    left = _in_transit(ctx, op.facility_id)
    if r.status == OperationStatus.EXECUTED:
        interest = re.search(r"with interest (¥[\d,]+\.\d{2})", r.message)
        extra = _t(ctx, f", interest {interest.group(1)}", f"，利息 {interest.group(1)}") if interest else ""
        return _join(ctx, _t(ctx, f"Done. {_op_sentences(ctx, [op], past=True)[0]}{extra}.", f"已完成。{_op_sentences(ctx, [op], past=True)[0]}{extra}。"), left)
    if r.status == OperationStatus.PENDING_APPROVAL:
        return _join(ctx, _t(ctx, f"This needs your approval before it runs ({r.approval_id}): {_op_sentences(ctx, [op])[0].lower()}. I have not run it.",
                             f"这需要您批准后才会执行（{r.approval_id}）：{_op_sentences(ctx, [op])[0]}。我尚未执行。"), approve_words(ctx))
    return _t(ctx, f"I could not repay: {_reason_of(ctx, r.message)}.", f"未能还款：{_reason_of(ctx, r.message)}。")


def _approval_label(ctx: NlContext, rec: Any) -> str:
    """One queued approval in a few words, with its id in a parenthesis: "Finance ¥80,000.00 of the invoice to X on Y (APR-000001)"."""
    from app.api.quotes import op_leg
    from app.operations.log import parse_operation

    op = parse_operation(rec.op_json)
    if op is None:  # a payload that is not a typed operation: the queue's own reason, in the owner's words
        words = (ctx.reads.words(rec.reason, ctx.lang) if ctx.reads is not None else rec.reason).rstrip(".。")
    else:
        facility_id, receivable_id, amount = op_leg(op)
        words = leg_words(ctx.state(), op.kind, facility_id, receivable_id, amount, ctx.lang)
    return f"{words} ({rec.id})"


def approval_reply(ctx: NlContext, turn: Turn) -> str | None:
    """An owner decision on a queued approval: approved and run, approved but refused, declined, or not possible."""
    f = turn.facts
    kind = f.get("approval")
    aid = f.get("id")
    if kind == "unknown":
        return _t(ctx, "I cannot find that approval in your queue; nothing was changed.", "我在您的待批队列中找不到该事项；未做任何更改。")
    if kind == "already":
        return _t(ctx, "That approval was already decided; nothing was changed.", "该事项已处理；未做任何更改。")
    if kind != "decided":
        return None
    if not f.get("owner"):
        return _t(ctx, f"Only you can decide this, and this request carries no owner credential. Nothing was changed ({aid}).",
                  f"只有您本人可以决定此事，而此请求没有业主凭证。未做任何更改（{aid}）。")
    op, status = f.get("op"), f.get("status")
    planned = _list(ctx, _op_sentences(ctx, [op], executed=True)) if op is not None else ""
    if not f.get("approve"):
        said = _t(ctx, f"Declined. Nothing was run ({aid}).", f"已拒绝。未执行任何操作（{aid}）。")
    elif status == OperationStatus.EXECUTED and op is not None:
        past = _list(ctx, _op_sentences(ctx, [op], past=True, executed=True))
        said = _t(ctx, f"Approved and done. {past}.", f"已批准并完成。{past}。")
    elif status == OperationStatus.REFUSED:
        said = _t(ctx, f"You approved it, but it could not run: {_reason_of(ctx, f.get('message') or '')}. Nothing was changed.",
                  f"您已批准，但未能执行：{_reason_of(ctx, f.get('message') or '')}。未做任何更改。")
    else:
        said = (ctx.reads.words(f.get("message") or "", ctx.lang) if ctx.reads is not None else "") or planned
    rest = [a for a in ctx.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING" and a.id != aid]
    if rest:
        said = _join(ctx, said, _t(ctx, "Still waiting for your decision: ", "仍待您审批：") + _t(ctx, "; ", "；").join(_approval_label(ctx, a) for a in rest) + _t(ctx, ".", "。"))
    return said


def approval_choice_reply(ctx: NlContext, turn: Turn) -> str | None:
    """"Which pending operation?": each option in a few words, its approval id in a parenthesis."""
    pc, clarification = turn.pending_clarification, turn.clarification
    if pc is None or clarification is None:
        return None
    options = []
    for option in clarification.options:
        rec = ctx.store.get_approval(str(pc.values.get(option.id)))
        options.append(ClarifyOption(id=option.id, label=_approval_label(ctx, rec) if rec is not None else option.label))
    turn.clarification = Clarification(question=clarification.question, options=options)
    pc.options = options
    return clarification.question + " " + " ".join(f"({o.id}) {o.label}" for o in options)


def status_reply(ctx: NlContext, turn: Turn) -> str | None:
    """"Show cash status" in the owner's words: cash against the minimum, the days it would fall short, the covenants, the concessions given,
    what is drawn and what waits for the owner. Each figure is the one the raw status carried."""
    s = turn.facts.get("status")
    if not s:
        return None
    lines = [_t(ctx, f"Cash today is {fmt_yuan(s['cash_fen'])}; your minimum cash reserve is {fmt_yuan(s['floor_fen'])}.",
                f"今天现金 {fmt_yuan(s['cash_fen'])}；您的最低现金储备为 {fmt_yuan(s['floor_fen'])}。")]
    if s["gaps"]:
        short = [_t(ctx, f"{fmt_yuan(shortfall)} short {landing_when(ctx, day)}", f"{landing_when(ctx, day)}缺 {fmt_yuan(shortfall)}")
                 for _low, day, shortfall in s["gaps"]]
        lines.append(_t(ctx, "Cash would fall below your minimum: " + "; ".join(short) + ".", "现金将低于最低现金储备：" + "；".join(short) + "。"))
    else:
        low_fen, low_day = s["lowest"]
        at = landing_when(ctx, low_day) if low_day >= ctx.day else ""
        lines.append(_t(ctx, f"Cash stays at or above your minimum through the forecast; the lowest point is {fmt_yuan(low_fen)}" + (f" {at}" if at else "") + ".",
                        f"预测期内现金始终不低于最低现金储备；最低点为 {fmt_yuan(low_fen)}" + (f"（{at}）" if at else "") + "。"))
    if s.get("dscr"):
        value, month, floor = s["dscr"]
        lines.append(_t(ctx, f"Debt service cover (DSCR) is lowest at {value}× in month {month}; your minimum is {floor}×.",
                        f"偿债覆盖率（DSCR）最低 {value}×（第 {month} 月），下限 {floor}×。"))
    if s.get("leverage"):
        value, month, top = s["leverage"]
        lines.append(_t(ctx, f"Leverage is highest at {value}× in month {month}; your maximum is {top}×.",
                        f"杠杆率最高 {value}×（第 {month} 月），上限 {top}×。"))
    given, cap = s["concessions"]
    lines.append(_t(ctx, f"Future concessions given: {fmt_yuan(given)} of your {_whole(cap)} limit.", f"已给出的远期让步：{fmt_yuan(given)}，上限 {_whole(cap)}。"))
    if s["drawn"]:
        drawn = [_t(ctx, f"{fmt_yuan(fen)} on the {_fac(ctx, fid)}", f"{_fac(ctx, fid)} {fmt_yuan(fen)}") for fid, fen in s["drawn"]]
        lines.append(_t(ctx, "Drawn: " + ", ".join(drawn) + ".", "已提款：" + "、".join(drawn) + "。"))
    if s["pending"]:
        n = len(s["pending"])  # an approval's id belongs to the record, not to the owner's sentence
        lines.append(_t(ctx, f"{n} {'item waits' if n == 1 else 'items wait'} for your approval.", f"{n} 项待您审批。"))
    return "\n".join(lines)


def rewrite(ctx: NlContext, turn: Turn) -> Turn:
    """Say the owner's reply in Business words when the turn asked for them; any other turn is returned as it is."""
    if not active(ctx) or turn.guarded:
        return turn
    reply: str | None = None
    voided = turn.awaiting and turn.reply.startswith(_VOID_LEADS)  # a stored plan was void: a fresh proposal follows the notice
    if turn.verdict is not None and not turn.awaiting and not turn.clear_pending and _RAW_VOICE.search(turn.reply):
        reply = explain_reply(ctx, turn)  # any owner read that still carries a verdict line, a tier or a reason code
    elif turn.intent == Intent.EVALUATE_OFFER and turn.awaiting:
        reply = evaluate_reply(ctx, turn)
    elif turn.intent == Intent.FUND_GAP and turn.awaiting:
        reply = plan_reply(ctx, turn)
    elif turn.intent == Intent.FUND_GAP and turn.clear_pending:
        reply = done_reply(ctx, turn) or (_cure_run(ctx, turn) if ctx.sent and landing.is_funding(ctx.sent[0]) else None)
    elif turn.intent == Intent.NEGOTIATE and turn.clear_pending:
        reply = negotiated_reply(ctx, turn)
    elif turn.intent == Intent.SHOW_ALERTS:
        reply = alerts_reply(ctx, turn)
    elif turn.intent == Intent.REPAY_FACILITY:
        reply = repay_reply(ctx, turn)
    elif turn.intent in (Intent.APPROVE, Intent.REJECT):
        reply = approval_reply(ctx, turn)
    elif turn.intent == Intent.AMBIGUOUS and turn.pending_clarification is not None and turn.pending_clarification.slot == "approval_id":
        reply = approval_choice_reply(ctx, turn)
    elif turn.intent == Intent.SHOW_STATUS and "status" in turn.facts:
        reply = status_reply(ctx, turn)
    if reply is not None:
        turn.reply = plural((_void_line(ctx) + " " if voided and ctx.lang != "zh" else _void_line(ctx) if voided else "") + reply)
    return turn
