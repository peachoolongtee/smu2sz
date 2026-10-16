"""Per-stage payment schedules: the days, unit and trigger of each milestone are read by code from its quote (en and zh)."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.contract import contract_document
from app.compiler.contract_checks import stage_basis, stage_deadline, stage_trigger, widen_to_row
from app.compiler.contract_parsing import cn_int
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import CompileStatus, ContractField, DocumentKind, PaymentBasis

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


@pytest.mark.parametrize("text, n", [("十五", 15), ("三十", 30), ("九十", 90), ("十", 10), ("二十五", 25), ("一百八十", 180),
                                     ("一百零五", 105), ("两", 2), ("六", 6)])
def test_chinese_numerals(text, n):
    assert cn_int(text) == n


@pytest.mark.parametrize("text", ["", "abc", "十五日"])
def test_not_a_chinese_numeral(text):
    assert cn_int(text) is None


@pytest.mark.parametrize("quote, days, working", [
    ("交付成果经甲方验收合格并出具书面验收报告后15日内", 15, False),
    ("质保期满且无质量问题后30个工作日内", 30, True),
    ("每季度服务考核合格之日起 45个工作日内，甲方以银行转账方式支付", 45, True),
    ("甲方收到乙方开具的合法有效发票后\n\n60日内", 60, False),
    ("货物经甲方验收合格后三十天内", 30, False),
    ("项目审计完成后一百八十日内", 180, False),
    ("2 质保金 3% 12213.60元 质保期满且无质量问题后15个工作日", 15, True),
    ("Payable within thirty (30) days after acceptance", 30, False),
    ("within 10 business days of delivery", 10, True),
    ("net 45 working days from the invoice date", 45, True),
])
def test_deadline_days_and_unit(quote, days, working):
    d = stage_deadline(quote)
    assert (d.status, d.days, d.working) == ("ok", days, working)


@pytest.mark.parametrize("quote, status", [
    ("1 预付款 30%", "none"),
    ("货物经甲方验收合格并出具书面验收报", "none"),
    ("合同总价的30%，票据期限不超过6个月", "none"),
    ("签订后10日内支付预付款，逾期30日内补正", "conflict"),
    ("payable on signing", "none"),
    ("within 10 days of signing and within 30 days of delivery", "conflict"),
])
def test_no_days_or_two_different_ones_is_no_value(quote, status):
    d = stage_deadline(quote)
    assert (d.status, d.days) == (status, None)


@pytest.mark.parametrize("quote, trigger", [
    ("（1）预付款：本合同签订生效之日起10个工作日内，甲方以银行转账方式支付", "sign"),
    ("本合同签订生效后15日内", "sign"),
    ("交付成果经甲方验收合格并出具书面验收报告后15日内", "acceptance"),
    ("货物经甲方验收合格并出具书面验收报告之日起60日内", "acceptance"),
    ("全部货物送达甲方指定地点并经甲方签收之日起60日内", "delivery"),
    ("货物到货后30日内", "delivery"),
    ("甲方收到乙方开具的合法有效发票后60日内", "invoice"),
    ("服务费按季度平均支付，每季度服务期满并经甲方考核合格之日起30个工作日内", "quarter"),
    ("项目经甲方或甲方委托的审计机构审计完成后30个工作日内", "audit"),
    ("质保期满且无质量问题后30个工作日内", "warranty_end"),
    ("乙方完成系统设计及开发阶段成果并经甲方书面确认之日起90日内", "milestone"),
    ("1 | 预付款 | 40% | 186400元 | 本合同签订生效后15日内 | 银行转账", "sign"),
    ("1 验收款 100% 191420.00元 货物经甲方验收合格并出具书面验收报\n\n告后60个工作日内 银行转账", "acceptance"),
    ("Payable within 30 days after acceptance of the Goods", "acceptance"),
    ("within 15 days of the date of signing", "sign"),
    ("within 45 days after receipt of a valid invoice", "invoice"),
    ("within 30 days after the end of each quarter", "quarter"),
    ("within 30 days after the audit is completed", "audit"),
    ("within 30 days after the warranty period expires", "warranty_end"),
])
def test_trigger_classification(quote, trigger):
    assert stage_trigger(quote) == trigger


def test_a_quote_naming_no_trigger_is_none_and_the_readings_own_words_are_the_fallback():
    assert stage_trigger("30日内") is None
    assert stage_trigger("1 预付款 30%", "合同签订") == "sign"


def test_only_the_payment_bases_the_engine_has_are_written_to_basis():
    assert [stage_basis(t) for t in ("invoice", "delivery", "acceptance")] == [
        PaymentBasis.INVOICE, PaymentBasis.DELIVERY, PaymentBasis.ACCEPTANCE]
    assert [stage_basis(t) for t in ("sign", "quarter", "audit", "warranty_end", "milestone", None)] == [None] * 6


ROWS = ("合同编号：X\n\n期次 款项 比例 金额 支付条件及期限 支付方式\n\n1 预付款 30%\n\n人民币\n\n111,000.00元\n\n"
        "本合同签订生效后7日内 银行转账\n\n2 进度款 40%\n\n人民币\n\n148,000.00元\n\n乙方完成阶段成\n\n果并经甲方书面确认后30个工作\n\n"
        "日内\n\n银行转账\n\n乙方应在每期付款前向甲方开具等额发票。\n")


def test_a_table_row_quoted_short_is_read_to_the_rows_end_and_no_further():
    a = ROWS.index("1 预付款 30%")
    end = widen_to_row(ROWS, a, a + len("1 预付款 30%"))
    assert ROWS[a:end].endswith("本合同签订生效后7日内 银行转账")
    b = ROWS.index("2 进度款 40%")
    end_b = widen_to_row(ROWS, b, b + len("2 进度款 40%"))
    assert ROWS[b:end_b].endswith("日内\n\n银行转账") and "乙方应在" not in ROWS[b:end_b]


def test_a_quote_that_already_states_its_deadline_or_is_not_a_row_is_not_widened():
    a = ROWS.index("本合同签订生效后7日内")
    assert widen_to_row(ROWS, a, a + 11) == a + 11
    b = ROWS.index("1 预付款 30%")
    assert widen_to_row(ROWS, b + 2, b + 6) == b + 6


def test_milestones_carry_their_own_days_unit_and_basis_and_payment_terms_do_not_conflict():
    text = ("采购合同\n\n四、付款\n\n1 | 预付款 | 40% | 186400元 | 本合同签订生效后15日内 | 银行转账\n\n"
            "2 | 验收款 | 60% | 279600元 | 交付成果经甲方验收合格后30个工作日内 | 银行转账\n")
    q1 = "1 | 预付款 | 40% | 186400元 | 本合同签订生效后15日内 | 银行转账"
    q2 = "2 | 验收款 | 60% | 279600元 | 交付成果经甲方验收合格后30个工作日内 | 银行转账"
    c = _read(text,
              _x(F.MILESTONE, q1, value_text="40%", trigger_text="本合同签订生效后15日内"),
              _x(F.MILESTONE, q2, value_text="60%", trigger_text="交付成果经甲方验收合格后30个工作日内"),
              _x(F.PAYMENT_TERMS, q1, period_text="15日"),
              _x(F.PAYMENT_TERMS, q2, period_text="30个工作日", basis_text="验收合格"),
              _x(F.PRICE, "186400元", value_text="186400元"))
    m = [t for t in c.terms if t.field == F.MILESTONE]
    assert [(t.rate_bp, t.days, t.business_days, t.basis) for t in m] == [
        (4000, 15, False, None), (6000, 30, True, PaymentBasis.ACCEPTANCE)]
    assert [stage_trigger(t.span.text, t.text) for t in m] == ["sign", "acceptance"]
    assert not [t for t in c.terms if t.field == F.PAYMENT_TERMS]
    assert c.status != CompileStatus.CONFLICTING_SOURCES
    assert any(a.field == "note:PAYMENT_TERMS" for a in c.abstentions)


def test_a_contract_wide_payment_rule_in_its_own_clause_is_kept():
    text = ("Supply Agreement\n\n4. Payment\n\n4.1 30% on signing, within 10 days of signing.\n\n"
            "4.2 70% on acceptance, within 30 days after acceptance.\n\n4.3 All sums are payable in 45 days of the invoice.\n")
    c = _read(text,
              _x(F.MILESTONE, "30% on signing, within 10 days of signing.", value_text="30%", trigger_text="on signing"),
              _x(F.MILESTONE, "70% on acceptance, within 30 days after acceptance.", value_text="70%",
                 trigger_text="on acceptance"),
              _x(F.PAYMENT_TERMS, "All sums are payable in 45 days of the invoice.", period_text="45 days",
                 basis_text="the invoice"))
    m = [t for t in c.terms if t.field == F.MILESTONE]
    assert [(t.days, t.basis) for t in m] == [(10, None), (30, PaymentBasis.ACCEPTANCE)]
    (pay,) = [t for t in c.terms if t.field == F.PAYMENT_TERMS]
    assert (pay.days, pay.basis) == (45, PaymentBasis.INVOICE)


def test_a_stage_with_no_days_or_two_deadlines_is_kept_without_days_and_says_so():
    text = "合同\n\n1 预付款 30% 合同签订后\n\n2 验收款 70% 验收合格后10日内，逾期30日内补正\n"
    q1, q2 = "1 预付款 30% 合同签订后", "2 验收款 70% 验收合格后10日内，逾期30日内补正"
    c = _read(text, _x(F.MILESTONE, q1, value_text="30%"), _x(F.MILESTONE, q2, value_text="70%"))
    m = [t for t in c.terms if t.field == F.MILESTONE]
    assert [(t.days, t.basis) for t in m] == [(None, None), (None, None)]
    reasons = [a.reason for a in c.abstentions if a.field == "MILESTONE"]
    assert any("no number of days" in r for r in reasons) and any("more than one payment deadline" in r for r in reasons)


def test_a_label_the_reading_wrote_in_its_own_words_does_not_drop_the_stage():
    q = "3 到货款 60% 货物运抵甲方仓库后90个工作日内"
    c = _read(f"合同\n\n{q}\n", _x(F.MILESTONE, q, value_text="60%", trigger_text="货物到货"))
    (t,) = [t for t in c.terms if t.field == F.MILESTONE]
    assert (t.rate_bp, t.days, t.business_days, t.text) == (6000, 90, True, None)


def test_warranty_money_read_as_a_stage_is_the_retention_and_an_audit_stage_read_as_retention_is_a_stage():
    q1 = "2 质保金 3% 12213.60元 质保期满且无质量问题后15个工作日内"
    q2 = "项目经甲方或甲方委托的审计机构审计完成之日起15日内，甲方向乙方支付合同总价的5%。"
    c = _read(f"合同\n\n{q1}\n\n{q2}\n", _x(F.MILESTONE, q1, value_text="3%"), _x(F.RETENTION, q2, value_text="5%"))
    (ret,) = [t for t in c.terms if t.field == F.RETENTION]
    (stage,) = [t for t in c.terms if t.field == F.MILESTONE]
    assert (ret.rate_bp, ret.days, ret.business_days) == (300, 15, True)
    assert (stage.rate_bp, stage.days, stage.business_days) == (500, 15, False)
    assert stage_trigger(stage.span.text) == "audit"


def test_english_retention_without_withholding_words_is_left_alone():
    q = "5% of the price is held until the end of the warranty."
    c = _read(f"Agreement\n\n{q}\n", _x(F.RETENTION, q, value_text="5%"))
    assert [t.field for t in c.terms] == [F.RETENTION]
