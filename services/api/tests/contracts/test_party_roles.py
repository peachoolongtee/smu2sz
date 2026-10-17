"""REG-2: the party check passes only a contract that names the chosen counterparty in the role its kind needs.

Each case reproduces a way the earlier matcher confirmed a contract that was not with the counterparty the owner chose: the
company named only as the other party, a different company sharing its first word, a longer company that contains its name,
a reading that found no parties, and a lender agreement whose lender was not found. Synthetic names; deterministic."""

from __future__ import annotations

import re

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.schema import ContractExtraction, XContractTerm
from app.contracts.parties import (
    PARTY_NOT_NAMED,
    PARTY_UNCHECKED,
    names_match,
    on_books,
    party_flags,
    party_matches,
    registry_names,
    with_party_check,
)
from app.contracts.records import read_document
from app.domain.fixtures import capex_contract_fixture_bytes, contract_fixture_bytes
from app.domain.models import ContractField, Counterparty, DocumentKind

FOSHAN = Counterparty(id="BUYER-1", name="Foshan Home Retail Co.", role="BUYER")
LING = "Lingnan Homeware Manufacturing Co., Ltd."


def _term(field: ContractField, quote: str, value: str | None = None) -> XContractTerm:
    return XContractTerm(field=field, quote=quote, value_text=value, date_text=None, period_text=None, basis_text=None,
                         unit_text=None, trigger_text=None, reference_text=None, confidence=0.9)


class _Reader:
    """Reads each party from its own "(n) <name> (the "Role")" line, as a live model does."""

    name = "model"

    def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
        terms = [_term(ContractField.PARTY_SUPPLIER if m["role"] in ("Supplier", "Seller") else ContractField.PARTY_BUYER,
                       m[0], m["name"])
                 for m in re.finditer(r'\(\d\) (?P<name>.+?) \(the "(?P<role>Supplier|Seller|Buyer)"\)', chunk.text)]
        return ContractResult(ContractExtraction(terms=terms, authority_claims=[], data_requests=[]), self.name)


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr("app.compiler.service._default_compiler", lambda: Compiler([_Reader()]))  # type: ignore[list-item]


def _doc(supplier: str | None, buyer: str | None) -> str:
    lines = []
    if supplier:
        lines.append(f'(1) {supplier} (the "Supplier"); and')
    if buyer:
        lines.append(f'(2) {buyer} (the "Buyer").')
    return ("SUPPLY AGREEMENT\n\nThis Agreement is made between:\n\n" + "\n\n".join(lines) +
            "\n\n4. PAYMENT\n\n4.1 The Buyer pays each invoice within forty-five (45) days after the Invoice Date.\n")


def _read(text: str, kind: DocumentKind = DocumentKind.BUYER_CONTRACT, cp: str = "BUYER-1"):  # type: ignore[no-untyped-def]
    return read_document(text, kind, cp, title=None, source="text", day=0, facilities=[])


def _kinds(rec, party: Counterparty = FOSHAN, extra=()):  # type: ignore[no-untyped-def]
    return [(f.kind, f.blocking) for f in party_flags(rec, registry_names(party, extra))]


# ---------------------------------------------------------------- the three reproductions


def test_the_counterparty_named_only_as_the_supplier_is_not_the_buyer(reader):
    rec = _read(_doc("Foshan Home Retail Co.", "Evil Holdings Ltd."))
    assert _kinds(rec) == [(PARTY_NOT_NAMED, True)]
    assert with_party_check(rec, FOSHAN).blocked


def test_a_buyer_sharing_only_the_first_word_is_a_different_company(reader):
    rec = _read(_doc(LING, "Foshan Evil Trading Co."))
    assert _kinds(rec) == [(PARTY_NOT_NAMED, True)]
    assert with_party_check(rec, FOSHAN).blocked


def test_a_longer_company_that_contains_the_name_is_a_different_company(reader):
    rec = _read(_doc(LING, "Foshan Home Retail Co. Hong Kong Shell Ltd."))
    assert _kinds(rec) == [(PARTY_NOT_NAMED, True)]
    assert with_party_check(rec, FOSHAN).blocked


# ---------------------------------------------------------------- the fail-open cases


def test_a_reading_with_no_party_names_is_blocked_not_confirmed_silently():
    rec = _read("Supply agreement.\n\nThe buyer pays each invoice 45 days after the invoice date.\n")
    assert _kinds(rec) == [(PARTY_UNCHECKED, True)]
    assert with_party_check(rec, FOSHAN).blocked


def test_a_reading_that_names_no_buyer_is_blocked(reader):
    rec = _read(_doc("Foshan Home Retail Co.", None))  # only the supplier slot is filled
    assert _kinds(rec) == [(PARTY_UNCHECKED, True)]


def test_a_lender_agreement_whose_lender_is_not_found_is_blocked():
    text = contract_fixture_bytes("MB_CREDIT_LINE_AGREEMENT")[1].decode("utf-8")
    rec = _read(text, DocumentKind.LENDER_AGREEMENT, "BANK-1")
    bank = Counterparty(id="BANK-1", name="Main bank", role="LENDER")
    assert rec.term_sheet.lender_name == "BANK-1"  # the reading fell back to the sender: it found no lender
    assert _kinds(rec, bank) == [(PARTY_UNCHECKED, True)]
    assert with_party_check(rec, bank).blocked


def test_a_lender_agreement_is_checked_against_the_party_the_document_defines():
    text = contract_fixture_bytes("MB_CREDIT_LINE_AGREEMENT")[1].decode("utf-8")
    rec = _read(text, DocumentKind.LENDER_AGREEMENT, "BANK-1")
    bank = Counterparty(id="BANK-1", name="Main bank", role="LENDER")
    # The owner registered the bank's name as the agreement writes it: the document defines that party, so it is checked.
    assert _kinds(rec, bank, ["Pearl River Commercial Bank, Foshan Branch"]) == []
    # Part of the defined party, or a party the document defines for someone else, is not the lender.
    assert _kinds(rec, bank, ["Pearl River"]) == [(PARTY_UNCHECKED, True)]
    assert _kinds(rec, bank, ["Commercial Bank, Foshan Branch"]) == [(PARTY_UNCHECKED, True)]
    assert _kinds(rec, bank, ["Lingnan Homeware Manufacturing"]) == [(PARTY_UNCHECKED, True)]
    gbr = _read(contract_fixture_bytes("GBR_INVOICE_FINANCING_AGREEMENT")[1].decode("utf-8"), DocumentKind.LENDER_AGREEMENT,
                "PLATFORM-1")
    platform = Counterparty(id="PLATFORM-1", name="Invoice financing platform", role="LENDER")
    assert _kinds(gbr, platform) == [(PARTY_UNCHECKED, True)]
    assert _kinds(gbr, platform, ["Greater Bay Receivables Finance Co."]) == []  # the legal-form words may differ


def test_a_lender_agreement_naming_another_lender_is_not_named():
    text = contract_fixture_bytes("MB_CREDIT_LINE_AGREEMENT")[1].decode("utf-8")
    rec = _read(text, DocumentKind.LENDER_AGREEMENT, "BANK-1")
    named = rec.model_copy(update={"term_sheet": rec.term_sheet.model_copy(
        update={"lender_name": "Pearl River Commercial Bank, Foshan Branch"})})
    other = Counterparty(id="BANK-2", name="Guaranteed-loan bank", role="LENDER")
    assert _kinds(named, other) == [(PARTY_NOT_NAMED, True)]
    assert _kinds(named, Counterparty(id="BANK-1", name="Pearl River Commercial Bank, Foshan Branch Co.", role="LENDER")) == []


# ---------------------------------------------------------------- roles for each kind


def test_a_capex_contract_is_checked_against_the_vendor_not_the_buyer_side():
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    vendor = Counterparty(id="VENDOR-GZPM", name="Guangzhou Precision Machinery Co., Ltd.", role="SUPPLIER")
    own = Counterparty(id="VENDOR-LING", name=LING, role="SUPPLIER")  # the business itself is the capex buyer
    rec = _read(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM")
    assert _kinds(rec, vendor) == []
    assert _kinds(rec, own) == [(PARTY_NOT_NAMED, True)]


def test_the_demo_supply_agreement_still_names_foshan_as_the_buyer():
    rec = _read(contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode("utf-8"))
    assert party_flags(rec, registry_names(FOSHAN)) == []


# ---------------------------------------------------------------- the matcher itself


@pytest.mark.parametrize("party", [
    "Foshan Home Retail Co.", "foshan home retail co.", "Foshan Home Retail Company Limited", "Foshan Home Retail Co., Ltd.",
    "Ｆｏｓｈａｎ　Ｈｏｍｅ　Ｒｅｔａｉｌ　Ｃｏ．", "FOSHAN HOME RETAIL",
])
def test_the_full_registry_name_matches_through_the_company_key(party):
    assert names_match(party, "Foshan Home Retail Co.")


@pytest.mark.parametrize("party", [
    "Foshan", "Foshan Evil Trading Co.", "Foshan Home Retail Co. Hong Kong Shell Ltd.", "Foshan Home Retail Group Ltd.",
    "Foshan Home", "Home Retail Co.", "",
])
def test_a_first_word_a_longer_name_or_a_part_is_not_the_company(party):
    assert not names_match(party, "Foshan Home Retail Co.")
    assert not party_matches([party], registry_names(FOSHAN))


def test_the_first_word_is_not_a_registry_name_but_an_owner_registered_short_name_is():
    assert registry_names(FOSHAN) == ["Foshan Home Retail Co."]
    assert not party_matches(["Foshan"], registry_names(FOSHAN))
    names = registry_names(FOSHAN, ["Foshan"])  # the short name the owner gave when adding the customer
    assert party_matches(["Foshan"], names) and party_matches(["Foshan Co., Ltd."], names)
    # The owner's own registration may sit inside a longer party name (澄昱智能 inside the legal name); the first word may not.
    assert party_matches(["深圳市澄昱智能制造股份有限公司"], ["Chengyu Intelligent Manufacturing", "澄昱智能"])
    assert not party_matches(["Foshan Evil Trading Co."], registry_names(FOSHAN))


def test_chinese_names_match_whole_through_the_company_key():
    names = ["深圳市晟达五金制品有限公司", "晟达五金"]
    assert party_matches(["深圳市晟达五金制品有限公司"], names) and party_matches(["深圳市晟达五金制品公司"], names)
    assert party_matches(["晟达五金"], names)
    assert not party_matches(["深圳市晟达五金制品有限公司香港分公司"], names[:1])
    assert not party_matches(["深圳市澄昱智能制造股份有限公司"], names)


def test_the_books_match_a_named_party_by_the_same_rule():
    registry = [FOSHAN, Counterparty(id="BUYER-2", name="Dongguan Office Supplies Ltd.", role="BUYER")]
    assert on_books("Foshan Home Retail Company Limited", "BUYER", registry) == "BUYER-1"
    assert on_books("Foshan Evil Trading Co.", "BUYER", registry) is None
    assert on_books("Foshan", "BUYER", registry) is None
    assert on_books("Foshan", "BUYER", registry, {"BUYER-1": ["Foshan"]}) == "BUYER-1"
