"""The customer-inputs table in both stores (map #88, brief H.4): append-only, latest row per (counterparty, field) wins and
the history stays, the firm's rows have no counterparty, `reset()` clears it, a raising unit of work keeps none of it, and it is
apart from the books and the hash chain."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import delete, insert, text, update
from sqlalchemy.exc import IntegrityError

from app.domain.fixtures import load_scenario
from app.persistence import (
    AppendOnlyViolation,
    CustomerInputRecord,
    InMemoryLedgerStore,
    SqlLedgerStore,
    latest_inputs,
)
from app.persistence import tables as t

ROW = CustomerInputRecord(
    org_id="ORG-1", counterparty_id="BUYER-1", field="typical_delay_days", value_json="15", provenance="OWNER_ENTERED",
    source_ref="the owner's call", entered_by="OWNER", entered_day=3, state_version=1,
)
FIRM = CustomerInputRecord(
    org_id="ORG-1", counterparty_id=None, field="vat_rate_bp", value_json="1300", provenance="OWNER_ENTERED",
    source_ref="", entered_by="OWNER", entered_day=3, state_version=1,
)


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[InMemoryLedgerStore | SqlLedgerStore]:
    s: InMemoryLedgerStore | SqlLedgerStore = (
        InMemoryLedgerStore() if request.param == "memory" else SqlLedgerStore(f"sqlite:///{tmp_path / 'inputs.db'}")
    )
    state, mandate = load_scenario()
    s.put_state(state)
    s.put_mandate(mandate)
    yield s
    if isinstance(s, SqlLedgerStore):
        s.dispose()


def test_a_write_returns_the_stored_row_with_the_stores_seq_and_time(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    assert store.all_customer_inputs() == []
    stored = store.add_customer_input(ROW)
    assert stored.seq == 1 and stored.recorded_at.endswith("+00:00")
    assert replace(stored, seq=0, recorded_at="") == ROW
    assert store.all_customer_inputs() == [stored] and store.customer_inputs("BUYER-1") == [stored]


def test_the_history_stays_and_the_latest_row_per_counterparty_and_field_wins(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    first = store.add_customer_input(ROW)
    second = store.add_customer_input(replace(ROW, value_json="9", provenance="ESTIMATED"))
    other_field = store.add_customer_input(replace(ROW, field="aggregate", value_json="true"))
    other_buyer = store.add_customer_input(replace(ROW, counterparty_id="BUYER-2"))
    assert store.customer_inputs("BUYER-1") == [first, second, other_field]  # oldest first, nothing replaced
    assert store.customer_inputs("BUYER-2") == [other_buyer]
    latest = store.latest_customer_inputs()
    assert latest == {("BUYER-1", "typical_delay_days"): second, ("BUYER-1", "aggregate"): other_field,
                      ("BUYER-2", "typical_delay_days"): other_buyer}
    assert latest == latest_inputs(store.all_customer_inputs())  # the one definition of "latest wins"


def test_the_same_value_written_again_is_a_new_row_not_a_merge(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    a, b = store.add_customer_input(ROW), store.add_customer_input(ROW)
    assert (a.seq, b.seq) == (1, 2) and len(store.customer_inputs("BUYER-1")) == 2


def test_a_firm_row_has_no_counterparty_and_is_read_apart_from_the_buyers(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    buyer = store.add_customer_input(ROW)
    firm = store.add_customer_input(FIRM)
    assert store.customer_inputs(None) == [firm] and store.customer_inputs("BUYER-1") == [buyer]
    assert store.latest_customer_inputs()[(None, "vat_rate_bp")] == firm


def test_the_records_are_frozen(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    rec = store.add_customer_input(ROW)
    with pytest.raises(AttributeError):
        rec.value_json = "1"  # type: ignore[misc]


def test_a_write_leaves_the_books_and_the_hash_chain_alone(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.append_operation("OP-1", "DRAW_FACILITY", "k-1", "{}", '{"status":"EXECUTED"}')
    head = [e.entry_hash for e in store.operations()]
    state, mandate, history = store.get_state(), store.get_mandate(), len(store.state_history())
    store.add_customer_input(ROW)
    assert [e.entry_hash for e in store.operations()] == head and store.verify_chain()
    assert (store.get_state(), store.get_mandate(), len(store.state_history())) == (state, mandate, history)


def test_reset_clears_the_inputs_with_the_ledger_and_numbering_starts_over(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.add_customer_input(ROW)
    store.reset()
    assert store.all_customer_inputs() == [] and store.latest_customer_inputs() == {}
    again = store.add_customer_input(ROW)
    assert store.all_customer_inputs() == [again]


def test_reset_with_telemetry_clears_them_too(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    store.add_customer_input(ROW)
    store.reset(include_telemetry=True)
    assert store.all_customer_inputs() == []


def test_a_raising_transaction_keeps_no_input(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    kept = store.add_customer_input(ROW)
    with pytest.raises(RuntimeError, match="boom"), store.transaction():
        store.add_customer_input(replace(ROW, value_json="9"))
        assert len(store.all_customer_inputs()) == 2
        raise RuntimeError("boom")
    assert store.all_customer_inputs() == [kept]


def test_a_committed_transaction_keeps_the_input(store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    with store.transaction():
        row = store.add_customer_input(ROW)
    assert store.all_customer_inputs() == [row]


def test_the_sql_table_refuses_update_and_delete() -> None:
    s = SqlLedgerStore("sqlite://")
    s.add_customer_input(ROW)
    with s.engine.begin() as conn:
        with pytest.raises(AppendOnlyViolation):
            conn.execute(update(t.customer_inputs).values(value_json="1"))
        with pytest.raises(AppendOnlyViolation):
            conn.execute(delete(t.customer_inputs))
    assert s.all_customer_inputs()[0].value_json == "15"
    s.dispose()


def test_the_sql_table_checks_the_field_and_the_provenance_in_the_database() -> None:
    s = SqlLedgerStore("sqlite://")
    base = {"org_id": "O", "counterparty_id": None, "field": "vat_rate_bp", "value_json": "1", "provenance": "ERP",
            "source_ref": "", "entered_by": "x", "entered_day": 0, "state_version": 1, "recorded_at": "x"}
    for bad in ({"field": "margin"}, {"provenance": "GUESSED"}):
        with pytest.raises(IntegrityError), s.engine.begin() as conn:
            conn.execute(insert(t.customer_inputs).values(**{**base, **bad}))
    with s.engine.begin() as conn:  # the good row goes in
        conn.execute(insert(t.customer_inputs).values(**base))
    assert len(s.all_customer_inputs()) == 1
    s.dispose()


def test_the_sql_table_keeps_the_json_as_written() -> None:
    s = SqlLedgerStore("sqlite://")
    s.add_customer_input(replace(ROW, field="classification", value_json='"strategic"'))
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT value_json FROM customer_inputs")).scalar_one() == '"strategic"'
    s.dispose()


def test_the_change_marker_counts_log_entries_approvals_and_decisions_without_reading_rows(
        store: InMemoryLedgerStore | SqlLedgerStore) -> None:
    """A read cache's key (the customer overview): counts only, in both stores, and every write that matters moves one of them."""
    assert store.change_marker() == (0, 0, 0, 0, 0)
    store.append_operation("OP-1", "NOTE", "idem-1", '{"kind":"NOTE"}', '{"status":"EXECUTED"}')
    assert store.change_marker() == (1, 0, 0, 0, 0)
    approval = store.add_approval('{"kind":"NOTE"}', "test")
    assert store.change_marker() == (1, 0, 1, 0, 0)
    store.decide_approval(approval, True, "OWNER")
    assert store.change_marker() == (1, 0, 1, 1, 0)
