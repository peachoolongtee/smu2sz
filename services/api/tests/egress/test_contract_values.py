"""Brief 03 §6.4: the egress guard treats contract terms as protected for counterparties, like other buyers' terms.
A buyer may see its own contract's values; another buyer may not; the owner sees everything."""

from __future__ import annotations

from app.contracts import read_document
from app.domain.fixtures import contract_fixture_bytes, load_contract_fixtures, load_scenario
from app.domain.models import DocumentKind
from app.egress import contract_private_values, protected_for, scan
from app.ingest import extract_text
from app.persistence import InMemoryLedgerStore


def _record(fixture_id: str):  # type: ignore[no-untyped-def]
    fx = load_contract_fixtures()[fixture_id]
    name, data = contract_fixture_bytes(fixture_id)
    state = load_scenario()[0]
    return read_document(extract_text(name, data), DocumentKind(fx["kind"]), fx["counterparty_id"], title=fx["title"],
                         source="test", day=0, facilities=state.facilities).model_copy(update={"id": "DOC-000001"})


def test_contract_values_are_owned_by_their_counterparty():
    state = load_scenario()[0]
    values = contract_private_values([_record("FHR_SUPPLY_AGREEMENT")], state)
    owners = {v.owner for v in values}
    assert owners == {"BUYER-1"}
    labels = {v.label for v in values}
    assert any(label.endswith("contract_reference.0.text") for label in labels)
    assert any(".early_payment." in label and label.endswith(".rate") for label in labels)
    lender = contract_private_values([_record("GBR_INVOICE_FINANCING_AGREEMENT")], state)
    assert {v.owner for v in lender} == {"PLATFORM-1"}


def test_another_buyer_cannot_receive_a_buyers_contract_terms():
    store = InMemoryLedgerStore()
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    store.add_contract_record(_record("FHR_SUPPLY_AGREEMENT"))
    pset = protected_for(store)
    text = "Their agreement FHR-2026-07 gives a 1.2% early settlement discount."
    leaked = {lk.label for lk in scan(text, pset, recipient_id="BUYER-2")}
    assert any("contract_reference" in x for x in leaked) and any(".rate" in x for x in leaked)
    assert scan(text, pset, recipient_id="BUYER-1") == []  # its own terms
    assert scan(text, pset, recipient_id="OWNER") == []


def test_a_store_without_contract_records_still_builds_the_set():
    class Bare:
        def get_state(self):  # type: ignore[no-untyped-def]
            return load_scenario()[0]

        def get_mandate(self):  # type: ignore[no-untyped-def]
            return load_scenario()[1]

    assert len(protected_for(Bare())) > 0
