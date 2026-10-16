"""The decision record's view of an offer the owner sent outside FLOW, and the deal's history (map: negotiation communication, phase 3).

`outbound_view` is the `outbound` block of `GET /decisions/{id}` for a deal with an OFFERED fact: what was sent (the counter's terms in the owner's
words, and the message as it was shown, re-rendered from its template and checked against the stored hash), when the offer closes, and what came
of it: still waiting (with what recording each answer would do), accepted, countered, declined (with the reason's words) or closed without an
answer. `deal_history` is the `history` block of every deal: the request, FLOW's check, each send, the buyer's answer, in order, each with its day.
Pure reads of the record: nothing here writes, prices or projects; every sentence is written for `lang` (INVARIANT 13).
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
    RepliedFact,
    SentFact,
    parse_fact,
)
from app.decisions.state import BUYER_YES, DealState, buyer_answer
from app.domain.models import CommitmentStatus, OperationStatus
from app.outbound import NoWording, calendar_date, render

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


def _terms(ctx: Any, counter: Any, lang: str) -> list[str]:
    out = []
    for ob in counter.obligations if counter is not None else []:
        try:
            out.append(obligation_sentence(ctx.state, ob, ctx.today, lang))
        except (ValueError, KeyError, AttributeError):
            continue
    return out


def _day_words(ctx: Any, day: int, lang: str) -> dict[str, Any]:
    return {"day": day, "when": when_text(day, ctx.today, lang), "date": calendar_date(ctx.state.as_of, day, lang)}


def outbound_view(ctx: Any, ds: Any, inp: Any, lang: str) -> dict[str, Any] | None:
    """The `outbound` block: None for a deal with no offer sent outside FLOW."""
    o: OfferedFact | None = ds.offered
    if o is None:
        return None
    from app.api.outbound import decline_reason_text, decline_reasons, picture_path, review_of

    state = ctx.state
    buyer = party_name(state, o.counterparty_id)
    counter = _counter(inp, o.verdict_id, o.counter_id)
    label = option_label(counter.label, lang) if counter is not None else None
    rows = _facts(inp, ds.decision_id)
    sent_row = next((r for r, f in rows if isinstance(f, OfferedFact) and f.verdict_id == o.verdict_id and f.counter_id == o.counter_id), None)
    sent_day = sent_row.day if sent_row is not None else ctx.today
    message, same = None, False
    if counter is not None:
        try:
            msg = render(counter, state, buyer_name=buyer, terms_hash=o.terms_hash, valid_until_day=o.valid_until_day, lang=o.lang)
            message, same = msg.text, msg.message_hash == o.message_hash
        except NoWording:
            message = None
    answer = buyer_answer(ds)
    closes = _day_words(ctx, o.valid_until_day, lang)
    span = max(1, o.valid_until_day + 1 - sent_day)
    view: dict[str, Any] = {
        "counter_id": o.counter_id, "verdict_id": o.verdict_id, "label_text": label, "lang": o.lang, "message_hash": o.message_hash,
        "sent": _day_words(ctx, sent_day, lang), "closes": closes, "terms": _terms(ctx, counter, lang),
        "message_text": message if same else None, "message_same": same,
        "sent_text": t(lang, f"You sent {label or 'your counter'} on {_day_words(ctx, sent_day, lang)['date']}, in "
                             f"{'English' if o.lang == 'en' else 'Chinese'}",
                       f"您于{_day_words(ctx, sent_day, lang)['date']}以{'英文' if o.lang == 'en' else '中文'}发出了{label or '还价'}"),
        "answer": answer,
        "tone": {None: "waiting", "accepted": "ok", "countered": "waiting", "declined": "neutral", "no_answer": "neutral",
                 "closed": "neutral"}[answer],
        "links": [],
        "actions": None,
    }
    if answer in (None, "no_answer") and (refusal := _refused_yes(ctx, inp, o.offer_id, lang, still_open=answer is None)) is not None:
        view["refusal_text"] = refusal  # the owner's record of the buyer's yes was refused: the offer stayed open, or closed without it
    if answer is None:
        view["title_text"] = t(lang, f"Waiting for {buyer}'s answer", f"等待{buyer}答复")
        view["text"] = t(lang, f"Unanswered by {closes['date']}, it closes as no deal on its own.",
                         f"如在{closes['date']}前未获答复，将自动关闭，不成交。")
        view["closes_text"] = t(lang, f"Closes {closes['date']} · {closes['when']}", f"{closes['date']}截止 · {closes['when']}")
        view["progress"] = round(min(1.0, max(0.0, (ctx.today - sent_day) / span)), 2)
        latest = ds.verdict is not None and ds.verdict.id == o.verdict_id
        review = review_of(picture_path(ctx.rt, o.offer_id, o.counter_id, lang)) if latest and getattr(ctx, "rt", None) is not None else None
        view["actions"] = {
            "question_text": t(lang, f"What did {buyer} say?", f"{buyer}怎么答复？"),
            "accept": {"label": t(lang, "They accepted", "对方已接受"), "hint_text": t(lang, "Becomes the agreement", "成为协议"),
                       "confirm_label": t(lang, "Record their acceptance", "记录对方已接受"),
                       "terms": _terms(ctx, counter, lang), "review": review,
                       "authority_text": (None if review is None
                                          else t(lang, "It goes to your approval before it is in force.", "生效前需经您批准。") if review.get("needs_owner")
                                          else t(lang, "Within your limits: in force when you record it.", "在您的授权范围内：记录后即生效。"))},
            "counter": {"label": t(lang, "They countered", "对方还价"), "hint_text": t(lang, "Paste their new terms", "粘贴对方的新条款"),
                        "confirm_label": t(lang, "Read their reply", "读取对方的回复"),
                        "placeholder_text": t(lang, "Paste the buyer's reply as they wrote it", "按原文粘贴买方的回复"),
                        "effect_text": t(lang, "FLOW reads their terms and checks them as a new request.", "FLOW 会读取对方的条款，并作为一项新请求进行核查。")},
            "decline": {"label": t(lang, "They declined", "对方已拒绝"), "hint_text": t(lang, "Close it as no deal", "以不成交关闭"),
                        "confirm_label": t(lang, "Record that they declined", "记录对方已拒绝"),
                        "reasons_label_text": t(lang, "Why, if they said", "如对方说明了原因"), "reasons": decline_reasons(lang),
                        "effect_text": (review or {}).get("if_declined_text") or t(lang, "Nothing is agreed and no money moves.", "不会达成任何协议，也不会动用资金。")},
        }
        return view
    answer_row = next(((r, f) for r, f in reversed(rows) if isinstance(f, BuyerAcceptedFact | RepliedFact | BuyerDeclinedFact)), None)
    when = _day_words(ctx, answer_row[0].day, lang) if answer_row is not None else closes
    view["answered"] = when
    if answer == "accepted":
        live = ds.commitment is not None and ds.commitment.status in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)
        view["title_text"] = t(lang, f"{buyer} accepted {label or 'your counter'} on {when['date']}", f"{buyer}于{when['date']}接受了{label or '您的还价'}")
        if ds.state == DealState.AUTHORIZATION_REQUIRED:
            view["text"] = t(lang, "The agreement waits for your approval.", "协议正等待您批准。")
        elif ds.state == DealState.DECLINED:
            view["text"], view["tone"] = t(lang, "You declined the agreement at approval: nothing is in force.", "您在批准时拒绝了该协议：没有任何协议生效。"), "neutral"
        elif ds.state == DealState.FAILED:
            view["text"], view["tone"] = t(lang, "FLOW could not record the agreement: nothing is in force.", "FLOW 未能记录该协议：没有任何协议生效。"), "neutral"
        elif live or ds.state in (DealState.AGREED, DealState.FULFILLED, DealState.MISSED):
            view["text"] = t(lang, "The agreement is in force.", "协议已生效。")
        else:
            view["text"], view["tone"] = t(lang, "The agreement is not in force.", "该协议未生效。"), "neutral"
    elif answer == "countered":
        reply: RepliedFact = ds.replied
        quote = _reply_words(ctx, reply.reply_offer_id)
        view["title_text"] = t(lang, f"{buyer} countered on {when['date']}", f"{buyer}于{when['date']}提出还价")
        view["text"] = t(lang, "Their reply is a new request: FLOW checks it like any other.", "对方的回复是一项新请求：FLOW 会像其他请求一样核查。")
        view["reply_quote"] = quote
        view["links"] = [{"label": t(lang, "Answer their new request", "答复对方的新请求"), "href": f"/deals?decision=deal:{reply.reply_offer_id}",
                          "primary": True}]
    elif answer == "declined":
        reason = decline_reason_text(ds.declined.reason, lang)
        refused = _counter(inp, ds.declined.verdict_id, ds.declined.counter_id)  # the counter the buyer refused, not the latest one sent
        refused_label = (option_label(refused.label, lang) if refused is not None else None) or label
        view["title_text"] = t(lang, f"{buyer} declined {refused_label or 'your counter'} on {when['date']}",
                               f"{buyer}于{when['date']}拒绝了{refused_label or '您的还价'}")
        view["reason_code"], view["reason_text"] = ds.declined.reason, reason
        view["text"] = t(lang, "Nothing was agreed and no money moved.", "未达成任何协议，也未动用资金。")
        view["links"] = [{"label": t(lang, "Review funding in Cash", "在现金页查看融资"), "href": "/cash#cash-options", "primary": True}]
    elif answer == "closed":
        view["title_text"] = t(lang, "This offer is closed", "这份报价已关闭")
        view["text"] = (t(lang, "FLOW could not record the agreement: nothing is in force.", "FLOW 未能记录该协议：没有任何协议生效。")
                        if ds.state == DealState.FAILED else t(lang, "The deal ended before the buyer answered.", "这笔交易在买方答复之前已结束。"))
    else:
        view["title_text"] = t(lang, f"No answer by {closes['date']}", f"截至{closes['date']}未获答复")
        view["text"] = t(lang, "The offer closed on its own. Nothing was agreed and no money moved.", "报价已自动关闭。未达成任何协议，也未动用资金。")
        view["links"] = [{"label": t(lang, "Review funding in Cash", "在现金页查看融资"), "href": "/cash#cash-options", "primary": True}]
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


def _reply_words(ctx: Any, offer_id: str) -> str | None:
    """The buyer's reply as they wrote it (its first document), for the owner to read back: from the session's documents, never stored as a fact."""
    rt = getattr(ctx, "rt", None)
    offer = ctx.offer(offer_id) if hasattr(ctx, "offer") else None
    if rt is None or offer is None:
        return None
    doc = next((rt.documents[d] for d in offer.doc_ids if d in rt.documents), None)
    return doc.text if doc is not None else None


def deal_history(ctx: Any, ds: Any, inp: Any, lang: str) -> list[dict[str, Any]]:
    """The deal's history, oldest first: the request, FLOW's first check, each send (simulated or by the owner), and the buyer's answer."""
    if ds.family != "DEAL" or ds.offer is None:
        return []
    state = ctx.state
    buyer = party_name(state, ds.offer.counterparty_id)
    out: list[tuple[int, int, dict[str, Any]]] = []

    def add(day: int | None, order: int, kind: str, text: str, tone: str = "neutral") -> None:
        if day is None:
            return
        out.append((day, order, {**_day_words(ctx, day, lang), "kind": kind, "text": text, "tone": tone}))

    add(ds.offer.received_day, 0, "received", t(lang, f"{buyer} sent their request", f"{buyer}发来请求"))
    rows = _facts(inp, ds.decision_id)
    evaluated = next((r for r, f in rows if isinstance(f, EvaluatedFact)), None)
    if evaluated is not None:
        add(evaluated.day, 1, "checked", t(lang, "FLOW checked it against your books", "FLOW 已对照您的账目核查"))
    for n, (r, f) in enumerate(rows):
        if isinstance(f, SentFact):
            add(r.day, 10 + n, "simulated", t(lang, "Sent to the simulated buyer: " + ("agreed" if f.outcome == "DEAL" else "no deal"),
                                              "已发给模拟买方：" + ("已成交" if f.outcome == "DEAL" else "未成交")))
        elif isinstance(f, OfferedFact):
            sent_counter = _counter(inp, f.verdict_id, f.counter_id)
            label = (option_label(sent_counter.label, lang) if sent_counter is not None else None) or t(lang, "your counter", "您的还价")
            date = calendar_date(state.as_of, f.valid_until_day, lang)
            add(r.day, 10 + n, "offered", t(lang, f"You sent {label}, open until {date}", f"您发出了{label}，有效至{date}"), "waiting")
        elif isinstance(f, BuyerAcceptedFact):
            add(r.day, 10 + n, "accepted", t(lang, f"{buyer} accepted; you recorded it", f"{buyer}已接受；由您记录"), "ok")
        elif isinstance(f, RepliedFact):
            add(r.day, 10 + n, "countered", t(lang, f"{buyer} countered with new terms", f"{buyer}以新条款还价"), "waiting")
        elif isinstance(f, BuyerDeclinedFact):
            from app.api.outbound import decline_reason_text

            reason = decline_reason_text(f.reason, lang) if f.reason != "NO_REASON" else None
            add(r.day, 10 + n, "declined", t(lang, f"{buyer} declined" + (f": {reason.lower()}" if reason else ""),
                                             f"{buyer}已拒绝" + (f"：{reason}" if reason else "")), "neutral")
    if buyer_answer(ds) == "no_answer" and ds.offered is not None:
        date = calendar_date(state.as_of, ds.offered.valid_until_day, lang)
        add(ds.offered.valid_until_day, 900, "no_answer", t(lang, f"No answer by {date}; the offer closed", f"截至{date}未获答复；报价已关闭"))
    if ds.accepted_as_asked:
        run = next((x for x in ds.ops if x.kind == "ACCEPT_OFFER"), None)
        add(run.day if run is not None else None, 800, "accepted_as_asked", t(lang, "You accepted their request as asked", "您已按对方要求接受"), "ok")
    return [row for _day, _order, row in sorted(out, key=lambda x: (x[0], x[1]))]
