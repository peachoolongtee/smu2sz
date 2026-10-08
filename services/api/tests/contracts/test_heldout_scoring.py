"""Brief 03 §6.8: the held-out scorer. Checked on synthetic labels here; the held-out set itself is pending and its
report says so (no figure is quoted from the demo documents the grammar was written against)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.compiler import Compiler
from app.compiler.contract import contract_document
from app.compiler.rules import RulesBackend
from app.contracts.heldout import ABSTAINED, AGREE, WRONG, ContractResult, report, score
from app.domain.models import DocumentKind

TEXT = ("SUPPLY CONTRACT\n\nAgreement No. DG-2026-031\n\n3.1 The Buyer shall pay the Supplier RMB 120,000 for each "
        "delivery.\n\n4.2 Each invoice is payable sixty (60) days after acceptance of the delivery by the Buyer.\n\n"
        "4.6 Five per cent (5%) of each invoice shall be retained by the Buyer for twelve (12) months.\n\n"
        "4.7 The price is reviewed every quarter against the copper index.\n")


def _reading():  # type: ignore[no-untyped-def]
    return Compiler([RulesBackend()]).compile_contract(contract_document(TEXT, DocumentKind.BUYER_CONTRACT, "BUYER-2"))


def test_agree_blank_and_wrong_are_told_apart():
    expected = {
        "PRICE": {"amount_fen": 12_000_000, "unit": "PER_DELIVERY"},
        "PAYMENT_TERMS": {"days": 60, "basis": "ACCEPTANCE"},
        "RETENTION": {"rate_bp": 500, "months": 12},
        "CONTRACT_REFERENCE": {"text": "DG-2026-031"},
        "LATE_INTEREST": None,
        "EARLY_PAYMENT": {"rate_bp": 100},  # the label says 1%: the reading left it blank
        "INVOICING": None,
        "REQUIRED_DOCUMENT": 0,
    }
    by = {r.field: r.outcome for r in score(_reading(), expected)}
    assert by == {"PRICE": AGREE, "PAYMENT_TERMS": AGREE, "RETENTION": AGREE, "CONTRACT_REFERENCE": AGREE,
                  "LATE_INTEREST": AGREE, "EARLY_PAYMENT": ABSTAINED, "INVOICING": AGREE, "REQUIRED_DOCUMENT": AGREE}
    wrong = {r.field: r.outcome for r in score(_reading(), {"PAYMENT_TERMS": {"days": 60, "basis": "INVOICE"},
                                                            "PRICE": None})}
    assert wrong == {"PAYMENT_TERMS": WRONG, "PRICE": WRONG}


def test_the_report_states_its_numbers_and_the_unsupported_clauses():
    r = ContractResult(id="HO-C01", compiler="rules-v1", status="COMPILED",
                       fields=score(_reading(), {"PRICE": {"amount_fen": 12_000_000}, "LATE_INTEREST": {"rate_bp": 600}}),
                       unsupported=["price review every quarter by the copper index"])
    text = report([r], pending=False)
    assert "1 contract(s), 2 labelled fields: **1 agree, 1 left blank, 0 wrong**" in text
    assert "not in the schema (by design, shown nowhere): price review" in text


def test_the_held_out_set_is_pending_and_the_report_quotes_no_figure():
    folder = Path(__file__).resolve().parents[4] / "fixtures" / "contracts_heldout"
    labels = yaml.safe_load((folder / "labels.yaml").read_text(encoding="utf-8"))
    assert labels["contracts"] == []
    text = report([], pending=True)
    assert "pending" in text and "%" not in text and "agree" not in text
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert "from acceptance" in readme and "retention" in readme and "cannot carry" in readme
