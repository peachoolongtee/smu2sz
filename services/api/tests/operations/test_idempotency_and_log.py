"""Idempotency and the hash-chained log: every result is appended, refusals and duplicates included."""

from __future__ import annotations

import json
from typing import Any

from app.domain.models import DrawFacility, IssueEquity, OperationResult, OperationStatus
from app.operations import parse_operation
from app.persistence import canonical_json
from tests.operations.builders import Clock, op


def test_same_key_twice_is_duplicate_with_no_double_effect(ex: Any, store: Any, clock: Clock) -> None:
    start = store.get_state().cash_fen
    first = ex.execute(op(DrawFacility, clock, key="K-DRAW", facility_id="FAC-LINE", amount_fen=5_000_000))
    second = ex.execute(op(DrawFacility, clock, key="K-DRAW", facility_id="FAC-LINE", amount_fen=5_000_000))
    assert first.status == OperationStatus.EXECUTED
    assert second.status == OperationStatus.DUPLICATE
    assert second.op_id == first.op_id and second.tier == first.tier
    assert f"seq {first.seq}" in second.message
    state = store.get_state()
    assert state.cash_fen == start + 5_000_000 and state.state_version == 2
    ops = store.operations()
    assert len(ops) == 2 and [o.idempotency_key for o in ops] == ["K-DRAW", "K-DRAW"]
    assert (second.seq, second.prev_hash) == (2, first.entry_hash)


def test_duplicate_of_a_refusal_stays_refused(ex: Any, store: Any, clock: Clock) -> None:
    first = ex.execute(op(IssueEquity, clock, key="K-EQ", amount_fen=1))
    second = ex.execute(op(IssueEquity, clock, key="K-EQ", amount_fen=1))
    assert first.status == OperationStatus.REFUSED
    assert second.status == OperationStatus.DUPLICATE and second.violations == first.violations


def test_every_result_is_logged_with_its_chain_position(ex: Any, store: Any, clock: Clock) -> None:
    results = [
        ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000)),
        ex.execute(op(IssueEquity, clock, amount_fen=1)),
        ex.execute(op(DrawFacility, clock, facility_id="FAC-GGL", amount_fen=1_000_000)),
    ]
    records = store.operations()
    assert [r.seq for r in results] == [1, 2, 3]
    for res, rec in zip(results, records, strict=True):
        assert (res.entry_hash, res.prev_hash) == (rec.entry_hash, rec.prev_hash)
        logged = OperationResult.model_validate_json(rec.result_json)
        assert logged.status == res.status and logged.seq is None
        assert parse_operation(rec.payload_json).op_id == res.op_id
        assert rec.payload_json == canonical_json(json.loads(rec.payload_json))
    assert store.verify_chain()
