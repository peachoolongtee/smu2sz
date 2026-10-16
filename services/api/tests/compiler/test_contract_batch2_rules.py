"""Code rules added after the second Chinese contract test set. Every string here is synthetic: written for the test,
not copied from a contract."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.contract import contract_document
from app.compiler.contract_parsing import parse_date
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import ContractField, DocumentKind

F = ContractField


def _x(field: ContractField, quote: str, **frags: str) -> XContractTerm:
    base = dict(value_text=None, date_text=None, period_text=None, basis_text=None, unit_text=None, trigger_text=None,
                reference_text=None)
    return XContractTerm(field=field, quote=quote, confidence=0.9, **{**base, **frags})  # type: ignore[arg-type]


class _Model:
    name = "model"

    def __init__(self, terms: list[XContractTerm]) -> None:
        self.terms = terms

    def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
        return ContractResult(ContractExtraction(terms=self.terms, authority_claims=[], data_requests=[]), self.name)


def _compile(text: str, terms: list[XContractTerm]):  # type: ignore[no-untyped-def]
    doc = contract_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1")
    return Compiler([_Model(terms)]).compile_contract(doc)  # type: ignore[list-item]


def _all(c, field: ContractField) -> list:  # type: ignore[no-untyped-def]
    return [t for t in c.terms if t.field == field]


def _one(c, field: ContractField):  # type: ignore[no-untyped-def]
    (t,) = _all(c, field)
    return t


def _lines(*parts: str) -> str:
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------- slash and dot dates


@pytest.mark.parametrize("text, iso", [
    ("签订日期：2026/5/24", "2026-05-24"), ("2026.03.05", "2026-03-05"), ("2026/3/5", "2026-03-05"),
    ("生效日期：2025.11.04。", "2025-11-04"), ("于2026/12/31前", "2026-12-31"), ("2026.03.05.", "2026-03-05"),
])
def test_slash_and_dot_dates_with_a_four_digit_year_are_read(text, iso):
    assert parse_date(text).value == iso


@pytest.mark.parametrize("text", ["5/24", "3.5", "2026.5", "金额1,234.00元", "单价3.14159元", "12026/3/5", "2026/3/5/7",
                                  "2026/03.05", "V12026.03.05"])
def test_no_date_without_a_four_digit_year_and_one_separator(text):
    assert parse_date(text).value is None
    assert not parse_date(text).conflict


@pytest.mark.parametrize("text", ["2026/2/30", "2026.13.01", "2026/4/31"])
def test_a_slash_or_dot_date_that_does_not_exist_is_not_a_date(text):
    p = parse_date(text)
    assert p.value is None and p.conflict


def test_two_different_slash_dates_are_a_conflict():
    assert parse_date("2026.3.5至2027.3.4").conflict


# ---------------------------------------------------------------- who pays whom

A_LINE = "甲方（总包方）：测试甲建设有限公司"
B_LINE = "乙方（专业方）：测试乙工程有限公司"


def _parties(text: str, buyer_line: str, supplier_line: str):  # type: ignore[no-untyped-def]
    def name(line: str) -> str:
        return line.split("：", 1)[1]
    return _compile(text, [_x(F.PARTY_BUYER, buyer_line, value_text=name(buyer_line)),
                           _x(F.PARTY_SUPPLIER, supplier_line, value_text=name(supplier_line))])


@pytest.mark.parametrize("evidence", [
    "乙方收款账户：户名 测试乙工程有限公司；开户行 测试银行；账号 6200000000000001。",
    "收款账户：户名 测试乙工程有限公司；账号 6200000000000001。",
    "本合同签订之日起7日内，甲方以银行转账方式向乙方支付合同价款的10%。",
])
def test_the_party_who_is_paid_is_the_supplier_even_when_read_the_other_way(evidence):
    c = _parties(_lines("测试分包合同", A_LINE, B_LINE, "第三条 付款", evidence), B_LINE, A_LINE)  # read the wrong way round
    assert _one(c, F.PARTY_BUYER).text == "测试甲建设有限公司"
    assert _one(c, F.PARTY_SUPPLIER).text == "测试乙工程有限公司"
    assert any(a.field == "note:PARTY_SUPPLIER" for a in c.abstentions)


def test_a_reading_that_agrees_with_the_evidence_is_left_alone():
    c = _parties(_lines("测试合同", A_LINE, B_LINE, "甲方应向乙方支付货款。"), A_LINE, B_LINE)
    assert _one(c, F.PARTY_BUYER).text == "测试甲建设有限公司"
    assert not any(a.field == "note:PARTY_SUPPLIER" for a in c.abstentions)


@pytest.mark.parametrize("evidence", [
    "",  # no evidence at all
    "乙方逾期履行的，每逾期一日，按合同价款的0.1%向甲方支付违约金。",  # a penalty runs the other way: not evidence
    "乙方应向甲方支付履约保证金。",  # a bond: not evidence
    "甲方应向乙方支付进度款。乙方应向甲方支付服务款。",  # both ways: ambiguous
    "甲方收款账户：户名 测试甲建设有限公司。乙方收款账户：户名 测试乙工程有限公司。",  # both hold one
])
def test_no_swap_without_clear_evidence(evidence):
    c = _parties(_lines("测试合同", A_LINE, B_LINE, evidence), B_LINE, A_LINE)
    assert _one(c, F.PARTY_BUYER).text == "测试乙工程有限公司"  # left as read
    assert not any(a.field == "note:PARTY_SUPPLIER" for a in c.abstentions)


def test_no_swap_when_a_party_has_no_role_label():
    text = _lines("测试合同", "买受人：测试甲建设有限公司", "出卖人：测试乙工程有限公司", "甲方应向乙方支付货款。")
    c = _parties(text, "出卖人：测试乙工程有限公司", "买受人：测试甲建设有限公司")
    assert _one(c, F.PARTY_BUYER).text == "测试乙工程有限公司"


# ---------------------------------------------------------------- a retention stated twice, read once

ROW = "4 保留金 5%"
CLAUSE = "保留金：按结算价的5%预留，保修期满后20日内无息返还。"


def _retentions(row: str, clause: str, row_rate: str, clause_rate: str):  # type: ignore[no-untyped-def]
    return _compile(_lines("测试合同", "付款表", row, "", "第五条", clause),
                    [_x(F.RETENTION, row, value_text=row_rate), _x(F.RETENTION, clause, value_text=clause_rate)])


def test_a_table_row_and_a_clause_with_the_same_retention_are_one_term_with_the_deadline():
    c = _retentions(ROW, CLAUSE, "5%", "5%")
    t = _one(c, F.RETENTION)
    assert (t.rate_bp, t.days) == (500, 20)
    assert c.status.value != "CONFLICTING_SOURCES"
    assert not any(a.reason.startswith("conflicting sources") for a in c.abstentions)


def test_two_different_retention_rates_still_conflict():
    c = _retentions(ROW, CLAUSE.replace("5%", "6%"), "5%", "6%")
    assert _all(c, F.RETENTION) == []
    assert any(a.field == "RETENTION" and a.reason.startswith("conflicting sources") for a in c.abstentions)


def test_two_different_retention_deadlines_still_conflict():
    row = "4 保留金 5% 保修期满后30日内"
    c = _retentions(row, CLAUSE, "5%", "5%")
    assert _all(c, F.RETENTION) == []
