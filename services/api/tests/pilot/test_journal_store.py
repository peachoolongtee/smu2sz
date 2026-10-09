"""The journal's table in both stores: the same contract, append-only, kept by reset, and apart from the hash chain."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypedDict, cast

import pytest
from sqlalchemy import delete, text, update

from app.domain.fixtures import load_scenario
from app.persistence import AppendOnlyViolation, InMemoryLedgerStore, SqlLedgerStore
from app.persistence import tables as t

from .conftest import HASH


class Fields(TypedDict):
    week: int
    sme: str
    answer: str
    flow_said: str
    snapshot_hash: str
    owner_did: str
    choice: str
    recorded_on: str
    state_version: int
    day: int


FIELDS: Fields = {
    "week": 2, "sme": "sme-a", "answer": "worth", "flow_said": "Call Buyer B today.", "snapshot_hash": HASH,
    "owner_did": "Called Buyer B first.", "choice": "followed", "recorded_on": "2026-10-12", "state_version": 1, "day": 0,
}


def fields(**changes: object) -> Fields:
    return cast(Fields, {**FIELDS, **changes})


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest) -> Iterator[InMemoryLedgerStore | SqlLedgerStore]:
    s: InMemoryLedgerStore | SqlLedgerStore = InMemoryLedgerStore() if request.param == "memory" else SqlLedgerStore("sqlite://")
    state, mandate = load_scenario()
    s.put_state(state)
    s.put_mandate(mandate)
    yield s
    if isinstance(s, SqlLedgerStore):
        s.dispose()


def test_entries_append_in_order_with_a_gap_free_seq(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    assert store.pilot_journal() == []
    a = store.add_pilot_journal(**FIELDS)
    b = store.add_pilot_journal(**fields(week=3, choice="ignored"))
    assert (a.seq, b.seq) == (1, 2)
    listed = store.pilot_journal()
    assert listed == [a, b]
    assert a.recorded_at.endswith("+00:00") and a.week == 2 and b.choice == "ignored"
    assert {k: getattr(a, k) for k in FIELDS} == dict(FIELDS)


def test_the_records_are_frozen(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    rec = store.add_pilot_journal(**FIELDS)
    with pytest.raises(AttributeError):
        rec.owner_did = "edited"  # type: ignore[misc]


def test_a_write_leaves_the_books_and_the_hash_chain_alone(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.append_operation("OP-1", "DRAW_FACILITY", "k-1", "{}", '{"status":"EXECUTED"}')
    head = [e.entry_hash for e in store.operations()]
    state, mandate, history = store.get_state(), store.get_mandate(), len(store.state_history())
    store.add_pilot_journal(**FIELDS)
    assert [e.entry_hash for e in store.operations()] == head and store.verify_chain()
    assert (store.get_state(), store.get_mandate(), len(store.state_history())) == (state, mandate, history)


def test_reset_keeps_the_journal_unless_telemetry_is_cleared_too(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.add_pilot_journal(**FIELDS)
    store.reset()
    assert len(store.pilot_journal()) == 1
    store.reset(include_telemetry=True)
    assert store.pilot_journal() == []


def test_the_sql_table_refuses_update_and_delete() -> None:
    s = SqlLedgerStore("sqlite://")
    s.add_pilot_journal(**FIELDS)
    with s.engine.begin() as conn:
        with pytest.raises(AppendOnlyViolation):
            conn.execute(update(t.pilot_journal).values(owner_did="edited"))
        with pytest.raises(AppendOnlyViolation):
            conn.execute(delete(t.pilot_journal))
    assert s.pilot_journal()[0].owner_did == FIELDS["owner_did"]
    s.dispose()


def test_the_sql_table_has_no_money_column_and_holds_the_text_as_written() -> None:
    assert not [c.name for c in t.pilot_journal.columns if c.name.endswith(("_fen", "_bp"))]
    s = SqlLedgerStore("sqlite://")
    sentence = "Saves ¥1,374.61 · 该客户"
    s.add_pilot_journal(**fields(flow_said=sentence))
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT flow_said FROM pilot_journal")).scalar_one() == sentence
    s.dispose()
