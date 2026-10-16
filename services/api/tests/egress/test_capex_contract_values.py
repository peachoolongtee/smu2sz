"""ADR-0013: a capex contract's values are the vendor's, protected from every buyer like any counterparty's terms. Its parties
are the other way round from a buyer contract: the vendor's name is protected, and the SME's own name (the buyer in a capex
contract, and the sender of every message) is not, so uploading a vendor contract never blocks the owner's own messages."""

from __future__ import annotations

from app.contracts import read_document
from app.domain.fixtures import capex_contract_fixture_bytes, contract_fixture_bytes, load_scenario
from app.domain.models import DocumentKind
from app.egress import contract_private_values, protected_for, scan
from app.persistence import InMemoryLedgerStore

SME = "Lingnan Homeware Manufacturing Co., Ltd."
VENDOR = "Guangzhou Precision Machinery Co., Ltd."


def _capex():  # type: ignore[no-untyped-def]
    state = load_scenario()[0]
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    return read_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM", title="GZPM", source="test", day=0,
                         facilities=state.facilities).model_copy(update={"id": "DOC-000002"})


def _buyer():  # type: ignore[no-untyped-def]
    state = load_scenario()[0]
    text = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode("utf-8")
    return read_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1", title="FHR", source="test", day=0,
                         facilities=state.facilities).model_copy(update={"id": "DOC-000001"})


def _party_texts(values) -> set[str]:  # type: ignore[no-untyped-def]
    return {str(v.value) for v in values if v.label.endswith(".party")}


def test_the_vendors_name_is_protected_and_the_smes_own_name_is_not():
    values = contract_private_values([_capex()], load_scenario()[0])
    assert {v.owner for v in values} == {"VENDOR-GZPM"}
    assert _party_texts(values) == {VENDOR}
    assert not any(SME in str(v.value) for v in values if v.label.endswith(".party"))


def test_a_buyer_contract_still_protects_the_buyer_and_not_the_sme():
    values = contract_private_values([_buyer()], load_scenario()[0])
    assert _party_texts(values) == {"Foshan Home Retail Co."}


def test_a_buyer_cannot_be_told_the_vendors_price_or_name_and_the_sme_may_sign_its_messages():
    store = InMemoryLedgerStore()
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    store.add_contract_record(_buyer())
    store.add_contract_record(_capex())
    pset = protected_for(store)
    leak = f"We are buying a line from {VENDOR} for RMB 600,000."
    leaked = {lk.label for lk in scan(leak, pset, recipient_id="BUYER-1")}
    assert any(x.endswith(".party") for x in leaked) and any(".price." in x for x in leaked)
    signed = f"Thank you for your order. Kind regards, {SME}"
    assert scan(signed, pset, recipient_id="BUYER-1") == []
