"""Derived performance dates and cross-checks between figures: code-side, from quoted text only."""

from __future__ import annotations

from app.compiler import Compiler
from app.compiler.base import ContractResult
from app.compiler.contract import contract_document
from app.compiler.contract_checks import cross_checks
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import ContractField, DocumentKind

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
    return doc, Compiler([_Model(*terms)]).compile_contract(doc)  # type: ignore[list-item]


SIGNED = _x(F.SIGNED_DATE, "签订日期：二〇二六年二月九日", date_text="二〇二六年二月九日")


def _dates(c):  # type: ignore[no-untyped-def]
    return {t.field: t for t in c.terms if t.field in (F.START_DATE, F.END_DATE)}


def test_a_delivery_period_counted_from_signing_gives_a_derived_start_and_end():
    text = "签订日期：二〇二六年二月九日\n\n1. 交货期限：本合同签订之日起15日内交货，即不迟于2026年2月24日完成供货。\n"
    _, c = _read(text, SIGNED)
    d = _dates(c)
    assert (d[F.START_DATE].date, d[F.END_DATE].date) == ("2026-02-09", "2026-02-24")
    assert d[F.END_DATE].text == "derived: the signing date plus 15 days" and d[F.START_DATE].text.startswith("derived:")
    assert d[F.END_DATE].span.text == "本合同签订之日起15日内"  # quoted from the document


def test_working_days_are_not_turned_into_a_date():
    text = "签订日期：二〇二六年二月九日\n\n交货期限：本合同签订之日起10个工作日内交货。\n"
    _, c = _read(text, SIGNED)
    assert _dates(c) == {} and any("working days" in a.reason for a in c.abstentions)


def test_a_payment_period_from_signing_is_not_a_performance_period():
    text = "签订日期：二〇二六年二月九日\n\n预付款：本合同签订生效之日起5日内，甲方向乙方支付合同总价的30%。\n"
    _, c = _read(text, SIGNED)
    assert _dates(c) == {}


def test_a_stated_end_date_that_disagrees_with_the_count_is_not_read():
    text = "签订日期：二〇二六年二月九日\n\n交货期限：本合同签订之日起15日内交货，即不迟于2026年3月1日完成供货。\n"
    _, c = _read(text, SIGNED)
    assert _dates(c) == {} and any("but the contract also says" in a.reason for a in c.abstentions)


def test_no_signed_date_no_derived_date():
    _, c = _read("交货期限：本合同签订之日起15日内交货。\n")
    assert _dates(c) == {}


def test_a_date_the_model_read_is_not_replaced():
    text = ("签订日期：二〇二六年二月九日\n\n服务期限：2026年3月1日至2026年3月31日。\n\n"
            "交货期限：本合同签订之日起15日内交货。\n")
    _, c = _read(text, SIGNED, _x(F.START_DATE, "服务期限：2026年3月1日至2026年3月31日", date_text="2026年3月1日"),
                 _x(F.END_DATE, "服务期限：2026年3月1日至2026年3月31日", date_text="2026年3月31日"))
    d = _dates(c)
    assert (d[F.START_DATE].date, d[F.END_DATE].date) == ("2026-03-01", "2026-03-31") and d[F.END_DATE].text is None


STAGES = ("合同总价为100,000元（大写：人民币壹拾万元整）\n\n预付款：合同总价的30%，即30,000元\n\n"
          "验收款：合同总价的60%，即60,000元\n\n质保金：合同总价的10%，即10,000元\n")


def _stage_terms(second: str = "60%", retention: str = "10%"):  # type: ignore[no-untyped-def]
    return [_x(F.PRICE, "合同总价为100,000元", value_text="100,000元"),
            _x(F.MILESTONE, "预付款：合同总价的30%，即30,000元", value_text="30%"),
            _x(F.MILESTONE, "验收款：合同总价的60%，即60,000元", value_text=second),
            _x(F.RETENTION, "质保金：合同总价的10%，即10,000元", value_text=retention)]


def test_stages_that_add_up_and_agree_with_the_total_raise_nothing():
    doc, c = _read(STAGES, *_stage_terms())
    checks = cross_checks(doc, c.terms)
    assert {x.kind for x in checks} == {"STAGES_SUM_100", "STAGE_AMOUNT", "WRITTEN_TOTAL"} and all(x.ok for x in checks)
    assert not [a for a in c.abstentions if a.field.startswith("note:STAGE")]


def test_stages_that_do_not_add_up_or_whose_amount_is_wrong_are_flagged_not_changed():
    text = STAGES.replace("60,000元", "61,000元")
    terms = _stage_terms()
    terms[2] = _x(F.MILESTONE, "验收款：合同总价的60%，即61,000元", value_text="60%")
    _, c = _read(text, *terms)
    reasons = [a.reason for a in c.abstentions if a.reason.startswith("check failed")]
    assert any("should be 60,000.00, but its clause states 61,000.00" in r for r in reasons)
    assert len([t for t in c.terms if t.field == F.MILESTONE]) == 2  # nothing is dropped or guessed


def test_percentages_that_miss_100_are_flagged():
    text = STAGES.replace("合同总价的10%", "合同总价的5%").replace("10,000元", "5,000元")
    _, c = _read(text, *_stage_terms(retention="5%")[:3], _x(F.RETENTION, "质保金：合同总价的5%，即5,000元", value_text="5%"))
    assert any("add up to 95%, not 100%" in a.reason for a in c.abstentions)


def test_the_amount_in_words_must_equal_the_total():
    text = STAGES.replace("壹拾万元整", "壹拾壹万元整")
    doc, c = _read(text, *_stage_terms())
    bad = [x for x in cross_checks(doc, c.terms) if x.kind == "WRITTEN_TOTAL"]
    assert len(bad) == 1 and not bad[0].ok
