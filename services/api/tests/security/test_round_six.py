"""Round six (Security Lead review of dev 70f23ac5, 18 Oct).

REG-8: a contract record blocked by PARTY_UNCHECKED (the reading named no party in the role, so it cannot be confirmed) stayed owned
by the counterparty it was filed under, so the egress guard let replies to that counterparty state its values: the exposure REG-1
closed for PARTY_NOT_NAMED. Every blocking party flag now makes the record entitle nobody, in both stores.
REG-2 allowance: the demo lender names for an unchanged demo agreement applied whatever the mode; now only in demo mode.
CT-2b: the borrower file (it goes to lenders) counted a contract set-up's invoices as recurring billing before the first was issued."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import DocumentFlag, RecurringInvoice, SourceSpan
from app.domain.ports import PARTY_UNCHECKED_FLAG, guard_row
from app.persistence import InMemoryLedgerStore, SqlLedgerStore
from tests.egress.test_refile_entitlement import PAYS, SIGNED, _leaks, _record, _store

MAKES = [pytest.param(InMemoryLedgerStore, id="memory"), pytest.param(lambda: SqlLedgerStore("sqlite://"), id="sql")]


def _unchecked() -> DocumentFlag:
    return DocumentFlag(kind="PARTY_UNCHECKED", blocking=True, note="the agent could not tell who it is with",
                        span=SourceSpan(doc_id="x", start=0, end=0, text=""))


@pytest.mark.parametrize("make", MAKES)
def test_a_record_blocked_by_party_unchecked_entitles_nobody(make):
    store = _store(make)
    rec = _record()
    store.add_contract_record(rec.model_copy(update={"counterparty_id": "BUYER-2", "flags": [*rec.flags, _unchecked()]}))
    for text in (PAYS, SIGNED):
        assert _leaks(store, text, "BUYER-2"), text  # filed under it, but not shown to be with it
    assert [r.party_not_named for r in store.contract_guard_rows()] == [guard_row(r).party_not_named for r in store.contract_records()]
    assert any(r.party_not_named for r in store.contract_guard_rows())


def test_the_unchecked_flag_name_is_the_party_checks_own():
    from app.contracts.parties import PARTY_UNCHECKED

    assert PARTY_UNCHECKED_FLAG == PARTY_UNCHECKED


def test_the_demo_lender_names_apply_in_demo_mode_only(monkeypatch):
    from app.api import documents

    fid, fx = next((k, v) for k, v in documents.load_contract_fixtures().items() if v.get("party_names"))
    name, data = documents.contract_fixture_bytes(fid, None)
    text = documents.extract_text(name, data)
    monkeypatch.setenv("DEMO_MODE", "1")
    assert documents._demo_upload_names(text, fx["counterparty_id"]) == list(fx["party_names"])
    monkeypatch.setenv("DEMO_MODE", "0")
    assert documents._demo_upload_names(text, fx["counterparty_id"]) == []


def test_the_borrower_file_does_not_bill_a_set_up_not_yet_issued():
    from app.borrower_file.build import build

    store = InMemoryLedgerStore()
    state, mandate = load_scenario()
    ri = RecurringInvoice(counterparty_id="BUYER-2", face_fen=18_000_000, every_days=30, next_issue_day=15, terms_days=30,
                          confirmed=False)
    store.put_state(state.model_copy(update={"recurring_invoices": [*state.recurring_invoices, ri]}))
    store.put_mandate(mandate)
    f = build(store, facility_id="FAC-LINE", amount_fen=1_000_000, use_of_proceeds="working capital", day=0)
    rows = {r.label: r for s in f.sections for r in s.rows}
    assert "Recurring invoicing set up from a contract, not yet issued" in rows
    store2 = InMemoryLedgerStore()
    store2.put_state(state)
    store2.put_mandate(mandate)
    g = build(store2, facility_id="FAC-LINE", amount_fen=1_000_000, use_of_proceeds="working capital", day=0)
    billed = lambda bf: next(r for s in bf.sections for r in s.rows if r.label == "Recurring invoicing per 30 days").figures[0]
    assert billed(f) == billed(g)  # the unconfirmed set-up adds nothing to what a lender is shown as billing
