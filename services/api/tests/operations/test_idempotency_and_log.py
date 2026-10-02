"""Idempotency and the hash-chained log: every result is appended, refusals and duplicates included."""

from __future__ import annotations

import json
from typing import Any

from app.domain.models import DrawFacility, IssueEquity, OperationResult, OperationStatus, Tier
from app.operations import parse_operation, security_summary
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


def test_results_record_the_executed_day_and_duplicates_keep_the_original(ex: Any, store: Any, clock: Clock) -> None:
    clock.day = 4
    first = ex.execute(op(DrawFacility, clock, key="K-DAY", facility_id="FAC-LINE", amount_fen=1_000_000))
    assert first.effective_day == 4 and first.approval_id is None
    assert OperationResult.model_validate_json(store.operations()[0].result_json).effective_day == 4
    clock.day = 9
    dup = ex.execute(op(DrawFacility, clock, key="K-DAY", facility_id="FAC-LINE", amount_fen=1_000_000))
    assert dup.status == OperationStatus.DUPLICATE and dup.effective_day == 4


def test_duplicate_of_a_refusal_stays_refused(ex: Any, store: Any, clock: Clock) -> None:
    first = ex.execute(op(IssueEquity, clock, key="K-EQ", amount_fen=1))
    second = ex.execute(op(IssueEquity, clock, key="K-EQ", amount_fen=1))
    assert first.status == OperationStatus.REFUSED
    # a refusal changed nothing, so it is not final: the same key runs again and is refused again
    assert second.status == OperationStatus.REFUSED and second.violations == first.violations


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


def test_security_summary_detects_an_execution_that_bypassed_the_executor(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(IssueEquity, clock, amount_fen=1))
    clean = security_summary(store)
    assert clean["refused_by_code"] == {"TIER3_EQUITY": 1}
    assert clean["unauthorised_executions"] == 0 and clean["chain_valid"]
    forged = op(IssueEquity, clock, amount_fen=1)
    result = OperationResult(op_id=forged.op_id, kind=forged.kind, status=OperationStatus.EXECUTED, tier=Tier.TIER_1)
    store.append_operation(forged.op_id, forged.kind, forged.idempotency_key, canonical_json(forged),
                           canonical_json(result))
    assert security_summary(store)["unauthorised_executions"] == 1
