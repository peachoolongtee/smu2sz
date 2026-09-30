"""Tamper detection and SQL-specific guarantees (append-only guard, BIGINT money, reopen, threads)."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import BigInteger, Float, Numeric, text

from app.persistence import (
    AppendOnlyViolation,
    InMemoryLedgerStore,
    SqlLedgerStore,
    canonical_json,
    compute_entry_hash,
)
from app.persistence import tables as t


def _fill(store, n: int = 4) -> None:
    for i in range(1, n + 1):
        store.append_operation(
            f"OP-{i}",
            "DRAW_FACILITY",
            f"idem-{i}",
            canonical_json({"op_id": f"OP-{i}", "kind": "DRAW_FACILITY", "amount_fen": 15_000_000}),
            canonical_json({"op_id": f"OP-{i}", "status": "EXECUTED"}),
        )


def _raw(store: SqlLedgerStore) -> sqlite3.Connection:
    """A connection outside SQLAlchemy, as someone with direct database access would use."""
    return sqlite3.connect(store.engine.url.database)


def _final(store) -> dict:
    return json.loads(store.export_evidence().splitlines()[-1])


def test_editing_a_result_with_sql_breaks_the_chain(sql_store):
    _fill(sql_store)
    assert sql_store.verify_chain() is True
    with _raw(sql_store) as db:
        db.execute(
            """UPDATE operations SET result_json = '{"op_id":"OP-2","status":"REFUSED"}' WHERE seq = 2"""
        )
    assert sql_store.verify_chain() is False
    assert _final(sql_store)["chain_valid"] is False


def test_editing_a_payload_amount_with_sql_breaks_the_chain(sql_store):
    _fill(sql_store)
    with _raw(sql_store) as db:
        db.execute(
            "UPDATE operations SET payload_json = replace(payload_json, '15000000', '99000000') WHERE seq = 3"
        )
    assert sql_store.verify_chain() is False


def test_rehashing_one_row_still_breaks_the_link_to_the_next(sql_store):
    _fill(sql_store)
    forged_result = '{"op_id":"OP-2","status":"REFUSED"}'
    row = sql_store.operations()[1]
    forged_hash = compute_entry_hash(row.prev_hash, row.payload_json, forged_result)
    with _raw(sql_store) as db:
        db.execute(
            "UPDATE operations SET result_json = ?, entry_hash = ? WHERE seq = 2",
            (forged_result, forged_hash),
        )
    assert sql_store.verify_chain() is False


def test_deleting_a_row_with_sql_breaks_the_chain(sql_store):
    _fill(sql_store)
    with _raw(sql_store) as db:
        db.execute("DELETE FROM operations WHERE seq = 2")
    assert sql_store.verify_chain() is False


def test_truncating_the_tail_is_visible_as_a_different_head(sql_store):
    _fill(sql_store)
    head = _final(sql_store)["head_hash"]
    with _raw(sql_store) as db:
        db.execute("DELETE FROM operations WHERE seq = 4")
    final = _final(sql_store)
    assert final["chain_valid"] is True  # a clean prefix is still a valid chain
    assert final["head_hash"] != head and final["operations"] == 3


def test_in_memory_tamper_is_detected():
    store = InMemoryLedgerStore()
    _fill(store)
    store._ops[1] = dataclasses.replace(store._ops[1], result_json='{"status":"REFUSED"}')
    assert store.verify_chain() is False


def test_update_or_delete_of_the_log_through_the_engine_is_refused(sql_store):
    _fill(sql_store, 2)
    with pytest.raises(AppendOnlyViolation), sql_store.engine.begin() as conn:
        conn.execute(t.operations.update().where(t.operations.c.seq == 1).values(result_json="{}"))
    with pytest.raises(AppendOnlyViolation), sql_store.engine.begin() as conn:
        conn.execute(t.operations.delete())
    sql_store.mark_nonce_used("n-1")
    with pytest.raises(AppendOnlyViolation), sql_store.engine.begin() as conn:
        conn.execute(t.used_nonces.delete())
    assert sql_store.verify_chain() is True and len(sql_store.operations()) == 2
    assert sql_store.nonce_used("n-1") is True


def test_ledger_survives_reopening_the_database(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'reopen.db'}"
    first = SqlLedgerStore(url)
    _fill(first, 3)
    first.mark_nonce_used("n-1")
    head = first.operations()[-1].entry_hash
    first.dispose()

    second = SqlLedgerStore(url)
    assert second.verify_chain() is True
    assert second.operations()[-1].entry_hash == head
    assert second.nonce_used("n-1") is True
    e = second.append_operation("OP-9", "RECEIVE_PAYMENT", "idem-9", "{}", '{"status":"EXECUTED"}')
    assert (e.seq, e.prev_hash) == (4, head)
    second.dispose()


def test_in_memory_sqlite_url_works():
    store = SqlLedgerStore("sqlite://")
    _fill(store, 2)
    assert store.verify_chain() is True
    store.dispose()


def test_money_columns_are_bigint_and_nothing_is_float():
    for table in t.metadata.sorted_tables:
        for col in table.columns:
            assert not isinstance(col.type, (Float, Numeric)), f"{table.name}.{col.name}"
            if col.name.endswith("_fen"):
                assert isinstance(col.type, BigInteger), f"{table.name}.{col.name}"


def test_money_above_32_bits_round_trips_exactly(sql_store):
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    big = state.model_copy(update={"cash_fen": 9_007_199_254_740_993})  # 2**53 + 1: not a float
    sql_store.put_state(big)
    assert sql_store.get_state().cash_fen == 9_007_199_254_740_993
    with sql_store.engine.connect() as conn:
        assert conn.execute(text("SELECT cash_fen FROM states")).scalar_one() == 9_007_199_254_740_993


def test_indexed_projections_are_written(sql_store):
    from app.domain.fixtures import load_scenario
    from tests.persistence import factories as f

    state, mandate = load_scenario()
    sql_store.put_state(state)
    sql_store.put_mandate(mandate)
    sql_store.put_offer(f.offer())
    with sql_store.engine.connect() as conn:
        facility_ids = {r[0] for r in conn.execute(text("SELECT facility_id FROM facilities"))}
        cps = {r[0] for r in conn.execute(text("SELECT id FROM counterparties"))}
        orgs = [r[0] for r in conn.execute(text("SELECT id FROM organizations"))]
        obs = conn.execute(text("SELECT count(*) FROM obligations WHERE offer_id = 'OFF-1'")).scalar_one()
    assert facility_ids == {fac.id for fac in state.facilities}
    assert cps == {c.id for c in state.counterparties}
    assert orgs == [state.org_id]
    assert obs == 3


def test_concurrent_appends_keep_one_contiguous_chain(sql_store):
    def worker(w: int) -> None:
        for i in range(10):
            sql_store.append_operation(f"OP-{w}-{i}", "DRAW_FACILITY", f"k-{w}-{i}", "{}", "{}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        for fut in [pool.submit(worker, w) for w in range(4)]:
            fut.result()  # re-raises any worker error
    ops = sql_store.operations()
    assert [e.seq for e in ops] == list(range(1, 41))
    assert sql_store.verify_chain() is True
