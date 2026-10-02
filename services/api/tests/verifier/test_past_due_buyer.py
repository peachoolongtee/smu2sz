"""Review gap G7: a buyer with a past-due open invoice cannot be accepted without the owner."""

from __future__ import annotations

import pytest

from app.compiler import compile_offer
from app.domain.fixtures import load_offers, load_scenario
from app.domain.models import Outcome, SourceDocument, Tier
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate
from tests.verifier.conftest import compiled, declared_for

TEXT = "Deduct 0.6% and we'll settle the open ¥420,000 invoice early."  # RCV-A (BUYER-1) is due on day 32


def _verdict(day: int, state=None, sender: str = "BUYER-1"):
    state = state or load_scenario()[0]
    offer = compile_offer([SourceDocument(doc_id="t1", channel="chat", sender_id=sender, received_day=0, text=TEXT)],
                          sender)
    return evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(),
                    day=day).verdict


def test_nothing_is_past_due_before_the_due_day_and_the_offer_is_accepted_as_before():
    for day in (0, 31, 32):  # due day 32 is not yet past due
        v = _verdict(day)
        assert (v.outcome, v.required_tier) == (Outcome.ACCEPT, Tier.TIER_1)
        assert "past-due" not in v.summary


def test_a_buyer_with_a_past_due_invoice_needs_the_owner_and_the_note_names_it():
    v = _verdict(34)
    assert (v.outcome, v.required_tier) == (Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2)
    assert "owner approval needed" in v.summary
    assert "BUYER-1 has a past-due invoice RCV-A" in v.summary and "2 day(s) past due" in v.summary
    assert "¥420,000.00 outstanding" in v.summary
    assert "2 day(s)" in _verdict(34).summary and "3 day(s) past due" in _verdict(35).summary


def test_another_buyers_past_due_invoice_does_not_change_this_buyers_verdict():
    state, _ = load_scenario()
    other = state.model_copy(update={"receivables": [
        r.model_copy(update={"counterparty_id": "BUYER-2"}) for r in state.receivables]})
    # the open invoice now belongs to BUYER-2 and is past due on day 34: BUYER-1 is clean
    offer = compile_offer([SourceDocument(doc_id="t2", channel="chat", sender_id="BUYER-1", received_day=0,
                                          text="Half a percent off next quarter's purchases, up to ¥300,000.")],
                          "BUYER-1")
    base = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(), day=0).verdict
    moved = evaluate(offer, other, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(), day=34).verdict
    assert "past-due" not in moved.summary and base.outcome == moved.outcome


@pytest.mark.parametrize("offer_id", sorted(load_offers()))
def test_no_day_0_golden_verdict_mentions_a_past_due_invoice(offer_id):
    state, _ = load_scenario()
    v = evaluate(compiled(offer_id), state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(),
                 owner_declared=declared_for(offer_id)).verdict
    assert "past-due" not in v.summary
