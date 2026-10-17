"""Contract ingestion (brief 03 §6.4): upload a document, review the agent's reading, confirm or reject it.

Owner only, every route: a counterparty never sees a contract record, and the agent key cannot reach them. A reading
is a proposal; confirmation is the owner's act, logged in the hash chain (CONFIRM_DOCUMENT) and bound to the hash of
the exact text shown. Nothing here writes the books.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_feature, require_owner
from app.api.document_outcome import document_outcome
from app.api.errors import ALREADY_DECIDED_CODE
from app.api.presentation import t
from app.api.runtime import Runtime, get_runtime
from app.compiler import ContractTooLong
from app.config import get_settings
from app.contracts import PARTY_FLAG_KINDS, read_document, record_view, with_party_check
from app.contracts.parties import without_party_check
from app.contracts.records import suggest_facility
from app.deals import documents_for
from app.domain.fixtures import (
    capex_contract_fixture_bytes,
    contract_fixture_bytes,
    load_capex_contract_fixtures,
    load_contract_fixtures,
)
from app.domain.models import (
    Actor,
    ContractRecord,
    DocumentKind,
    DocumentStatus,
    OperationResult,
    OperationStatus,
    SecurityEvent,
    SecurityEventKind,
    Tier,
)
from app.ingest import DocumentTooLarge, IngestError, extract_text

router = APIRouter(dependencies=[Depends(require_owner), Depends(require_feature("contracts"))])

Lang = Literal["en", "zh"]
_ROLE = {DocumentKind.BUYER_CONTRACT: "BUYER", DocumentKind.LENDER_AGREEMENT: "LENDER",
         DocumentKind.CAPEX_CONTRACT: "SUPPLIER"}
_ROLE_WORDS = {"BUYER": ("customer", "客户"), "LENDER": ("lender", "贷款方"), "SUPPLIER": ("supplier", "供应商")}
# ADR-0013 (D12): the vendor of a capex contract need not be on the registry yet (the owner is shopping); committing the
# purchase registers it. Its id must still look like a registry id.
_VENDOR_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")


class DocumentIn(BaseModel):
    """A demo fixture (`fixture_id`, optionally its Word or PDF copy), an upload (`filename` + `content_base64`) or
    pasted `text`. The owner says what it is (`kind`) and who it is with (`counterparty_id`); a fixture says both."""

    model_config = ConfigDict(extra="forbid")

    fixture_id: str | None = Field(default=None, max_length=64)
    format: Literal["md", "docx", "pdf"] | None = None
    kind: Literal["BUYER_CONTRACT", "LENDER_AGREEMENT", "CAPEX_CONTRACT"] | None = None
    counterparty_id: str | None = Field(default=None, max_length=64)
    filename: str | None = Field(default=None, max_length=200)
    content_base64: str | None = Field(default=None, max_length=7_200_000)  # 5 MB of file
    text: str | None = Field(default=None, max_length=400_000)
    title: str | None = Field(default=None, max_length=120)


REFILE_DOCUMENT_KIND = "REFILE_DOCUMENT"


class RefileIn(BaseModel):
    """File a PROPOSED document's text under another registered counterparty of the right role (the owner chose the wrong one,
    or has just added the right customer). `doc_hash` binds the request to the text the owner was shown."""

    model_config = ConfigDict(extra="forbid")

    counterparty_id: str = Field(min_length=1, max_length=64)
    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    link_facility_id: str | None = Field(default=None, max_length=64)


def _event(kind: SecurityEventKind, day: int, counterparty_id: str | None, detail: str, spans: list | None = None) -> None:
    rt = get_runtime()
    sid = "SEC-DOC-" + hashlib.sha256(f"{kind}|{detail}|{day}|{uuid.uuid4().hex}".encode()).hexdigest()[:12]
    rt.store.add_security_event(SecurityEvent(id=sid, day=day, kind=kind, counterparty_id=counterparty_id,
                                              action_taken="document not read into any record; nothing confirmed"
                                              if kind == SecurityEventKind.UNKNOWN_COUNTERPARTY
                                              else "flagged; the document cannot be confirmed",
                                              detail=detail, spans=spans or []))


def _capex_on() -> bool:
    return get_settings().features.capex_contracts


def _refusal(code: str, message: str, message_zh: str | None) -> dict[str, str]:
    return {"code": code, "message": message, **({"message_zh": message_zh} if message_zh else {})}


def _view(rt: Runtime, rec: ContractRecord, lang: Lang) -> dict:
    """The review screen of `rec` on the books as they are now, with the parties it names matched to the registry."""
    from app.api.customers import added_short_names

    return record_view(rec, rt.store.get_state(), lang, rt.day, rt.store.contract_guard_rows(), added_short_names(rt.store))


def _short_names(rt: Runtime, counterparty_id: str) -> list[str]:
    from app.api.customers import added_short_names

    return added_short_names(rt.store).get(counterparty_id, [])


@router.post("/documents")
def post_document(body: DocumentIn, lang: Lang = "en") -> dict:
    rt = get_runtime()
    title = body.title
    if body.fixture_id is not None:
        capex_fx = load_capex_contract_fixtures().get(body.fixture_id) if _capex_on() else None
        fx = load_contract_fixtures().get(body.fixture_id) or capex_fx
        if fx is None:
            raise HTTPException(404, {"code": "UNKNOWN_FIXTURE", "message": "no such demo document"})
        kind, cp = DocumentKind(fx["kind"]), fx["counterparty_id"]
        if (body.kind and body.kind != kind.value) or (body.counterparty_id and body.counterparty_id != cp):
            raise HTTPException(422, {"code": "FIXTURE_MISMATCH", "message": "the demo document says what it is"})
        fmt = None if body.format in (None, "md") else body.format
        if fx is capex_fx and fmt is not None and fmt not in fx.get("formats", []):
            raise HTTPException(422, {"code": "FORMAT_NOT_AVAILABLE",
                                      "message": f"this demo document has no {fmt} copy"})
        name, data = (capex_contract_fixture_bytes(body.fixture_id, fmt) if fx is capex_fx
                      else contract_fixture_bytes(body.fixture_id, fmt))
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
    if kind == DocumentKind.CAPEX_CONTRACT and not _capex_on():
        raise HTTPException(403, {"code": "FEATURE_DISABLED", "feature": "capex_contracts",
                                  "message": "Capex contracts are switched off (FEATURE_CAPEX_CONTRACTS)."})
    # The registry check, then the slow part (the file, its text, the reading) with the runtime lock released: a large or
    # crafted file must never hold up every other route. The lock is taken again only to store the record.
    with rt.lock:
        state = rt.store.get_state()
        day = rt.day
        party = next((c for c in state.counterparties if c.id == cp), None)
        new_vendor = kind == DocumentKind.CAPEX_CONTRACT and party is None
        if new_vendor and not _VENDOR_ID.fullmatch(cp):
            raise HTTPException(422, {"code": "BAD_COUNTERPARTY_ID",
                                      "message": "a vendor id is capital letters, digits, '-' or '_' (2 to 64 characters)"})
        if not new_vendor and (party is None or not party.known):
            _event(SecurityEventKind.UNKNOWN_COUNTERPARTY, day, cp,
                   f"a {kind.value.lower().replace('_', ' ')} naming {cp}, who is not on the owner's registry, was "
                   f"refused before it was read")
            raise HTTPException(422, {"code": "UNKNOWN_COUNTERPARTY",
                                      "message": f"{cp} is not on your registry; documents are read only for known "
                                                 f"counterparties"})
        if party is not None and party.role != _ROLE[kind]:
            raise HTTPException(422, {"code": "COUNTERPARTY_ROLE_MISMATCH",
                                      "message": f"{cp} is a {party.role.lower()}, not a {_ROLE[kind].lower()}"})
    try:
        text = extract_text(name, data)
        record = read_document(text, kind, cp, title=title, source=source, day=day, facilities=state.facilities)
        # The owner's rule of 17 Oct: the counterparty chosen must be a party the document names (app.contracts.parties).
        record = with_party_check(record, party, _short_names(rt, cp))
    except IngestError as e:
        raise HTTPException(413 if isinstance(e, DocumentTooLarge) else 422,
                            _refusal(e.code, str(e), e.message_zh)) from None
    except ContractTooLong as e:
        raise HTTPException(413, _refusal(e.code, str(e), e.message_zh)) from None
    with rt.lock:
        rid = rt.store.add_contract_record(record)
        stored = rt.store.get_contract_record(rid)
        assert stored is not None
        for f in stored.flags:
            if f.blocking and f.kind not in PARTY_FLAG_KINDS:  # a party the document does not name is no attack
                _event(SecurityEventKind.INJECTION, rt.day, cp, f"{rid}: {f.note}", [f.span])
        return {"document": _view(rt, stored, lang)}


@router.get("/documents")
def list_documents(lang: Lang = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        return {"documents": documents_for(rt.store, lang, rt.day), "day": rt.day, "lang": lang}


@router.get("/documents/{document_id}")
def get_document(document_id: str, lang: Lang = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        rec = rt.store.get_contract_record(document_id)
        if rec is None:
            raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
        return {"document": _view(rt, rec, lang), "lang": lang}


def _decide(document_id: str, body: DecisionIn, confirm: bool, lang: Lang) -> dict:
    """The owner's decision. The same decision sent again is answered with the first (same op_id and log position, nothing
    appended); the other decision on a decided document is refused and answered 409 `ALREADY_DECIDED`; a hash that is not the
    stored text's is refused and answered 409 `TERMS_CHANGED`. Any other refusal is a 200 whose result says REFUSED (and whose
    `outcome` is null). A decision made carries `outcome`: what it saved, under whom, what it changes and what it does not, in words
    (`app.api.document_outcome`)."""
    rt = get_runtime()
    before = rt.store.get_contract_record(document_id)
    if before is None:
        raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
    result = rt.executor.decide_document(document_id, Actor.OWNER, confirm=confirm, doc_hash=body.doc_hash,
                                         link_facility_id=body.link_facility_id)
    if result.status.value == "REFUSED" and before.status != DocumentStatus.PROPOSED:
        raise HTTPException(409, {"code": ALREADY_DECIDED_CODE, "message": result.message,
                                  "status": before.status.value, "result": result.model_dump(mode="json")})
    if result.violations and result.violations[0].code.value == "TERMS_CHANGED":  # the text shown is not the stored text
        raise HTTPException(409, {"code": "TERMS_CHANGED", "message": result.message,
                                  "result": result.model_dump(mode="json")})
    rec = rt.store.get_contract_record(document_id)
    assert rec is not None
    state, rows = rt.store.get_state(), rt.store.contract_guard_rows()
    # What the decision did, in words (the outcome card): only for a decision that was made, never for a refusal.
    outcome = document_outcome(rec, state, rows, lang, rt.day) if result.status.value == "EXECUTED" else None
    return {"result": result.model_dump(mode="json"), "document": _view(rt, rec, lang), "outcome": outcome}


@router.post("/documents/{document_id}/confirm")
def confirm_document(document_id: str, body: DecisionIn, lang: Lang = "en") -> dict:
    return _decide(document_id, body, confirm=True, lang=lang)


@router.post("/documents/{document_id}/reject")
def reject_document(document_id: str, body: DecisionIn, lang: Lang = "en") -> dict:
    return _decide(document_id, body, confirm=False, lang=lang)


@router.post("/documents/{document_id}/refile")
def refile_document(document_id: str, body: RefileIn, lang: Lang = "en") -> dict:
    """File a PROPOSED document under another registered counterparty of its kind's role: a NEW record holding the same text
    and the same reading (no new model call), with the party check run again for the new counterparty; the old record is
    closed, superseded by the new one (its `superseded_by`, the new record's `replaces`). One REFILE_DOCUMENT entry in the
    hash chain records it. Refused, with nothing written: an unknown document (404); a document already confirmed, rejected
    or filed again (409 NOT_PROPOSED); a hash that is not the stored text's (409 DOCUMENT_CHANGED); an unknown counterparty
    (404); one of the wrong role or the same one (422). Nothing in the books changes."""
    from app.persistence.canonical import canonical_json

    rt = get_runtime()
    with rt.lock:
        rec = rt.store.get_contract_record(document_id)
        if rec is None:
            raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": t(
                lang, "FLOW has no such document.", "FLOW 中没有这份文件。")})
        if rec.status != DocumentStatus.PROPOSED:
            raise HTTPException(409, {"code": "NOT_PROPOSED", "status": rec.status.value, "message": t(
                lang, "This document has already been decided or filed again, so it was not moved.",
                "这份文件已经处理过或已改归，因此没有移动。")})
        if not hmac.compare_digest(body.doc_hash.encode(), rec.doc_hash.encode()):
            raise HTTPException(409, {"code": "DOCUMENT_CHANGED", "message": t(
                lang, "The document shown is not the one FLOW holds, so nothing was moved. Reload it and try again.",
                "显示的文件与 FLOW 保存的不一致，因此没有移动任何内容。请重新加载后再试。")})
        state = rt.store.get_state()
        party = next((c for c in state.counterparties if c.id == body.counterparty_id and c.known), None)
        if party is None:
            raise HTTPException(404, {"code": "UNKNOWN_COUNTERPARTY", "message": t(
                lang, "That counterparty is not on your books.", "该对方不在您的账簿中。")})
        role = _ROLE[rec.kind]
        if party.role != role:
            raise HTTPException(422, {"code": "COUNTERPARTY_ROLE_MISMATCH", "message": t(
                lang, f"{party.name} is not a {_ROLE_WORDS[role][0]}, so this document cannot be filed under it.",
                f"{party.name}不是{_ROLE_WORDS[role][1]}，因此不能将这份文件归入其下。")})
        if party.id == rec.counterparty_id:
            raise HTTPException(422, {"code": "SAME_COUNTERPARTY", "message": t(
                lang, f"This document is already filed under {party.name}.", f"这份文件已归入{party.name}。")})
        moved = without_party_check(rec).model_copy(update={"counterparty_id": party.id})
        if moved.term_sheet is not None:  # the agreement's facility is now this lender's, and so is the one it describes
            ts = moved.term_sheet
            if ts.proposed_facility is not None:
                ts = ts.model_copy(update={"proposed_facility": ts.proposed_facility.model_copy(update={"lender_id": party.id})})
            moved = moved.model_copy(update={"term_sheet": ts,
                                             "suggested_facility_id": suggest_facility(ts, party.id, state.facilities)})
        moved = with_party_check(moved, party, _short_names(rt, party.id))
        day = rt.day
        with rt.store.transaction():  # the new record, the entry that records the move and the old record's closing, together
            new_id = rt.store.add_contract_record(moved)
            op_id = f"REFILE-{document_id}-{day}-{len(rt.store.operations()) + 1}"
            payload = {"kind": REFILE_DOCUMENT_KIND, "op_id": op_id, "document_id": document_id, "new_document_id": new_id,
                       "from_counterparty_id": rec.counterparty_id, "counterparty_id": party.id, "doc_hash": rec.doc_hash,
                       "requested_by": Actor.OWNER.value, "day": day}
            result = OperationResult(op_id=op_id, kind=REFILE_DOCUMENT_KIND, status=OperationStatus.EXECUTED, tier=Tier.TIER_2,
                                     effective_day=day, message=(f"Document {document_id} filed again under {party.id} as "
                                                                 f"{new_id} by the owner; nothing in the books changed"))
            entry = rt.store.append_operation(op_id, REFILE_DOCUMENT_KIND, op_id, canonical_json(payload),
                                              canonical_json(result))
            rt.store.close_refiled_record(document_id, new_id, day, entry.seq)
        stored = rt.store.get_contract_record(new_id)
        assert stored is not None
        return {"document": _view(rt, stored, lang)}


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


@router.get("/fixtures/capex-contracts")
def list_capex_contract_fixtures() -> dict:
    """The demo capex contracts (ADR-0013), listed apart from `/fixtures/contracts` because the demo never confirms them."""
    if not _capex_on():
        raise HTTPException(403, {"code": "FEATURE_DISABLED", "feature": "capex_contracts",
                                  "message": "Capex contracts are switched off (FEATURE_CAPEX_CONTRACTS)."})
    return {"contracts": [{"id": k, "kind": v["kind"], "counterparty_id": v["counterparty_id"],
                           "counterparty_name": v.get("counterparty_name"), "title": v["title"],
                           "formats": ["md", *v.get("formats", [])]}
                          for k, v in load_capex_contract_fixtures().items()]}
