"""Hash chain over the operations log, computed in Python (ADR-0001: the chain is never computed
by triggers; the database triggers of migration 0003 only refuse UPDATE/DELETE on the log).

entry_hash = sha256(prev_hash + payload_json + result_json); the genesis prev_hash is "0" * 64
and `seq` runs 1, 2, 3, ... with no gaps.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from app.domain.ports import OperationRecord
from app.persistence.canonical import canonical_json
from app.persistence.errors import InvalidPayload

GENESIS_HASH = "0" * 64


def compute_entry_hash(prev_hash: str, payload_json: str, result_json: str) -> str:
    return hashlib.sha256((prev_hash + payload_json + result_json).encode("utf-8")).hexdigest()


def verify_entries(entries: Sequence[OperationRecord]) -> bool:
    """True when seq is contiguous from 1, every prev_hash links to the previous entry and every
    entry_hash matches its content."""
    prev = GENESIS_HASH
    for expected_seq, e in enumerate(entries, start=1):
        if e.seq != expected_seq or e.prev_hash != prev:
            return False
        if e.entry_hash != compute_entry_hash(e.prev_hash, e.payload_json, e.result_json):
            return False
        prev = e.entry_hash
    return True


def head_hash(entries: Sequence[OperationRecord]) -> str:
    return entries[-1].entry_hash if entries else GENESIS_HASH


def parse_json(text: str, what: str) -> Any:
    if not isinstance(text, str):
        raise InvalidPayload(f"{what} must be JSON text, got {type(text).__name__}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidPayload(f"{what} is not valid JSON: {exc.msg}") from exc


def _field(text: str, key: str) -> str | None:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, str) else None


def op_identity(op_json: str) -> tuple[str | None, str | None]:
    """(op_id, kind) of a serialised operation, if present."""
    return _field(op_json, "op_id"), _field(op_json, "kind")


def _parsed(text: str) -> dict:
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def evidence_line(e: OperationRecord) -> dict:
    """One operation as judges see it: timestamp (simulated day), action, result, and the exact
    payload/result text so `entry_hash = sha256(prev_hash + payload_json + result_json)` can be
    recomputed without our code (scripts/verify_evidence.py)."""
    op, res = _parsed(e.payload_json), _parsed(e.result_json)
    return {
        "record": "operation",
        "seq": e.seq,
        "op_id": e.op_id,
        "kind": e.kind,
        "idempotency_key": e.idempotency_key,
        "day": res.get("effective_day", op.get("day")),
        "requested_by": op.get("requested_by"),
        "status": res.get("status"),
        "tier": res.get("tier"),
        "violations": [v.get("code") for v in res.get("violations", []) if isinstance(v, dict)],
        "message": res.get("message", ""),
        "payload_json": e.payload_json,
        "result_json": e.result_json,
        "prev_hash": e.prev_hash,
        "entry_hash": e.entry_hash,
    }


def chain_line(entries: Sequence[OperationRecord]) -> dict:
    return {
        "record": "chain",
        "operations": len(entries),
        "chain_valid": verify_entries(entries),
        "head_hash": head_hash(entries),
        "genesis_hash": GENESIS_HASH,
    }


def build_evidence(entries: Sequence[OperationRecord]) -> str:
    """JSONL: one line per operation, then one chain line with `chain_valid` and `head_hash`."""
    lines = [canonical_json(evidence_line(e)) for e in entries]
    lines.append(canonical_json(chain_line(entries)))
    return "\n".join(lines) + "\n"


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Obligation fields that identify or evidence a term but do not change its economics (the same set
# `app.commitments.terms` strips for the terms hash).
_NON_ECONOMIC = frozenset({"id", "spans", "confidence"})


def offer_fingerprint(offer: Any) -> str:
    """What an offer version commits to: its counterparty, compile status and the economic terms
    of its obligations (order-independent). Re-storing a version is allowed only when this is
    unchanged, so a stored version can never be swapped for richer terms (F-07)."""
    terms = sorted(
        canonical_json({k: v for k, v in o.model_dump(mode="json").items() if k not in _NON_ECONOMIC})
        for o in offer.obligations
    )
    body = canonical_json({"counterparty_id": offer.counterparty_id, "status": str(offer.status), "terms": terms})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def approval_id(n: int) -> str:
    return f"APR-{n:06d}"


def document_id(n: int) -> str:
    return f"DOC-{n:06d}"


_DECISION_FIELDS = ("status", "decided_day", "decided_seq", "linked_facility_id")


def refiled_record(stored: Any, superseded_by: str, day: int, seq: int) -> Any:
    """A PROPOSED record closed because the owner filed its text again under another counterparty: REJECTED (it can no longer
    be confirmed), decided by the REFILE_DOCUMENT entry at `seq`, superseded by the new record. Nothing else changes."""
    from app.domain.models import DocumentStatus

    if not superseded_by or superseded_by == stored.id:
        raise ValueError(f"a refiled record is superseded by another record, not {superseded_by!r}")
    return stored.model_copy(update={"status": DocumentStatus.REJECTED, "decided_day": day, "decided_seq": seq,
                                     "linked_facility_id": None, "superseded_by": superseded_by})


def check_decision(stored: Any, decided: Any) -> None:
    """A decision on a contract record may change only the decision fields, and only to CONFIRMED or REJECTED."""
    from app.domain.models import DocumentStatus

    if decided.status not in (DocumentStatus.CONFIRMED, DocumentStatus.REJECTED):
        raise ValueError(f"a decision is CONFIRMED or REJECTED, not {decided.status}")
    keep = {f: getattr(stored, f) for f in _DECISION_FIELDS}
    if decided.model_copy(update=keep) != stored:
        raise ValueError(f"a decision on {stored.id} cannot change the document or its reading")
