"""The reconciliation report compares receipts with what live commitments promised (tracker C3).

The early-pay face, rate and day are read from the commitment's own obligation, never hard-coded."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.alerts import PromiseStatus, reconcile
from app.api.alerts import router as alerts_router
from app.api.auth import DEMO_OWNER_TOKEN
from app.api.runtime import Runtime, set_runtime
from app.clock import advance
from app.config import get_settings
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    Commitment,
    CommitmentStatus,
    OperationStatus,
    ReceivePayment,
)
from app.domain.money import bp, fmt_yuan, post
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.operations.builders import Clock, early_pay, make_executor, op, seed_offer, seeded_store

PORTION = 12_345_678  # the invoice portion this test's commitment covers (RCV-A's face is larger)
RATE_BP = 85
DAY = 2


@pytest.fixture
def store() -> Any:
    return seeded_store("memory")


@pytest.fixture
def clock() -> Clock:
    return Clock(0)


@pytest.fixture
def ex(store: Any, clock: Clock) -> Any:
    return make_executor(store, clock)


def accepted(store: Any, ex: Any, clock: Clock, offer_id: str = "OFF-P") -> Commitment:
    """An early-pay commitment on RCV-A, accepted through the executor with the clock at day 0."""
    ob = early_pay("OB-P", rate_bp=RATE_BP).model_copy(update={
        "effective_day": DAY, "base": early_pay().base.model_copy(update={"kind": BaseKind.INVOICE, "amount_fen": PORTION})})
    c = seed_offer(store, ex, offer_id, obligations=[ob], value_fen=0)
    res = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version,
                        terms_hash=c.terms_hash, nonce=c.nonce))
    assert res.status == OperationStatus.EXECUTED, res.message
    return store.get_commitment(c.id)


def terms(c: Commitment) -> tuple[int, int, int, int | None]:
    """(P, d, P - d, effective day) read from the commitment's obligation."""
    [o] = c.obligations
    assert o.base.amount_fen is not None and o.rate_bp is not None
    p = o.base.amount_fen
    d = post(bp(o.rate_bp) * p)
    return p, d, p - d, o.effective_day


def pay(ex: Any, clock: Clock, amount: int, rid: str = "RCV-A") -> Any:
    return ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id=rid, amount_fen=amount))


def receivable(store: Any, rid: str = "RCV-A") -> Any:
    return next(r for r in store.get_state().receivables if r.id == rid)


def test_an_accepted_early_payment_is_awaited(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    p, d, expected, day = terms(c)
    rep = reconcile(store, day=0)
    [row] = rep.promised
    assert row.status == PromiseStatus.AWAITED and row.receipt_seq is None
    assert (row.commitment_id, row.obligation_id, row.receivable_id) == (c.id, "OB-P", "RCV-A")
    assert row.counterparty_id == c.counterparty_id
    assert (row.face_fen, row.discount_fen, row.expected_fen, row.promised_day) == (p, d, expected, day)
    assert fmt_yuan(p) in row.formula and fmt_yuan(d) in row.formula and fmt_yuan(expected) in row.formula
    assert rep.lapsed_promises == 0 and rep.receipts == []


def test_the_agreed_amount_on_the_promised_day_is_received(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    _, _, expected, day = terms(c)
    clock.day = day or 0
    assert pay(ex, clock, expected).status == OperationStatus.EXECUTED
    rep = reconcile(store, day=clock.day)
    [row] = rep.promised
    [receipt] = rep.receipts
    assert row.status == PromiseStatus.RECEIVED and row.receipt_seq == receipt.seq
    assert rep.lapsed_promises == 0


def test_a_missing_early_payment_is_reported_as_lapsed(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    _, _, expected, day = terms(c)
    assert day is not None
    advance(store, day + 1)
    clock.day = day + 1
    rep = reconcile(store, day=day + 1)
    [row] = rep.promised
    assert row.status == PromiseStatus.LAPSED and row.receipt_seq is None and rep.lapsed_promises == 1
    assert f"day {day}" in row.detail and "did not arrive" in row.detail
    assert f"day {receivable(store).due_day}" in row.detail
    assert fmt_yuan(receivable(store).outstanding_fen) in row.detail and fmt_yuan(expected) in row.detail
    assert rep.flagged == 0  # flagged still counts receipts only


def test_a_late_discounted_receipt_is_a_plain_receipt_not_the_agreed_payment(store: Any, ex: Any,
                                                                             clock: Clock) -> None:
    """Red team d, F6: the executor books P − d after the promised day as a plain receipt (the difference stays due);
    reconciliation must not call it the agreed early payment or settle the whole portion in its replay."""
    c = accepted(store, ex, clock)
    _p, d, expected, day = terms(c)
    assert day is not None
    advance(store, day + 1)
    clock.day = day + 1
    assert pay(ex, clock, expected).status == OperationStatus.EXECUTED
    assert receivable(store).settled_fen == expected  # booked as what it is
    ended = store.get_commitment(c.id)
    assert ended.status == CommitmentStatus.EXPIRED and ended.lapsed_obligations == ["OB-P"]  # F3
    assert pay(ex, clock, d).status == OperationStatus.EXECUTED  # the buyer pays the difference
    rep = reconcile(store, day=clock.day)
    [late, rest] = rep.receipts
    assert late.status.value == "DISCOUNT_IGNORED" and late.expected_fen == receivable(store).face_fen
    # replayed on what was booked: face − (P − d) outstanding, not face − P as if the portion had been settled
    assert rest.expected_fen == receivable(store).face_fen - expected
    assert rest.status.value == "SHORT_PAYMENT"  # the portion covers part of RCV-A: the rest of the face is still due
    [row] = rep.promised
    assert row.status == PromiseStatus.LAPSED and row.receipt_seq is None


def test_the_day_itself_is_not_yet_lapsed(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    day = terms(c)[3]
    assert day is not None
    advance(store, day)
    [row] = reconcile(store, day=day).promised
    assert row.status == PromiseStatus.AWAITED


def test_full_face_paid_instead_is_settled_otherwise(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    clock.day = terms(c)[3] or 0
    assert pay(ex, clock, receivable(store).face_fen).status == OperationStatus.EXECUTED
    rep = reconcile(store, day=clock.day)
    [row] = rep.promised
    assert row.status == PromiseStatus.SETTLED_OTHERWISE and row.receipt_seq is None
    assert rep.lapsed_promises == 0


@pytest.mark.parametrize("status", [CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED, CommitmentStatus.PROPOSED])
def test_revoked_expired_or_proposed_commitments_contribute_no_row(store: Any, ex: Any, clock: Clock,
                                                                   status: CommitmentStatus) -> None:
    c = accepted(store, ex, clock)
    store.put_commitment(c.model_copy(update={"status": status}))
    rep = reconcile(store, day=0)
    assert rep.promised == [] and rep.lapsed_promises == 0


def test_rows_are_ordered_by_promised_day_then_ids(store: Any, ex: Any, clock: Clock) -> None:
    c = accepted(store, ex, clock)
    [o] = c.obligations
    later = c.model_copy(update={"id": "C-A-LATER", "obligations": [o.model_copy(update={
        "id": "OB-A", "effective_day": (o.effective_day or 0) + 3})]})
    undated = c.model_copy(update={"id": "C-0-UNDATED", "obligations": [o.model_copy(update={
        "id": "OB-Z", "effective_day": None})]})
    store.put_commitment(undated)
    store.put_commitment(later)
    assert [(p.commitment_id, p.promised_day) for p in reconcile(store, day=0).promised] == [
        (c.id, o.effective_day), ("C-A-LATER", (o.effective_day or 0) + 3), ("C-0-UNDATED", None)]


def test_reconciliation_endpoint_returns_the_promised_list() -> None:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    try:
        ex = make_executor(rt.store, Clock(0))
        c = accepted(rt.store, ex, Clock(0))
        p, d, expected, day = terms(c)
        app = FastAPI()
        app.include_router(alerts_router)
        client = TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN})
        rep = client.get("/reconciliation").json()["reconciliation"]
        [row] = rep["promised"]
        assert row["status"] == "AWAITED" and rep["lapsed_promises"] == 0
        assert row["expected_fen"] == expected and row["expected_display"] == fmt_yuan(expected)
        assert row["face_display"] == fmt_yuan(p) and row["discount_display"] == fmt_yuan(d)
        rt.advance_to((day or 0) + 1)
        rep = client.get("/reconciliation").json()["reconciliation"]
        assert [r["status"] for r in rep["promised"]] == ["LAPSED"] and rep["lapsed_promises"] == 1
    finally:
        set_runtime(None)
