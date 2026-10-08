"""Contract ingestion (brief 03 §6.4): upload a document, review the agent's reading, confirm or reject it.

Owner only, every route: a counterparty never sees a contract record, and the agent key cannot reach them. A reading
is a proposal; confirmation is the owner's act, logged in the hash chain (CONFIRM_DOCUMENT) and bound to the hash of
the exact text shown. Nothing here writes the books.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_feature, require_owner
from app.api.runtime import Runtime, get_runtime
from app.contracts import read_document, record_view
from app.deals import documents_for
from app.domain.fixtures import contract_fixture_bytes, load_contract_fixtures
from app.domain.models import Actor, DocumentKind, SecurityEvent, SecurityEventKind
from app.ingest import IngestError, extract_text

router = APIRouter(dependencies=[Depends(require_owner), Depends(require_feature("contracts"))])

_ROLE = {DocumentKind.BUYER_CONTRACT: "BUYER", DocumentKind.LENDER_AGREEMENT: "LENDER"}


class DocumentIn(BaseModel):
    """A demo fixture (`fixture_id`, optionally its Word or PDF copy), an upload (`filename` + `content_base64`) or
    pasted `text`. The owner says what it is (`kind`) and who it is with (`counterparty_id`); a fixture says both."""

    model_config = ConfigDict(extra="forbid")

    fixture_id: str | None = Field(default=None, max_length=64)
    format: Literal["md", "docx", "pdf"] | None = None
    kind: Literal["BUYER_CONTRACT", "LENDER_AGREEMENT"] | None = None
    counterparty_id: str | None = Field(default=None, max_length=64)
    filename: str | None = Field(default=None, max_length=200)
    content_base64: str | None = Field(default=None, max_length=7_200_000)  # 5 MB of file
    text: str | None = Field(default=None, max_length=400_000)
    title: str | None = Field(default=None, max_length=120)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    link_facility_id: str | None = Field(default=None, max_length=64)


def _event(kind: SecurityEventKind, day: int, counterparty_id: str | None, detail: str, spans: list | None = None) -> None:
    rt = get_runtime()
    sid = "SEC-DOC-" + hashlib.sha256(f"{kind}|{detail}|{day}|{len(rt.store.security_events())}".encode()).hexdigest()[:12]
    rt.store.add_security_event(SecurityEvent(id=sid, day=day, kind=kind, counterparty_id=counterparty_id,
                                              action_taken="document not read into any record; nothing confirmed"
                                              if kind == SecurityEventKind.UNKNOWN_COUNTERPARTY
                                              else "flagged; the document cannot be confirmed",
                                              detail=detail, spans=spans or []))


@router.post("/documents")
def post_document(body: DocumentIn) -> dict:
    rt = get_runtime()
    title = body.title
    if body.fixture_id is not None:
        fx = load_contract_fixtures().get(body.fixture_id)
        if fx is None:
            raise HTTPException(404, {"code": "UNKNOWN_FIXTURE", "message": "no such demo document"})
        kind, cp = DocumentKind(fx["kind"]), fx["counterparty_id"]
        if (body.kind and body.kind != kind.value) or (body.counterparty_id and body.counterparty_id != cp):
            raise HTTPException(422, {"code": "FIXTURE_MISMATCH", "message": "the demo document says what it is"})
        name, data = contract_fixture_bytes(body.fixture_id, None if body.format in (None, "md") else body.format)
        source, title = f"fixture:{body.fixture_id}", title or fx["title"]
    else:
        if body.kind is None or body.counterparty_id is None:
            raise HTTPException(422, {"code": "KIND_AND_COUNTERPARTY_REQUIRED",
                                      "message": "say what the document is and who it is with"})
        kind, cp = DocumentKind(body.kind), body.counterparty_id
        if body.content_base64 is not None:
            if not body.filename:
                raise HTTPException(422, {"code": "FILENAME_REQUIRED", "message": "an upload needs its file name"})
            try:
                data = base64.b64decode(body.content_base64, validate=True)
            except (binascii.Error, ValueError):
                raise HTTPException(422, {"code": "BAD_UPLOAD", "message": "the upload is not valid base64"}) from None
            name, source = body.filename, f"upload:{body.filename}"
        elif body.text:
            name, data, source = "pasted.txt", body.text.encode("utf-8"), "text"
        else:
            raise HTTPException(422, {"code": "DOCUMENT_REQUIRED", "message": "a fixture, an upload or text is required"})
    with rt.lock:
        state = rt.store.get_state()
        party = next((c for c in state.counterparties if c.id == cp), None)
        if party is None or not party.known:
            _event(SecurityEventKind.UNKNOWN_COUNTERPARTY, rt.day, cp,
                   f"a {kind.value.lower().replace('_', ' ')} naming {cp}, who is not on the owner's registry, was "
                   f"refused before it was read")
            raise HTTPException(422, {"code": "UNKNOWN_COUNTERPARTY",
                                      "message": f"{cp} is not on your registry; documents are read only for known "
                                                 f"counterparties"})
        if party.role != _ROLE[kind]:
            raise HTTPException(422, {"code": "COUNTERPARTY_ROLE_MISMATCH",
                                      "message": f"{cp} is a {party.role.lower()}, not a {_ROLE[kind].lower()}"})
        try:
            text = extract_text(name, data)
        except IngestError as e:
            raise HTTPException(422, {"code": e.code, "message": str(e)}) from None
        record = read_document(text, kind, cp, title=title, source=source, day=rt.day, facilities=state.facilities)
        rid = rt.store.add_contract_record(record)
        stored = rt.store.get_contract_record(rid)
        assert stored is not None
        for f in stored.flags:
            if f.blocking:
                _event(SecurityEventKind.INJECTION, rt.day, cp, f"{rid}: {f.note}", [f.span])
        return {"document": record_view(stored, state)}


@router.get("/documents")
def list_documents() -> dict:
    rt = get_runtime()
    with rt.lock:
        return {"documents": documents_for(rt.store), "day": rt.day}


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    rt = get_runtime()
    with rt.lock:
        rec = rt.store.get_contract_record(document_id)
        if rec is None:
            raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
        return {"document": record_view(rec, rt.store.get_state())}


def _decide(document_id: str, body: DecisionIn, confirm: bool) -> dict:
    rt = get_runtime()
    if rt.store.get_contract_record(document_id) is None:
        raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
    result = rt.executor.decide_document(document_id, Actor.OWNER, confirm=confirm, doc_hash=body.doc_hash,
                                         link_facility_id=body.link_facility_id)
    rec = rt.store.get_contract_record(document_id)
    assert rec is not None
    return {"result": result.model_dump(mode="json"), "document": record_view(rec, rt.store.get_state())}


@router.post("/documents/{document_id}/confirm")
def confirm_document(document_id: str, body: DecisionIn) -> dict:
    return _decide(document_id, body, confirm=True)


@router.post("/documents/{document_id}/reject")
def reject_document(document_id: str, body: DecisionIn) -> dict:
    return _decide(document_id, body, confirm=False)


def confirm_demo_documents(rt: Runtime) -> None:
    """The demo's starting point: the three demo documents already read by the agent and confirmed by the owner, so the
    deal summary is ready once a deal is agreed on Deals. Each is read from its fixture text exactly as an upload is,
    and confirmed through the executor as the owner, so three CONFIRM_DOCUMENT entries open the chain. Nothing in the
    books changes."""
    with rt.lock:
        state = rt.store.get_state()
        for fixture_id, fx in load_contract_fixtures().items():
            name, data = contract_fixture_bytes(fixture_id, None)
            record = read_document(extract_text(name, data), DocumentKind(fx["kind"]), fx["counterparty_id"],
                                   title=fx["title"], source=f"fixture:{fixture_id}", day=rt.day,
                                   facilities=state.facilities)
            rid = rt.store.add_contract_record(record)
            result = rt.executor.decide_document(rid, Actor.OWNER, confirm=True, doc_hash=record.doc_hash,
                                                 link_facility_id=fx.get("link_facility_id"))
            if result.status.value != "EXECUTED":
                raise RuntimeError(f"demo document {fixture_id} was not confirmed: {result.message}")


@router.get("/fixtures/contracts")
def list_contract_fixtures() -> dict:
    return {"contracts": [{"id": k, "kind": v["kind"], "counterparty_id": v["counterparty_id"], "title": v["title"],
                           "formats": ["md", *v.get("formats", [])], "link_facility_id": v.get("link_facility_id")}
                          for k, v in load_contract_fixtures().items()]}
