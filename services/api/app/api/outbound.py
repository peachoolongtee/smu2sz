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
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.accept import PROPOSAL_DAYS, _answer, _conflict, _not_recorded, _standing, over_mandate
from app.api.auth import require_feature, require_owner
from app.api.decide import _counter_allow, _counter_changed
from app.api.decisions import lapsed_conflict, latest_verdict_for, record_fact
from app.api.offers import _unclaimed, store_compiled
from app.api.presentation import option_label, party_name, t, when_text
from app.api.runtime import Runtime, get_runtime
from app.commitments import terms_hash
from app.compiler import compile_offer
from app.decisions.facts import BuyerAcceptedFact, OfferedFact, ReceivedFact, RepliedFact, parse_fact
from app.decisions.identity import deal_id
from app.domain.models import (
    AcceptOffer,
    Actor,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CounterProposal,
    OperationStatus,
    SourceDocument,
    Verdict,
)
from app.egress import guard, protected_for
from app.mandate import MandatePolicyImpl
from app.operations.executor import committable
from app.operations.log import read_entries
from app.outbound import NoWording, calendar_date, render, valid_until

router = APIRouter(tags=["offers"], dependencies=[Depends(require_owner), Depends(require_feature("terms_guard")),
                                                  Depends(require_feature("buyer_negotiation"))])

KNOWN_SENDERS = frozenset({"owner", "agent", "buyer_key", "buyer_reply"})
BUYER_YES = "buyer-yes-"  # the op id of the owner's AcceptOffer that records a buyer's yes (Activity words it as that, not "as asked")
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
    return next((f for f in reversed(_facts(rt, offer.offer_id))
                 if isinstance(f, ReceivedFact) and f.offer_id == offer.offer_id and f.offer_version == offer.version), None)


def _offered(rt: Runtime, offer_id: str, verdict_id: str, counter_id: str) -> OfferedFact | None:
    return next((f for f in _facts(rt, offer_id)
                 if isinstance(f, OfferedFact) and f.verdict_id == verdict_id and f.counter_id == counter_id), None)


def _replied(rt: Runtime, offer_id: str) -> RepliedFact | None:
    return next((f for f in _facts(rt, offer_id) if isinstance(f, RepliedFact)), None)


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
    if (closed := lapsed_conflict(rt, offer_id, verdict, lang)) is not None:
        raise closed
    if verdict.state_version != version:
        raise _counter_changed(rt, offer, verdict, version, "BOOKS_CHANGED", lang)
    return offer, verdict, counter


def _sendable(rt: Runtime, offer_id: str, counter_id: str, lang: str) -> bool:
    """Whether the offer picture lets this reply be sent (within the owner's limits). A picture that cannot be read sends nothing."""
    from app.api.offer_picture import (
        cached_picture,  # the picture reads the decision record, which reads this module's neighbours
    )

    try:
        paths = cached_picture(rt, offer_id, lang).get("paths") or []
    except Exception:  # noqa: BLE001  a supporting read: no message rather than a guess
        return False
    return any(p.get("kind") == "reply" and p.get("key") == counter_id and p.get("sendable") for p in paths)


def _message_view(rt: Runtime, offer: CompiledOffer, verdict: Verdict, counter: CounterProposal, lang: Literal["en", "zh"]) -> dict[str, Any]:
    """The message for `counter` with everything the send review shows beside it. Call under `rt.lock`."""
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    th = terms_hash(committable(list(counter.obligations)))
    until = valid_until(counter, rt.day, mandate.expires_day)
    received = _received(rt, offer)
    via = received.via if received is not None else None
    blocked: str | None = None
    text: str | None = None
    message_hash: str | None = None
    if via not in KNOWN_SENDERS:
        blocked = "UNVERIFIED_SENDER"
    elif not _sendable(rt, offer.offer_id, counter.id, lang):
        blocked = "NOT_SENDABLE"
    elif until < rt.day:
        blocked = "WINDOW_PASSED"
    else:
        try:
            msg = render(counter, state, buyer_name=party_name(state, offer.counterparty_id), terms_hash=th, valid_until_day=until, lang=lang)
        except NoWording:
            blocked = "NO_WORDING"
        else:
            g = guard(msg.text, protected_for(rt.store), recipient_id=offer.counterparty_id, allow=_counter_allow(counter), day=rt.day,
                      lang=lang)
            if g.security_event:
                rt.store.add_security_event(g.security_event)
            if g.ok:
                text, message_hash = msg.text, msg.message_hash
            else:
                blocked = "OUTBOUND_BLOCKED"
    sent = _offered(rt, offer.offer_id, verdict.id, counter.id)
    return {
        "offer_id": offer.offer_id, "decision_id": deal_id(offer.offer_id), "verdict_id": verdict.id, "counter_id": counter.id,
        "counter_label_when": option_label(counter.label, lang), "state_version": state.state_version,
        "counterparty_id": offer.counterparty_id, "buyer_name": party_name(state, offer.counterparty_id), "lang": lang,
        "text": text, "message_hash": message_hash, "terms_hash": th, "template_version": "buyer-message-v1",
        "copyable": text is not None,
        "blocked": None if blocked is None else {"code": blocked, "text": t(lang, *_BLOCKED[blocked])},
        "valid_until_day": until, "valid_until_when": when_text(until, rt.day, lang), "valid_until_date": calendar_date(state.as_of, until, lang),
        "provenance": {"via": via, "text": _provenance_text(via, lang)},
        "offered": None if sent is None else {
            "recorded": True, "lang": sent.lang, "message_hash": sent.message_hash, "valid_until_day": sent.valid_until_day,
            "valid_until_when": when_text(sent.valid_until_day, rt.day, lang), "same_message": sent.message_hash == message_hash},
        "notice_text": t(lang, "FLOW does not send this message. Copy it, send it to the buyer yourself, then mark it as sent.",
                         "FLOW 不会发送这条消息。请复制后由您亲自发给买方，然后标记为已发送。"),
        "copy_label": t(lang, "Copy the message", "复制消息"),
        "mark_sent_label": t(lang, "I've sent it to the buyer", "我已发给买方"),
        "mark_sent_effect_text": t(lang, "Marking it sent agrees nothing and moves no money: the deal waits for the buyer's answer.",
                                   "标记为已发送不会达成任何协议，也不会动用资金：这笔交易将等待买方答复。"),
        "accepted_label": t(lang, "The buyer accepted", "买方已接受"),
        "reply_label": t(lang, "Paste the buyer's reply", "粘贴买方的回复"),
    }


@router.get("/offers/{offer_id}/counters/{counter_id}/message")
def get_message(offer_id: str, counter_id: str, lang: str = "en") -> dict[str, Any]:
    """The message to the buyer for one counter of the latest verdict, in `lang` (en | zh): the buyer's language, which the owner picks. When
    FLOW prepares none, `text` is null and `blocked` says why."""
    rt = get_runtime()
    said: Literal["en", "zh"] = "zh" if lang == "zh" else "en"
    with rt.lock:
        offer, verdict, counter = _current(rt, offer_id, counter_id, said)
        return _message_view(rt, offer, verdict, counter, said)


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
            raise _conflict("MESSAGE_CHANGED", offer_id, "The message changed since you copied it; copy it again before marking it sent.",
                            "您复制之后消息已有变化；请重新复制后再标记为已发送。", said, message_hash=view["message_hash"])
        fact = OfferedFact(offer_id=offer_id, verdict_id=verdict.id, counter_id=counter.id, counterparty_id=offer.counterparty_id,
                           state_version_shown=version, terms_hash=view["terms_hash"], message_hash=view["message_hash"],
                           template_version=view["template_version"], lang=body.lang, valid_until_day=view["valid_until_day"])
        recorded = record_fact(rt, deal_id(offer_id), f"{verdict.id}:{counter.id}", fact, state_version=version, day=rt.day)
        if recorded is False:
            raise HTTPException(500, {"code": "NOT_RECORDED", "offer_id": offer_id,
                                      "message_when": t(said, "FLOW could not record that you sent it; try again.", "FLOW 未能记录您已发送；请重试。")})
        out = _message_view(rt, offer, verdict, counter, said)
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
        record_fact(rt, deal_id(offer_id), f"accept-{commitment.id}",
                    BuyerAcceptedFact(offer_id=offer_id, verdict_id=verdict.id, counter_id=counter.id, message_hash=sent.message_hash,
                                      commitment_id=commitment.id, accept_op_id=op.op_id),
                    state_version=rt.store.get_state().state_version, day=rt.day)
        out = _answer(rt, offer_id, said, accepting=True)
        out["status"] = "agreed" if result.status == OperationStatus.EXECUTED else "waiting_approval"
        out["approval_id"] = result.approval_id
        return out


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
        _sent_counter(rt, offer_id, body.verdict_id, body.counter_id, None, said)
        stored = store_compiled(rt, [doc], compiled, said, via="buyer_reply", in_reply_to=offer_id)
        record_fact(rt, deal_id(offer_id), compiled.offer_id,
                    RepliedFact(offer_id=offer_id, verdict_id=body.verdict_id, counter_id=body.counter_id, reply_offer_id=compiled.offer_id),
                    state_version=rt.store.get_state().state_version, day=rt.day)
    reply_decision = deal_id(compiled.offer_id)
    return {
        "offer_id": offer_id, "decision_id": deal_id(offer_id), "reply_offer_id": compiled.offer_id, "reply_decision_id": reply_decision,
        "reply_href": f"/deals?decision={reply_decision}", "offer": stored["offer"],
        "message_when": t(said, "The buyer's reply is now a request of its own. Read it to answer.", "买方的回复已作为一项新请求。请阅读后答复。"),
    }

