"""ADR-0006 section 4: partial settlement and commitment fulfilment on ReceivePayment."""

from __future__ import annotations

from typing import Any

from app.alerts import MatchStatus, reconcile
from app.books import current_books
from app.clock import advance as advance_clock
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    Commitment,
    CommitmentStatus,
    Mode,
    OperationStatus,
    ReceivePayment,
    SubmitInvoiceForFinancing,
)
from app.financial import project
from app.operations.charges import finance_invoice_charges
from tests.operations.builders import Clock, early_pay, op, seed_offer

FACE = 42_000_000  # RCV-A, due day 32
PORTION = 21_190_000  # Counter A: ¥211,900 of RCV-A ...
EARLY = 21_009_885  # ... at 0.85%: 21_190_000 - post(0.0085 * 21_190_000) = 21_190_000 - 180_115
RESIDUAL = FACE - PORTION  # 20_810_000
DUE = 32


def receipt(ex: Any, clock: Clock, amount: int, rid: str = "RCV-A", **kw: Any) -> Any:
    return ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id=rid, amount_fen=amount, **kw))


def rcv(store: Any, rid: str = "RCV-A") -> Any:
    return next(r for r in store.get_state().receivables if r.id == rid)


def cash(store: Any) -> int:
    return store.get_state().cash_fen


def counter_a(store: Any, ex: Any, clock: Clock, offer_id: str = "OFF-A") -> Commitment:
    """Counter A of the EX01 flow, accepted: 0.85% on ¥211,900 of RCV-A, paid on day 2."""
    ob = early_pay("OB-A").model_copy(update={
        "effective_day": 2, "base": early_pay().base.model_copy(update={"kind": BaseKind.INVOICE, "amount_fen": PORTION})})
    c = seed_offer(store, ex, offer_id, obligations=[ob], value_fen=0)
    accepted = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version,
                             terms_hash=c.terms_hash, nonce=c.nonce))
    assert accepted.status == OperationStatus.EXECUTED
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    return c


# ---------------------------------------------------------------- 1, 5, 6, 7, 8: Golden Option A


def test_golden_option_a_fulfils_the_commitment_and_leaves_the_residual(ex: Any, store: Any, clock: Clock) -> None:
    c = counter_a(store, ex, clock)
    clock.day = 2
    before = cash(store)
    feed = op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=EARLY)
    first = ex.execute(feed)
    assert first.status == OperationStatus.EXECUTED, first.message
    assert first.message == (f"Received ¥210,098.85 on RCV-A (settles ¥211,900.00 at the agreed 0.85% early-payment "
                             f"discount; ¥208,100.00 still due on day {DUE})")
    r = rcv(store)
    assert (r.settled_fen, r.status, r.outstanding_fen) == (PORTION, "OPEN", RESIDUAL)
    assert store.get_commitment(c.id).status == CommitmentStatus.FULFILLED
    assert cash(store) == before + EARLY

    # 5. the same idempotency key is a DUPLICATE and changes nothing
    version = store.get_state().state_version
    dup = ex.execute(feed)
    assert dup.status == OperationStatus.DUPLICATE
    assert rcv(store).settled_fen == PORTION and cash(store) == before + EARLY
    assert store.get_state().state_version == version

    # 6. the books: the FULFILLED commitment is not live, nothing lapsed, one receipt of the residual
    commitments = store.commitments()
    books = current_books(store.get_state(), commitments)
    assert books.obligations == () and books.lapsed == ()
    traj = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, 40)
    receipts = [(d.day, e.amount_fen) for d in traj.days for e in d.events if e.ref == "RCV-A"]
    assert receipts == [(DUE, RESIDUAL)]

    # 7. a fresh early-pay commitment for the residual is accepted: FULFILLED does not block exclusivity
    ob = early_pay("OB-RES").model_copy(update={
        "effective_day": 3, "base": early_pay().base.model_copy(update={"amount_fen": RESIDUAL})})
    c2 = seed_offer(store, ex, "OFF-RES", obligations=[ob], value_fen=0, expires_day=10)
    clock.day = 3
    again = ex.execute(op(AcceptOffer, clock, offer_id=c2.offer_id, offer_version=c2.offer_version,
                          terms_hash=c2.terms_hash, nonce=c2.nonce))
    assert again.status == OperationStatus.EXECUTED, again.message
    assert store.get_commitment(c2.id).status == CommitmentStatus.ACTIVE
    assert store.get_commitment(c.id).status == CommitmentStatus.FULFILLED

    # 1 (cont.) the residual arrives in full on the due day (the second commitment, unpaid, stays ACTIVE)
    clock.day = DUE
    before = cash(store)
    second = receipt(ex, clock, RESIDUAL)
    assert second.status == OperationStatus.EXECUTED, second.message
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE, "SETTLED")
    assert cash(store) == before + RESIDUAL
    third = receipt(ex, clock, 1)
    assert third.status == OperationStatus.REFUSED and "nothing is owed" in third.message
    assert rcv(store).settled_fen == FACE

    # 8.
    assert store.verify_chain()


def test_accepted_commitment_goes_through_active_to_fulfilled(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, "OFF-ACC", value_fen=0)
    store.put_commitment(c.model_copy(update={"status": CommitmentStatus.ACCEPTED}))
    clock.day = 1
    r = receipt(ex, clock, 42_000_000 - 357_000)  # RCV-A full face less 0.85% (post(0.0085 * 42_000_000) = 357_000)
    assert r.status == OperationStatus.EXECUTED, r.message
    assert store.get_commitment(c.id).status == CommitmentStatus.FULFILLED
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE, "SETTLED")
    assert store.verify_chain()


# ---------------------------------------------------------------- 2: no commitment


def test_partial_then_rest_settles(ex: Any, store: Any, clock: Clock) -> None:
    before = cash(store)
    half = receipt(ex, clock, FACE // 2)
    assert half.status == OperationStatus.EXECUTED
    assert half.message == f"Received ¥210,000.00 on RCV-A (¥210,000.00 still due on day {DUE})"
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE // 2, "OPEN")
    assert cash(store) == before + FACE // 2

    over = receipt(ex, clock, FACE // 2 + 1)
    assert over.status == OperationStatus.REFUSED
    assert "¥210,000.01" in over.message and "¥210,000.00 outstanding" in over.message
    assert rcv(store).settled_fen == FACE // 2 and cash(store) == before + FACE // 2

    rest = receipt(ex, clock, FACE // 2)
    assert rest.status == OperationStatus.EXECUTED and rest.message == "Received ¥210,000.00 on RCV-A"
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE, "SETTLED")
    assert cash(store) == before + FACE
    assert store.verify_chain()


def test_full_receipt_in_one_go_still_settles(ex: Any, store: Any, clock: Clock) -> None:
    before = cash(store)
    assert receipt(ex, clock, FACE).status == OperationStatus.EXECUTED
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE, "SETTLED")
    assert cash(store) == before + FACE
    assert receipt(ex, clock, 1).status == OperationStatus.REFUSED


def test_receipt_above_face_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    r = receipt(ex, clock, FACE + 1)
    assert r.status == OperationStatus.REFUSED and rcv(store).settled_fen == 0 and rcv(store).status == "OPEN"


# ---------------------------------------------------------------- 3: a different amount is a plain partial


def test_one_fen_off_the_agreed_amount_is_a_plain_partial_payment(ex: Any, store: Any, clock: Clock) -> None:
    c = counter_a(store, ex, clock)
    clock.day = 2
    before = cash(store)
    r = receipt(ex, clock, EARLY - 1)
    assert r.status == OperationStatus.EXECUTED
    assert "settles" not in r.message and "early-payment" not in r.message
    assert (rcv(store).settled_fen, rcv(store).status) == (EARLY - 1, "OPEN")
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    assert cash(store) == before + EARLY - 1
    assert store.verify_chain()


def test_agreed_amount_that_would_settle_more_than_is_outstanding_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    c = counter_a(store, ex, clock)
    clock.day = 2
    assert receipt(ex, clock, FACE - PORTION + 1_000_000).status == OperationStatus.EXECUTED  # outstanding < PORTION
    before = cash(store)
    r = receipt(ex, clock, EARLY)
    assert r.status == OperationStatus.REFUSED and "outstanding" in r.message
    assert cash(store) == before and store.get_commitment(c.id).status == CommitmentStatus.ACTIVE


# ---------------------------------------------------------------- 4: financed receivable


def test_financed_receivable_repays_the_advance_once(ex: Any, store: Any, clock: Clock) -> None:
    """A partial receipt on a financed invoice goes to the lender and never takes the owner's cash (red-team p03);
    the receipt that clears the advance pays its charges once, from landing to clearing."""
    advance = 21_000_000  # ¥210,000 of RCV-A's ¥420,000
    fin = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                        advance_fen=advance))
    assert fin.status == OperationStatus.EXECUTED, fin.message
    assert rcv(store).status == "FINANCED"
    advance_clock(store, 4)  # the advance lands on day 3 (ADR-0010)
    fac0 = next(f for f in store.get_state().facilities if f.id == "FAC-IF")
    interest, fee, _ = finance_invoice_charges(fac0, advance, DUE - 3)

    clock.day = 10
    before = cash(store)
    part = receipt(ex, clock, 10_000_000)
    assert part.status == OperationStatus.EXECUTED, part.message
    assert "still outstanding" in part.message and "repaid advance" not in part.message
    assert f"¥{(FACE - 10_000_000) / 100:,.2f} still due on day {DUE}" in part.message
    fac1 = next(f for f in store.get_state().facilities if f.id == "FAC-IF")
    assert fac1.drawn_fen == fac0.drawn_fen - 10_000_000
    assert cash(store) == before  # all of it went to the lender
    assert (rcv(store).settled_fen, rcv(store).status, rcv(store).advance_fen) == (10_000_000, "FINANCED",
                                                                                 advance - 10_000_000)

    clock.day = DUE
    before = cash(store)
    rest = receipt(ex, clock, FACE - 10_000_000)
    assert rest.status == OperationStatus.EXECUTED and "repaid advance ¥110,000.00" in rest.message
    assert (rcv(store).settled_fen, rcv(store).status) == (FACE, "SETTLED")
    assert cash(store) == before + FACE - 10_000_000 - (advance - 10_000_000) - interest - fee
    assert next(f for f in store.get_state().facilities if f.id == "FAC-IF").drawn_fen == 0
    assert store.get_state().lots == []
    assert store.verify_chain()


# ---------------------------------------------------------------- reconciliation follows the same semantics


def test_reconciliation_matches_the_agreed_amount_and_reports_partials_with_the_residual(
    ex: Any, store: Any, clock: Clock
) -> None:
    counter_a(store, ex, clock)
    clock.day = 2
    assert receipt(ex, clock, EARLY).status == OperationStatus.EXECUTED
    clock.day = 20
    assert receipt(ex, clock, 5_000_000).status == OperationStatus.EXECUTED  # a partial of the residual
    rep = reconcile(store, day=20)
    agreed, partial = rep.receipts
    assert agreed.status == MatchStatus.MATCHED and not agreed.flagged and agreed.commitment_id is not None
    assert agreed.expected_fen == EARLY and agreed.difference_fen == 0
    assert partial.status == MatchStatus.SHORT_PAYMENT and partial.flagged and partial.commitment_id is None
    assert partial.expected_fen == RESIDUAL and partial.difference_fen == 5_000_000 - RESIDUAL
    assert "partial payment" in partial.detail and "¥158,100.00 of RCV-A still due" in partial.detail
    [out] = [o for o in rep.outstanding if o.receivable_id == "RCV-A"]
    assert out.face_fen == RESIDUAL - 5_000_000 and out.status == "OPEN"
    assert rep.chain_valid
