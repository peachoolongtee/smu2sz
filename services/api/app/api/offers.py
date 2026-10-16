"""Intake: documents -> compiler -> stored CompiledOffer. The compiler's output is a proposal only."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.api.auth import counterparty_for_key, is_agent, require_owner
from app.api.decisions import latest_verdict_for, record_fact
from app.api.display import displayed
from app.api.presentation import abstention_words, business_text
from app.api.runtime import Runtime, get_runtime
from app.api.selection import Selection, build_context, selection
from app.compiler import compile_offer, compile_term_sheet
from app.decisions.facts import ReceivedFact, Via, parse_fact
from app.decisions.identity import deal_id
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import CompiledOffer, SourceDocument
from app.persistence import OfferVersionConflict

router = APIRouter()

# What POST /offers accepts from anyone (security register SEC-17): the compiler's time grows faster than the text, so one unbounded
# anonymous request could hold a worker for minutes. A buyer's message is short (the fixtures: at most 247 characters, 2 documents);
# the cap per document matches the one POST /nl puts on a turn. Contracts arrive through POST /documents, term sheets through
# POST /facilities/compile; neither is bounded here.
MAX_DOCUMENTS = 5
MAX_DOCUMENT_CHARS = 4000
BUYER_CHANNELS = frozenset({"chat", "email", "portal", "attachment"})  # SEC-18: only the owner files on the owner's own channels


class OfferIn(BaseModel):
    fixture_id: str | None = None
    counterparty_id: str | None = None
    documents: list[dict] | None = None


def _docs(body: OfferIn) -> tuple[list[SourceDocument], str]:
    if body.fixture_id:
        fx = load_offers().get(body.fixture_id)
        if fx is None:
            raise HTTPException(404, "unknown fixture")
        return offer_documents(body.fixture_id), fx["counterparty_id"]
    if not body.documents:
        raise HTTPException(422, "documents or fixture_id required")
    docs = [SourceDocument.model_validate_json(json.dumps(d)) for d in body.documents]
    return docs, body.counterparty_id or docs[0].sender_id


def enforce_intake_cap(rt: Runtime, route: str, claimed: str | None) -> None:
    """R04 and R05: an unauthenticated intake over today's cap is refused (429) and logged as one security event.
    The caller has already established that no owner token, agent key or valid channel key was presented."""
    import hashlib

    from app.domain.models import SecurityEvent, SecurityEventKind

    with rt.lock:
        if rt.take_intake_slot():
            return
        key = f"intake-capped {route} {claimed} {rt.day} {uuid.uuid4().hex}"
        rt.store.add_security_event(SecurityEvent(
            id="SEC-INTAKE-" + hashlib.sha256(key.encode()).hexdigest()[:12], day=rt.day,
            kind=SecurityEventKind.PRIVILEGE_ESCALATION, counterparty_id=claimed,
            action_taken="request refused before reaching any module",
            detail=f"unauthenticated intake over the daily cap of {rt.settings.intake_cap_per_day}: {route}"))
    raise HTTPException(429, {"code": "INTAKE_CAPPED",
                              "message": "too many unauthenticated submissions today; try again tomorrow or use a channel key"})


@router.post("/offers")
def post_offer(body: OfferIn, x_owner_token: str | None = Header(default=None),
               x_agent_key: str | None = Header(default=None),
               x_counterparty_key: str | None = Header(default=None), lang: Literal["en", "zh"] = "en") -> dict:
    rt = get_runtime()
    owner = rt.is_owner(x_owner_token)
    bound = counterparty_for_key(x_counterparty_key)
    if body.documents is not None:
        _bounded(body.documents, owner=owner)
    if bound is not None and not owner:
        # SEC-18: the sender is whoever the channel key says (as on POST /nl), never whoever the body claims
        if body.counterparty_id is not None and body.counterparty_id != bound:
            raise HTTPException(403, {"code": "COUNTERPARTY_MISMATCH", "message": "the channel key does not belong to the stated counterparty"})
        if body.fixture_id is None:
            body = body.model_copy(update={"counterparty_id": bound})
    agent = is_agent(x_agent_key)
    if not (owner or agent or bound):
        enforce_intake_cap(rt, "POST /offers", body.counterparty_id)
    # a channel key vouches only for its own buyer: a fixture filed under another buyer's name by that key is not that buyer's request
    claimed = (load_offers().get(body.fixture_id) or {}).get("counterparty_id") if body.fixture_id else body.counterparty_id
    via: Via = "owner" if owner else "agent" if agent else "buyer_key" if bound and claimed == bound else "anonymous"
    return intake_offer(rt, body, lang, via=via)


def _bounded(documents: list[dict], *, owner: bool) -> None:
    """SEC-17 and SEC-18: refuse, before anything is compiled, a submission too large to read or written on a channel the caller does not own."""
    if len(documents) > MAX_DOCUMENTS:
        raise HTTPException(413, {"code": "TOO_MANY_DOCUMENTS", "limit": MAX_DOCUMENTS,
                                  "message": f"at most {MAX_DOCUMENTS} documents per submission"})
    for d in documents:
        text = d.get("text") if isinstance(d, dict) else None
        if isinstance(text, str) and len(text) > MAX_DOCUMENT_CHARS:
            raise HTTPException(413, {"code": "DOCUMENT_TOO_LARGE", "limit": MAX_DOCUMENT_CHARS,
                                      "message": f"a document holds at most {MAX_DOCUMENT_CHARS} characters"})
        if not owner and isinstance(d, dict) and d.get("channel") not in BUYER_CHANNELS:
            raise HTTPException(422, {"code": "CHANNEL_NOT_ALLOWED", "channel": d.get("channel"),
                                      "message": "a buyer's document arrives by chat, email, portal or attachment"})


def _offer_view(rt: Runtime, offer: CompiledOffer, channels: Mapping[str, str], lang: str) -> dict:
    """The offer as stored, with each abstention's reason in the owner's words beside it (`reason_when`; null where there is no sentence)."""
    view = displayed(json.loads(offer.model_dump_json()))
    state = rt.store.get_state()
    for raw, said in zip(offer.abstentions, view.get("abstentions") or [], strict=False):
        said["reason_when"] = (abstention_words(raw.reason, {channels[s.doc_id] for s in raw.spans if s.doc_id in channels}, "zh" if lang == "zh" else "en")
                               or business_text(state, raw.reason, rt.day, "zh" if lang == "zh" else "en"))
    return view


def intake_offer(rt: Runtime, body: OfferIn, lang: str = "en", *, via: Via = "owner", in_reply_to: str | None = None) -> dict:
    """Compile the documents and store the offer: the part of POST /offers after the caller is known. The demo's seed replay
    (`app.api.demo_seed`) takes the same path, so a seeded offer is the offer the route would have stored (the owner's own, `via`).
    `via` is how the request reached FLOW, kept as the deal's RECEIVED fact: a message to the buyer is prepared only for a request whose
    sender is known (SEC-19)."""
    docs, cp = _docs(body)
    with rt.lock:
        _unclaimed(rt, docs)
    return store_compiled(rt, docs, compile_offer(docs, cp), lang, via=via, in_reply_to=in_reply_to)


# How much a sender vouches for a request: a stronger sender may upgrade how the same request arrived, never the other way (F4).
SENDER_RANK: dict[str, int] = {"anonymous": 0, "agent": 1, "buyer_key": 2, "buyer_reply": 2, "owner": 3}


def received_key(rt: Runtime, offer: CompiledOffer, via: Via) -> str | None:
    """The fact key to record how this request (offer, version) arrived: the plain key when nothing is recorded; a key naming the sender
    when `via` is stronger than every sender recorded so far (facts are append-only, the stronger one is a new fact that the reader prefers);
    None when an equal or stronger sender already filed it. Call under `rt.lock`."""
    base = f"{offer.offer_id}:v{offer.version}"
    store: Any = rt.store
    held = [f for f in (parse_fact(r) for r in store.decision_facts(deal_id(offer.offer_id)))
            if isinstance(f, ReceivedFact) and f.offer_id == offer.offer_id and f.offer_version == offer.version]
    if not held:
        return base
    if SENDER_RANK[via] <= max(SENDER_RANK[f.via] for f in held):
        return None
    return f"{base}:{via}"


def store_compiled(rt: Runtime, docs: list[SourceDocument], offer: CompiledOffer, lang: str = "en", *, via: Via,
                   in_reply_to: str | None = None) -> dict:
    """Store a compiled offer and its documents, with how it reached FLOW (its RECEIVED fact). `intake_offer` and the buyer's pasted reply
    (`app.api.outbound`) both end here."""
    with rt.lock:
        _unclaimed(rt, docs)  # again: another submission may have taken the id while this one compiled
        try:
            rt.store.put_offer(offer)
        except OfferVersionConflict:
            raise HTTPException(409, {"code": "OFFER_VERSION_CONFLICT", "offer_id": offer.offer_id}) from None
        for d in docs:
            rt.documents[d.doc_id] = d
        key = received_key(rt, offer, via)
        if key is not None:
            record_fact(rt, deal_id(offer.offer_id), key,
                        ReceivedFact(offer_id=offer.offer_id, offer_version=offer.version, counterparty_id=offer.counterparty_id, via=via,
                                     in_reply_to_offer_id=in_reply_to),
                        state_version=rt.store.get_state().state_version, day=rt.day)
    return {"offer": _offer_view(rt, offer, {d.doc_id: d.channel for d in docs}, lang),
            "documents": [json.loads(d.model_dump_json()) for d in docs]}


def _unclaimed(rt: Runtime, docs: list[SourceDocument]) -> None:
    """SEC-16: a document id names one document. Sending the same document again is harmless; a different document under an id already
    stored would replace the words the owner reads (and the spans of the offer that quoted them), so it is refused. Call under `rt.lock`."""
    for d in docs:
        held = rt.documents.get(d.doc_id)
        if held is not None and held != d:
            raise HTTPException(409, {"code": "DOCUMENT_ID_TAKEN", "doc_id": d.doc_id,
                                      "message": "a different document already has this id; send it under a new id"})


@router.get("/offers/{offer_id}", dependencies=[Depends(require_owner)])
def get_offer(offer_id: str, lang: Literal["en", "zh"] = "en", *, sel: Annotated[Selection, Depends(selection)]) -> dict:
    """The compiled offer as stored (its latest version) with the id of the latest verdict stored for it and its decision id
    (ADR-0011), so a page can open an offer without the session cache (ledger F06), and the `context` of the URL contract
    (`app.api.selection`: the selections this record honours, the way back, and what it could not use). Owner only."""
    from app.decisions.identity import deal_id

    rt = get_runtime()
    with rt.lock:
        offer = rt.store.get_offer(offer_id)
        if offer is None:
            raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
        latest = latest_verdict_for(rt, offer_id)
        documents = [json.loads(rt.documents[d].model_dump_json()) for d in offer.doc_ids if d in rt.documents]
        context = build_context(rt, lang, sel, page="offer", buyer=offer.counterparty_id, deal=deal_id(offer_id))
    return {"offer": _offer_view(rt, offer, {d["doc_id"]: d["channel"] for d in documents}, lang), "documents": documents,
            "latest_verdict_id": latest.id if latest is not None else None, "decision_id": deal_id(offer_id), "context": context}


@router.post("/facilities/compile", dependencies=[Depends(require_owner)])
def post_term_sheet(body: OfferIn) -> dict:
    docs, _ = _docs(body)
    ts = compile_term_sheet(docs[0])
    return {"term_sheet": json.loads(ts.model_dump_json()), "document": json.loads(docs[0].model_dump_json()),
            "note": "Proposal only. The owner must approve before it enters the funding menu."}


@router.get("/fixtures/offers")
def list_offer_fixtures() -> dict:
    from app.config import get_settings

    show_security = get_settings().features.security_scenes
    return {"offers": [{"id": k, "counterparty_id": v["counterparty_id"], "kind": v.get("kind", "offer"),
                        "text": v["documents"][0]["text"]} for k, v in load_offers().items()
                       if show_security or not k.startswith("SEC_")]}
