"""REG-1: filing a contract under the wrong buyer must not entitle that buyer to the contract's values.

A contract record is owned by its counterparty, so a mis-filed contract made the wrong buyer entitled to the values of
another buyer's contract. A refile closes the wrong record (REJECTED, superseded_by set) and a record whose party check
failed (PARTY_NOT_NAMED, blocking) cannot be confirmed: both stay protected from everyone and entitle nobody. A record the
owner plainly confirms, rejects or replaces by a later contract of the same buyer keeps its owner.
"""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import DocumentFlag, DocumentStatus, SourceSpan
from app.domain.ports import PARTY_NOT_NAMED_FLAG, guard_row
from app.egress import contract_private_values, protected_for, scan
from app.persistence import InMemoryLedgerStore, SqlLedgerStore
from tests.egress.test_contract_values_extended import _record

PAYS = "Under the agreement Foshan Home Retail pays within 45 days of the invoice date."
SIGNED = "The agreement was signed on 1 September 2026."


def _store(make):  # type: ignore[no-untyped-def]
    store = make()
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    return store


def _leaks(store, text, to):  # type: ignore[no-untyped-def]
    return {lk.label for lk in scan(text, protected_for(store), recipient_id=to) if lk.label.startswith("contract.")}


def _misfiled(store):  # type: ignore[no-untyped-def]
    """Buyer 1's contract filed under buyer 2 by mistake."""
    rec = _record()
    assert rec.counterparty_id == "BUYER-1"
    return store.add_contract_record(rec.model_copy(update={"counterparty_id": "BUYER-2"}))


def _not_named() -> DocumentFlag:
    return DocumentFlag(kind="PARTY_NOT_NAMED", blocking=True, note="not the counterparty you chose",
                        span=SourceSpan(doc_id="x", start=0, end=0, text=""))


MAKES = [pytest.param(InMemoryLedgerStore, id="memory"), pytest.param(lambda: SqlLedgerStore("sqlite://"), id="sql")]


@pytest.mark.parametrize("make", MAKES)
def test_a_misfiled_contract_entitles_the_wrong_buyer_until_it_is_refiled(make):
    """The mis-filing itself is the exposure this closes: before the refile the record is the wrong buyer's."""
    store = _store(make)
    _misfiled(store)
    assert _leaks(store, PAYS, "BUYER-2") == set()  # the record is filed under BUYER-2: the bare mis-filing entitles it


@pytest.mark.parametrize("make", MAKES)
def test_refile_does_not_widen_entitlement(make):
    store = _store(make)
    wrong = _misfiled(store)
    right = store.add_contract_record(_record())  # the owner files the same text under the right buyer
    store.close_refiled_record(wrong, right, 1, 7)
    closed = store.get_contract_record(wrong)
    assert closed.status == DocumentStatus.REJECTED and closed.superseded_by == right
    for text in (PAYS, SIGNED):
        assert _leaks(store, text, "BUYER-2"), text  # the wrong buyer is no longer entitled
        assert not _leaks(store, text, "BUYER-1"), text  # the right buyer reads its own contract
        assert not _leaks(store, text, "OWNER"), text
    assert any(v.label.startswith(f"contract.{wrong}.") for v in protected_for(store).values)  # still protected


@pytest.mark.parametrize("make", MAKES)
def test_a_record_blocked_by_party_not_named_entitles_nobody(make):
    store = _store(make)
    rec = _record()
    store.add_contract_record(rec.model_copy(update={"counterparty_id": "BUYER-2", "flags": [*rec.flags, _not_named()]}))
    for text in (PAYS, SIGNED):
        assert _leaks(store, text, "BUYER-2"), text  # filed under it, but the document is not with it
        assert not _leaks(store, text, "OWNER"), text
    # the date is in the contract only (the 45 days are also buyer 1's books terms): until the owner files the text right,
    # not even the buyer it is with is entitled to it
    assert _leaks(store, SIGNED, "BUYER-1")


@pytest.mark.parametrize("make", MAKES)
def test_a_plainly_decided_or_replaced_record_keeps_its_owner(make):
    store = _store(make)
    a = store.add_contract_record(_record())
    b = store.add_contract_record(_record())
    store.decide_contract_record(store.get_contract_record(a).model_copy(update={"status": DocumentStatus.CONFIRMED, "decided_day": 1, "decided_seq": 5}))
    store.decide_contract_record(store.get_contract_record(b).model_copy(update={"status": DocumentStatus.CONFIRMED, "decided_day": 2, "decided_seq": 6}))
    assert store.get_contract_record(a).superseded_by == b  # replaced by a later contract of the same buyer
    assert not _leaks(store, PAYS, "BUYER-1")
    assert _leaks(store, PAYS, "BUYER-2")


def test_the_slim_rows_and_the_full_records_protect_the_same_values_for_a_refile_and_a_blocked_record():
    state = load_scenario()[0]
    for make in (InMemoryLedgerStore, lambda: SqlLedgerStore("sqlite://")):
        store = _store(make)
        wrong = _misfiled(store)
        right = store.add_contract_record(_record())
        store.close_refiled_record(wrong, right, 1, 7)
        rec = _record()
        store.add_contract_record(rec.model_copy(update={"counterparty_id": "BUYER-2", "flags": [*rec.flags, _not_named()]}))
        assert contract_private_values(store.contract_records(), state) == contract_private_values(store.contract_guard_rows(), state)
        # the field itself, not only the values it protects: the SQL store's reading of the payload is the reference projection's
        assert [r.party_not_named for r in store.contract_guard_rows()] == [guard_row(r).party_not_named for r in store.contract_records()]
        assert [r.party_not_named for r in store.contract_guard_rows()].count(True) == 1


def test_the_guard_rows_flag_name_is_the_party_checks_own():
    """ports.PARTY_NOT_NAMED_FLAG is a copy of the kind app.contracts.parties raises (the domain imports no contracts module):
    a rename on one side alone would silently turn the REG-1 guard off."""
    from app.contracts.parties import PARTY_NOT_NAMED

    assert PARTY_NOT_NAMED_FLAG == PARTY_NOT_NAMED
