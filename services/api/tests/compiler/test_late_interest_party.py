"""LATE_INTEREST is interest the BUYER owes for paying late. The supplier's penalty for late delivery, which a model
sometimes files under the same field, is dropped by code with an abstention, in English and in Chinese."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.contract import contract_document, supplier_late_delivery_penalty
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import ContractField, DocumentKind

F = ContractField

SELLER_ZH = "乙方逾期交货的，每逾期一日，按合同金额的0.1%向甲方支付违约金"
BUYER_ZH = "甲方逾期付款的，每逾期一日，按逾期未付金额的0.05%向乙方支付违约金"
SELLER_EN = "If the Supplier delivers late, the Supplier shall pay the Buyer liquidated damages of 0.5% of the price per day."
BUYER_EN = "If the Buyer pays an invoice late, the Buyer shall pay interest at 6% per annum on the overdue amount."


class _Model:
    name = "model"

    def __init__(self, quote: str, rate: str, period: str | None = None) -> None:
        self.term = XContractTerm(field=F.LATE_INTEREST, quote=quote, value_text=rate, date_text=None,
                                  period_text=period, basis_text=None, unit_text=None, trigger_text=None,
                                  reference_text=None, confidence=0.9)

    def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
        return ContractResult(ContractExtraction(terms=[self.term], authority_claims=[], data_requests=[]), self.name)


def _read(quote: str, rate: str, period: str | None = None):  # type: ignore[no-untyped-def]
    text = f"Agreement\n\n7. Breach\n\n7.1 {quote}\n"
    doc = contract_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1")
    return Compiler([_Model(quote, rate, period)]).compile_contract(doc)  # type: ignore[list-item]


@pytest.mark.parametrize("quote, rate", [(SELLER_ZH, "0.1%"), (SELLER_EN, "0.5%"),
                                         ("卖方延期交货的，每延期一日，按合同总价的0.3%向买方支付违约金", "0.3%"),
                                         ("供应商逾期交付的，按日0.2%承担违约金", "0.2%")])
def test_the_suppliers_late_delivery_penalty_is_not_late_interest(quote, rate):
    c = _read(quote, rate)
    assert [t for t in c.terms if t.field == F.LATE_INTEREST] == []
    (a,) = [a for a in c.abstentions if a.field == "LATE_INTEREST"]
    assert a.reason == "term dropped: the clause is the supplier's penalty, not interest owed by the buyer"
    assert a.spans and quote in a.spans[0].text


@pytest.mark.parametrize("quote, rate, period, bp", [
    (BUYER_ZH, "0.05%", None, 5), (BUYER_EN, "6%", "per annum", 600),
    ("甲方逾期付款的，应按年利率6%向乙方支付逾期利息", "6%", "年", 600),
    ("Late payment carries interest at 6% per annum on the overdue amount.", "6%", "per annum", 600),
])
def test_the_buyers_late_payment_interest_is_kept(quote, rate, period, bp):
    c = _read(quote, rate, period)
    (t,) = [t for t in c.terms if t.field == F.LATE_INTEREST]
    assert t.rate_bp == bp
    assert not [a for a in c.abstentions if a.field == "LATE_INTEREST"]


def test_a_clause_that_names_both_a_late_delivery_and_a_late_payment_is_kept():
    both = "乙方逾期交货的，按日0.1%支付违约金；甲方逾期付款的，按日0.05%支付违约金"
    assert supplier_late_delivery_penalty(both) is False
    assert supplier_late_delivery_penalty(SELLER_ZH) is True
    assert supplier_late_delivery_penalty(BUYER_EN) is False
    assert supplier_late_delivery_penalty("Delay in delivery by the Supplier carries a penalty of 1% per week.") is True
