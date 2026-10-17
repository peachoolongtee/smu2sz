"""The party check (owner's rule, 17 Oct; roles and whole-company matching, REG-2): the counterparty the owner chose against
the companies the reading found named in its role. Synthetic names; deterministic matching only (the same-company key).
The REG-2 cases themselves are in test_party_roles.py."""

from __future__ import annotations

import pytest

from app.contracts.parties import (
    PARTY_NOT_NAMED,
    PARTY_UNCHECKED,
    names_match,
    normalise,
    party_flags,
    party_matches,
    party_note,
    registry_names,
    with_party_check,
)
from app.contracts.records import read_document
from app.domain.fixtures import capex_contract_fixture_bytes, contract_fixture_bytes
from app.domain.models import ContractField, Counterparty, DocumentKind

FOSHAN = Counterparty(id="BUYER-1", name="Foshan Home Retail Co.", role="BUYER")


def _names(name: str) -> list[str]:
    return registry_names(Counterparty(id="X-1", name=name, role="BUYER"))


# ---------------------------------------------------------------- the matcher


def test_normalise_folds_width_case_punctuation_and_whitespace():
    assert normalise("ＦＯＳＨＡＮ　Home  Retail Co., Ltd.") == "foshan home retail co ltd"
    assert normalise("深圳市晟达（五金）制品有限公司") == "深圳市晟达 五金 制品有限公司"


@pytest.mark.parametrize("party, chosen", [
    ("Foshan Home Retail Co.", "Foshan Home Retail Co."),  # exact
    ("foshan home retail co.", "Foshan Home Retail Co."),  # case
    ("Foshan Home Retail Co., Ltd.", "Foshan Home Retail Co."),  # the legal-form words differ
    ("Foshan Home Retail", "Foshan Home Retail Co., Ltd."),  # the legal form left out
    ("Ｆｏｓｈａｎ　Ｈｏｍｅ　Ｒｅｔａｉｌ　Ｃｏ．", "Foshan Home Retail Co."),  # full-width
    ("深圳市晟达五金制品有限公司", "深圳市晟达五金制品有限公司"),  # Chinese, exact
    ("深圳市晟达五金制品公司", "深圳市晟达五金制品有限公司"),  # the Chinese legal form differs
])
def test_names_that_match(party, chosen):
    assert names_match(party, chosen)


@pytest.mark.parametrize("party, chosen", [
    ("Lingnan Homeware Manufacturing Co., Ltd.", "Foshan Home Retail Co."),
    ("深圳市澄昱智能制造股份有限公司", "深圳市晟达五金制品有限公司"),
    ("Foshanxi Trading Ltd.", "Foshan"),  # half a word is not the name
    ("Co., Ltd.", "Foshan Home Retail Co., Ltd."),  # too short to name a company
    ("", "Foshan Home Retail Co."),
    ("深圳市晟达五金制品有限公司", "晟达五金"),  # a part of a name is not the company
])
def test_names_that_do_not_match(party, chosen):
    assert not names_match(party, chosen)


def test_the_registry_names_are_the_name_and_the_short_names_the_owner_gave():
    assert _names("Foshan Home Retail Co.") == ["Foshan Home Retail Co."]  # the first word is the pages', not a registration
    names = _names("Foshan Home Retail Co.") + ["Foshan"]
    assert party_matches(["Lingnan Homeware Manufacturing Co., Ltd.", "Foshan Home Retail Company Limited"], names)
    assert party_matches(["Foshan"], names)  # a name the owner registered
    assert not party_matches(["FOSHAN HOME RETAIL (GROUP) CO., LTD."], names[:1])  # another company, not a form of this one
    assert not party_matches(["Lingnan Homeware Manufacturing Co., Ltd.", "Dongguan Office Supplies Ltd."], names)
    assert not party_matches([], names)


def test_a_chinese_registry_name_and_its_forms():
    names = ["深圳市晟达五金制品有限公司", "晟达五金"]  # a registry name and a short or Chinese name the owner registered
    assert party_matches(["深圳市晟达五金制品有限公司"], names)
    assert party_matches(["晟达五金"], names)  # the registered short name, whole
    assert party_matches(["晟达五金（深圳）有限公司"], names)  # the owner's short name inside a longer legal name
    assert not party_matches(["晟达五金（深圳）有限公司"], names[:1])  # but not from the registry name alone
    assert not party_matches(["深圳市晟达五金制品有限公司香港分公司"], names[:1])
    assert not party_matches(["深圳市澄昱智能制造股份有限公司"], names)


def test_matching_is_deterministic():
    found = ["Foshan Home Retail Co., Ltd.", "Lingnan Homeware Manufacturing Co., Ltd."]
    assert len({party_matches(found, _names("Foshan Home Retail Co.")) for _ in range(50)}) == 1


# ---------------------------------------------------------------- the flags on a reading


def _fhr(text: str | None = None, kind: DocumentKind = DocumentKind.BUYER_CONTRACT, cp: str = "BUYER-1"):  # type: ignore[no-untyped-def]
    text = text or contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode("utf-8")
    return read_document(text, kind, cp, title=None, source="text", day=0, facilities=[])


def test_the_demo_supply_agreement_names_foshan():
    rec = _fhr()
    assert {t.field for t in rec.contract.terms} >= {ContractField.PARTY_BUYER, ContractField.PARTY_SUPPLIER}
    assert party_flags(rec, registry_names(FOSHAN)) == []
    assert with_party_check(rec, FOSHAN) is rec


def test_the_demo_vendor_contract_names_its_vendor():
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    rec = read_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM", title=None, source="text", day=0, facilities=[])
    vendor = Counterparty(id="VENDOR-GZPM", name="Guangzhou Precision Machinery Co., Ltd.", role="SUPPLIER")
    assert party_flags(rec, registry_names(vendor)) == []
    assert with_party_check(rec, None) is rec  # a vendor not yet on the registry is not checked


def test_a_contract_with_two_other_companies_is_blocked_with_both_names():
    rec = _fhr()
    other = Counterparty(id="BUYER-2", name="Dongguan Office Supplies Ltd.", role="BUYER")
    (flag,) = party_flags(rec, registry_names(other))
    assert flag.kind == PARTY_NOT_NAMED and flag.blocking
    assert flag.note == ("This contract names Lingnan Homeware Manufacturing Co., Ltd. and Foshan Home Retail Co., not "
                         "Dongguan Office Supplies Ltd. Check who it is with before confirming.")
    assert rec.document.text[flag.span.start:flag.span.end] == flag.span.text
    checked = with_party_check(rec, other)
    assert checked.blocked and checked.flags[-1] == flag
    assert party_note(flag, checked, other.name, "zh") == (
        "这份合同列明的是Lingnan Homeware Manufacturing Co., Ltd.和Foshan Home Retail Co.，而不是Dongguan Office "
        "Supplies Ltd.。确认前请核实它的对方是谁。")


def test_a_reading_with_no_party_names_blocks_the_contract():
    rec = _fhr("Supply agreement.\n\nThe buyer pays each invoice 45 days after the invoice date.\n")
    (flag,) = party_flags(rec, registry_names(FOSHAN))
    assert flag.kind == PARTY_UNCHECKED and flag.blocking
    assert "could not check that it is with Foshan Home Retail Co." in flag.note
    assert with_party_check(rec, FOSHAN).blocked


def test_a_lender_agreement_is_checked_against_the_lender_the_reading_names():
    text = contract_fixture_bytes("MB_CREDIT_LINE_AGREEMENT")[1].decode("utf-8")
    rec = read_document(text, DocumentKind.LENDER_AGREEMENT, "BANK-1", title=None, source="text", day=0, facilities=[])
    bank = Counterparty(id="BANK-1", name="Main bank", role="LENDER")
    assert rec.term_sheet.lender_name == "BANK-1"  # the recorded reading names no lender, so "Main bank" is not found
    assert [f.kind for f in party_flags(rec, registry_names(bank))] == [PARTY_UNCHECKED]  # blocked, not skipped (REG-2)
    named = rec.model_copy(update={"term_sheet": rec.term_sheet.model_copy(
        update={"lender_name": "Pearl River Commercial Bank, Foshan Branch"})})
    pearl = Counterparty(id="BANK-1", name="Pearl River Commercial Bank, Foshan Branch", role="LENDER")
    assert party_flags(named, registry_names(pearl)) == []
    (flag,) = party_flags(named, registry_names(Counterparty(id="BANK-2", name="Guaranteed-loan bank", role="LENDER")))
    assert flag.kind == PARTY_NOT_NAMED and flag.blocking and flag.note.startswith(
        "This agreement names Pearl River Commercial Bank, Foshan Branch, not Guaranteed-loan bank.")
    assert text[flag.span.start:flag.span.end] == "Pearl River Commercial Bank, Foshan Branch"
