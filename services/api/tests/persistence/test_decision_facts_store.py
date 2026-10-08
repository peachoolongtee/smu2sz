"""The decision record's fact table in both stores (ADR-0011): insert-if-absent, append-only, cleared by reset, rolled back
with its unit of work, and apart from the books and the hash chain."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, text, update

from app.domain.fixtures import load_scenario
from app.persistence import AppendOnlyViolation, DecisionFactRecord, InMemoryLedgerStore, SqlLedgerStore
from app.persistence import tables as t

FACT = DecisionFactRecord(
    decision_id="deal:OFF-1", family="DEAL", fact="EVALUATED", fact_key="V-1", state_version=1, day=3,
    body_json='{"offer_id":"OFF-1","outcome":"ACCEPT"}',
)


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[InMemoryLedgerStore | SqlLedgerStore]:
    s: InMemoryLedgerStore | SqlLedgerStore = (
        InMemoryLedgerStore() if request.param == "memory" else SqlLedgerStore(f"sqlite:///{tmp_path / 'facts.db'}")
    )
    state, mandate = load_scenario()
    s.put_state(state)
    s.put_mandate(mandate)
    yield s
    if isinstance(s, SqlLedgerStore):
        s.dispose()


def test_a_write_returns_the_stored_row_with_the_stores_seq_and_time(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    assert store.decision_facts() == []
    stored = store.add_decision_fact(FACT)
    assert stored.seq == 1 and stored.recorded_at.endswith("+00:00")
    assert replace(stored, seq=0, recorded_at="") == FACT
    assert store.decision_facts() == [stored]


def test_a_second_write_with_the_same_key_returns_the_first_row_and_changes_nothing(
    store: InMemoryLedgerStore | SqlLedgerStore,
) -> None:
    first = store.add_decision_fact(FACT)
    again = store.add_decision_fact(replace(FACT, state_version=9, day=40, body_json='{"outcome":"REJECT"}'))
    assert again == first
    assert store.decision_facts() == [first]
    assert store.decision_facts()[0].body_json == FACT.body_json


def test_the_key_is_decision_fact_and_fact_key_together(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    a = store.add_decision_fact(FACT)
    b = store.add_decision_fact(replace(FACT, fact_key="V-2"))
    c = store.add_decision_fact(replace(FACT, fact="SENT"))
    d = store.add_decision_fact(replace(FACT, decision_id="deal:OFF-2"))
    assert [x.seq for x in (a, b, c, d)] == [1, 2, 3, 4]
    assert store.decision_facts() == [a, b, c, d]


def test_facts_filter_by_decision_id_oldest_first(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    a = store.add_decision_fact(FACT)
    store.add_decision_fact(replace(FACT, decision_id="alert:A-1:v2", family="FUNDING", fact="QUOTED", fact_key="alert:A-1:v2"))
    b = store.add_decision_fact(replace(FACT, fact_key="V-2"))
    assert store.decision_facts("deal:OFF-1") == [a, b]
    assert store.decision_facts("deal:none") == []


def test_the_records_are_frozen(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    rec = store.add_decision_fact(FACT)
    with pytest.raises(AttributeError):
        rec.body_json = "{}"  # type: ignore[misc]


def test_a_write_leaves_the_books_and_the_hash_chain_alone(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.append_operation("OP-1", "DRAW_FACILITY", "k-1", "{}", '{"status":"EXECUTED"}')
    head = [e.entry_hash for e in store.operations()]
    state, mandate, history = store.get_state(), store.get_mandate(), len(store.state_history())
    store.add_decision_fact(FACT)
    assert [e.entry_hash for e in store.operations()] == head and store.verify_chain()
    assert (store.get_state(), store.get_mandate(), len(store.state_history())) == (state, mandate, history)


def test_reset_clears_the_facts_with_the_ledger(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.add_decision_fact(FACT)
    store.reset()
    assert store.decision_facts() == []
    # The cleared key can be written again, and numbering starts over for the memory store.
    again = store.add_decision_fact(FACT)
    assert store.decision_facts() == [again]


def test_reset_with_telemetry_clears_them_too(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.add_decision_fact(FACT)
    store.reset(include_telemetry=True)
    assert store.decision_facts() == []


def test_a_raising_transaction_keeps_no_fact(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    kept = store.add_decision_fact(FACT)
    with pytest.raises(RuntimeError, match="boom"), store.transaction():
        store.add_decision_fact(replace(FACT, fact_key="V-2"))
        assert len(store.decision_facts()) == 2
        raise RuntimeError("boom")
    assert store.decision_facts() == [kept]


def test_a_committed_transaction_keeps_the_fact(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    with store.transaction():
        store.add_decision_fact(FACT)
        again = store.add_decision_fact(FACT)
    assert store.decision_facts() == [again]


def test_the_sql_table_refuses_update_and_delete() -> None:
    s = SqlLedgerStore("sqlite://")
    s.add_decision_fact(FACT)
    with s.engine.begin() as conn:
        with pytest.raises(AppendOnlyViolation):
            conn.execute(update(t.decision_facts).values(body_json="{}"))
        with pytest.raises(AppendOnlyViolation):
            conn.execute(delete(t.decision_facts))
    assert s.decision_facts()[0].body_json == FACT.body_json
    s.dispose()


def test_the_sql_table_enforces_the_unique_key_in_the_database() -> None:
    s = SqlLedgerStore("sqlite://")
    s.add_decision_fact(FACT)
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), s.engine.begin() as conn:
        conn.execute(
            insert(t.decision_facts).values(
                decision_id=FACT.decision_id, family="DEAL", fact=FACT.fact, fact_key=FACT.fact_key, state_version=1, day=0,
                body_json="{}", recorded_at="x",
            )
        )
    s.dispose()


def test_a_unique_conflict_after_the_read_returns_the_stored_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Another writer stores the same key between our read and our insert: the insert conflicts, and we return its row."""
    s = SqlLedgerStore("sqlite://")
    rival = s.add_decision_fact(replace(FACT, body_json='{"who":"rival"}'))
    calls = {"n": 0}
    from sqlalchemy.engine import Connection

    real_execute = Connection.execute

    def blind_first_read(self: Connection, statement: Any, *a: Any, **k: Any) -> Any:
        # Make the existence read (the first select of the write) come back empty, as if the rival had not written yet.
        if calls["n"] == 0 and getattr(statement, "is_select", False):
            calls["n"] += 1
            return real_execute(self, text("SELECT * FROM decision_facts WHERE 1 = 0"))
        return real_execute(self, statement, *a, **k)

    monkeypatch.setattr(Connection, "execute", blind_first_read)
    got = s.add_decision_fact(replace(FACT, body_json='{"who":"late"}'))
    monkeypatch.undo()
    assert calls["n"] == 1  # the blind read happened, so the insert really conflicted
    assert got == rival and s.decision_facts() == [rival]
    s.dispose()


def test_the_sql_table_holds_numbers_and_ids_only_and_the_json_as_written() -> None:
    assert not [c.name for c in t.decision_facts.columns if c.name.endswith(("_text", "_sentence"))]
    s = SqlLedgerStore("sqlite://")
    s.add_decision_fact(replace(FACT, body_json='{"net_fen":137461}'))
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT body_json FROM decision_facts")).scalar_one() == '{"net_fen":137461}'
    s.dispose()
