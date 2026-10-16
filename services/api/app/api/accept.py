"""Accept the buyer's request as asked, or decline it (map #121, "Accept as asked").

A negotiation whose request needs the owner's review (`lifecycle: owner_review`: the verdict is NEEDS_OWNER_APPROVAL and FLOW has no counter) had
no way to be answered. Two owner-only routes answer it, each bound to what the owner was shown (the verdict and the books' state version):

    POST /offers/{offer_id}/accept   {verdict_id, state_version}           the buyer's terms become the agreement, as asked
    POST /offers/{offer_id}/decline  {verdict_id, state_version, reason?}  the request is closed; nothing moves

The accept runs the executor's AcceptOffer under the OWNER's authority. The executor queues it (an agreement that lengthens terms, or is not an
early payment on a named invoice, is Tier 2) and the owner's own call is the approval: the same request approves it, so the approvals history
holds an approval decided by the owner, as it does for any approved approval, and Activity says "You accepted ...". The funding plan for the
asked path is none (#132): nothing is drawn, financed or paid, and the receipt says so. A request over a hard limit the owner cannot waive (the
mandate's signed cap, or a mandate that is not in force) is 409 OVER_MANDATE: only a new mandate changes it.

The decline runs the executor's RejectOffer under the owner's authority. Nothing moves; the decision becomes DECLINED and leaves every tier.

`accept_block` is the `accept` block of the offer picture and of the Deals workspace: whether the asked path can be accepted and why not, the
two button labels, and the receipt of accepting. The receipt is built from the words the picture already carries for the asked path (its cost
words); a line it has no word for is null, never invented. Written for `lang` through `t(lang, en, zh)` (INVARIANT 13): no id in a sentence.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Mapping
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import require_feature, require_owner
from app.api.decisions import (
    decision_detail,
    lapsed_conflict,
    latest_verdict_for,
    load_context,
    sent_outside_conflict,
)
from app.api.presentation import business_text, party_name, request_of, t
from app.api.receipt import receipt
from app.api.runtime import Runtime, get_runtime
from app.api.subjects import ask_phrase
from app.decisions import derive
from app.decisions.identity import deal_id
from app.decisions.state import owner_declined
from app.domain.models import (
    AcceptOffer,
    Actor,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    OperationResult,
    OperationStatus,
    Outcome,
    RejectOffer,
    Tier,
    Verdict,
)
from app.mandate import MandatePolicyImpl
from app.operations.executor import committable
from app.operations.log import read_entries
from app.persistence.records import ApprovalStatus
from app.verifier.evaluate import CAP_CODES

log = logging.getLogger("termsledger.decisions")
router = APIRouter(tags=["offers"], dependencies=[Depends(require_owner), Depends(require_feature("terms_guard"))])

# how long a proposed agreement waits for its acceptance: the window `POST /negotiate` gives a send, and nothing else here is timed
PROPOSAL_DAYS = 7
REASON_MAX = 500

FLOW_MAY, NEEDS_OWNER, OVER_LIMIT = "flow_may", "needs_owner", "over_limit"  # the offer picture's three classes of who decides the asked path


# ---------------------------------------------------------------- the words


def commit_label(lang: str) -> str:
    return t(lang, "Accept their request", "接受对方的要求")


def decline_label(lang: str) -> str:
    return t(lang, "Decline the request", "拒绝该请求")


def over_limit_text(lang: str) -> str:
    """Why the asked path cannot be accepted when it crosses a limit the owner signed (the picture's words for the same class)."""
    return t(lang, "Over a limit you signed: only a new mandate changes that.", "超出您签署的上限：只有签署新的授权才能改变。")


def not_acceptable_text(lang: str) -> str:
    return t(lang, "FLOW cannot accept their request.", "FLOW 无法接受对方的要求。")


def asked_authority(verdict: Verdict) -> str | None:
    """Who decides the offer as asked, the way the offer picture classes it: over a limit you signed (a cap code), the owner (the verdict's tier,
    the funding plan's flag, or a verdict that asks for the owner), FLOW alone, or None when the asked terms cannot be accepted at all."""
    codes = {v.code for v in verdict.violations}
    if codes & CAP_CODES:
        return OVER_LIMIT
    if verdict.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL) and committable(list(verdict.bound_obligations)):
        owner = (verdict.required_tier != Tier.TIER_1 or bool(verdict.plan is not None and verdict.plan.needs_owner_approval)
                 or verdict.outcome == Outcome.NEEDS_OWNER_APPROVAL)
        return NEEDS_OWNER if owner else FLOW_MAY
    return None


def _asks(state: Any, verdict: Verdict, lang: str) -> list[str]:
    """What the buyer asks, one phrase each, from the obligations the agreement would carry (never a claimed prior concession)."""
    return [ask_phrase(state, o, lang) for o in committable(list(verdict.bound_obligations))]


def _cost_lines(cost: Mapping[str, Any], months: int, lang: str) -> tuple[str | None, str | None]:
    """(the fees line, the future-cost sentence) from the asked path's own cost words: its one total and the basis it states, else its two parts
    side by side (never added). Both None when the path carries no cost word."""
    total, basis = cost.get("cost_total_display"), cost.get("cost_basis_text")
    once, forward = cost.get("cost_once_display"), cost.get("cost_forward_display")
    if total:
        fees = f"{total}{t(lang, ', ', '，')}{basis}" if basis else str(total)
        return fees, t(lang, f"Future cost of the terms you accept: {fees}.", f"您接受这些条款的未来成本：{fees}。")
    if once and forward:
        fees = t(lang, f"{once} once, and {forward} over {months} months", f"一次性 {once}，另加 {months} 个月内 {forward}")
        return fees, t(lang, f"Future cost of the terms you accept: {fees}.", f"您接受这些条款的未来成本：{fees}。")
    return None, None


def _cash_text(cost: Mapping[str, Any], lang: str) -> str | None:
    """What the asked terms do to cash, in the asked path's own words (its band and the day it first goes below the minimum), and that accepting
    runs no funding for it. Null when the asked path keeps the reserve (the picture has no band for it) or carries no such word."""
    band, when = cost.get("band_text"), cost.get("first_breach_when")
    if not band:
        return None
    start = (f", starting {when}" if when else "") if lang != "zh" else (f"（最早{' ' if str(when)[:1].isdigit() else ''}{when}）" if when else "")
    return t(lang, f"If you accept their request: {str(band)[:1].lower() + str(band)[1:]}{start}. Accepting runs no funding, so that gap stays open.",
             f"如果接受对方的要求：{band}{start}。接受不会办理融资，缺口仍然存在。")


def accept_receipt(lang: str, state: Any, verdict: Verdict, *, buyer: str, authority: str, cost: Mapping[str, Any] | None, months: int) -> dict[str, str | None]:
    """The receipt of accepting the asked terms (the eleven fields, then `cash_text`): what is authorized, that it records the agreement and moves no money, that nobody
    else has to agree (these are the buyer's own terms), and who decides. `cost` is the asked path's cost words (None: the picture could not be
    read, and the lines that need them are null)."""
    sep = t(lang, "; ", "；")
    asks = sep.join(_asks(state, verdict, lang))
    asked = request_of(buyer, lang)
    fees, future = _cost_lines(cost or {}, months, lang)
    return {**receipt(
        authorizes_text=(t(lang, f"Accept {asked}: {asks}; FLOW records the agreement under your authority.",
                           f"接受{asked}：{asks}；FLOW 将在您的授权下记录这份协议。") if asks else None),
        executes_now_text=t(lang, "Records the agreement now; no payment and no funding moves.", "立即记录协议；不会有付款，也不会办理融资。"),
        others_must_agree_text=t(lang, "Nobody else: these are the buyer's own terms.", "无需其他方同意：这些就是买方自己提出的条款。"),
        in_hand_vs_future_text=future,
        fees_display=fees,
        when_text=t(lang, "As soon as you confirm.", "您确认后立即生效。"),
        assumptions_text=t(lang, "Priced on today's books with no new funding. If the books move before you confirm, nothing is recorded and you are asked to look again.",
                           "按今天的账目定价，不新增融资。如果在您确认之前账目有变动，将不会记录任何内容，并请您重新查看。"),
        authority_text=(t(lang, "Above what FLOW may agree alone; your click is the approval.", "超出 FLOW 可自行同意的范围；您的点击即是批准。")
                        if authority == NEEDS_OWNER else t(lang, "Within what FLOW may agree.", "在 FLOW 可同意的范围内。")),
        remaining_text=t(lang, "Nothing remains open once recorded.", "记录之后没有未决事项。")), "cash_text": _cash_text(cost or {}, lang)}


def decline_receipt(lang: str, state: Any, verdict: Verdict, *, buyer: str) -> dict[str, str | None]:
    """The receipt of declining the request: it closes the offer and moves nothing. Nobody is told by FLOW."""
    sep = t(lang, "; ", "；")
    asks = sep.join(_asks(state, verdict, lang))
    asked = request_of(buyer, lang)
    return receipt(
        authorizes_text=(t(lang, f"Decline {asked}: {asks}.", f"拒绝{asked}：{asks}。") if asks else t(lang, f"Decline {asked}.", f"拒绝{asked}。")),
        executes_now_text=t(lang, "Records your refusal now; nothing is agreed, sent, paid or funded.", "立即记录您的拒绝；不会达成、发送、支付或融资任何事项。"),
        others_must_agree_text=t(lang, "Nobody else: the choice is yours.", "无需其他方同意：这由您决定。"),
        in_hand_vs_future_text=t(lang, "Your cash does not change: no payment is made and no concession is booked.", "您的现金不变：不付款，也不记入任何让步。"),
        when_text=t(lang, "As soon as you confirm.", "您确认后立即生效。"),
        authority_text=t(lang, "Your decision; declining needs no one else's approval.", "由您决定；拒绝无需其他人批准。"),
        remaining_text=t(lang, "The offer is closed. FLOW sends nothing to the buyer.", "该报价已关闭。FLOW 不会向买方发送任何内容。"))


def accept_block(lang: str, *, state: Any, offer: CompiledOffer, verdict: Verdict, months: int, lapsed_text: str | None = None,
                 cost: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The `accept` block of the offer picture and the workspace: `available` and, when it is not, `reason_text` (the offer has lapsed, the asked
    terms are over a limit the owner signed, or FLOW cannot accept them as asked); the two button labels; `decline_available` (a request can be
    declined whatever its verdict, unless the offer has lapsed); and the `receipt` of accepting, null when there is nothing to accept."""
    authority = None if lapsed_text is not None else asked_authority(verdict)
    ok = authority in (FLOW_MAY, NEEDS_OWNER)
    reason = lapsed_text if lapsed_text is not None else None if ok else over_limit_text(lang) if authority == OVER_LIMIT else not_acceptable_text(lang)
    buyer = party_name(state, offer.counterparty_id)
    return {"available": ok, "reason_text": reason, "authority": authority, "commit_label": commit_label(lang), "decline_label": decline_label(lang),
            "decline_available": lapsed_text is None,
            "receipt": accept_receipt(lang, state, verdict, buyer=buyer, authority=authority or NEEDS_OWNER, cost=cost, months=months) if ok else None}


# ---------------------------------------------------------------- the routes' bindings and refusals


class AcceptIn(BaseModel):
    """What the owner was shown: the verdict and the books' state version of the read they are answering. Both are required, and any mismatch is
    409 COUNTER_CHANGED with nothing accepted or declined."""

    verdict_id: str
    state_version: int


class DeclineIn(AcceptIn):
    # The owner's own words for the refusal. RejectOffer carries no free text and the ledger stores none (INVARIANT: no sentence is stored), so the
    # reason is accepted, bounded and not kept.
    reason: str | None = Field(default=None, max_length=REASON_MAX)


def _conflict(code: str, offer_id: str, en: str, zh: str, lang: str, **more: Any) -> HTTPException:
    return HTTPException(409, detail={"code": code, "offer_id": offer_id, "message": en, "message_when": t(lang, en, zh), **more})


def over_mandate(offer_id: str, lang: str, *, why: str | None = None) -> HTTPException:
    """409 OVER_MANDATE {code, message, message_when}: the owner cannot waive it; only a new mandate changes it. Nothing was accepted."""
    en = "This request is over a limit you signed, and only a new mandate changes that. Nothing was accepted."
    zh = "该请求超出了您签署的上限，只有签署新的授权才能改变。未接受任何内容。"
    if why == "mandate":
        en = "Your signed mandate is not in force, and only a new mandate changes that. Nothing was recorded."
        zh = "您签署的授权目前无效，只有签署新的授权才能改变。未记录任何内容。"
    return _conflict("OVER_MANDATE", offer_id, en, zh, lang)


def _changed(rt: Runtime, offer: CompiledOffer, verdict: Verdict, version: int, why: str, lang: str, *, accepting: bool) -> HTTPException:
    """The negotiate route's COUNTER_CHANGED, worded for a request that was to be accepted or declined."""
    from app.api.decide import (
        _counter_changed,  # decide builds the workspace, which carries this module's block
    )

    exc = _counter_changed(rt, offer, verdict, version, why, lang)
    en = (f"The request changed since you read it; nothing was {'accepted' if accepting else 'declined'}. Review it again.")
    zh = f"该请求在您阅读之后已发生变化，未{'接受' if accepting else '拒绝'}任何内容。请重新查看。"
    return HTTPException(exc.status_code, detail={**cast(dict[str, Any], exc.detail), "message": en, "message_when": t(lang, en, zh)})


def _answered(rt: Runtime, offer_id: str) -> tuple[str, Commitment | None] | None:
    """What has already been done with this request: ("accepted", the agreement in force), ("pending", the agreement waiting for the owner's
    approval: an accept something else queued), ("declined", None) when the owner declined it, else None."""
    live = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE, CommitmentStatus.FULFILLED)
    mine = [c for c in rt.store.commitments() if c.offer_id == offer_id]
    agreement = next((c for c in mine if c.status in live), None)
    if agreement is not None:
        return "accepted", agreement
    waiting = {c.nonce for c in mine if c.status == CommitmentStatus.PROPOSED}
    queued = next((c for c in mine if c.nonce in waiting and any(
        a.status == ApprovalStatus.PENDING and _names(a.op_json, c.nonce) for a in rt.store.approvals())), None)
    if queued is not None:
        return "pending", queued
    entries, _ = read_entries(rt.store.operations())
    if owner_declined([e for e in entries if e.payload.get("offer_id") == offer_id]):
        return "declined", None
    return None


def answered_block(rt: Runtime, offer_id: str, block: Mapping[str, Any] | None, lang: str) -> dict[str, Any] | None:
    """The `accept` block as it stands now. The picture is cached per version of the books, and a refusal changes no books, so the block it
    carries is read again against the log here: a request already accepted, waiting for approval or declined is not available, and says why.
    Call under `rt.lock`."""
    if block is None:
        return None
    answered = _answered(rt, offer_id)
    if answered is None:
        return dict(block)
    why = {"accepted": t(lang, "An agreement for this request is already in place.", "该请求的协议已经生效。"),
           "pending": t(lang, "An agreement for this request is already waiting for your approval.", "该请求的协议已在等待您批准。"),
           "declined": t(lang, "You declined this request.", "您已拒绝该请求。")}[answered[0]]
    return {**block, "available": False, "reason_text": why, "decline_available": False, "receipt": None}


def _standing(rt: Runtime, offer_id: str, lang: str) -> HTTPException | None:
    """409 ALREADY_ACCEPTED when an agreement from this offer is in force, 409 ALREADY_SENT when one is already waiting for the owner's approval,
    409 ALREADY_DECLINED when the owner declined it: the request is answered, and answering it again changes nothing."""
    answered = _answered(rt, offer_id)
    if answered is None:
        return None
    kind, agreement = answered
    if agreement is not None:
        approval = next((a for a in reversed(rt.store.approvals()) if _names(a.op_json, agreement.nonce)), None)
        waiting = kind == "pending"
        return _conflict("ALREADY_SENT" if waiting else "ALREADY_ACCEPTED", offer_id,
                         "An agreement for this request is already waiting for your approval; nothing was recorded again." if waiting
                         else "An agreement for this request already exists; nothing was recorded again.",
                         "该请求的协议已在等待您批准；未重复记录。" if waiting else "该请求的协议已存在；未重复记录。", lang,
                         decision_id=deal_id(offer_id), commitment_id=agreement.id, commitment_status=agreement.status.value,
                         approval_id=approval.id if approval is not None else None)
    return _conflict("ALREADY_DECLINED", offer_id, "This request was already declined; nothing was changed.", "该请求已被拒绝；未做任何更改。",
                     lang, decision_id=deal_id(offer_id))


def _names(op_json: str, nonce: str) -> bool:
    try:
        return json.loads(op_json).get("nonce") == nonce
    except (ValueError, AttributeError):
        return False


def _bound(rt: Runtime, offer_id: str, body: AcceptIn, lang: str, *, accepting: bool) -> tuple[CompiledOffer, Verdict]:
    """The offer and the verdict the owner was shown, after every check that the request is still what they read. Call under `rt.lock`."""
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
    latest = latest_verdict_for(rt, offer_id)
    if latest is None:
        raise _conflict("NOT_EVALUATED", offer_id, "Evaluate the offer first; there is nothing to answer yet.", "请先评估该报价；目前没有可回应的内容。", lang)
    version = rt.store.get_state().state_version
    if body.verdict_id != latest.id:
        raise _changed(rt, offer, latest, version, "VERDICT_CHANGED", lang, accepting=accepting)
    if (standing := _standing(rt, offer_id, lang)) is not None:
        raise standing  # whatever the books have done since, the owner learns the request is answered
    if (outside := sent_outside_conflict(rt, offer_id, lang)) is not None:
        raise outside  # the buyer has the owner's counter: their answer is recorded on the deal
    if (closed := lapsed_conflict(rt, offer_id, latest, lang)) is not None:
        raise closed
    if body.state_version != version or latest.state_version != version:
        raise _changed(rt, offer, latest, version, "BOOKS_CHANGED", lang, accepting=accepting)
    mandate = rt.store.get_mandate()
    if MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex).check_validity(mandate, rt.day, mandate.version):
        raise over_mandate(offer_id, lang, why="mandate")
    return offer, latest


def _open_proposal(rt: Runtime, offer: CompiledOffer, verdict: Verdict) -> Commitment | None:
    """The PROPOSED commitment an earlier refused accept of this verdict left (its accept never queued nor ran), still unexpired, else None.
    Reusing it keeps a refused click from leaving one more proposal behind each time (SEC-03). Call under `rt.lock`."""
    want = committable(list(verdict.bound_obligations))
    entries, _ = read_entries(rt.store.operations())
    used = {e.idempotency_key for e in entries if e.result.status in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL)}
    return next((c for c in rt.store.commitments()
                 if c.offer_id == offer.offer_id and c.verdict_id == verdict.id and c.status == CommitmentStatus.PROPOSED
                 and c.expires_day >= rt.day and list(c.obligations) == want and f"accept-{c.id}" not in used), None)


def _not_recorded(rt: Runtime, offer_id: str, result: OperationResult, lang: str, *, accepting: bool) -> HTTPException:
    """409 NOT_RECORDED: the executor refused the owner's request after every check here passed (a circuit it opened, the books moved under it).
    Its reason, in Business words."""
    state = rt.store.get_state()
    reason = business_text(state, "; ".join(v.message for v in result.violations) or result.message.removeprefix("Refused: "), rt.day, lang) or ""
    en = f"FLOW could not {'record the agreement' if accepting else 'record your refusal'}. {reason}".strip()
    zh = f"FLOW 未能{'记录协议' if accepting else '记录您的拒绝'}。{reason}".strip()
    return _conflict("NOT_RECORDED", offer_id, en, zh, lang, reason_text=reason or None)


def _answer(rt: Runtime, offer_id: str, lang: str, *, accepting: bool) -> dict[str, Any]:
    """The decision record as `GET /decisions/{id}` gives it, with the receipt (the agreement's, or the refusal's) and what was executed."""
    ctx = load_context(rt)
    found = ctx.states().get(deal_id(offer_id))
    if found is None:
        inp = ctx.inputs_for(deal_id(offer_id))
        found = (ctx.lapse(derive(inp)), inp)
    ds, inp = found
    detail = decision_detail(ctx, ds, inp, lang)
    if accepting:
        receipt_block = (detail.get("agreement") or {}).get("receipt")
    else:
        verdict = ds.verdict
        receipt_block = (decline_receipt(lang, ctx.state, verdict, buyer=party_name(ctx.state, ds.offer.counterparty_id))
                         if verdict is not None and ds.offer is not None else None)
    return {"decision": detail, "receipt": receipt_block, "execution": {"summary_text": detail["execution"]["summary_text"]}}


# ---------------------------------------------------------------- the routes


@router.post("/offers/{offer_id}/accept")
def accept_as_asked(offer_id: str, body: AcceptIn, lang: str = "en") -> dict[str, Any]:
    """Accept the buyer's request as asked, under the owner's authority. `lang` (en | zh, additive) is the language of the words the server
    writes (the decision record, the receipt, `message_when`)."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:  # one critical section from the binding check to the last write: what was checked is what runs
        offer, verdict = _bound(rt, offer_id, body, lang, accepting=True)
        authority = asked_authority(verdict)
        if authority == OVER_LIMIT:
            raise over_mandate(offer_id, lang)
        if authority is None:
            raise _conflict("NOT_ACCEPTABLE", offer_id, "FLOW cannot accept their request; nothing was accepted.",
                            "FLOW 无法按对方的要求接受该请求；未接受任何内容。", lang)
        try:
            # the verdict's own bound terms, no counter; an earlier refused attempt's proposal is reused, never a new one per click (SEC-03)
            commitment = _open_proposal(rt, offer, verdict) or rt.executor.propose_commitment(verdict.id, expires_day=rt.day + PROPOSAL_DAYS)
        except (LookupError, ValueError):
            raise _conflict("NOT_ACCEPTABLE", offer_id, "FLOW cannot accept their request; nothing was accepted.",
                            "FLOW 无法按对方的要求接受该请求；未接受任何内容。", lang) from None
        mandate = rt.store.get_mandate()
        op = AcceptOffer(op_id=f"accept-{commitment.id}", idempotency_key=f"accept-{commitment.id}", mandate_version=mandate.version,
                         requested_by=Actor.OWNER, source_verdict_id=verdict.id, day=rt.day, offer_id=offer.offer_id,
                         offer_version=offer.version, terms_hash=commitment.terms_hash, nonce=commitment.nonce)
        result = rt.executor.execute(op)
        if result.status == OperationStatus.PENDING_APPROVAL and result.approval_id:
            # the executor queued it (the agreement is Tier 2): the owner's click on this route is the approval, recorded as the owner's own decision
            result = rt.executor.decide(result.approval_id, True, Actor.OWNER)
        if result.status != OperationStatus.EXECUTED:
            raise _not_recorded(rt, offer_id, result, lang, accepting=True)
        return _answer(rt, offer_id, lang, accepting=True)


@router.post("/offers/{offer_id}/decline")
def decline_request(offer_id: str, body: DeclineIn, lang: str = "en") -> dict[str, Any]:
    """Decline the buyer's request, under the owner's authority. Nothing is agreed, sent, paid or funded, and the decision is closed."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        offer, verdict = _bound(rt, offer_id, body, lang, accepting=False)
        codes = list(dict.fromkeys(v.code for v in verdict.violations))
        mandate = rt.store.get_mandate()
        # SEC-04: a server-side random part, so no other credential can claim this key first; a second click is ALREADY_DECLINED (`_standing`)
        key = f"decline-{offer_id}-{verdict.id}-{secrets.token_hex(6)}"
        op = RejectOffer(op_id=key, idempotency_key=key, mandate_version=mandate.version,
                         requested_by=Actor.OWNER, source_verdict_id=verdict.id, day=rt.day, offer_id=offer.offer_id, reason_codes=codes)
        result = rt.executor.execute(op)
        if result.status != OperationStatus.EXECUTED:
            raise _not_recorded(rt, offer_id, result, lang, accepting=False)
        return _answer(rt, offer_id, lang, accepting=False)


__all__ = ["AcceptIn", "DeclineIn", "accept_block", "accept_receipt", "answered_block", "asked_authority", "decline_receipt", "router"]
