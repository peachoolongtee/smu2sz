"""POST /documents checks that the counterparty the owner chose is a party the document names (owner's rule, 17 Oct): a
contract between two other companies is blocked with a note naming them, in en and zh, and cannot be confirmed; a reading
that found no party names carries a warning; the demo documents, read with their own kind and counterparty, carry neither."""

from __future__ import annotations

import re

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import ContractField

SHENGDA = "深圳市晟达五金制品有限公司"
CHENGYU = "深圳市澄昱智能制造股份有限公司"
OTHERS = (f"SUPPLY AGREEMENT\n\nThis Agreement is made between:\n\n(1) {SHENGDA} (the \"Supplier\"); and\n\n"
          f"(2) {CHENGYU} (the \"Buyer\").\n\n4. PAYMENT\n\n4.1 The Buyer pays each invoice within forty-five (45) days "
          f"after the Invoice Date.\n")
NO_PARTIES = "SUPPLY AGREEMENT\n\n4. PAYMENT\n\n4.1 The Buyer pays each invoice within forty-five (45) days after the Invoice Date.\n"


def _term(field: ContractField, quote: str, value: str | None = None) -> XContractTerm:
    return XContractTerm(field=field, quote=quote, value_text=value, date_text=None, period_text=None, basis_text=None,
                         unit_text=None, trigger_text=None, reference_text=None, confidence=0.9)


class _Reader:
    """A model that reads the parties as a live model would: each name quoted from its own "(n) <name> (the ...)" line."""

    name = "model"

    def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
        terms = [_term(ContractField.PARTY_SUPPLIER if m["role"] == "Supplier" else ContractField.PARTY_BUYER, m[0], m["name"])
                 for m in re.finditer(r'\(\d\) (?P<name>.+?) \(the "(?P<role>Supplier|Buyer)"\)', chunk.text)]
        return ContractResult(ContractExtraction(terms=terms, authority_claims=[], data_requests=[]), self.name)


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr("app.compiler.service._default_compiler", lambda: Compiler([_Reader()]))  # type: ignore[list-item]


@pytest.fixture
def capex_on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


def _post(client, lang: str = "en", **body) -> dict:  # type: ignore[no-untyped-def]
    r = client.post(f"/documents?lang={lang}", json=body)
    assert r.status_code == 200, r.text
    return r.json()["document"]


@pytest.mark.parametrize("fixture_id", ["FHR_SUPPLY_AGREEMENT", "MB_CREDIT_LINE_AGREEMENT", "GBR_INVOICE_FINANCING_AGREEMENT",
                                        "GZPM_EQUIPMENT_PURCHASE"])
@pytest.mark.parametrize("fmt", ["md", "docx", "pdf"])
def test_each_demo_document_read_with_its_own_counterparty_carries_no_party_flag(client, capex_on, fixture_id, fmt):
    listed = {f["id"]: f for f in [*client.get("/fixtures/contracts").json()["contracts"],
                                   *client.get("/fixtures/capex-contracts").json()["contracts"]]}
    if fmt not in listed[fixture_id]["formats"]:
        pytest.skip(f"{fixture_id} has no {fmt} copy")
    d = _post(client, fixture_id=fixture_id, format=fmt)
    assert not [f for f in d["flags"] if f["kind"].startswith("PARTY_")]
    assert d["can_confirm"] is True


def test_the_demo_supply_agreement_pasted_as_text_for_foshan_carries_no_party_flag(client):
    from app.domain.fixtures import contract_fixture_bytes

    text = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode("utf-8")
    d = _post(client, kind="BUYER_CONTRACT", counterparty_id="BUYER-1", text=text)
    assert d["flags"] == [] and d["can_confirm"] is True


def test_a_contract_between_two_other_companies_is_blocked_and_cannot_be_confirmed(client, reader):
    from app.api.runtime import get_runtime

    d = _post(client, kind="BUYER_CONTRACT", counterparty_id="BUYER-1", text=OTHERS)
    assert {t["field"] for t in d["terms"]} >= {"PARTY_BUYER", "PARTY_SUPPLIER"}
    (flag,) = [f for f in d["flags"] if f["kind"] == "PARTY_NOT_NAMED"]
    assert flag["blocking"] is True and flag["kind_text"] == "not the counterparty you chose"
    assert flag["note"] == (f"This contract names {SHENGDA} and {CHENGYU}, not Foshan Home Retail Co. "
                            f"Check who it is with before confirming.")
    assert flag["quote"] == OTHERS[flag["span"]["start"]:flag["span"]["end"]] and SHENGDA in flag["quote"]
    assert d["blocked"] is True and d["can_confirm"] is False
    assert d["status_text"] == "Cannot be confirmed: it does not name the counterparty you chose"
    assert get_runtime().store.security_events() == []  # the wrong counterparty is a mistake, not an attack

    zh = client.get(f"/documents/{d['id']}?lang=zh").json()["document"]
    (zflag,) = [f for f in zh["flags"] if f["kind"] == "PARTY_NOT_NAMED"]
    assert zflag["kind_text"] == "不是您选择的对方"
    assert zflag["note"] == f"这份合同列明的是{SHENGDA}和{CHENGYU}，而不是Foshan Home Retail Co.。确认前请核实它的对方是谁。"
    assert zh["status_text"] == "无法确认：文件没有列明您选择的对方"

    c = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    assert c.status_code == 200
    assert c.json()["result"]["status"] == "REFUSED" and c.json()["document"]["status"] == "PROPOSED"
    assert get_runtime().store.get_contract_record(d["id"]).status.value == "PROPOSED"


def test_the_same_contract_naming_foshan_in_its_long_form_is_not_flagged(client, reader):
    d = _post(client, kind="BUYER_CONTRACT", counterparty_id="BUYER-1",
              text=OTHERS.replace(CHENGYU, "FOSHAN HOME RETAIL CO., LTD."))
    assert [t["value_display"] for t in d["terms"] if t["field"] == "PARTY_BUYER"] == ["FOSHAN HOME RETAIL CO., LTD."]
    assert d["flags"] == [] and d["can_confirm"] is True


def test_a_reading_with_no_party_names_carries_a_warning_and_can_be_confirmed(client):
    d = _post(client, kind="BUYER_CONTRACT", counterparty_id="BUYER-1", text=NO_PARTIES)
    (flag,) = [f for f in d["flags"] if f["kind"] == "PARTY_UNCHECKED"]
    assert flag["blocking"] is False and flag["kind_text"] == "parties not checked"
    assert flag["note"] == ("The agent found no party names in this document, so it could not check that it is with "
                            "Foshan Home Retail Co. Check who it is with before confirming.")
    assert d["blocked"] is False and d["can_confirm"] is True
    zh = client.get(f"/documents/{d['id']}?lang=zh").json()["document"]
    (zflag,) = zh["flags"]
    assert zflag["kind_text"] == "未能核对合同各方"
    assert zflag["note"] == "代理没有在文件中读到各方的名称，因此无法核实它是否与Foshan Home Retail Co.签订。确认前请核实它的对方是谁。"
    c = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).json()
    assert c["result"]["status"] == "EXECUTED"


def test_a_lender_agreement_whose_reading_names_no_lender_is_not_checked(client):
    d = _post(client, kind="LENDER_AGREEMENT", counterparty_id="BANK-1",
              text="Credit line of RMB 100,000 at 5% a year. Funds released within 1 day.")
    assert not [f for f in d["flags"] if f["kind"].startswith("PARTY_")]
