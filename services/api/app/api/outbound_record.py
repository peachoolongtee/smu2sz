"""The decision record's view of an offer the owner sent outside FLOW, and the deal's history (map: negotiation communication, rounds 3 and 4).

`outbound_view` is the `outbound` block of `GET /decisions/{id}` for a deal with an OFFERED mark that stands: what was sent (the counter's terms in
the owner's words, and the message re-rendered from its template and checked against the stored hash), when the offer closes, and what came of
it. While the buyer may answer: the one-line status (marked sent by the owner, which FLOW cannot confirm) and the answers the owner can record.
After: accepted (recorded by the owner, with the buyer's message when pasted; what the agreement changes), countered (our last offer beside their
reply), declined (the reason as the owner reported it), no answer, or closed another way. `reply_to_view` is the `reply_to` block of a request
that answers such an offer. `deal_history` is the `history` block of every deal: each event with its day and who it comes from.

Every claim follows the record: a mark is the owner's report, never a delivery; a yes is the owner's report, never an authenticated message;
nothing here says FLOW funds, sends or receives anything it did not. Pure reads: nothing here writes, prices or projects; every sentence is
written for `lang` (INVARIANT 13).
"""

from __future__ import annotations

import logging
from typing import Any

from app.api.presentation import business_text, obligation_sentence, option_label, party_name, t, when_text
from app.decisions.facts import (
    BuyerAcceptedFact,
    BuyerDeclinedFact,
    EvaluatedFact,
    OfferedFact,
    OfferWithdrawnFact,
    ReceivedFact,
    RepliedFact,
    SentFact,
    parse_fact,
)
from app.decisions.identity import deal_id
from app.decisions.state import BUYER_YES, DealState, buyer_answer
from app.domain.models import CommitmentStatus, CompileStatus, ObligationType, OperationStatus
from app.domain.money import fmt_yuan
from app.outbound import NoWording, calendar_date
from app.outbound.message import early_settlement, remainder_fen

log = logging.getLogger("termsledger.decisions")


def _facts(inp: Any, decision_id: str) -> list[tuple[Any, Any]]:
    """(row, fact) of this decision, oldest first."""
    out = []
    for r in inp.facts:
        if r.decision_id != decision_id:
            continue
        f = parse_fact(r)
        if f is not None:
            out.append((r, f))
    return out


def _counter(inp: Any, verdict_id: str, counter_id: str) -> Any:
    verdict = next((v for v in inp.verdicts if v.id == verdict_id), None)
    return next((c for c in verdict.counters if c.id == counter_id), None) if verdict is not None else None


def _terms(ctx: Any, obligations: Any, lang: str) -> list[str]:
    out = []
    for ob in obligations or []:
        try:
            out.append(obligation_sentence(ctx.state, ob, ctx.today, lang))
        except (ValueError, KeyError, AttributeError):
            continue
    return out


def _day_words(ctx: Any, day: int, lang: str) -> dict[str, Any]:
    return {"day": day, "when": when_text(day, ctx.today, lang), "date": calendar_date(ctx.state.as_of, day, lang)}


def _label(counter: Any, lang: str) -> str:
    return (option_label(counter.label, lang) if counter is not None else None) or t(lang, "your counter", "您的还价")


def _doc_text(ctx: Any, doc_id: str | None) -> str | None:
    """A buyer document's words (the session's documents; never a fact), for the owner to read back."""
    rt = getattr(ctx, "rt", None)
    if rt is None or doc_id is None:
        return None
    doc = rt.documents.get(doc_id)
    return doc.text if doc is not None else None


def _reply_words(ctx: Any, offer_id: str) -> str | None:
    offer = ctx.offer(offer_id) if hasattr(ctx, "offer") else None
    return next((w for w in (_doc_text(ctx, d) for d in (offer.doc_ids if offer is not None else [])) if w), None)


def _changes(ctx: Any, ours: Any, theirs: Any, buyer: str | None, lang: str) -> list[dict[str, Any]]:
    """Our last offer beside their reply, row by row (payment terms, early payment, rebate or price), each in the offer picture's own words."""
    from app.api.offer_picture import (  # the picture's reading of terms; it reads the record, so imported here
        _TERM_ROWS,
        _term_rows,
    )

    mine = _term_rows(ctx.state, list(ours or []), buyer, lang)
    them = _term_rows(ctx.state, list(theirs or []), buyer, lang)
    rows = []
    for key, en, zh in _TERM_ROWS:
        a, b = mine[key][0], them[key][0]
        if a is None and b is None:
            continue
        rows.append({"key": key, "label": t(lang, en, zh), "ours_text": a or t(lang, "Not offered", "未提供"),
                     "theirs_text": b or t(lang, "Not mentioned", "未提及"), "changed": a != b})
    return rows


def _consequences(ctx: Any, ds: Any, buyer: str, lang: str) -> tuple[list[str], list[dict[str, Any]]]:
    """What the recorded agreement changes, from the commitment's own terms and the books: what payment is expected and when, what stays
    due, what changes on future invoices, and whether any cash has arrived. With the links to the receivable and the customer."""
    c = ds.commitment
    if c is None:
        return [], []
    state = ctx.state
    lines: list[str] = []
    links: list[dict[str, Any]] = []
    for o in c.obligations:
        if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id and o.base.amount_fen and o.effective_day is not None:
            rcv = next((r for r in state.receivables if r.id == o.base.receivable_id), None)
            cap, net = early_settlement(o)
            by = calendar_date(state.as_of, o.effective_day, lang)
            due = calendar_date(state.as_of, rcv.issue_day + rcv.terms_days, lang) if rcv is not None else None
            promise = next((p for p in getattr(ctx, "promised", ()) if getattr(p, "commitment_id", None) == c.id
                            and getattr(p, "receivable_id", None) == o.base.receivable_id), None)
            status = getattr(promise, "status", None)
            if status == "RECEIVED":
                lines.append(t(lang, f"The early payment for {fmt_yuan(cap)} of the invoice has arrived.", f"发票中 {fmt_yuan(cap)} 的提前付款已到账。"))
            elif status in ("LAPSED", "SETTLED_OTHERWISE") or ctx.today > o.effective_day:
                lines.append(t(lang, f"No early payment arrived by {by}; the invoice stays due" + (f" on {due}." if due else "."),
                               f"截至{by}未收到提前付款；发票仍" + (f"于{due}到期。" if due else "按原条款到期。")))
            else:
                lines.append(t(lang, f"{buyer} can settle {fmt_yuan(cap)} of the invoice by paying {fmt_yuan(net)} by {by}.",
                               f"{buyer}可在{by}前支付 {fmt_yuan(net)}，结清发票中的 {fmt_yuan(cap)}。"))
                if due is not None and (rest := remainder_fen(o, state)):
                    lines.append(t(lang, f"The other {fmt_yuan(rest)} stays due on {due}.", f"其余 {fmt_yuan(rest)} 仍于{due}到期。"))
            links.append({"label": t(lang, "View receivable", "查看应收账款"), "href": f"/receivables#{o.base.receivable_id}"})
        else:
            lines += _terms(ctx, [o], lang)
    awaited = any(getattr(p, "commitment_id", None) == c.id and getattr(p, "status", None) == "AWAITED" for p in getattr(ctx, "promised", ()))
    if awaited:
        lines.append(t(lang, "No cash has been received yet; FLOW reconciles the payment when it arrives.", "尚未收到任何款项；款项到账后 FLOW 会进行对账。"))
    links.append({"label": t(lang, "View customer", "查看客户"), "href": f"/customers/{c.counterparty_id}"})
    return lines, links


def outbound_view(ctx: Any, ds: Any, inp: Any, lang: str) -> dict[str, Any] | None:
    """The `outbound` block: None for a deal with no standing offer sent outside FLOW."""
    o: OfferedFact | None = ds.offered
    if o is None:
        return None
    from app.api.outbound import (
        authority_words,
        decline_reason_text,
        decline_reasons,
        picture_path,
        render_for,
        review_of,
    )

    state = ctx.state
    buyer = party_name(state, o.counterparty_id)
    counter = _counter(inp, o.verdict_id, o.counter_id)
    label = _label(counter, lang)
    rows = _facts(inp, ds.decision_id)
    sent_row = next((r for r, f in reversed(rows) if isinstance(f, OfferedFact) and f == o), None)
    sent_day = sent_row.day if sent_row is not None else ctx.today
    sent = _day_words(ctx, sent_day, lang)
    message, same = None, False
    verdict = next((v for v in inp.verdicts if v.id == o.verdict_id), None)
    from app.api.outbound import sent_doc_id
    from app.outbound import message_hash as hash_of

    kept = _doc_text(ctx, sent_doc_id(o.message_hash))
    if kept is not None and hash_of(kept, lang=o.lang, terms_hash=o.terms_hash, template_version=o.template_version) == o.message_hash:
        message, same = kept, True
    elif counter is not None and verdict is not None and ds.offer is not None:
        try:
            msg = render_for(state, ds.offer, verdict, counter, terms_hash=o.terms_hash, valid_until_day=o.valid_until_day, lang=o.lang)
            message, same = msg.text, msg.message_hash == o.message_hash
        except NoWording:
            message = None
    answer = buyer_answer(ds)
    closes = _day_words(ctx, o.valid_until_day, lang)
    sent_lang = t(lang, "English" if o.lang == "en" else "Chinese", "英文" if o.lang == "en" else "中文")
    view: dict[str, Any] = {
        "counter_id": o.counter_id, "verdict_id": o.verdict_id, "label_text": label, "lang": o.lang, "message_hash": o.message_hash,
        "sent": sent, "closes": closes, "terms": _terms(ctx, counter.obligations if counter is not None else [], lang),
        "message_text": message if same else None, "message_same": same,
        "sent_text": t(lang, f"You marked {label} as sent on {sent['date']}, in {sent_lang}", f"您于{sent['date']}将{label}标记为已发送（{sent_lang}）"),
        "provenance_text": t(lang, "Marked sent by you · FLOW cannot confirm delivery", "由您标记为已发送 · FLOW 无法确认对方已收到"),
        "answer": answer,
        "tone": {None: "waiting", "accepted": "ok", "countered": "waiting", "declined": "neutral", "no_answer": "neutral",
                 "closed": "neutral"}[answer],
        "links": [], "actions": None,
    }
    if answer in (None, "no_answer") and (refusal := _refused_yes(ctx, inp, o.offer_id, lang, still_open=answer is None)) is not None:
        view["refusal_text"] = refusal  # the owner's record of the buyer's yes was refused: the offer stayed open, or closed without it
    if answer is None:
        view["title_text"] = t(lang, f"Waiting for {buyer}'s response", f"等待{buyer}答复")
        view["status_text"] = t(lang, f"{label} · marked sent by you on {sent['date']} · FLOW cannot confirm delivery · expires {closes['date']} "
                                      f"({closes['when']})",
                                f"{label} · 您于{sent['date']}标记为已发送 · FLOW 无法确认对方已收到 · {closes['date']}到期（{closes['when']}）")
        view["text"] = t(lang, f"If there is no response by {closes['date']}, the offer closes with no agreement.",
                         f"如在{closes['date']}前未获答复，报价将关闭，不达成任何协议。")
        view["closes_text"] = t(lang, f"Expires {closes['date']} · {closes['when']}", f"{closes['date']}到期 · {closes['when']}")
        span = max(1, o.valid_until_day + 1 - sent_day)
        view["progress"] = round(min(1.0, max(0.0, (ctx.today - sent_day) / span)), 2)
        latest = ds.verdict is not None and ds.verdict.id == o.verdict_id
        path = picture_path(ctx.rt, o.offer_id, o.counter_id, lang) if latest and getattr(ctx, "rt", None) is not None else None
        review = review_of(path, lang)
        view["actions"] = {
            "question_text": t(lang, f"What did {buyer} reply?", f"{buyer}如何答复？"),
            "record_label": t(lang, "Record their response", "记录对方的答复"),
            "view_message_label": t(lang, "View sent message", "查看已发送的消息"),
            "accept": {"label": t(lang, "Accepted", "已接受"), "hint_text": t(lang, "Becomes the agreement", "成为协议"),
                       "title_text": t(lang, "Confirm buyer acceptance", "确认买方已接受"),
                       "confirm_label": t(lang, "Confirm and record agreement", "确认并记录协议"),
                       "binding_text": t(lang, f"You confirm that {buyer} accepted exactly these terms of {label}, as sent on {sent['date']}, "
                                               f"before the offer expires on {closes['date']}.",
                                         f"您确认{buyer}已在报价于{closes['date']}到期前，接受了您于{sent['date']}发出的{label}的上述条款，且未作改动。"),
                       "evidence_label": t(lang, "Their message (optional)", "对方的消息（可选）"),
                       "evidence_placeholder": t(lang, "Paste the buyer's reply that accepts the offer", "粘贴买方接受报价的回复"),
                       "evidence_hint_text": t(lang, "Without it, the record says you confirmed the acceptance yourself.",
                                               "如不粘贴，记录将注明由您本人确认接受。"),
                       "terms": _terms(ctx, counter.obligations if counter is not None else [], lang), "review": review,
                       "authority_text": (None if review is None
                                          else t(lang, "It goes to your approval before it is in force.", "生效前需经您批准。") if review.get("needs_owner")
                                          else t(lang, "Within your mandate: in force when you record it.", "在您的授权范围内：记录后即生效。"))},
            "counter": {"label": t(lang, "Proposed different terms", "提出了不同条款"), "hint_text": t(lang, "Paste their reply", "粘贴对方的回复"),
                        "confirm_label": t(lang, "Evaluate their proposal", "评估对方的提议"),
                        "placeholder_text": t(lang, "Paste the buyer's reply as they wrote it", "按原文粘贴买方的回复"),
                        "effect_text": t(lang, "FLOW reads their terms and checks them as a new request in this negotiation.",
                                         "FLOW 会读取对方的条款，并作为本次谈判中的新请求进行核查。")},
            "unclear": {"label": t(lang, "Unclear or a question", "不明确或提出问题"),
                        "hint_text": t(lang, "Paste their reply; FLOW says what is missing", "粘贴对方的回复；FLOW 会指出缺少的信息"),
                        "confirm_label": t(lang, "Read their reply", "读取对方的回复"),
                        "placeholder_text": t(lang, "Paste the buyer's reply as they wrote it", "按原文粘贴买方的回复"),
                        "effect_text": t(lang, "FLOW records nothing it cannot read safely; it says what to ask the buyer.",
                                         "FLOW 不会记录无法安全读取的内容；它会说明需要向买方询问什么。")},
            "decline": {"label": t(lang, "Declined", "已拒绝"), "hint_text": t(lang, "Close it with no agreement", "以不达成协议关闭"),
                        "confirm_label": t(lang, "Record that they declined", "记录对方已拒绝"),
                        "reasons_label_text": t(lang, "Reason they gave, as you report it (optional)", "对方给出的原因，由您报告（可选）"),
                        "reasons": decline_reasons(lang),
                        "effect_text": t(lang, "Nothing is agreed and no money moves. The invoice stays due on its existing terms.",
                                         "不会达成任何协议，也不会动用资金。发票仍按原条款到期。")},
            "withdraw": {"label": t(lang, "I marked it sent by mistake", "我误标为已发送"), "confirm_label": t(lang, "Undo “marked sent”", "撤销“已发送”"),
                         "effect_text": t(lang, "The mark stays on the record beside your correction, and the deal is ready to send again.",
                                          "该标记会与您的更正一同保留在记录中，交易将恢复为待发送。")},
        }
        view["authority_text"] = authority_words(review.get("needs_owner"), lang) if review is not None else None
        view["terms_title_text"] = t(lang, "What you offered", "您提出的条款")
        return view
    answer_row = next(((r, f) for r, f in reversed(rows) if isinstance(f, BuyerAcceptedFact | RepliedFact | BuyerDeclinedFact)), None)
    when = _day_words(ctx, answer_row[0].day, lang) if answer_row is not None else closes
    view["answered"] = when
    customer = {"label": t(lang, "View customer", "查看客户"), "href": f"/customers/{o.counterparty_id}"}
    deals = {"label": t(lang, "Back to Deals", "返回交易"), "href": "/deals"}
    if answer == "accepted":
        yes = next((f for f in reversed([f for _, f in rows]) if isinstance(f, BuyerAcceptedFact)), None)
        quote = _doc_text(ctx, yes.evidence_doc_id) if yes is not None else None
        live = ds.commitment is not None and ds.commitment.status in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)
        view["title_text"] = t(lang, "Buyer acceptance recorded", "已记录买方接受")
        view["text"] = t(lang, f"You confirmed that {buyer} accepted {label} on {when['date']}.", f"您确认{buyer}已于{when['date']}接受{label}。")
        view["provenance_text"] = (t(lang, "Source: recorded by you, with the buyer's message", "来源：由您记录，附买方的消息") if quote
                                   else t(lang, "Source: recorded by you; no buyer message attached", "来源：由您记录；未附买方的消息"))
        view["evidence_quote"] = quote
        if ds.state == DealState.AUTHORIZATION_REQUIRED:
            view["status_text"] = t(lang, "The agreement waits for your approval and is not in force yet.", "协议正等待您批准，尚未生效。")
        elif ds.state == DealState.DECLINED:
            view["status_text"], view["tone"] = t(lang, "You declined the agreement at approval: nothing is in force.", "您在批准时拒绝了该协议：没有任何协议生效。"), "neutral"
        elif ds.state == DealState.FAILED:
            view["status_text"], view["tone"] = t(lang, "FLOW could not record the agreement: nothing is in force.", "FLOW 未能记录该协议：没有任何协议生效。"), "neutral"
        elif ds.state == DealState.MISSED:
            view["status_text"], view["tone"] = (t(lang, "The early payment did not arrive by its day; the invoice stays due on its existing terms.",
                                                   "提前付款未在约定日期前到账；发票仍按原条款到期。"), "neutral")
        elif ds.state == DealState.FULFILLED:
            view["status_text"] = t(lang, "The agreement is fulfilled.", "协议已履行。")
        elif live or ds.state == DealState.AGREED:
            view["status_text"] = t(lang, "The agreement is in force.", "协议已生效。")
        else:
            view["status_text"], view["tone"] = t(lang, "The agreement is not in force.", "该协议未生效。"), "neutral"
        consequences, links = (_consequences(ctx, ds, buyer, lang) if ds.state in (DealState.AGREED, DealState.MISSED, DealState.FULFILLED)
                               else ([], [customer]))
        from app.api.decisions import funding_next_step, funding_none_needed

        if (step := funding_next_step(ctx, ds, lang)) is not None:  # recording the yes funded nothing: the gap and FLOW's plan for it
            consequences = [*consequences, step["text"]]
            links = [{"label": step["label"], "href": step["href"], "primary": True}, *links]
        elif (none_needed := funding_none_needed(ctx, ds, lang)) is not None:  # or that no funding is needed
            consequences = [*consequences, none_needed]
        view["consequences"], view["links"] = consequences, links
        view["consequences_title_text"] = t(lang, "What changes now", "接下来的变化")
    elif answer == "countered":
        reply: RepliedFact = ds.replied
        new = ctx.offer(reply.reply_offer_id) if hasattr(ctx, "offer") else None
        view["title_text"] = t(lang, f"{buyer} proposed different terms on {when['date']}", f"{buyer}于{when['date']}提出了不同条款")
        view["text"] = t(lang, "You pasted their reply; FLOW reads it as the next request in this negotiation.",
                         "您粘贴了对方的回复；FLOW 将其作为本次谈判中的下一项请求读取。")
        view["reply_quote"] = _reply_words(ctx, reply.reply_offer_id)
        view["changes"] = _changes(ctx, counter.obligations if counter is not None else [], new.obligations if new is not None else [],
                                   o.counterparty_id, lang)
        unclear = new is not None and new.status in (CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES)
        checked = any(v.offer_id == reply.reply_offer_id for v in inp.verdicts)
        view["reply_state_text"] = (t(lang, "FLOW needs one more detail from the buyer before it can evaluate their reply.",
                                      "FLOW 需要买方补充一项信息后才能评估其回复。") if unclear
                                    else t(lang, "FLOW has evaluated their reply.", "FLOW 已评估对方的回复。") if checked
                                    else t(lang, "FLOW has not evaluated their reply yet.", "FLOW 尚未评估对方的回复。"))
        view["links"] = [{"label": t(lang, "Evaluate their proposal", "评估对方的提议"), "href": f"/deals?decision={deal_id(reply.reply_offer_id)}",
                          "primary": True}, customer]
    elif answer == "declined":
        refused = _counter(inp, ds.declined.verdict_id, ds.declined.counter_id)  # the counter the buyer refused, not the latest one sent
        view["title_text"] = t(lang, "No agreement was reached", "未达成协议")
        view["text"] = t(lang, f"You recorded that {buyer} declined {_label(refused, lang)} on {when['date']}. Their invoice stays due on its "
                               f"existing terms; nothing was agreed, borrowed or moved.",
                         f"您记录了{buyer}于{when['date']}拒绝{_label(refused, lang)}。其发票仍按原条款到期；未达成、借入或动用任何资金。")
        view["reason_code"] = ds.declined.reason
        reason = decline_reason_text(ds.declined.reason, lang)
        view["reason_text"] = t(lang, f"Reason, as you reported it: {reason}", f"原因（由您报告）：{reason}") if reason else None
        view["links"] = [{"label": t(lang, "Review your cash outlook", "查看您的现金展望"), "href": "/cash", "primary": True}, customer, deals]
    elif answer == "closed":
        view["title_text"] = t(lang, "This offer is closed", "这份报价已关闭")
        view["text"] = (t(lang, "FLOW could not record the agreement: nothing is in force.", "FLOW 未能记录该协议：没有任何协议生效。")
                        if ds.state == DealState.FAILED else t(lang, "The deal ended before the buyer responded.", "这笔交易在买方答复之前已结束。"))
        view["links"] = [customer, deals]
    else:
        view["title_text"] = t(lang, f"No response by {closes['date']}", f"截至{closes['date']}未获答复")
        view["text"] = t(lang, "The offer expired with no agreement. Their invoice stays due on its existing terms; no money moved.",
                         "报价已到期，未达成协议。其发票仍按原条款到期；未动用任何资金。")
        view["links"] = [{"label": t(lang, "Review your cash outlook", "查看您的现金展望"), "href": "/cash", "primary": True}, customer, deals]
    if answer == "accepted":
        view["terms_title_text"] = t(lang, "What was agreed", "达成的条款")
    else:  # an offer that ended without an agreement: what was offered, never said as obligations in force ("effective yesterday")
        view["terms"] = _offered_rows(ctx, counter, o.counterparty_id, lang)
        view["terms_title_text"] = t(lang, "What you offered (not agreed)", "您提出的条款（未达成）")
    return view


def _refused_yes(ctx: Any, inp: Any, offer_id: str, lang: str, *, still_open: bool) -> str | None:
    """In the owner's words, why the executor refused the owner's last record of the buyer's yes, or None when it was not refused (or none was
    made). While the offer is open it says they can record it again."""
    runs = [e for e in inp.log if e.payload.get("offer_id") == offer_id and str(e.payload.get("op_id") or e.result.op_id).startswith(BUYER_YES)
            and e.result.status != OperationStatus.DUPLICATE]
    if not runs or runs[-1].result.status != OperationStatus.REFUSED:
        return None
    r = runs[-1].result
    reason = business_text(ctx.state, "; ".join(v.message for v in r.violations) or r.message.removeprefix("Refused: "), ctx.today, lang) or ""
    en = f"FLOW could not record their yes: nothing is in force. {reason}".strip()
    zh = f"FLOW 未能记录对方的接受：没有任何协议生效。{reason}".strip()
    return t(lang, en + (" Check your books, then record it again while the offer is open." if still_open else ""),
             zh + (" 请检查您的账目，并在报价有效期内再次记录。" if still_open else ""))


def _offered_rows(ctx: Any, counter: Any, buyer: str | None, lang: str) -> list[str]:
    """The counter's terms as offered, one line per row of the offer picture ("Early payment: 0.85% off ¥257,200.00"), with no effective day."""
    from app.api.offer_picture import (  # the picture's reading of terms; it reads the record, so imported here
        _TERM_ROWS,
        _term_rows,
    )

    rows = _term_rows(ctx.state, list(counter.obligations) if counter is not None else [], buyer, lang)
    return [f"{t(lang, en, zh)}{t(lang, ': ', '：')}{rows[key][0] or t(lang, 'Not offered', '未提供')}" for key, en, zh in _TERM_ROWS]


def reply_to_view(ctx: Any, ds: Any, inp: Any, lang: str) -> dict[str, Any] | None:
    """The `reply_to` block of a request that answers an offer the owner sent outside FLOW: which offer it answers, linked back. None otherwise."""
    if ds.family != "DEAL" or ds.offer is None:
        return None
    rx = next((f for _, f in reversed(_facts(inp, ds.decision_id))
               if isinstance(f, ReceivedFact) and f.offer_id == ds.offer.offer_id and f.in_reply_to_offer_id), None)
    if rx is None:
        return None
    original = deal_id(rx.in_reply_to_offer_id)
    earlier = _facts(inp, original)
    answered = next((f for _, f in earlier if isinstance(f, RepliedFact) and f.reply_offer_id == ds.offer.offer_id), None)
    sent = next(((r, f) for r, f in reversed(earlier) if isinstance(f, OfferedFact)
                 and (answered is None or (f.verdict_id, f.counter_id) == (answered.verdict_id, answered.counter_id))), None)
    if sent is None:
        return {"decision_id": original, "href": f"/deals?decision={original}", "title_text": t(lang, "In reply to your offer", "回复您的报价"),
                "terms": []}
    row, fact = sent
    counter = _counter(inp, fact.verdict_id, fact.counter_id)
    date = calendar_date(ctx.state.as_of, row.day, lang)
    return {"decision_id": original, "href": f"/deals?decision={original}",
            "title_text": t(lang, f"In reply to {_label(counter, lang)} you sent on {date}", f"回复您于{date}发出的{_label(counter, lang)}"),
            "terms": _terms(ctx, counter.obligations if counter is not None else [], lang)}


def deal_history(ctx: Any, ds: Any, inp: Any, lang: str) -> list[dict[str, Any]]:
    """The deal's history, oldest first: the request, FLOW's first check, each send (simulated, or marked sent by the owner) and its correction,
    and the buyer's answer as the owner recorded it. `source` says where each event comes from: buyer, flow, owner or simulator."""
    if ds.family != "DEAL" or ds.offer is None:
        return []
    from app.api.outbound import decline_reason_text

    state = ctx.state
    buyer = party_name(state, ds.offer.counterparty_id)
    out: list[tuple[int, int, dict[str, Any]]] = []

    def add(day: int | None, order: int, kind: str, text: str, tone: str = "neutral", source: str = "owner") -> None:
        if day is None:
            return
        out.append((day, order, {**_day_words(ctx, day, lang), "kind": kind, "text": text, "tone": tone, "source": source}))

    add(ds.offer.received_day, 0, "received", t(lang, f"{buyer} sent their request", f"{buyer}发来请求"), source="buyer")
    rows = _facts(inp, ds.decision_id)
    evaluated = next((r for r, f in rows if isinstance(f, EvaluatedFact)), None)
    if evaluated is not None:
        add(evaluated.day, 1, "checked", t(lang, "FLOW checked it against your books", "FLOW 已对照您的账目核查"), source="flow")
    for n, (r, f) in enumerate(rows):
        if isinstance(f, SentFact):
            add(r.day, 10 + n, "simulated", t(lang, "Sent to the simulated buyer: " + ("agreed" if f.outcome == "DEAL" else "no deal"),
                                              "已发给模拟买方：" + ("已成交" if f.outcome == "DEAL" else "未成交")), source="simulator")
        elif isinstance(f, OfferedFact):
            label = _label(_counter(inp, f.verdict_id, f.counter_id), lang)
            date = calendar_date(state.as_of, f.valid_until_day, lang)
            add(r.day, 10 + n, "offered", t(lang, f"You marked {label} as sent, open until {date}", f"您将{label}标记为已发送，有效至{date}"), "waiting")
        elif isinstance(f, OfferWithdrawnFact):
            label = _label(_counter(inp, f.verdict_id, f.counter_id), lang)
            add(r.day, 10 + n, "withdrawn", t(lang, f"You corrected it: {label} was not sent", f"您已更正：{label}并未发送"))
        elif isinstance(f, BuyerAcceptedFact):
            add(r.day, 10 + n, "accepted", (t(lang, f"You recorded that {buyer} accepted, with their message", f"您记录了{buyer}已接受，附对方的消息")
                                            if f.evidence_doc_id else t(lang, f"You recorded that {buyer} accepted", f"您记录了{buyer}已接受")), "ok")
        elif isinstance(f, RepliedFact):
            add(r.day, 10 + n, "countered", t(lang, f"{buyer} proposed different terms; you pasted their reply", f"{buyer}提出了不同条款；由您粘贴其回复"),
                "waiting")
        elif isinstance(f, BuyerDeclinedFact):
            reason = decline_reason_text(f.reason, lang) if f.reason != "NO_REASON" else None
            add(r.day, 10 + n, "declined", t(lang, f"You recorded that {buyer} declined" + (f" ({reason.lower()})" if reason else ""),
                                             f"您记录了{buyer}已拒绝" + (f"（{reason}）" if reason else "")))
    if buyer_answer(ds) == "no_answer" and ds.offered is not None:
        date = calendar_date(state.as_of, ds.offered.valid_until_day, lang)
        add(ds.offered.valid_until_day, 900, "no_answer", t(lang, f"No response by {date}; the offer expired", f"截至{date}未获答复；报价已到期"),
            source="flow")
    if ds.accepted_as_asked:
        run = next((x for x in ds.ops if x.kind == "ACCEPT_OFFER"), None)
        add(run.day if run is not None else None, 800, "accepted_as_asked", t(lang, "You accepted their request as asked", "您已按对方要求接受"), "ok")
    return [row for _day, _order, row in sorted(out, key=lambda x: (x[0], x[1]))]
