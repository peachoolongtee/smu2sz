"""A performance bond is not retention, and a price stated again inside its own total is read once."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.contract import contract_document, is_performance_bond
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import CompileStatus, ContractField, DocumentKind

F = ContractField


def _x(field: ContractField, quote: str, **kw: str | None) -> XContractTerm:
    base = {"value_text": None, "date_text": None, "period_text": None, "basis_text": None, "unit_text": None,
            "trigger_text": None, "reference_text": None, "confidence": 0.9}
    base.update(kw)
    return XContractTerm(field=field, quote=quote, **base)  # type: ignore[arg-type]


class _Model:
    name = "model"

    def __init__(self, *terms: XContractTerm) -> None:
        self.terms = list(terms)

    def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
        return ContractResult(ContractExtraction(terms=self.terms, authority_claims=[], data_requests=[]), self.name)


def _read(text: str, *terms: XContractTerm):  # type: ignore[no-untyped-def]
    doc = contract_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1")
    return Compiler([_Model(*terms)]).compile_contract(doc)  # type: ignore[list-item]


BOND_ZH = "履约保证金为合同金额的3%，即人民币4,248.00元，乙方以银行保函形式于合同签订前提交，项目验收合格后无息退还。"
BOND_EN = "The Supplier shall post a performance bond of 5% of the Contract Price before signing, returned after acceptance."
HELD_ZH = "质保金为合同金额的5%，在最后一笔货款中扣留，质保期满后无息退还。"
HELD_EN = "The Buyer shall retain 5% of each invoice for twelve (12) months as a quality guarantee."


@pytest.mark.parametrize("quote, rate", [(BOND_ZH, "3%"), (BOND_EN, "5%"),
                                         ("履约担保金额为合同总价的10%，以保函提交。", "10%"),
                                         ("The Supplier provides a security deposit of 10% of the price.", "10%")])
def test_a_performance_bond_is_not_retention(quote, rate):
    c = _read(f"Agreement\n\n5. Security\n\n5.1 {quote}\n", _x(F.RETENTION, quote, value_text=rate))
    assert [t for t in c.terms if t.field == F.RETENTION] == []
    (a,) = [a for a in c.abstentions if a.field == "RETENTION"]
    assert a.reason == "term dropped: the clause is a performance bond the supplier posts, not money withheld from payments"


@pytest.mark.parametrize("quote, rate, bp", [(HELD_ZH, "5%", 500), (HELD_EN, "5%", 500),
                                             ("质量保证金为合同金额的3%，质保期满后支付。", "3%", 300),
                                             ("尾款3%于质保期满后支付。", "3%", 300),
                                             ("The Buyer may withhold 10% of the price until the performance guarantee is returned.", "10%", 1000)])
def test_money_withheld_is_still_retention(quote, rate, bp):
    c = _read(f"Agreement\n\n5. Payment\n\n5.1 {quote}\n", _x(F.RETENTION, quote, value_text=rate))
    (t,) = [t for t in c.terms if t.field == F.RETENTION]
    assert t.rate_bp == bp


def test_the_cue_words():
    assert is_performance_bond(BOND_ZH) and is_performance_bond(BOND_EN)
    assert not is_performance_bond(HELD_ZH) and not is_performance_bond(HELD_EN)
    assert not is_performance_bond("The Buyer retains 5% as a performance guarantee.")


TABLE = ("合同金额小写：37950元　大写：人民币叁万柒仟玖佰伍拾元整\n\n序号 | 名称 | 单位 | 数量 | 单价 | 金额\n\n"
         "1 | 激光打印机 | 台 | 15 | 2530元 | 37950元\n")
TOTAL = _x(F.PRICE, "合同金额小写：37950元　大写：人民币叁万柒仟玖佰伍拾元整", value_text="37950元", unit_text="合同金额")
ROW = _x(F.PRICE, "1 | 激光打印机 | 台 | 15 | 2530元 | 37950元", value_text="2530元", unit_text="台")


def test_a_line_whose_row_states_the_total_is_read_inside_the_total():
    c = _read(TABLE, TOTAL, ROW)
    (p,) = [t for t in c.terms if t.field == F.PRICE]
    assert p.amount_fen == 3_795_000 and c.status != CompileStatus.CONFLICTING_SOURCES
    assert any("line of the contract total" in a.reason for a in c.abstentions)


def test_lines_that_add_up_to_the_total_are_read_inside_it():
    text = "Contract Price: RMB 30,000.\n\nItem A: RMB 10,000.\n\nItem B: RMB 20,000.\n"
    c = _read(text, _x(F.PRICE, "Contract Price: RMB 30,000.", value_text="RMB 30,000"),
              _x(F.PRICE, "Item A: RMB 10,000.", value_text="RMB 10,000"),
              _x(F.PRICE, "Item B: RMB 20,000.", value_text="RMB 20,000"))
    (p,) = [t for t in c.terms if t.field == F.PRICE]
    assert p.amount_fen == 3_000_000


def test_a_genuinely_different_amount_is_still_a_conflict():
    text = "Contract Price: RMB 30,000.\n\nElsewhere the Contract Price is RMB 35,000.\n"
    c = _read(text, _x(F.PRICE, "Contract Price: RMB 30,000.", value_text="RMB 30,000"),
              _x(F.PRICE, "Elsewhere the Contract Price is RMB 35,000.", value_text="RMB 35,000"))
    assert [t for t in c.terms if t.field == F.PRICE] == [] and c.status == CompileStatus.CONFLICTING_SOURCES
