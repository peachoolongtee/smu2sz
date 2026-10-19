"""Real compiled dated offers use existing receipt arithmetic on both local stores."""
import pytest

from app.compiler import Compiler
from app.compiler.rules import RulesBackend
from app.domain.models import AcceptOffer, Actor, ReceivePayment, SourceDocument
from app.mandate import demo_owner_public_key_hex
from app.verifier import evaluate
from tests.operations.builders import op


@pytest.mark.parametrize("receipt_day", [1, 2])
def test_promise_never_posts_cash_and_only_timely_receipt_earns_discount(store, ex, clock, receipt_day):
    before = store.get_state()
    doc = SourceDocument(doc_id="payment-promise", channel="chat", sender_id="BUYER-1", received_day=0,
                         text="We will pay invoice RCV-A (¥420,000) tomorrow, 0.5% off.")
    offer = Compiler([RulesBackend()]).compile_offer([doc], "BUYER-1")
    result = evaluate(offer, before, store.get_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex())
    assert result.verdict.outcome.value == "ACCEPT"
    store.put_offer(offer)
    store.put_verdict(result.verdict)
    restored = store.get_offer(offer.offer_id)
    assert restored.obligations[0].payment_timing == offer.obligations[0].payment_timing
    c = ex.propose_commitment(result.verdict.id, expires_day=7)
    accepted = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version,
                              terms_hash=c.terms_hash, nonce=c.nonce, source_verdict_id=result.verdict.id))
    assert accepted.status.value == "EXECUTED", accepted
    promised = store.get_state()
    assert promised.cash_fen == before.cash_fen
    assert promised.receivables == before.receivables
    assert store.get_commitment(c.id).obligations[0].effective_day == 1
    clock.day = receipt_day
    paid = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=41_790_000))
    assert paid.status.value == "EXECUTED", paid
    after = store.get_state()
    assert after.cash_fen == promised.cash_fen + 41_790_000
    invoice = next(r for r in after.receivables if r.id == "RCV-A")
    if receipt_day == 1:
        assert invoice.status == "SETTLED" and invoice.settled_fen == 42_000_000
        assert store.get_commitment(c.id).status.value == "FULFILLED"
    else:
        assert invoice.status == "OPEN" and invoice.outstanding_fen == 210_000
    assert store.verify_chain()
