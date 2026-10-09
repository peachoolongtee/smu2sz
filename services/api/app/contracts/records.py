"""Reading an uploaded document into a PROPOSED `ContractRecord` (brief 03 §6.4).

The compiler reads the text (a buyer contract with `compile_contract`, a lender agreement with `compile_term_sheet`);
this module adds the security flags for contracts, the facility the agreement appears to describe, and the record's
provenance. Nothing here writes the books or decides: the owner confirms through `Executor.decide_document`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.compiler import compile_contract, compile_term_sheet
from app.compiler.contract import contract_document, document_flags, ground_flags
from app.compiler.schema import XAuthorityClaim, XDataRequest
from app.domain.models import (
    CompiledTermSheet,
    ContractField,
    ContractRecord,
    DocumentKind,
    Facility,
)

KIND_TITLES = {DocumentKind.BUYER_CONTRACT: "Buyer contract", DocumentKind.LENDER_AGREEMENT: "Lender agreement"}


def doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def suggest_facility(ts: CompiledTermSheet, counterparty_id: str, facilities: Sequence[Facility]) -> str | None:
    """The one facility on the menu this agreement appears to describe: the same lender and the same kind."""
    proposed = ts.proposed_facility
    found = [f.id for f in facilities if f.lender_id == counterparty_id and (proposed is None or f.kind == proposed.kind)]
    return found[0] if len(found) == 1 else None


def read_document(text: str, kind: DocumentKind, counterparty_id: str, *, title: str | None, source: str, day: int,
                  facilities: Sequence[Facility]) -> ContractRecord:
    """The agent's reading of one document, as a PROPOSED record (its id is assigned by the store)."""
    doc = contract_document(text, kind, counterparty_id)
    if kind == DocumentKind.BUYER_CONTRACT:
        reading = compile_contract(doc)
        ref = next((t.text for t in reading.terms if t.field == ContractField.CONTRACT_REFERENCE), None)
        return ContractRecord(
            id="DOC-PENDING", kind=kind, counterparty_id=counterparty_id,
            title=title or (f"Contract {ref}" if ref else KIND_TITLES[kind]), document=doc, doc_hash=doc_hash(text),
            source=source, uploaded_day=day, contract=reading,
            flags=document_flags(reading.authority_claims, reading.data_requests),
        )
    ts = compile_term_sheet(doc)
    # The term-sheet path flags every lexicon hit; a lender agreement states its own limit and covenants, so its
    # flags are re-read with the contract filter, the model's own claims included.
    claims, requests = ground_flags(
        doc, kind,
        [XAuthorityClaim(kind=c.kind, doc_id=doc.doc_id, quote=c.span.text) for c in ts.authority_claims],
        [XDataRequest(kind=r.kind, doc_id=doc.doc_id, quote=r.span.text) for r in ts.data_requests],
    )
    return ContractRecord(
        id="DOC-PENDING", kind=kind, counterparty_id=counterparty_id, title=title or KIND_TITLES[kind], document=doc,
        doc_hash=doc_hash(text), source=source, uploaded_day=day, term_sheet=ts, flags=document_flags(claims, requests),
        suggested_facility_id=suggest_facility(ts, counterparty_id, facilities),
    )


__all__ = ["KIND_TITLES", "doc_hash", "read_document", "suggest_facility"]
