"""Brief 03 §6.3: lender agreements through the term-sheet path: advance rate, covenant thresholds, lead times and
fee periods read from the wording agreements use."""

from __future__ import annotations

import pytest

from app.compiler import Compiler, compile_term_sheet
from app.compiler.cache import CACHE_MODEL_ID
from app.compiler.contract import contract_document
from app.compiler.rules import RulesBackend
from app.domain.fixtures import contract_fixture_bytes, load_offers, load_scenario, offer_documents
from app.domain.models import CompileStatus, CovenantKind, DocumentKind, SourceDocument
from app.ingest import extract_text


def _agreement(fixture_id: str, fmt: str | None = None) -> SourceDocument:
    name, data = contract_fixture_bytes(fixture_id, fmt)
    cp = {"MB_CREDIT_LINE_AGREEMENT": "BANK-1", "GBR_INVOICE_FINANCING_AGREEMENT": "PLATFORM-1"}[fixture_id]
    return contract_document(extract_text(name, data), DocumentKind.LENDER_AGREEMENT, cp)


def _sheet(text: str, sender: str = "BANK-1"):  # type: ignore[no-untyped-def]
    doc = SourceDocument(doc_id="TS", channel="term_sheet", sender_id=sender, received_day=0, text=text)
    return Compiler([RulesBackend()]).compile_term_sheet(doc)


def _covenants(facility) -> set[tuple]:  # type: ignore[no-untyped-def]
    return {(c.kind, c.threshold_bp, c.clean_down_days) for c in facility.covenants}


@pytest.mark.parametrize("fmt", [None, "docx", "pdf"])
def test_the_credit_line_agreement_reads_to_the_golden_line(fmt):
    golden = next(f for f in load_scenario()[0].facilities if f.id == "FAC-LINE")
    ts = (compile_term_sheet if fmt is None else Compiler([RulesBackend()]).compile_term_sheet)(
        _agreement("MB_CREDIT_LINE_AGREEMENT", fmt))
    f = ts.proposed_facility
    assert ts.status == CompileStatus.COMPILED and f is not None
    assert (f.kind, f.limit_fen, f.rate_bp, f.fee_bp_per_advance, f.upfront_fee_bp, f.lead_time_days,
            f.advance_rate_bp, f.repayment) == (golden.kind, golden.limit_fen, golden.rate_bp,
                                                golden.fee_bp_per_advance, golden.upfront_fee_bp,
                                                golden.lead_time_days, golden.advance_rate_bp, golden.repayment)
    assert _covenants(f) == _covenants(golden) == {(CovenantKind.DSCR_MIN, 12500, None),
                                                   (CovenantKind.LEVERAGE_MAX, 25000, None),
                                                   (CovenantKind.CLEAN_DOWN, None, 30)}
    if fmt is None:
        assert ts.compiler == CACHE_MODEL_ID  # the recorded demo reading


@pytest.mark.parametrize("fmt", [None, "docx", "pdf"])
def test_the_invoice_financing_agreement_reads_to_the_golden_platform(fmt):
    golden = next(f for f in load_scenario()[0].facilities if f.id == "FAC-IF")
    ts = (compile_term_sheet if fmt is None else Compiler([RulesBackend()]).compile_term_sheet)(
        _agreement("GBR_INVOICE_FINANCING_AGREEMENT", fmt))
    f = ts.proposed_facility
    assert f is not None
    assert (f.kind, f.limit_fen, f.rate_bp, f.fee_bp_per_advance, f.fee_period_days, f.upfront_fee_bp,
            f.lead_time_days, f.advance_rate_bp, f.repayment, f.covenants) == (
        golden.kind, golden.limit_fen, golden.rate_bp, golden.fee_bp_per_advance, golden.fee_period_days,
        golden.upfront_fee_bp, golden.lead_time_days, golden.advance_rate_bp, golden.repayment, [])
    assert ts.all_in_rate_bp == 1084  # 7.8% + 0.25% x 365/30


@pytest.mark.parametrize(("clause", "kind", "bp", "days"), [
    ("The Borrower shall keep a DSCR of 1.25x.", CovenantKind.DSCR_MIN, 12500, None),
    ("Debt service coverage ratio (DSCR) of at least 1.3 times in each month.", CovenantKind.DSCR_MIN, 13000, None),
    ("DSCR not less than 1.2:1.", CovenantKind.DSCR_MIN, 12000, None),
    ("Leverage: total debt shall not exceed 2.5 times annual EBITDA.", CovenantKind.LEVERAGE_MAX, 25000, None),
    ("Debt to EBITDA of no more than 3.0x at each quarter end.", CovenantKind.LEVERAGE_MAX, 30000, None),
    ("Clean-down: the balance shall be reduced to zero for at least fifteen (15) consecutive days a year.",
     CovenantKind.CLEAN_DOWN, None, 15),
    ("Clean down of 30 days each year.", CovenantKind.CLEAN_DOWN, None, 30),
])
def test_covenant_thresholds_are_parsed_into_numbers(clause, kind, bp, days):
    ts = _sheet(f"Credit line of RMB 100,000 at 5%. {clause}")
    cov = [c for c in ts.proposed_facility.covenants if c.kind == kind]
    assert [(c.threshold_bp, c.clean_down_days) for c in cov] == [(bp, days)]


def test_dscr_and_leverage_in_one_sentence_each_take_their_own_number():
    ts = _sheet("Credit line of RMB 100,000 at 5%. Covenants: DSCR at least 1.25x and leverage at most 2.5x.")
    assert _covenants(ts.proposed_facility) == {(CovenantKind.DSCR_MIN, 12500, None),
                                                (CovenantKind.LEVERAGE_MAX, 25000, None)}


@pytest.mark.parametrize(("clause", "days", "note"), [
    ("Drawdowns are funded on the same day as the request.", 0, False),
    ("Funds are disbursed within three (3) days of a request.", 3, False),
    ("Disbursement within 5 business days.", 5, True),
])
def test_lead_times_as_agreements_write_them(clause, days, note):
    ts = _sheet(f"Credit line of RMB 100,000 at 5%. {clause}")
    assert ts.proposed_facility.lead_time_days == days
    assert any(a.field == "note:lead_time.business_days" for a in ts.abstentions) is note


@pytest.mark.parametrize("fee", [
    "A service fee of 0.25% of each advance is charged for each period of thirty (30) days.",
    "Service fee: 0.25% per 30-day period.",
    "A service fee of 0.25% is charged every 30 days.",
])
def test_a_fee_per_period_is_read_from_its_whole_sentence(fee):
    ts = _sheet(f"Invoice financing facility with a facility limit of RMB 350,000. The interest rate is 7.8%. {fee}",
                sender="PLATFORM-1")
    f = ts.proposed_facility
    assert (f.fee_bp_per_advance, f.fee_period_days, f.upfront_fee_bp) == (25, 30, 0)


def test_two_different_advance_rates_conflict():
    ts = _sheet("Invoice financing facility with a facility limit of RMB 350,000 at 7.8%. Advance rate: 80% of the "
                "face. The Financier advances up to 70% of the face amount of each invoice.", sender="PLATFORM-1")
    assert ts.status == CompileStatus.CONFLICTING_SOURCES and ts.proposed_facility is None


def test_the_ex09_term_sheet_reads_as_before():
    assert load_offers()["EX09_TERM_SHEET_PG"]["expect"]["all_in_rate_bp"] == 590
    ts = compile_term_sheet(offer_documents("EX09_TERM_SHEET_PG")[0])
    assert ts.compiler == CACHE_MODEL_ID and ts.all_in_rate_bp == 590
    assert [c.field for c in ts.tier3_clauses] == ["guarantee"]
    assert ts.proposed_facility is not None and ts.proposed_facility.advance_rate_bp is None
