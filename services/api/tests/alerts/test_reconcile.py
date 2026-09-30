"""Receipt reconciliation against open receivables and accepted commitments."""

from __future__ import annotations

from app.alerts import MatchStatus, reconcile
from app.domain.models import (
    Actor,
    BaseKind,
    Commitment,
    CommitmentStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    ReceivePayment,
    SourceSpan,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.operations import Executor
from app.persistence import InMemoryLedgerStore
from tests.egress.helpers import state_with_buyer_b


def _setup():
    state, _ = state_with_buyer_b()  # RCV-A ¥420,000 (BUYER-1), RCV-B ¥250,000 (BUYER-2)
    store = InMemoryLedgerStore()
    store.put_state(state)
    store.put_mandate(load_signed_mandate())
    return store, Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=lambda: 0)


def _pay(ex: Executor, rid: str, amount: int, n: int):
    return ex.execute(ReceivePayment(op_id=f"OP-RCV-{n}", idempotency_key=f"rcv-{n}", mandate_version=1,
                                     requested_by=Actor.SYSTEM, day=0, receivable_id=rid, amount_fen=amount))


def _discount_commitment(rate_bp: int = 120) -> Commitment:
    ob = Obligation(id="OB-D", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
                    effective_day=2, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A"),
                    contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
                    spans=[SourceSpan(doc_id="D", start=0, end=4, text="1.2%")], confidence=1.0)
    return Commitment(id="C-DISC", offer_id="OFF-1", offer_version=1, counterparty_id="BUYER-1", verdict_id="V-1",
                      terms_hash="h", obligations=[ob], status=CommitmentStatus.ACTIVE, nonce="n",
                      expires_day=10, mandate_version=1, forward_value_fen=0)


def test_exact_payment_matched_short_payment_flagged_unknown_unmatched():
    store, ex = _setup()
    assert _pay(ex, "RCV-A", 42_000_000, 1).status.value == "EXECUTED"
    assert _pay(ex, "RCV-B", 20_000_000, 2).status.value == "EXECUTED"
    assert _pay(ex, "RCV-ZZZ", 5_000_000, 3).status.value == "REFUSED"
    rep = reconcile(store, day=0)
    by = {m.receivable_id: m for m in rep.receipts}
    assert by["RCV-A"].status == MatchStatus.MATCHED and not by["RCV-A"].flagged
    assert by["RCV-A"].expected_fen == 42_000_000 and by["RCV-A"].difference_fen == 0
    short = by["RCV-B"]
    assert short.status == MatchStatus.SHORT_PAYMENT and short.flagged
    assert short.difference_fen == -5_000_000 and "¥50,000.00" in short.detail
    assert by["RCV-ZZZ"].status == MatchStatus.UNMATCHED and by["RCV-ZZZ"].flagged
    assert (rep.matched, rep.flagged) == (1, 2)
    assert rep.chain_valid and rep.chain_head_hash == store.operations()[-1].entry_hash
    assert by["RCV-A"].entry_hash == store.operations()[0].entry_hash


def test_discounted_payment_under_an_accepted_discount_is_matched():
    store, ex = _setup()
    store.put_commitment(_discount_commitment())
    _pay(ex, "RCV-A", 42_000_000 - 504_000, 1)  # face − 1.2% (¥5,040), inside the window
    [m] = reconcile(store, day=0).receipts
    assert m.status == MatchStatus.MATCHED and m.agreed_discount_fen == 504_000 and m.commitment_id == "C-DISC"


def test_full_face_inside_the_window_ignores_the_accepted_discount():
    store, ex = _setup()
    store.put_commitment(_discount_commitment())
    _pay(ex, "RCV-A", 42_000_000, 1)
    [m] = reconcile(store, day=0).receipts
    assert m.status == MatchStatus.DISCOUNT_IGNORED and m.flagged and "credit" in m.detail


def test_short_payment_below_the_discounted_face():
    store, ex = _setup()
    store.put_commitment(_discount_commitment())
    _pay(ex, "RCV-A", 41_000_000, 1)
    [m] = reconcile(store, day=0).receipts
    assert m.status == MatchStatus.SHORT_PAYMENT and m.difference_fen == 41_000_000 - (42_000_000 - 504_000)


def test_outstanding_receivables_are_listed():
    store, ex = _setup()
    _pay(ex, "RCV-A", 42_000_000, 1)
    rep = reconcile(store, day=70)
    assert [(o.receivable_id, o.past_due) for o in rep.outstanding] == [("RCV-B", True)]
