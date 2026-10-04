"""Brief 03 §6.4: contract records in both stores. Ids are assigned by the store, a document is decided once
(compare-and-swap on its status), and a decision cannot change the document or its reading."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import read_document
from app.domain.fixtures import contract_fixture_bytes, load_scenario
from app.domain.models import DocumentKind, DocumentStatus
from app.ingest import extract_text
from app.persistence import DocumentAlreadyDecided, InMemoryLedgerStore, NotFound, SqlLedgerStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path: Path):
    if request.param == "memory":
        yield InMemoryLedgerStore()
        return
    s = SqlLedgerStore(f"sqlite:///{tmp_path / 'ledger.db'}")
    yield s
    s.dispose()


def _record(fixture_id: str = "FHR_SUPPLY_AGREEMENT", day: int = 0):  # type: ignore[no-untyped-def]
    from app.domain.fixtures import load_contract_fixtures

    fx = load_contract_fixtures()[fixture_id]
    name, data = contract_fixture_bytes(fixture_id)
    return read_document(extract_text(name, data), DocumentKind(fx["kind"]), fx["counterparty_id"], title=fx["title"],
                         source=f"fixture:{fixture_id}", day=day, facilities=load_scenario()[0].facilities)


def test_the_store_assigns_ids_in_upload_order_and_round_trips_the_record(store):
    a, b = _record(), _record("MB_CREDIT_LINE_AGREEMENT", day=3)
    assert store.add_contract_record(a) == "DOC-000001"
    assert store.add_contract_record(b) == "DOC-000002"
    got = store.get_contract_record("DOC-000001")
    assert got == a.model_copy(update={"id": "DOC-000001"})
    assert got.status == DocumentStatus.PROPOSED and got.contract is not None
    assert [r.id for r in store.contract_records()] == ["DOC-000001", "DOC-000002"]
    assert store.get_contract_record("DOC-000009") is None


def test_a_new_record_is_always_stored_as_proposed(store):
    sneaky = _record().model_copy(update={"status": DocumentStatus.CONFIRMED, "decided_day": 0, "decided_seq": 1})
    rid = store.add_contract_record(sneaky)
    got = store.get_contract_record(rid)
    assert (got.status, got.decided_day, got.decided_seq) == (DocumentStatus.PROPOSED, None, None)


def test_a_document_is_decided_once(store):
    rid = store.add_contract_record(_record())
    rec = store.get_contract_record(rid)
    decided = rec.model_copy(update={"status": DocumentStatus.CONFIRMED, "decided_day": 0, "decided_seq": 7})
    assert store.decide_contract_record(decided) == decided
    assert store.get_contract_record(rid).status == DocumentStatus.CONFIRMED
    with pytest.raises(DocumentAlreadyDecided):
        store.decide_contract_record(rec.model_copy(update={"status": DocumentStatus.REJECTED, "decided_day": 1}))
    assert store.get_contract_record(rid) == decided


def test_a_decision_cannot_change_the_document_or_its_reading(store):
    rid = store.add_contract_record(_record())
    rec = store.get_contract_record(rid)
    forged = rec.model_copy(update={"status": DocumentStatus.CONFIRMED, "title": "Something else"})
    with pytest.raises(ValueError, match="cannot change"):
        store.decide_contract_record(forged)
    with pytest.raises(ValueError, match="CONFIRMED or REJECTED"):
        store.decide_contract_record(rec)  # still PROPOSED: not a decision
    assert store.get_contract_record(rid).status == DocumentStatus.PROPOSED


def test_deciding_an_unknown_document_is_not_found(store):
    rec = _record().model_copy(update={"id": "DOC-000042", "status": DocumentStatus.CONFIRMED})
    with pytest.raises(NotFound):
        store.decide_contract_record(rec)


def test_reset_clears_the_records_and_a_failed_unit_of_work_keeps_none(store):
    store.add_contract_record(_record())
    with pytest.raises(RuntimeError), store.transaction():
        store.add_contract_record(_record("MB_CREDIT_LINE_AGREEMENT"))
        raise RuntimeError("the unit of work fails after the write")
    assert [r.id for r in store.contract_records()] == ["DOC-000001"]
    store.reset()
    assert store.contract_records() == []
