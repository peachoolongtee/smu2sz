"""Intake: documents -> compiler -> stored CompiledOffer. The compiler's output is a proposal only."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.api.auth import counterparty_for_key, is_agent, require_owner
from app.api.decisions import latest_verdict_for
from app.api.display import displayed
from app.api.runtime import Runtime, get_runtime
from app.compiler import compile_offer, compile_term_sheet
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import SourceDocument
from app.persistence import OfferVersionConflict

router = APIRouter()


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
        key = f"intake-capped {route} {claimed} {rt.day} {len(rt.store.security_events())}"
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
               x_counterparty_key: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    if not (rt.is_owner(x_owner_token) or is_agent(x_agent_key) or counterparty_for_key(x_counterparty_key)):
        enforce_intake_cap(rt, "POST /offers", body.counterparty_id)
    return intake_offer(rt, body)


def intake_offer(rt: Runtime, body: OfferIn) -> dict:
    """Compile the documents and store the offer: the part of POST /offers after the caller is known. The demo's seed replay
    (`app.api.demo_seed`) takes the same path, so a seeded offer is the offer the route would have stored."""
    docs, cp = _docs(body)
    offer = compile_offer(docs, cp)
    try:
        rt.store.put_offer(offer)
    except OfferVersionConflict:
        raise HTTPException(409, {"code": "OFFER_VERSION_CONFLICT", "offer_id": offer.offer_id}) from None
    for d in docs:
        rt.documents[d.doc_id] = d
    return {"offer": displayed(json.loads(offer.model_dump_json())), "documents": [json.loads(d.model_dump_json()) for d in docs]}


@router.get("/offers/{offer_id}", dependencies=[Depends(require_owner)])
def get_offer(offer_id: str) -> dict:
    """The compiled offer as stored (its latest version) with the id of the latest verdict stored for it and its decision id
    (ADR-0011), so a page can open an offer without the session cache (ledger F06). Owner only."""
    from app.decisions.identity import deal_id

    rt = get_runtime()
    with rt.lock:
        offer = rt.store.get_offer(offer_id)
        if offer is None:
            raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
        latest = latest_verdict_for(rt, offer_id)
        documents = [json.loads(rt.documents[d].model_dump_json()) for d in offer.doc_ids if d in rt.documents]
    return {"offer": displayed(json.loads(offer.model_dump_json())), "documents": documents,
            "latest_verdict_id": latest.id if latest is not None else None, "decision_id": deal_id(offer_id)}


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
