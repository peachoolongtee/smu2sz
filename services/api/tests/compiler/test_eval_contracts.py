"""scripts/eval_contracts.py: the map from FLOW's terms to the answer key's fields, and the scoring."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from app.domain.models import CompileStatus, ContractField, ContractTerm, PaymentBasis, SourceSpan

_spec = importlib.util.spec_from_file_location("eval_contracts", Path(__file__).resolve().parents[2] / "scripts" / "eval_contracts.py")
ev = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(ev)  # type: ignore[union-attr]

F = ContractField


def _t(field: ContractField, **kw) -> ContractTerm:  # type: ignore[no-untyped-def]
    return ContractTerm(field=field, span=SourceSpan(doc_id="d", start=0, end=1, text="x"), **kw)


KEY = {
    "id": "CN-X", "contract_no": "A-1", "sign_date": "2026-02-09", "buyer": {"name": "甲 公司"}, "seller": {"name": "乙公司"},
    "amount_total": 141600.0, "performance": {"start_date": "2026-02-09", "end_date": "2026-02-24"}, "retention_pct": 0,
    "late_payment_interest": {"type": "daily_rate", "rate_pct": 0.05},
    "payment_stages": [
        {"percent": 30, "trigger": "sign", "days_after_trigger": 10, "days_unit": "working"},
        {"percent": 70, "trigger": "acceptance", "days_after_trigger": 30, "days_unit": "calendar"}],
}


def _compiled(terms):  # type: ignore[no-untyped-def]
    return SimpleNamespace(terms=terms, compiler="deepseek-flash", status=CompileStatus.COMPILED, chunks=1, abstentions=[])


def test_terms_map_to_the_keys_fields_and_score() -> None:
    c = _compiled([
        _t(F.CONTRACT_REFERENCE, text="A-1"), _t(F.SIGNED_DATE, date="2026-02-09"), _t(F.PARTY_BUYER, text="甲公司"),
        _t(F.PARTY_SUPPLIER, text="乙公司"), _t(F.PRICE, amount_fen=1_000_000), _t(F.PRICE, amount_fen=14_160_000),
        _t(F.START_DATE, date="2026-02-09"), _t(F.MILESTONE, rate_bp=3000, text="签订"), _t(F.MILESTONE, rate_bp=7000),
        _t(F.PAYMENT_TERMS, days=10, business_days=True), _t(F.PAYMENT_TERMS, days=30, basis=PaymentBasis.ACCEPTANCE),
        _t(F.LATE_INTEREST, rate_bp=5, text="每日"),
    ])
    p = ev.predict(c, "CN-X", "x.pdf")
    assert (p["amount_total"], p["retention_pct"], p["late_payment_interest"]) == (
        141600.0, 0, {"type": "daily_rate", "rate_pct": 0.05})
    assert [(s["percent"], s["days_after_trigger"], s["days_unit"], s["trigger"]) for s in p["payment_stages"]] == [
        (30.0, 10, "working", None), (70.0, 30, "calendar", "acceptance")]
    s = ev.score(KEY, p)
    assert s["contract_no"] == (1, 1, 0) and s["buyer.name"] == (1, 1, 0) and s["performance.end_date"] == (1, 0, 0)
    assert s["payment_stages[].percent"] == (2, 2, 0) and s["payment_stages[].days_unit"] == (2, 2, 0)
    assert s["payment_stages[].trigger"] == (2, 1, 0)  # "sign" is not a payment basis FLOW has
    assert s["late_payment_interest"] == (1, 1, 0)


def test_one_payment_term_and_no_milestone_reads_as_one_whole_stage_and_a_wrong_party_rate_is_scored_wrong() -> None:
    p = ev.predict(_compiled([_t(F.PAYMENT_TERMS, days=60, basis=PaymentBasis.INVOICE)]), "CN-Y", "y.pdf")
    assert p["payment_stages"] == [{"seq": 1, "percent": 100.0, "trigger_text": None, "implied": True,
                                    "days_after_trigger": 60, "days_unit": "calendar", "trigger": "invoice"}]
    key = {**KEY, "late_payment_interest": {"type": "not_specified"}}
    wrong = ev.predict(_compiled([_t(F.LATE_INTEREST, rate_bp=10, text="per day")]), "CN-Y", "y.pdf")
    assert ev.score(key, wrong)["late_payment_interest"] == (1, 0, 1)


def test_stages_that_state_their_own_deadline_and_trigger_are_scored_by_them_and_retention_is_a_last_stage() -> None:
    def stage(rate, quote, days, working=False):  # type: ignore[no-untyped-def]
        return ContractTerm(field=F.MILESTONE, rate_bp=rate, days=days, business_days=working,
                            span=SourceSpan(doc_id="d", start=0, end=1, text=quote))
    ret = ContractTerm(field=F.RETENTION, rate_bp=300, days=30, business_days=True,
                       span=SourceSpan(doc_id="d", start=0, end=1, text="质保金 3% 质保期满且无质量问题后30个工作日内"))
    c = _compiled([stage(9700, "验收款 97% 货物经甲方验收合格后10日内", 10), ret,
                   _t(F.PAYMENT_TERMS, days=99, business_days=True)])
    p = ev.predict(c, "CN-Z", "z.pdf")
    assert [(s["percent"], s["trigger"], s["days_after_trigger"], s["days_unit"]) for s in p["payment_stages"]] == [
        (97.0, "acceptance", 10, "calendar"), (3.0, "warranty_end", 30, "working")]  # a contract-wide term never overwrites
