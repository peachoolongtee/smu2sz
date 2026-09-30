"""Simulated-bank effects: exact interest, FIFO repayment, invoice financing and settlement."""

from __future__ import annotations

from typing import Any

from app.domain.fixtures import golden_values
from app.domain.models import (
    Actor,
    DrawFacility,
    FundingAction,
    FundingActionKind,
    LedgerEventKind,
    Mode,
    OperationStatus,
    ReceivePayment,
    RepayFacility,
    SubmitInvoiceForFinancing,
    ViolationCode,
)
from app.domain.money import bp, post, simple_interest
from app.financial import project
from tests.operations.builders import Clock, op


def facility(store: Any, fid: str) -> Any:
    return next(f for f in store.get_state().facilities if f.id == fid)


def receivable(store: Any, rid: str) -> Any:
    return next(r for r in store.get_state().receivables if r.id == rid)


def test_repay_interest_matches_money_arithmetic_exactly(ex: Any, store: Any, clock: Clock) -> None:
    start = store.get_state().cash_fen
    assert ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=15_000_000)).status == "EXECUTED"
    clock.day = 32
    r = ex.execute(op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=15_000_000))
    assert r.status == OperationStatus.EXECUTED
    assert golden_values()["line_interest_150k_32d"] == 84164
    assert store.get_state().cash_fen == start - 84164
    assert facility(store, "FAC-LINE").drawn_fen == 0
    assert "¥841.64" in r.message


def test_repayment_is_fifo_over_draws(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=10_000_000))
    clock.day = 10
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=5_000_000))
    clock.day = 20
    before = store.get_state().cash_fen
    ex.execute(op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=12_000_000))
    rate = bp(640)
    first = post(simple_interest(10_000_000, rate, 20)) + post(simple_interest(2_000_000, rate, 10))
    assert store.get_state().cash_fen == before - 12_000_000 - first
    clock.day = 30
    before = store.get_state().cash_fen
    ex.execute(op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=3_000_000))
    assert store.get_state().cash_fen == before - 3_000_000 - post(simple_interest(3_000_000, rate, 20))


def test_repay_more_than_drawn_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000))
    before = store.get_state()
    r = ex.execute(op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_001))
    assert r.status == OperationStatus.REFUSED and store.get_state() == before
    assert [v.code for v in r.violations] == [ViolationCode.PRECONDITION_FAILED]


def test_invoice_financing_and_settlement_match_the_financial_engine(ex: Any, store: Any, clock: Clock) -> None:
    state0 = store.get_state()
    advance = 33_600_000  # 80% of RCV-A's ¥420,000 face
    # Reference: the engine requests on day 0 and the cash lands on day 3 (lead time); due day 32.
    traj = project(state0, [], [FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF", day=0,
                                              amount_fen=advance, receivable_id="RCV-A")], Mode.CONSERVATIVE, 40)
    day32 = next(d for d in traj.days if d.day == 32).events
    charges = {e.kind: -e.amount_fen for e in day32 if e.ref == "FAC-IF" and e.kind in
               (LedgerEventKind.INTEREST, LedgerEventKind.FEE)}

    clock.day = 3  # the simulated bank credits the advance when the executor runs it
    too_much = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                             advance_fen=advance + 1))
    assert too_much.status == OperationStatus.REFUSED
    r = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                      advance_fen=advance))
    assert r.status == OperationStatus.EXECUTED
    assert store.get_state().cash_fen == state0.cash_fen + advance
    assert receivable(store, "RCV-A").status == "FINANCED"
    assert facility(store, "FAC-IF").drawn_fen == advance
    again = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                          advance_fen=1_000_000))
    assert again.status == OperationStatus.REFUSED

    clock.day = 32
    before = store.get_state().cash_fen
    paid = ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=42_000_000))
    assert paid.status == OperationStatus.EXECUTED
    expected = 42_000_000 - advance - charges[LedgerEventKind.INTEREST] - charges[LedgerEventKind.FEE]
    assert store.get_state().cash_fen - before == expected
    assert receivable(store, "RCV-A").status == "SETTLED"
    assert facility(store, "FAC-IF").drawn_fen == 0
    assert ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=1)).status == "REFUSED"


def test_financing_bills_whole_periods(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                  advance_fen=10_000_000))
    clock.day = 31  # 31 days outstanding -> two 30-day periods
    before = store.get_state().cash_fen
    ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=42_000_000))
    interest = post(simple_interest(10_000_000, bp(780), 60))
    fee = post(bp(25) * 10_000_000 * 2)
    assert store.get_state().cash_fen - before == 42_000_000 - 10_000_000 - interest - fee


def test_financing_needs_an_open_confirmed_buyer_receivable(ex: Any, store: Any, clock: Clock) -> None:
    state = store.get_state()
    rcv = state.receivables[0]
    extra = [
        rcv.model_copy(update={"id": "RCV-U", "confirmed": False}),
        rcv.model_copy(update={"id": "RCV-L", "counterparty_id": "BANK-1"}),
        rcv.model_copy(update={"id": "RCV-S", "status": "SETTLED"}),
    ]
    store.put_state(state.model_copy(update={"receivables": [*state.receivables, *extra]}))
    expected = {
        "RCV-U": ViolationCode.PRECONDITION_FAILED,
        "RCV-L": ViolationCode.UNKNOWN_COUNTERPARTY,
        "RCV-S": ViolationCode.PRECONDITION_FAILED,
        "RCV-NOPE": ViolationCode.PRECONDITION_FAILED,
    }
    for rid, code in expected.items():
        ex.reset_circuit("PLATFORM-1", Actor.OWNER)  # four refusals in a row would otherwise open it
        r = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id=rid,
                          advance_fen=1_000_000))
        assert r.status == OperationStatus.REFUSED and [v.code for v in r.violations] == [code], rid
    wrong_facility = ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-LINE", receivable_id="RCV-A",
                                   advance_fen=1_000_000))
    assert [v.code for v in wrong_facility.violations] == [ViolationCode.PRECONDITION_FAILED]


def test_receive_payment_on_open_receivable(ex: Any, store: Any, clock: Clock) -> None:
    before = store.get_state().cash_fen
    r = ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=42_000_000))
    assert r.status == OperationStatus.EXECUTED
    assert store.get_state().cash_fen == before + 42_000_000
    assert receivable(store, "RCV-A").status == "SETTLED"
    over = ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=1))
    assert over.status == OperationStatus.REFUSED
