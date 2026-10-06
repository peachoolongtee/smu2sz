"""`in_words`: invoice ids inside a server sentence become business words, and only where they stand as whole tokens."""

from __future__ import annotations

import pytest

from app.api.presentation import in_words
from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState

BUYER = "Foshan Home Retail Co."


@pytest.fixture(scope="module")
def golden() -> FinancialState:
    return load_scenario()[0]


def only(state: FinancialState, *, issued: bool) -> FinancialState:
    """The golden books with a single invoice of the buyer: the issued one, or the recurring one (which then never repeats)."""
    if issued:
        return state.model_copy(update={"recurring_invoices": []})
    ri = state.recurring_invoices[0].model_copy(update={"every_days": 0})
    return state.model_copy(update={"receivables": [], "recurring_invoices": [ri]})


def test_an_issued_invoice_id_becomes_the_invoice_to_the_buyer(golden: FinancialState):
    state = only(golden, issued=True)
    assert in_words(state, "Advance on RCV-A, repaid day 30.") == f"Advance on the ¥420,000.00 invoice to {BUYER}, repaid day 30."
    assert in_words(state, "RCV-A") == f"the ¥420,000.00 invoice to {BUYER}"


def test_a_recurring_invoice_id_becomes_the_invoice_to_the_buyer(golden: FinancialState):
    state = only(golden, issued=False)
    assert in_words(state, "Advance on RI:BUYER-1:2.") == f"Advance on the ¥420,000.00 invoice to {BUYER}."


def test_two_invoices_of_the_same_buyer_and_face_are_told_apart_by_their_due_day(golden: FinancialState):
    out = in_words(golden, "Finance ¥80,000.00 on RI:BUYER-1:32 and ¥120,000.00 on RI:BUYER-1:2, then RCV-A.")
    assert out == (f"Finance ¥80,000.00 on the ¥420,000.00 invoice to {BUYER} due day 77 and ¥120,000.00 on the "
                   f"¥420,000.00 invoice to {BUYER} due day 47, then the ¥420,000.00 invoice to {BUYER} due day 32.")
    assert "RI:" not in out and "RCV-A" not in out


def test_operation_hash_and_unknown_ids_are_left_alone(golden: FinancialState):
    for text in ("alert:RI:BUYER-1:2:plan:0", "alert:9f2c:v3:plan:1", "OFF-1234", "op-RCV-A-1", "RCV-AB", "RI:BUYER-9:2",
                 "RI:BUYER-1:2:plan:0", "sha 3f8aRCV-A"):
        assert in_words(golden, text) == text
    assert in_words(golden, "Run alert:RI:BUYER-1:2:plan:0 for RCV-A").startswith("Run alert:RI:BUYER-1:2:plan:0 for the ")
    assert in_words(golden, "Drawn on BANK-1 for BUYER-1") == f"Drawn on Main bank for {BUYER}"
