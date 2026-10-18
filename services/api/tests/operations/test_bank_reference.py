"""Review gap G6: one bank event books once, whatever idempotency key it arrives under (backlog R03)."""

from __future__ import annotations

from app.alerts import MatchStatus, reconcile
from app.domain.models import Actor, OperationStatus, ReceivePayment, SecurityEventKind, ViolationCode
from tests.alerts.test_reconcile import _setup


def _pay(ex, rid: str, amount: int, n: int, ref: str | None = None):
    return ex.execute(ReceivePayment(op_id=f"OP-BR-{n}", idempotency_key=f"br-{n}", mandate_version=1,
                                     requested_by=Actor.SYSTEM, day=0, receivable_id=rid, amount_fen=amount,
                                     bank_reference=ref))


def test_the_same_reference_under_a_new_key_is_refused_and_cash_is_counted_once():
    store, ex = _setup()
    first = _pay(ex, "RCV-B", 10_000_000, 1, "BANK-7")
    assert first.status == OperationStatus.EXECUTED
    cash = store.get_state().cash_fen
    second = _pay(ex, "RCV-B", 10_000_000, 2, "BANK-7")
    assert second.status == OperationStatus.REFUSED
    [v] = second.violations
    assert v.code == ViolationCode.PRECONDITION_FAILED
    assert "Duplicate bank event" in v.message and "BANK-7" in v.message and "OP-BR-1" in v.message
    state = store.get_state()
    assert state.cash_fen == cash  # counted once
    assert next(r for r in state.receivables if r.id == "RCV-B").settled_fen == 10_000_000
    assert not [e for e in store.security_events() if e.kind == SecurityEventKind.REPLAY]  # a plain duplicate is no attack


def test_the_same_reference_with_a_different_amount_is_a_conflicting_event_and_a_replay_event():
    store, ex = _setup()
    _pay(ex, "RCV-B", 10_000_000, 1, "BANK-8")
    cash = store.get_state().cash_fen
    second = _pay(ex, "RCV-B", 12_000_000, 2, "BANK-8")
    assert second.status == OperationStatus.REFUSED
    assert second.violations[0].code == ViolationCode.REPLAY
    assert "Conflicting bank event" in second.violations[0].message and "OP-BR-1" in second.violations[0].message
    assert store.get_state().cash_fen == cash
    [ev] = [e for e in store.security_events() if e.kind == SecurityEventKind.REPLAY]
    assert "BANK-8" in ev.detail


def test_without_a_reference_behaviour_is_unchanged():
    _store, ex = _setup()
    assert _pay(ex, "RCV-B", 5_000_000, 1).status == OperationStatus.EXECUTED
    assert _pay(ex, "RCV-B", 5_000_000, 2).status == OperationStatus.EXECUTED  # no way to tell it from a second payment
    assert _pay(ex, "RCV-B", 5_000_000, 3, "BANK-9").status == OperationStatus.EXECUTED  # a reference nobody used yet


def test_a_reference_is_per_receivable_and_a_refused_receipt_does_not_burn_it():
    _store, ex = _setup()
    assert _pay(ex, "RCV-A", 10_000_000, 1, "BANK-10").status == OperationStatus.EXECUTED
    assert _pay(ex, "RCV-B", 10_000_000, 2, "BANK-10").status == OperationStatus.EXECUTED  # another receivable
    over = _pay(ex, "RCV-B", 99_000_000_000, 3, "BANK-11")  # refused: more than is owed
    assert over.status == OperationStatus.REFUSED
    assert _pay(ex, "RCV-B", 5_000_000, 4, "BANK-11").status == OperationStatus.EXECUTED  # the reference is still free


def test_the_same_key_is_still_an_idempotent_replay():
    _store, ex = _setup()
    _pay(ex, "RCV-B", 10_000_000, 1, "BANK-12")
    again = _pay(ex, "RCV-B", 10_000_000, 1, "BANK-12")
    assert again.status == OperationStatus.DUPLICATE


def test_reconciliation_shows_the_reference_on_each_receipt():
    store, ex = _setup()
    _pay(ex, "RCV-B", 10_000_000, 1, "BANK-13")
    _pay(ex, "RCV-B", 10_000_000, 2, "BANK-13")  # refused: listed as unmatched, with the reference
    _pay(ex, "RCV-A", 42_000_000, 3)
    rep = reconcile(store, day=0)
    by_op = {m.op_id: m for m in rep.receipts}
    assert by_op["OP-BR-1"].bank_reference == "BANK-13"
    assert by_op["OP-BR-2"].bank_reference == "BANK-13" and by_op["OP-BR-2"].status == MatchStatus.UNMATCHED
    assert by_op["OP-BR-3"].bank_reference is None
