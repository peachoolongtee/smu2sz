"""Brief 03 §6.7: the golden equality test. The three demo documents, read by the agent and confirmed by the owner,
reproduce the golden books to the fen and the day:

- the supply agreement: the recurring invoices (face, interval, next issue day, terms), RCV-A (face, issue day,
  terms) and FAC-EARLYPAY (rate and lead time);
- the credit-line and invoice-financing agreements: FAC-LINE and FAC-IF (limit, rates, fees, lead time, advance rate
  and covenants).

The golden books (`fixtures/scenarios/golden_sme.json`) are not re-seeded from the contracts: they are pinned across
the suite, and this test proves the contracts agree with them. Nothing here writes them."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.compiler import Compiler
from app.compiler.rules import RulesBackend
from app.config import get_settings
from app.contracts import buyer_terms, read_document
from app.domain.fixtures import contract_fixture_bytes, load_contract_fixtures, load_scenario
from app.domain.models import DocumentKind, DocumentStatus
from app.ingest import extract_text
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
GOLDEN_STATE = load_scenario()[0]


def _facility(fid: str):  # type: ignore[no-untyped-def]
    return next(f for f in GOLDEN_STATE.facilities if f.id == fid)


def _covenants(f) -> set[tuple]:  # type: ignore[no-untyped-def]
    return {(c.kind, c.threshold_bp, c.clean_down_days) for c in f.covenants}


@pytest.fixture
def confirmed() -> dict:
    """The three demo documents uploaded and confirmed through the API on day 0, keyed by fixture id."""
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    client = TestClient(app, headers=OWNER)
    out = {}
    for fid, fx in load_contract_fixtures().items():
        d = client.post("/documents", json={"fixture_id": fid}).json()["document"]
        body = {"doc_hash": d["doc_hash"]}
        if fx.get("link_facility_id"):
            body["link_facility_id"] = fx["link_facility_id"]
        r = client.post(f"/documents/{d['id']}/confirm", json=body).json()
        assert r["result"]["status"] == "EXECUTED", r["result"]
        out[fid] = rt.store.get_contract_record(d["id"])
    assert rt.store.get_state().model_copy(update={"scenario": None}) == GOLDEN_STATE  # confirming wrote no books
    yield out
    set_runtime(None)


def test_the_supply_agreement_reproduces_the_golden_buyer_books(confirmed):
    rec = confirmed["FHR_SUPPLY_AGREEMENT"]
    assert rec.status == DocumentStatus.CONFIRMED and rec.contract is not None
    implied = buyer_terms(rec.contract, rec.counterparty_id, GOLDEN_STATE.as_of)
    (golden_recurring,) = GOLDEN_STATE.recurring_invoices
    assert implied.recurring(today=0) == golden_recurring  # BUYER-1, ¥420,000.00, every 30 days, next day 2, 45 days
    rcv = next(r for r in GOLDEN_STATE.receivables if r.id == "RCV-A")
    sched = implied.scheduled_invoice("RCV-A")
    assert sched is not None
    assert (sched.face_fen, sched.issue_day, implied.terms_days) == (rcv.face_fen, rcv.issue_day, rcv.terms_days)
    early = _facility("FAC-EARLYPAY")
    assert (implied.early_pay_rate_bp, implied.early_pay_window_days) == (early.rate_bp, early.lead_time_days)
    assert early.lender_id == rec.counterparty_id and early.limit_fen == implied.face_fen  # one invoice, early


@pytest.mark.parametrize(("fixture_id", "facility_id"), [("MB_CREDIT_LINE_AGREEMENT", "FAC-LINE"),
                                                         ("GBR_INVOICE_FINANCING_AGREEMENT", "FAC-IF")])
def test_the_lender_agreements_reproduce_the_golden_facilities(confirmed, fixture_id, facility_id):
    rec = confirmed[fixture_id]
    assert rec.linked_facility_id == facility_id and rec.term_sheet is not None
    agreed, golden = rec.term_sheet.proposed_facility, _facility(facility_id)
    assert agreed is not None
    fields = ("kind", "limit_fen", "rate_bp", "fee_bp_per_advance", "fee_period_days", "upfront_fee_bp",
              "lead_time_days", "advance_rate_bp", "repayment")
    assert {f: getattr(agreed, f) for f in fields} == {f: getattr(golden, f) for f in fields}
    assert _covenants(agreed) == _covenants(golden)
    assert agreed.lender_id == golden.lender_id == rec.counterparty_id


@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_the_word_and_pdf_copies_reproduce_the_same_books(fmt):
    """Through the upload path (no recorded reading: the grammar reads the extracted text directly)."""
    compiler = Compiler([RulesBackend()])
    fx = load_contract_fixtures()["FHR_SUPPLY_AGREEMENT"]
    name, data = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT", fmt)
    from app.compiler.contract import contract_document

    doc = contract_document(extract_text(name, data), DocumentKind.BUYER_CONTRACT, fx["counterparty_id"])
    implied = buyer_terms(compiler.compile_contract(doc), "BUYER-1", GOLDEN_STATE.as_of)
    assert implied.recurring(today=0) == GOLDEN_STATE.recurring_invoices[0]
    assert implied.scheduled_invoice("RCV-A").issue_day == -13
    for fid, golden in (("MB_CREDIT_LINE_AGREEMENT", "FAC-LINE"), ("GBR_INVOICE_FINANCING_AGREEMENT", "FAC-IF")):
        name, data = contract_fixture_bytes(fid, fmt)
        rec = read_document(extract_text(name, data), DocumentKind.LENDER_AGREEMENT,
                            load_contract_fixtures()[fid]["counterparty_id"], title=None, source="test", day=0,
                            facilities=GOLDEN_STATE.facilities)
        f = rec.term_sheet.proposed_facility
        g = _facility(golden)
        assert (f.limit_fen, f.rate_bp, f.fee_bp_per_advance, f.lead_time_days, f.advance_rate_bp) == (
            g.limit_fen, g.rate_bp, g.fee_bp_per_advance, g.lead_time_days, g.advance_rate_bp)
        assert rec.suggested_facility_id == golden


def test_the_recurring_invoice_moves_with_the_day_as_the_books_do():
    """The contract's schedule (every 30 days from 3 October 2026) gives the books' next issue day on any day."""
    from app.compiler import compile_contract
    from app.compiler.contract import contract_document

    name, data = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")
    doc = contract_document(extract_text(name, data), DocumentKind.BUYER_CONTRACT, "BUYER-1")
    implied = buyer_terms(compile_contract(doc), "BUYER-1", GOLDEN_STATE.as_of)
    assert [implied.next_issue_day(d) for d in (0, 2, 3, 32, 33, 34)] == [2, 2, 32, 32, 62, 62]
