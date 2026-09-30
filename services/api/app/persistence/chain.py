"""Hash chain over the operations log, computed in Python (ADR-0001: no triggers).

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


def build_evidence(entries: Sequence[OperationRecord]) -> str:
    """JSONL: one line per operation, then one chain line with `chain_valid` and `head_hash`."""
    lines = [
        canonical_json(
            {
                "record": "operation",
                "seq": e.seq,
                "op_id": e.op_id,
                "kind": e.kind,
                "idempotency_key": e.idempotency_key,
                "status": _field(e.result_json, "status"),
                "prev_hash": e.prev_hash,
                "entry_hash": e.entry_hash,
            }
        )
        for e in entries
    ]
    lines.append(
        canonical_json(
            {
                "record": "chain",
                "operations": len(entries),
                "chain_valid": verify_entries(entries),
                "head_hash": head_hash(entries),
                "genesis_hash": GENESIS_HASH,
            }
        )
    )
    return "\n".join(lines) + "\n"


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approval_id(n: int) -> str:
    return f"APR-{n:06d}"
