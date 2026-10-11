"""Ticket #103: the guard protects a contract's dates, window days, retention months, party names and clause text as well as
its amounts and rates. A buyer may be told values from its own contract and never another counterparty's."""

from __future__ import annotations

import pytest

from app.contracts import read_document
from app.domain.fixtures import contract_fixture_bytes, load_contract_fixtures, load_scenario
from app.domain.models import ContractField, DocumentKind
from app.egress import protected_for, scan
from app.ingest import extract_text
from app.persistence import InMemoryLedgerStore


def _record(fixture_id: str = "FHR_SUPPLY_AGREEMENT", edit=None):  # type: ignore[no-untyped-def]
    fx = load_contract_fixtures()[fixture_id]
    name, data = contract_fixture_bytes(fixture_id)
    state = load_scenario()[0]
    rec = read_document(extract_text(name, data), DocumentKind(fx["kind"]), fx["counterparty_id"], title=fx["title"],
                        source="test", day=0, facilities=state.facilities)
    return edit(rec) if edit is not None else rec


def _retention(rec):  # type: ignore[no-untyped-def]
    """The demo contract has no retention clause: add one to the reading, as a live model's could."""
    assert rec.contract is not None
    donor = next(t for t in rec.contract.terms if t.field == ContractField.EARLY_PAYMENT)
    term = donor.model_copy(update={"field": ContractField.RETENTION, "rate_bp": 500, "days": None, "months": 18,
                                    "date": None, "text": None})
    return rec.model_copy(update={"contract": rec.contract.model_copy(update={"terms": [*rec.contract.terms, term]})})


@pytest.fixture(scope="module")
def pset():
    store = InMemoryLedgerStore()
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    store.add_contract_record(_record(edit=_retention))
    return protected_for(store)


def _kinds(text, pset, to):  # type: ignore[no-untyped-def]
    return {lk.label.split(".")[-1] for lk in scan(text, pset, recipient_id=to) if lk.label.startswith("contract.")}


def test_the_contract_values_now_include_dates_window_days_months_names_and_clauses(pset):
    kinds = {label.split(".")[-1] for label in pset.labels() if label.startswith("contract.")}
    assert {"date", "window_days", "retention_months", "party", "quote", "days"} <= kinds


@pytest.mark.parametrize("sentence", [
    "The agreement was signed on 1 September 2026.",
    "It starts 2026-09-01 and the first invoice is dated 2026年9月18日.",
])
def test_another_buyer_is_not_told_the_dates_of_a_contract(pset, sentence):
    assert "date" in _kinds(sentence, pset, "BUYER-2")
    assert _kinds(sentence, pset, "BUYER-1") == set()
    assert _kinds(sentence, pset, "OWNER") == set()


def test_another_buyer_is_not_told_the_window_the_retention_the_name_or_the_clause_words(pset):
    cases = {
        "window_days": "Foshan Home Retail may settle early within 2 days.",
        "retention_months": "A retention is held for 18 months.",
        "party": "We are talking to Foshan Home Retail about the supply.",
    }
    for kind, text in cases.items():
        assert kind in _kinds(text, pset, "BUYER-2"), (kind, text)
        assert _kinds(text, pset, "BUYER-1") == set(), (kind, text)
    clause = next(v for v in pset.values if v.label.endswith(".quote") and "two (2) days" in str(v.value))
    assert any(lk.label == clause.label for lk in scan(str(clause.value), pset, recipient_id="BUYER-2"))
    assert not any(lk.label == clause.label for lk in scan(str(clause.value), pset, recipient_id="BUYER-1"))


def test_the_buyer_reads_its_own_payment_days_and_another_buyer_does_not(pset):
    text = "Under our agreement Foshan Home Retail pays within 45 days of the invoice."
    assert "days" not in _kinds(text, pset, "BUYER-1")
    assert "days" in _kinds(text, pset, "BUYER-2")


def test_a_common_value_in_the_buyers_own_offer_does_not_block_a_reply_to_that_buyer(pset):
    own = "You asked for 2 days: Foshan Home Retail would then settle early within 2 days of the request."
    assert [lk for lk in scan(own, pset, recipient_id="BUYER-1") if lk.label.startswith("contract.")] == []
    other = "Dongguan Office Supplies would pay 30 days from the invoice date."
    assert [lk for lk in scan(other, pset, recipient_id="BUYER-2") if lk.label.startswith("contract.")] == []
