"""The owner sends a verified counter to the buyer themself (map: negotiation communication, phases 1 and 2).

FLOW transmits nothing. It prepares the message for one counter (`app.outbound`), guarded like every outbound text, and the owner copies it and
sends it by their own channel. Four owner-only routes, each bound to what the owner was shown:

    GET  /offers/{offer_id}/counters/{counter_id}/message          the message, or why there is none
    POST /offers/{offer_id}/counters/{counter_id}/offered          {verdict_id, state_version, message_hash, lang}: "I've sent it"
    POST /offers/{offer_id}/counters/{counter_id}/buyer-accepted   {verdict_id, state_version, message_hash}: "the buyer accepted"
    POST /offers/{offer_id}/buyer-reply                            {verdict_id, counter_id, text}: the buyer answered with terms of their own

Marking it sent records an OFFERED fact and nothing else: no agreement, no operation, no funding (the simulated send of `POST /negotiate` does
all three, because its buyer answers at once). The deal then waits for the buyer until the day the message says the offer is open.

The buyer's yes is the owner's to record. It makes the agreement the offered counter states, bound to the verdict it was offered from, through
the executor's AcceptOffer under the owner's authority: the executor screens the terms against that verdict, re-verifies them on today's books
and queues the agreement for approval where its tier asks. Nothing a buyer writes reaches an operation: a reply with terms of its own is compiled
and verified as a new request, and this deal is closed as answered by it.

A message is prepared only for a request whose sender is known (the RECEIVED fact: the owner's token, the agent's key, the buyer's own channel
key, or a reply the owner pasted), never for one filed anonymously under a buyer's name (SEC-19). The words are written for `lang` through
`t(lang, en, zh)` (INVARIANT 13).
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.accept import PROPOSAL_DAYS, _answer, _conflict, _not_recorded, _standing, over_mandate
from app.api.auth import require_feature, require_owner
from app.api.decide import _counter_allow, _counter_changed
from app.api.decisions import lapsed_conflict, latest_verdict_for, record_fact
from app.api.offers import SENDER_RANK, _unclaimed, store_compiled
from app.api.presentation import option_label, party_name, t, when_text
from app.api.runtime import Runtime, get_runtime
from app.commitments import terms_hash
from app.compiler import compile_offer
from app.decisions.facts import (
    BuyerAcceptedFact,
    BuyerDeclinedFact,
    DeclineReason,
    OfferedFact,
    OfferWithdrawnFact,
    ReceivedFact,
    RepliedFact,
    parse_fact,
)
from app.decisions.identity import deal_id
from app.decisions.state import BUYER_YES, active_offers
from app.domain.models import (
    AcceptOffer,
    Actor,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CounterProposal,
    ObligationType,
    OperationStatus,
    SourceDocument,
    Verdict,
)
from app.egress import guard, protected_for
from app.egress.values import AllowedValue
from app.mandate import MandatePolicyImpl
from app.operations.executor import committable
from app.operations.log import read_entries
from app.outbound import TEMPLATE_VERSION, NoWording, calendar_date, render, valid_until
from app.outbound.message import BuyerMessage, early_settlement, remainder_fen

router = APIRouter(tags=["offers"], dependencies=[Depends(require_owner), Depends(require_feature("terms_guard")),
                                                  Depends(require_feature("buyer_negotiation"))])

KNOWN_SENDERS = frozenset({"owner", "agent", "buyer_key", "buyer_reply"})
REPLY_MAX = 4000  # a buyer's message, as POST /offers bounds one document (SEC-17)

_BLOCKED = {
    "UNVERIFIED_SENDER": ("FLOW does not know who sent this request, so it prepares no message. Confirm the request with the buyer first.",
                          "FLOW 无法确认这项请求的发送方，因此不准备消息。请先与买方确认这项请求。"),
    "NOT_SENDABLE": ("This reply is not one you can send within your limits, so FLOW prepares no message for it.",
                     "该回复不在您可发送的授权范围内，FLOW 不为其准备消息。"),
    "NO_WORDING": ("FLOW has no wording for one of these terms, so it prepares no message. Write to the buyer yourself.",
                   "其中有一项条款 FLOW 没有对应的措辞，因此不准备消息。请您自行联系买方。"),
    "OUTBOUND_BLOCKED": ("The message would state a figure the buyer must not see, so FLOW withheld it.",
                         "该消息会透露买方不应看到的数字，FLOW 已将其拦截。"),
    "WINDOW_PASSED": ("The day this offer could be accepted by has passed, so FLOW prepares no message.",
                      "该报价可被接受的期限已过，FLOW 不准备消息。"),
}


def _provenance_text(via: str | None, lang: str) -> str:
    words = {
        "owner": ("You entered this request.", "这项请求由您录入。"),
        "agent": ("FLOW's agent entered this request.", "这项请求由 FLOW 的代理录入。"),
        "buyer_key": ("The buyer sent this request on their own channel.", "这项请求由买方通过其专属渠道发送。"),
        "buyer_reply": ("You pasted this request from the buyer's reply.", "这项请求由您从买方的回复中粘贴。"),
        "anonymous": ("Nobody signed this request: it came without a buyer's key.", "这项请求没有签名：它未附带买方的密钥。"),
    }
    en, zh = words.get(via or "", ("FLOW has no record of how this request arrived.", "FLOW 没有这项请求如何到达的记录。"))
    return t(lang, en, zh)


# ---------------------------------------------------------------- the deal's facts


def _facts(rt: Runtime, offer_id: str) -> list[Any]:
    store: Any = rt.store
    return [f for f in (parse_fact(r) for r in store.decision_facts(deal_id(offer_id))) if f is not None]


def _received(rt: Runtime, offer: CompiledOffer) -> ReceivedFact | None:
    """How this request arrived: the strongest sender that filed it (a later, stronger filing upgrades an earlier, weaker one; see `received_key`)."""
    held = [f for f in _facts(rt, offer.offer_id) if isinstance(f, ReceivedFact) and f.offer_id == offer.offer_id and f.offer_version == offer.version]
    return max(held, key=lambda f: SENDER_RANK[f.via], default=None)


def _offered(rt: Runtime, offer_id: str, verdict_id: str, counter_id: str) -> OfferedFact | None:
    """The OFFERED mark that stands for this counter (a corrected mark does not), else None."""
    return next((f for f in active_offers(_facts(rt, offer_id)) if f.verdict_id == verdict_id and f.counter_id == counter_id), None)


def sent_doc_id(message_hash: str) -> str:
    """Where the words of a message marked sent are kept for the session: the owner's own text (channel "owner"), never a buyer document."""
    return f"sent-{message_hash[:24]}"


def _corrections(rt: Runtime, offer_id: str, verdict_id: str, counter_id: str) -> int:
    """How many times the owner corrected a mark of this counter: each new mark and correction takes the next key."""
    return sum(1 for f in _facts(rt, offer_id)
               if isinstance(f, OfferWithdrawnFact) and f.verdict_id == verdict_id and f.counter_id == counter_id)


def _replied(rt: Runtime, offer_id: str) -> RepliedFact | None:
    return next((f for f in _facts(rt, offer_id) if isinstance(f, RepliedFact)), None)


def _declined(rt: Runtime, offer_id: str) -> BuyerDeclinedFact | None:
    return next((f for f in _facts(rt, offer_id) if isinstance(f, BuyerDeclinedFact)), None)


def _already_answered(offer_id: str, reply: RepliedFact, lang: str) -> HTTPException:
    return _conflict("ALREADY_ANSWERED", offer_id, "The buyer already answered this offer with terms of their own; answer that request instead.",
                     "买方已以新条款答复了这份报价；请改为答复那项请求。", lang, decision_id=deal_id(offer_id),
                     reply_offer_id=reply.reply_offer_id, reply_decision_id=deal_id(reply.reply_offer_id))


def _not_offered(offer_id: str, lang: str) -> HTTPException:
    return _conflict("NOT_OFFERED", offer_id, "You have not marked this message as sent to the buyer; nothing was recorded.",
                     "您尚未将这条消息标记为已发给买方；未记录任何内容。", lang)


def _mandate_in_force(rt: Runtime, offer_id: str, lang: str) -> None:
    mandate = rt.store.get_mandate()
    if MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex).check_validity(mandate, rt.day, mandate.version):
        raise over_mandate(offer_id, lang, why="mandate")


# ---------------------------------------------------------------- the message


def _current(rt: Runtime, offer_id: str, counter_id: str, lang: str) -> tuple[CompiledOffer, Verdict, CounterProposal]:
    """The offer, its latest verdict and the counter, when that counter can still be offered on today's books. Call under `rt.lock`."""
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
    verdict = latest_verdict_for(rt, offer_id)
    if verdict is None:
        raise _conflict("NOT_EVALUATED", offer_id, "Evaluate the offer first; there is nothing to send yet.", "请先评估该报价；目前没有可发送的内容。", lang)
    version = rt.store.get_state().state_version
    counter = next((c for c in verdict.counters if c.id == counter_id), None)
    if counter is None:
        raise _counter_changed(rt, offer, verdict, version, "COUNTER_NOT_IN_VERDICT", lang)
    if (standing := _standing(rt, offer_id, lang)) is not None:
        raise standing
    if (reply := _replied(rt, offer_id)) is not None:
        raise _already_answered(offer_id, reply, lang)
    if _declined(rt, offer_id) is not None:
        raise _conflict("ALREADY_DECLINED_BY_BUYER", offer_id, "You recorded that the buyer declined this offer; send a new one from a fresh request.",
                        "您已记录买方拒绝了这份报价；请针对新的请求另行发出报价。", lang, decision_id=deal_id(offer_id))
    if (closed := lapsed_conflict(rt, offer_id, verdict, lang)) is not None:
        raise closed
    if verdict.state_version != version:
        raise _counter_changed(rt, offer, verdict, version, "BOOKS_CHANGED", lang)
    return offer, verdict, counter


def current_terms(state: Any, counterparty_id: str) -> int | None:
    """The payment terms the buyer's next invoice is issued with (the counters' own reading), else the terms of their open invoice."""
    from app.financial.invoices import terms_in_force

    terms = terms_in_force(state, counterparty_id)
    if terms is not None:
        return terms
    open_ = [r for r in state.receivables if r.status == "OPEN" and r.counterparty_id == counterparty_id]
    return open_[0].terms_days if open_ else None


def render_for(state: Any, offer: CompiledOffer, verdict: Verdict, counter: CounterProposal, *, terms_hash: str, valid_until_day: int,
               lang: Literal["en", "zh"]) -> BuyerMessage:
    """The message for `counter`, answering every term the buyer asked for (the verdict's bound obligations). Raises `NoWording`."""
    return render(counter, state, buyer_name=party_name(state, offer.counterparty_id), terms_hash=terms_hash, valid_until_day=valid_until_day,
                  lang=lang, asked=list(verdict.bound_obligations), current_terms_days=current_terms(state, offer.counterparty_id))


def message_allow(counter: CounterProposal, state: Any) -> list[AllowedValue]:
    """What the message may state: the counter's own figures, and for an early payment the net that settles its face and the rest of the
    invoice (both the buyer's own invoice, derived from the counter's terms)."""
    allow = list(_counter_allow(counter))
    for o in counter.obligations:
        if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.amount_fen:
            _cap, net = early_settlement(o)
            allow.append(AllowedValue.money(net))
            if rest := remainder_fen(o, state):
                allow.append(AllowedValue.money(rest))
    return allow


def picture_path(rt: Runtime, offer_id: str, counter_id: str, lang: str) -> dict[str, Any] | None:
    """The offer picture's path for this reply (its terms beside the ask, its cost, who decides, what a refusal leaves), else None. A picture
    that cannot be read gives none. Call under `rt.lock`."""
    from app.api.offer_picture import (
        cached_picture,  # the picture reads the decision record, which reads this module's neighbours
    )

    try:
        paths = cached_picture(rt, offer_id, lang).get("paths") or []
    except Exception:  # noqa: BLE001  a supporting read: no message rather than a guess
        return None
    return next((p for p in paths if p.get("kind") == "reply" and p.get("key") == counter_id), None)


def authority_words(needs_owner: bool | None, lang: str) -> str:
    """Whether the terms are within the owner's signed mandate: what the owner decides, never who sends (FLOW sends nothing here)."""
    return (t(lang, "Needs your approval before you send it.", "发送前需经您批准。") if needs_owner
            else t(lang, "Within your mandate: no approval needed.", "在您的授权范围内：无需批准。"))


def channel_view(lang: str) -> dict[str, str]:
    """How the message reaches the buyer: by hand, since no channel is connected, so FLOW cannot confirm where it went or that it arrived."""
    return {"kind": "manual", "label": t(lang, "Manual sending · No channel connected", "手动发送 · 未连接任何渠道"),
            "text": t(lang, "FLOW cannot send this or confirm it arrived. Copy it and send it through your usual channel.",
                      "FLOW 无法发送这条消息，也无法确认对方已收到。请复制后通过您惯用的渠道发送。")}


def review_of(path: dict[str, Any] | None, lang: str = "en") -> dict[str, Any] | None:
    """What the owner reads beside the message: the reply's terms against the ask and its cost in the picture's own words, and whether it is
    within the owner's mandate (`decides_text`). Nothing about what a refusal funds: the picture's sentence for that is the simulated send's,
    which funds the gap at once; recording a real buyer's no runs nothing. None when the picture has no such path."""
    if path is None:
        return None
    cost = path.get("cost_display")
    return {"terms": path.get("terms"), "cost_display": cost, "cost_note": path.get("cost_note"),
            "cost_text": (t(lang, f"Estimated one-time cost: {cost}", f"预计一次性成本：{cost}") if cost else None),
            "decides_text": authority_words(path.get("needs_owner"), lang), "authority": path.get("authority"),
            "needs_owner": path.get("needs_owner")}


def _message_view(rt: Runtime, offer: CompiledOffer, verdict: Verdict, counter: CounterProposal, lang: Literal["en", "zh"],
                  ui: Literal["en", "zh"] | None = None) -> dict[str, Any]:
    """The message for `counter` in `lang` (the buyer's language) with everything the send review shows beside it, worded in `ui` (the page's
    language; `lang` when not given). Call under `rt.lock`."""
    words: Literal["en", "zh"] = ui or lang
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    path = picture_path(rt, offer.offer_id, counter.id, words)
    th = terms_hash(committable(list(counter.obligations)))
    until = valid_until(counter, rt.day, mandate.expires_day)
    received = _received(rt, offer)
    via = received.via if received is not None else None
    blocked: str | None = None
    text: str | None = None
    message_hash: str | None = None
    if via not in KNOWN_SENDERS:
        blocked = "UNVERIFIED_SENDER"
    elif path is None or not path.get("sendable"):
        blocked = "NOT_SENDABLE"
    elif until < rt.day:
        blocked = "WINDOW_PASSED"
    else:
        try:
            msg = render_for(state, offer, verdict, counter, terms_hash=th, valid_until_day=until, lang=lang)
        except NoWording:
            blocked = "NO_WORDING"
        else:
            g = guard(msg.text, protected_for(rt.store), recipient_id=offer.counterparty_id, allow=message_allow(counter, state), day=rt.day,
                      lang=lang)
            if g.security_event:
                rt.store.add_security_event(g.security_event)
            if g.ok:
                text, message_hash = msg.text, msg.message_hash
            else:
                blocked = "OUTBOUND_BLOCKED"
    sent = _offered(rt, offer.offer_id, verdict.id, counter.id)
    buyer = party_name(state, offer.counterparty_id)
    return {
        "offer_id": offer.offer_id, "decision_id": deal_id(offer.offer_id), "verdict_id": verdict.id, "counter_id": counter.id,
        "counter_label_when": option_label(counter.label, words), "state_version": state.state_version,
        "counterparty_id": offer.counterparty_id, "buyer_name": buyer, "lang": lang, "ui_lang": words,
        "text": text, "message_hash": message_hash, "terms_hash": th, "template_version": TEMPLATE_VERSION,
        "copyable": text is not None,
        "blocked": None if blocked is None else {"code": blocked, "text": t(words, *_BLOCKED[blocked])},
        "valid_until_day": until, "valid_until_when": when_text(until, rt.day, words),
        "valid_until_date": calendar_date(state.as_of, until, words),
        "provenance": {"via": via, "text": _provenance_text(via, words), "verified": via in KNOWN_SENDERS},
        "review": review_of(path, words),
        "authority_text": authority_words(path.get("needs_owner") if path else None, words) if path is not None else None,
        "channel": channel_view(words),
        "languages": [{"code": "en", "label": t(words, "English", "英文")}, {"code": "zh", "label": t(words, "Chinese", "中文")}],
        "send_title_text": t(words, f"Your response to {buyer}", f"您给{buyer}的答复"),
        "offered": None if sent is None else {
            "recorded": True, "lang": sent.lang, "message_hash": sent.message_hash, "valid_until_day": sent.valid_until_day,
            "valid_until_when": when_text(sent.valid_until_day, rt.day, words), "same_message": sent.message_hash == message_hash},
        "notice_text": t(words, "FLOW does not send this message. Copy it, send it through your usual channel, then mark it as sent.",
                         "FLOW 不会发送这条消息。请复制后通过您惯用的渠道发送，然后标记为已发送。"),
        "copy_label": t(words, "Copy response", "复制答复"),
        "copied_text": t(words, "Copied", "已复制"),
        "copy_failed_text": t(words, "Could not copy. Select the message and copy it.", "无法复制。请选中消息后复制。"),
        "mark_sent_label": t(words, "Mark as sent", "标记为已发送"),
        "mark_sent_effect_text": t(words, "This records that you sent it; FLOW cannot confirm it arrived. Nothing is agreed and no money moves.",
                                   "这只记录您已发送；FLOW 无法确认对方已收到。不会达成任何协议，也不会动用资金。"),
        "back_label": t(words, "Back to Deals", "返回交易"),
        "accepted_label": t(words, "The buyer accepted", "买方已接受"),
        "reply_label": t(words, "Paste the buyer's reply", "粘贴买方的回复"),
    }


@router.get("/offers/{offer_id}/counters/{counter_id}/message")
def get_message(offer_id: str, counter_id: str, lang: str = "en", ui_lang: str | None = None) -> dict[str, Any]:
    """The message to the buyer for one counter of the latest verdict, in `lang` (en | zh): the buyer's language, which the owner picks; the
    words around it in `ui_lang` (the page's language, `lang` when absent). When FLOW prepares none, `text` is null and `blocked` says why."""
    rt = get_runtime()
    said: Literal["en", "zh"] = "zh" if lang == "zh" else "en"
    ui: Literal["en", "zh"] = said if ui_lang is None else ("zh" if ui_lang == "zh" else "en")
    with rt.lock:
        offer, verdict, counter = _current(rt, offer_id, counter_id, ui)
        return _message_view(rt, offer, verdict, counter, said, ui)


class OfferedIn(BaseModel):
    verdict_id: str
    state_version: int
    message_hash: str
    lang: Literal["en", "zh"] = "en"


@router.post("/offers/{offer_id}/counters/{counter_id}/offered")
def mark_offered(offer_id: str, counter_id: str, body: OfferedIn, lang: str = "en") -> dict[str, Any]:
    """The owner sent the message outside FLOW. Records the OFFERED fact, bound to the verdict, the books and the exact message the owner was
    shown; agrees nothing, runs nothing. A second mark of the same counter changes nothing."""
    rt = get_runtime()
    said: Literal["en", "zh"] = "zh" if lang == "zh" else "en"
    with rt.lock:
        offer, verdict, counter = _current(rt, offer_id, counter_id, said)
        version = rt.store.get_state().state_version
        if body.verdict_id != verdict.id:
            raise _counter_changed(rt, offer, verdict, version, "VERDICT_CHANGED", said)
        if body.state_version != version:
            raise _counter_changed(rt, offer, verdict, version, "BOOKS_CHANGED", said)
        _mandate_in_force(rt, offer_id, said)
        view = _message_view(rt, offer, verdict, counter, body.lang)
        if view["blocked"] is not None:
            raise _conflict(view["blocked"]["code"], offer_id, _BLOCKED[view["blocked"]["code"]][0], _BLOCKED[view["blocked"]["code"]][1], said)
        if body.message_hash != view["message_hash"]:
            other: Literal["en", "zh"] = "zh" if body.lang == "en" else "en"
            if body.message_hash == _message_view(rt, offer, verdict, counter, other)["message_hash"]:  # the other language's words were copied
                names = {"en": ("English", "英文"), "zh": ("Chinese", "中文")}
                raise _conflict("MESSAGE_LANGUAGE", offer_id,
                                f"You copied the {names[other][0]} message, but are marking the {names[body.lang][0]} one as sent; copy the "
                                f"{names[body.lang][0]} message first.",
                                f"您复制的是{names[other][1]}消息，但标记为已发送的是{names[body.lang][1]}消息；请先复制{names[body.lang][1]}消息。",
                                said, message_hash=view["message_hash"])
            raise _conflict("MESSAGE_CHANGED", offer_id, "The message changed since you copied it; copy it again before marking it sent.",
                            "您复制之后消息已有变化；请重新复制后再标记为已发送。", said, message_hash=view["message_hash"])
        fact = OfferedFact(offer_id=offer_id, verdict_id=verdict.id, counter_id=counter.id, counterparty_id=offer.counterparty_id,
                           state_version_shown=version, terms_hash=view["terms_hash"], message_hash=view["message_hash"],
                           template_version=view["template_version"], lang=body.lang, valid_until_day=view["valid_until_day"])
        n = _corrections(rt, offer_id, verdict.id, counter.id)
        if (standing_mark := _offered(rt, offer_id, verdict.id, counter.id)) is not None:  # a second mark of a standing one changes nothing
            recorded: bool | str = True if standing_mark == fact else "already_recorded_differently"
        else:
            recorded = record_fact(rt, deal_id(offer_id), f"{verdict.id}:{counter.id}" + (f":{n}" if n else ""), fact,
                                   state_version=version, day=rt.day)
        if recorded is False:
            raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id,
                                      "message_when": t(said, "FLOW could not record that you sent it; try again.", "FLOW 未能记录您已发送；请重试。")})
        sent_doc = SourceDocument(doc_id=sent_doc_id(view["message_hash"]), channel="owner", sender_id="OWNER", received_day=rt.day,
                                  text=view["text"])
        rt.documents.setdefault(sent_doc.doc_id, sent_doc)
        out = _message_view(rt, offer, verdict, counter, body.lang, said)
        out["already_recorded"] = recorded == "already_recorded_differently"
        closes = out["offered"]["valid_until_when"]
        out["message_when"] = t(said, f"Recorded as sent. The deal waits for {out['buyer_name']}'s answer; the offer closes {closes}.",
                                f"已记录为已发送。这笔交易将等待{out['buyer_name']}答复；该报价将于{closes}截止。")
        return out


# ---------------------------------------------------------------- the buyer's answer


class AcceptedIn(BaseModel):
    verdict_id: str
    state_version: int
    message_hash: str
    # the buyer's own words of acceptance, pasted by the owner as evidence (kept as a document of the deal); optional
    evidence_text: str | None = Field(default=None, max_length=4000)


def _sent_counter(rt: Runtime, offer_id: str, verdict_id: str, counter_id: str, message_hash: str | None,
                  lang: str) -> tuple[CompiledOffer, OfferedFact]:
    """The offer and the OFFERED fact the owner names, when the deal is still waiting for this buyer's answer. Call under `rt.lock`."""
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
    sent = _offered(rt, offer_id, verdict_id, counter_id)
    if sent is None or (message_hash is not None and sent.message_hash != message_hash):
        raise _not_offered(offer_id, lang)
    if (standing := _standing(rt, offer_id, lang)) is not None:
        raise standing
    if (reply := _replied(rt, offer_id)) is not None:
        raise _already_answered(offer_id, reply, lang)
    if _declined(rt, offer_id) is not None:
        raise _conflict("ALREADY_DECLINED_BY_BUYER", offer_id, "You recorded that the buyer declined this offer; nothing was changed.",
                        "您已记录买方拒绝了这份报价；未做任何更改。", lang, decision_id=deal_id(offer_id))
    if any(isinstance(f, BuyerAcceptedFact) for f in _facts(rt, offer_id)):  # the buyer's yes was recorded; its approval decided the rest
        raise _conflict("ALREADY_ANSWERED", offer_id, "You already recorded the buyer's answer to this offer; nothing was changed.",
                        "您已记录买方对这份报价的答复；未做任何更改。", lang, decision_id=deal_id(offer_id))
    return offer, sent


def _counter_lapsed(rt: Runtime, offer_id: str, counter: CounterProposal, lang: str) -> HTTPException | None:
    """409 OFFER_LAPSED when an invoice the offered counter is about is no longer owed (settled, or settled under another agreement since),
    else None. The request's own lapse (`lapsed_conflict`, read on the buyer's asked terms) does not close an offer the owner already sent:
    the message promised it until its day. Call under `rt.lock`."""
    owed = {r.id for r in rt.store.get_state().receivables if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0}
    named = {o.base.receivable_id for o in counter.obligations if o.base.receivable_id}
    if named <= owed:
        return None
    return _conflict("OFFER_LAPSED", offer_id, "The invoice this offer is about is no longer owed, so the offer has lapsed; nothing was recorded.",
                     "这份报价所针对的发票已不再欠付，报价已失效；未记录任何内容。", lang)


def _open_proposal(rt: Runtime, offer: CompiledOffer, verdict: Verdict, counter: CounterProposal) -> Commitment | None:
    """The PROPOSED commitment an earlier refused record of this answer left for these terms (its accept never queued nor ran), still unexpired,
    else None: a refused click does not leave one more proposal behind each time (SEC-03). Call under `rt.lock`."""
    want = committable(list(counter.obligations))
    entries, _ = read_entries(rt.store.operations())
    used = {e.idempotency_key for e in entries if e.result.status in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL)}
    return next((c for c in rt.store.commitments()
                 if c.offer_id == offer.offer_id and c.verdict_id == verdict.id and c.status == CommitmentStatus.PROPOSED
                 and c.expires_day >= rt.day and list(c.obligations) == want and f"{BUYER_YES}{c.id}" not in used), None)


@router.post("/offers/{offer_id}/counters/{counter_id}/buyer-accepted")
def buyer_accepted(offer_id: str, counter_id: str, body: AcceptedIn, lang: str = "en") -> dict[str, Any]:
    """The owner records that the buyer accepted the offered counter, within the day the message gave. The agreement is the counter's terms,
    bound to the verdict it was offered from, run through the executor's AcceptOffer under the owner's authority: screened against that
    verdict, re-verified on today's books, queued for approval where its tier asks."""
    rt = get_runtime()
    said = "zh" if lang == "zh" else "en"
    with rt.lock:  # one critical section from the binding check to the last write
        offer, sent = _sent_counter(rt, offer_id, body.verdict_id, counter_id, body.message_hash, said)
        if rt.day > sent.valid_until_day:
            raise _conflict("OFFER_EXPIRED", offer_id, "The offer you sent was open until a day that has passed; nothing was recorded.",
                            "您发出的报价有效期已过；未记录任何内容。", said, valid_until_day=sent.valid_until_day)
        verdict = rt.store.get_verdict(sent.verdict_id)
        counter = next((c for c in verdict.counters if c.id == counter_id), None) if verdict is not None else None
        if verdict is None or counter is None or terms_hash(committable(list(counter.obligations))) != sent.terms_hash:
            raise _not_offered(offer_id, said)
        # the counter's own invoices, not the request's: the offer stands until its day while what it is about is still owed (the
        # executor checks the same again, on today's books)
        if (closed := _counter_lapsed(rt, offer_id, counter, said)) is not None:
            raise closed
        if body.state_version != rt.store.get_state().state_version:
            raise _conflict("BOOKS_CHANGED", offer_id, "Your books changed since you read this; read it again before recording the buyer's answer.",
                            "您阅读之后账目已有变化；请重新查看后再记录买方的答复。", said, state_version=rt.store.get_state().state_version)
        _mandate_in_force(rt, offer_id, said)
        try:
            commitment = (_open_proposal(rt, offer, verdict, counter)
                          or rt.executor.propose_commitment(verdict.id, expires_day=rt.day + PROPOSAL_DAYS, counter_id=counter.id))
        except (LookupError, ValueError):
            raise _conflict("NOT_ACCEPTABLE", offer_id, "FLOW cannot record this agreement; nothing was recorded.",
                            "FLOW 无法记录这项协议；未记录任何内容。", said) from None
        mandate = rt.store.get_mandate()
        op = AcceptOffer(op_id=f"{BUYER_YES}{commitment.id}", idempotency_key=f"{BUYER_YES}{commitment.id}", mandate_version=mandate.version,
                         requested_by=Actor.OWNER, source_verdict_id=verdict.id, day=rt.day, offer_id=offer.offer_id,
                         offer_version=offer.version, terms_hash=commitment.terms_hash, nonce=commitment.nonce)
        result = rt.executor.execute(op)
        if result.status not in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL):
            raise _not_recorded(rt, offer_id, result, said, accepting=True)
        evidence_id = None
        if body.evidence_text and body.evidence_text.strip():  # buyer text, kept as a document like any buyer message, never in the fact
            doc = SourceDocument(doc_id=f"accept-{secrets.token_hex(12)}", channel="email", sender_id=offer.counterparty_id, received_day=rt.day,
                                 text=body.evidence_text, parent_doc_id=offer.doc_ids[0] if offer.doc_ids else None)
            rt.documents[doc.doc_id] = doc  # a fresh random id: no earlier submission can hold it (SEC-16)
            evidence_id = doc.doc_id
        yes = BuyerAcceptedFact(offer_id=offer_id, verdict_id=verdict.id, counter_id=counter.id, message_hash=sent.message_hash,
                                commitment_id=commitment.id, accept_op_id=op.op_id, evidence_doc_id=evidence_id)
        for _try in range(2):  # insert-if-absent, so a second try is safe
            recorded = record_fact(rt, deal_id(offer_id), f"accept-{commitment.id}", yes,
                                   state_version=rt.store.get_state().state_version, day=rt.day)
            if recorded is not False:
                break
        else:  # the agreement ran, but the record that it came from the buyer's yes did not: say so, not "recorded"
            raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id, "decision_id": deal_id(offer_id),
                                      "message_when": t(said, "The agreement went through, but FLOW could not record that the buyer accepted. "
                                                              "Open the deal to check it before you do anything else.",
                                                        "协议已生效，但 FLOW 未能记录买方已接受。请先打开这笔交易核对，再进行其他操作。")})
        out = _answer(rt, offer_id, said, accepting=True)
        out["status"] = "agreed" if result.status == OperationStatus.EXECUTED else "waiting_approval"
        out["approval_id"] = result.approval_id
        return out


DECLINE_REASONS: dict[str, tuple[str, str]] = {
    "DISCOUNT_TOO_LOW": ("Discount too low", "折扣太低"),
    "WANTED_LONGER_TERMS": ("Payment terms unacceptable", "付款期限不可接受"),
    "NO_LONGER_NEEDED": ("No longer interested", "已不再感兴趣"),
    "OTHER": ("Other", "其他"),
    "NO_REASON": ("Unknown", "原因不明"),
}


def decline_reasons(lang: str) -> list[dict[str, str]]:
    """The reasons the owner can record for a buyer's no, as codes with their words: a buyer's own words are never stored (ADR-0011)."""
    return [{"code": code, "text": t(lang, en, zh)} for code, (en, zh) in DECLINE_REASONS.items()]


def decline_reason_text(code: str | None, lang: str) -> str | None:
    return t(lang, *DECLINE_REASONS[code]) if code in DECLINE_REASONS else None


def _decision(rt: Runtime, offer_id: str, lang: str) -> dict[str, Any]:
    """The deal's decision record as `GET /decisions/{id}` gives it. Call under `rt.lock`."""
    from app.api.decisions import decision_detail, load_context
    from app.decisions import derive

    ctx = load_context(rt)
    found = ctx.states().get(deal_id(offer_id))
    if found is None:
        inp = ctx.inputs_for(deal_id(offer_id))
        found = (ctx.lapse(derive(inp)), inp)
    ds, inp = found
    return decision_detail(ctx, ds, inp, lang)


class DeclinedIn(BaseModel):
    verdict_id: str
    message_hash: str
    reason: DeclineReason = "NO_REASON"


@router.post("/offers/{offer_id}/counters/{counter_id}/buyer-declined")
def buyer_declined(offer_id: str, counter_id: str, body: DeclinedIn, lang: str = "en") -> dict[str, Any]:
    """The owner records that the buyer said no to the offered counter, with the reason they gave as a code. Nothing is agreed, run or funded;
    the deal ends as no deal and the decision record says what is left (the funding the gap still needs)."""
    rt = get_runtime()
    said = "zh" if lang == "zh" else "en"
    with rt.lock:
        _offer, sent = _sent_counter(rt, offer_id, body.verdict_id, counter_id, body.message_hash, said)
        if rt.day > sent.valid_until_day:  # unanswered by its day, the offer already closed as no deal
            raise _conflict("OFFER_EXPIRED", offer_id, "The offer you sent closed on a day that has passed; nothing was recorded.",
                            "您发出的报价已过截止日；未记录任何内容。", said, valid_until_day=sent.valid_until_day)
        recorded = record_fact(rt, deal_id(offer_id), f"declined:{sent.verdict_id}:{counter_id}",
                               BuyerDeclinedFact(offer_id=offer_id, verdict_id=sent.verdict_id, counter_id=counter_id,
                                                 message_hash=sent.message_hash, reason=body.reason),
                               state_version=rt.store.get_state().state_version, day=rt.day)
        if recorded is False:
            raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id,
                                      "message_when": t(said, "FLOW could not record the buyer's answer; try again.", "FLOW 未能记录买方的答复；请重试。")})
        return {"decision": _decision(rt, offer_id, said), "status": "declined"}


class WithdrawIn(BaseModel):
    verdict_id: str
    message_hash: str


@router.post("/offers/{offer_id}/counters/{counter_id}/offered/withdraw")
def withdraw_offered(offer_id: str, counter_id: str, body: WithdrawIn, lang: str = "en") -> dict[str, Any]:
    """The owner marked the message sent by mistake. Records the correction (OFFER_WITHDRAWN) beside the mark, never deleting it; the deal is
    ready for the owner's response again. Only while the buyer's answer is not recorded."""
    rt = get_runtime()
    said = "zh" if lang == "zh" else "en"
    with rt.lock:
        _offer, sent = _sent_counter(rt, offer_id, body.verdict_id, counter_id, body.message_hash, said)
        if rt.day > sent.valid_until_day:
            raise _conflict("OFFER_EXPIRED", offer_id, "The offer you marked sent has already closed; its record stands as it is.",
                            "您标记为已发送的报价已关闭；其记录保持不变。", said, valid_until_day=sent.valid_until_day)
        n = _corrections(rt, offer_id, sent.verdict_id, counter_id)
        recorded = record_fact(rt, deal_id(offer_id), f"withdrawn:{sent.verdict_id}:{counter_id}:{n}",
                               OfferWithdrawnFact(offer_id=offer_id, verdict_id=sent.verdict_id, counter_id=counter_id,
                                                  message_hash=sent.message_hash),
                               state_version=rt.store.get_state().state_version, day=rt.day)
        if recorded is False:
            raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id,
                                      "message_when": t(said, "FLOW could not record the correction; try again.", "FLOW 未能记录该更正；请重试。")})
        return {"decision": _decision(rt, offer_id, said), "status": "withdrawn",
                "message_when": t(said, "Corrected: the message is not marked as sent. Nothing else changed.",
                                  "已更正：这条消息不再标记为已发送。其他均未改变。")}


class ReplyIn(BaseModel):
    verdict_id: str
    counter_id: str
    text: str = Field(min_length=1, max_length=REPLY_MAX)


@router.post("/offers/{offer_id}/buyer-reply")
def buyer_reply(offer_id: str, body: ReplyIn, lang: str = "en") -> dict[str, Any]:
    """The buyer answered the offered counter with terms of their own, and the owner pasted their reply. It is compiled and stored as a new
    request from the same buyer (never as whoever the text claims), to be read and verified like any other; this deal is closed as answered
    by it. A reply with no terms in it is refused and nothing is stored: if the buyer agreed, the owner records their acceptance instead."""
    rt = get_runtime()
    said = "zh" if lang == "zh" else "en"
    with rt.lock:
        offer, _sent = _sent_counter(rt, offer_id, body.verdict_id, body.counter_id, None, said)
        digest = hashlib.sha256(f"{offer_id}|{body.text}".encode()).hexdigest()[:16]
        doc = SourceDocument(doc_id=f"reply-{digest}", channel="email", sender_id=offer.counterparty_id, received_day=rt.day, text=body.text,
                             parent_doc_id=offer.doc_ids[0] if offer.doc_ids else None)
        _unclaimed(rt, [doc])
    compiled = compile_offer([doc], offer.counterparty_id)  # outside the lock, as intake compiles
    if not compiled.obligations and not compiled.abstentions:
        raise _conflict("NO_TERMS_IN_REPLY", offer_id, "FLOW found no terms in this reply, so nothing was stored. If the buyer agreed, record their acceptance instead.",
                        "FLOW 在这条回复中没有找到任何条款，因此未保存。如果买方已同意，请改为记录其接受。", said)
    with rt.lock:  # again, after the compile: the buyer's yes or another reply may have been recorded meanwhile
        _offer, sent = _sent_counter(rt, offer_id, body.verdict_id, body.counter_id, None, said)
        late = rt.day > sent.valid_until_day  # a buyer may write after the offer closed: a request of its own, which answers nothing
        stored = store_compiled(rt, [doc], compiled, said, via="buyer_reply", in_reply_to=offer_id)
        if not late:  # the closed offer stays closed without an answer (NO_DEAL), not REPLIED
            recorded = record_fact(rt, deal_id(offer_id), compiled.offer_id,
                                   RepliedFact(offer_id=offer_id, verdict_id=body.verdict_id, counter_id=body.counter_id,
                                               reply_offer_id=compiled.offer_id),
                                   state_version=rt.store.get_state().state_version, day=rt.day)
            if recorded is False:
                raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id,
                                          "message_when": t(said, "FLOW could not record the buyer's reply; try again.", "FLOW 未能记录买方的回复；请重试。")})
    reply_decision = deal_id(compiled.offer_id)
    return {**({"offer_closed": True} if late else {}),
        "offer_id": offer_id, "decision_id": deal_id(offer_id), "reply_offer_id": compiled.offer_id, "reply_decision_id": reply_decision,
        "reply_href": f"/deals?decision={reply_decision}", "offer": stored["offer"],
        "message_when": (t(said, "The offer you sent had closed. The buyer's reply is a new request of its own; read it to answer.",
                           "您发出的报价已截止。买方的回复是一项新请求；请阅读后答复。") if late else
                         t(said, "The buyer's reply is now a request of its own. Read it to answer.", "买方的回复已作为一项新请求。请阅读后答复。")),
    }

