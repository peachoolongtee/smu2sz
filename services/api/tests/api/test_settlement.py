"""Inbound clocks are server-owned and timing evidence survives owner reads."""
import pytest

from app.api.runtime import get_runtime


@pytest.mark.parametrize("forged_day", [-900, 4, 99999])
def test_buyer_cannot_choose_reference_day(client, forged_day):
    doc = {"doc_id": "forged-day", "channel": "chat", "sender_id": "BUYER-1", "received_day": forged_day,
           "text": "We will pay invoice RCV-A (¥420,000) tomorrow, 0.5% off."}
    r = client.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [doc]},
                    headers={"X-Owner-Token": "", "X-Counterparty-Key": "demo-buyer-1-key"})
    assert r.status_code == 200
    offer = r.json()["offer"]
    timing = offer["obligations"][0]["payment_timing"]
    assert offer["received_day"] == timing["reference_day"] == get_runtime().day == 0
    assert r.json()["documents"][0]["received_day"] == 0
    ev = client.post(f"/offers/{offer['offer_id']}/evaluate", json={})
    assert ev.status_code == 200
    assert ev.json()["bound_obligations"][0]["effective_day"] == 1
    fetched = client.get(f"/offers/{offer['offer_id']}").json()["offer"]
    assert fetched["obligations"][0]["payment_timing"] == timing


def test_owner_words_state_the_condition_and_do_not_claim_receipt(client):
    from app.api.presentation import obligation_sentence
    from app.compiler import Compiler
    from app.compiler.rules import RulesBackend
    from app.domain.models import SourceDocument

    doc = SourceDocument(doc_id="date-words", channel="chat", sender_id="BUYER-1", received_day=0,
                         text="We will pay invoice RCV-A (¥420,000) tomorrow, 0.5% off.")
    offer = Compiler([RulesBackend()]).compile_offer([doc], "BUYER-1")
    ob = offer.obligations[0]
    state = get_runtime().store.get_state()
    en = obligation_sentence(state, ob, 0, "en")
    zh = obligation_sentence(state, ob, 0, "zh")
    assert "only to payment received by" in en and "not yet received" in en
    assert "享受折扣" in zh and "尚未收款" in zh
