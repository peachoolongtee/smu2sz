"""Regression tests for the second red team of 3 Oct 2026 (docs/research/redteam-2026-10-03b): F1 to F7.

Each test asserts the stored state (the store's FinancialState, commitments, log and security events), not only
the operation's message. Tests of the projection side of F3 run after `fix/router-admission-agree` merges (it
makes the projection repay an orphaned lot today); they are skipped here with that reason.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.alerts import AlertKind, alerts
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    CommitmentStatus,
    CounterOffer,
    Duration,
    DurationKind,
    FinancialState,
    FundingAction,
    FundingActionKind,
    LedgerEventKind,
    Mode,
    ObligationBase,
    OperationStatus,
    ReceivePayment,
    RejectOffer,
    RepayFacility,
    SecurityEventKind,
    SubmitInvoiceForFinancing,
    ViolationCode,
)
from app.financial import EngineError, finance_invoice_charges, project
from app.financial.concessions import scoped_invoices
from app.financial.invoices import scope_at
from app.financial.lots import apply_receipt, is_fixed_remainder, landing_cash
from app.mandate import load_demo_owner_key, load_signed_mandate, revoke, sign
from app.verifier.bind import early_pay_lead
from tests.books.test_funding_lots import IF, World, check_lots
from tests.operations.builders import Clock, early_pay, extension, make_executor, op, seed_offer, seeded_store

EXECUTED, REFUSED, PENDING, DUPLICATE = (OperationStatus.EXECUTED, OperationStatus.REFUSED,
                                         OperationStatus.PENDING_APPROVAL, OperationStatus.DUPLICATE)
C = Mode.CONSERVATIVE


def codes(result: Any) -> list[ViolationCode]:
    return [v.code for v in result.violations]


def accept(clock: Clock, c: Any) -> AcceptOffer:
    return op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
              nonce=c.nonce)


def next_invoice(oid: str = "OB-T", days_delta: int = 15) -> Any:
    """'+15 days on the next invoice': an unnamed ONE_OFF terms extension."""
    return extension(oid, days_delta).model_copy(update={"duration": Duration(kind=DurationKind.ONE_OFF)})


def accept_as_owner(w: World, offer_id: str, obligations: list[Any], value_fen: int) -> Any:
    """Seed a verified offer, accept it (a lengthening is Tier 2) and let the owner approve it."""
    c = seed_offer(w.store, w.ex, offer_id, obligations=obligations, value_fen=value_fen,
                   expires_day=w.clock.day + 7)
    r = w.ex.execute(accept(w.clock, c))
    if r.status == PENDING:
        r = w.ex.decide(r.approval_id, True, Actor.OWNER)
    return r


def rcv(state: FinancialState, rid: str) -> Any:
    return next(r for r in state.receivables if r.id == rid)


# ================================================================ F1: early pay and financing


def test_f1_financing_is_refused_while_an_early_pay_agreement_names_the_invoice() -> None:
    w = World()
    c = seed_offer(w.store, w.ex, "OFF-EP", obligations=[early_pay(receivable_id="RCV-A").model_copy(
        update={"base": ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A", amount_fen=21_190_000)})])
    assert w.ex.execute(accept(w.clock, c)).status == EXECUTED
    before = w.state
    r = w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=16_648_000)
    assert r.status == REFUSED and codes(r) == [ViolationCode.PRECONDITION_FAILED]
    assert c.id in r.message and "early-payment agreement" in r.message
    assert w.state == before and w.fac(IF).drawn_fen == 0 and w.rcv("RCV-A").status == "OPEN"
    # once the owner revokes the agreement the invoice can be financed again
    assert w.ex.revoke_commitment(c.id, Actor.OWNER).status == EXECUTED
    assert w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A",
                 advance_fen=16_648_000).status == EXECUTED
    assert w.rcv("RCV-A").status == "FINANCED"


def test_f1_the_engine_never_finances_an_invoice_with_an_early_settlement_booked() -> None:
    state = seeded_store().get_state()
    ob = early_pay(receivable_id="RCV-A").model_copy(
        update={"base": ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A", amount_fen=21_190_000)})
    fin = FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=IF, day=0, receivable_id="RCV-A",
                        amount_fen=16_648_000)
    project(state, [ob], [], C, 60)  # the agreement alone binds
    project(state, [], [fin], C, 60)  # the advance alone books
    with pytest.raises(EngineError, match="early settlement"):
        project(state, [ob], [fin], C, 60)


def test_f1_a_small_receipt_before_landing_leaves_the_advance_to_land() -> None:
    w = World()
    cash = w.state.cash_fen
    assert w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A",
                 advance_fen=30_000_000).status == EXECUTED  # 80% of 42m is 33.6m: room to spare
    w.clock.day = 1
    r = w.receive("RCV-A", 1)
    assert r.status == EXECUTED and "advance stands" in r.message
    s = w.state
    assert s.cash_fen == cash + 1  # the receipt is the owner's: the lender has advanced nothing yet
    (lot,) = s.lots
    assert (lot.remaining_fen, lot.settled, lot.arrival_day) == (30_000_000, False, 3)
    assert (rcv(s, "RCV-A").status, rcv(s, "RCV-A").advance_fen, rcv(s, "RCV-A").settled_fen) == ("FINANCED", 30_000_000, 1)
    assert w.fac(IF).drawn_fen == 30_000_000
    w.move(4)  # the advance lands on day 3 as planned
    (landed,) = w.state.lots
    assert landed.settled and w.state.cash_fen == cash + 1 + landing_cash(w.fac(IF), lot)
    check_lots(w.state)


def test_f1_a_receipt_before_landing_that_leaves_the_advance_above_the_rate_cancels_it() -> None:
    w = World()
    cash = w.state.cash_fen
    w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=30_000_000)
    w.clock.day = 1
    r = w.receive("RCV-A", 10_000_000)  # 32m outstanding: 80% is 25.6m < 30m
    assert r.status == EXECUTED and "cancelled with no charges" in r.message
    s = w.state
    assert s.lots == [] and w.fac(IF).drawn_fen == 0 and s.cash_fen == cash + 10_000_000
    assert (rcv(s, "RCV-A").status, rcv(s, "RCV-A").advance_fen) == ("OPEN", 0)
    w.move(5)
    assert w.state.cash_fen == cash + 10_000_000  # nothing lands


def test_f1_an_advance_at_the_rate_cap_is_cancelled_by_any_receipt_before_landing() -> None:
    """The decided rule, stated: an advance at exactly 80% of the face exceeds 80% of anything less (p03 part B)."""
    w = World()
    w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=33_600_000)
    w.clock.day = 1
    assert "cancelled" in w.receive("RCV-A", 1).message
    assert w.state.lots == [] and w.rcv("RCV-A").status == "OPEN"


# ================================================================ F2: an unnamed scope starts today


def test_f2_next_invoice_on_day_3_is_valued_and_written_on_the_day_32_invoice() -> None:
    w = World()
    w.move(3)
    ob = next_invoice()
    assert scope_at(w.state, ob).receivable_ids == ("RI:BUYER-1:32",)
    assert [d.issue_day for d in scoped_invoices(ob, w.state, 365)] == [32]
    r = accept_as_owner(w, "OFF-N1", [ob], 187_130)
    assert r.status == EXECUTED, r.message
    s = w.state
    assert rcv(s, "RI:BUYER-1:2").terms_days == 45 and rcv(s, "RI:BUYER-1:2").applied == []
    (adj,) = s.invoice_adjustments
    assert adj.receivable_ids == ["RI:BUYER-1:32"]
    w.move(33)
    assert (rcv(w.state, "RI:BUYER-1:32").terms_days, rcv(w.state, "RI:BUYER-1:32").due_day) == (60, 92)
    assert rcv(w.state, "RI:BUYER-1:2").due_day == 47


def test_f2_day_0_scope_is_unchanged_and_a_named_older_invoice_is_still_named() -> None:
    s0 = seeded_store().get_state()
    assert scope_at(s0, next_invoice()).receivable_ids == ("RI:BUYER-1:2",)
    s3 = s0.model_copy(update={"as_of_day": 3})
    named = next_invoice().model_copy(update={"base": ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A")})
    assert scope_at(s3, named).receivable_ids == ("RCV-A",)
    perpetual = extension().model_copy(update={"duration": Duration(kind=DurationKind.RECURRING_PERPETUAL)})
    assert scope_at(s3, perpetual).from_issue_day == 3


def test_f2_an_overdue_invoice_keeps_its_due_day_and_its_past_due_alert() -> None:
    """The p07 sequence: on day 50 RI:BUYER-1:2 (due day 47) is unpaid; '+15 days on the next invoice' is
    accepted. It goes on the invoice issued on day 62; the overdue one is untouched and still past due."""
    w = World()
    w.move(50)
    m = w.store.get_mandate()
    past_due = [a for a in alerts(w.state, m, w.store, 50) if a.kind == AlertKind.RECEIVABLE_PAST_DUE
                and a.inputs.get("receivable_id") == "RI:BUYER-1:2"]
    assert past_due and past_due[0].day == 47
    ob = next_invoice()
    t = project(w.state, [ob], [], C, 120)  # what the offer is evaluated on: no receipt revived from the overdue one
    assert not [e for p in t.days for e in p.events if e.ref == "RI:BUYER-1:2"]
    r = accept_as_owner(w, "OFF-N50", [ob], 187_130)
    assert r.status == EXECUTED, r.message
    s = w.state
    late = rcv(s, "RI:BUYER-1:2")
    assert (late.status, late.terms_days, late.due_day, late.applied) == ("OPEN", 45, 47, [])
    (adj,) = s.invoice_adjustments
    assert adj.receivable_ids == ["RI:BUYER-1:62"]
    after = [a for a in alerts(s, m, w.store, 50) if a.kind == AlertKind.RECEIVABLE_PAST_DUE
             and a.inputs.get("receivable_id") == "RI:BUYER-1:2"]
    assert after and after[0].day == 47


# ================================================================ F3: an invoice with nothing outstanding is settled


def _full_face_world() -> World:
    """p05: a facility advancing the whole face, no lead time; RCV-A (¥420,000, due day 32) financed in full."""
    w = World()
    s = w.state
    base = next(f for f in s.facilities if f.id == IF)
    full = base.model_copy(update={"id": "FAC-IF100", "advance_rate_bp": None, "lead_time_days": 0,
                                   "limit_fen": 50_000_000, "drawn_fen": 0, "upfront_fee_bp": 0})
    w.store.put_state(s.model_copy(update={"facilities": [*s.facilities, full]}))
    assert w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id="FAC-IF100", receivable_id="RCV-A",
                 advance_fen=42_000_000).status == EXECUTED
    w.move(32)
    return w


def test_f3_the_last_receipt_settles_the_invoice_and_leaves_a_fixed_amount_owed() -> None:
    w = _full_face_world()
    lot = w.state.lots[0]
    f = w.fac("FAC-IF100")
    interest, fee, _ = finance_invoice_charges(f, 42_000_000, 32 - lot.arrival_day)
    cash = w.state.cash_fen
    r = w.receive("RCV-A", 42_000_000)
    assert r.status == EXECUTED and "owes it to the lender directly" in r.message
    s = w.state
    a = rcv(s, "RCV-A")
    assert (a.status, a.outstanding_fen, a.advance_fen, a.advance_facility_id) == ("SETTLED", 0, 0, None)
    (left,) = s.lots
    assert is_fixed_remainder(left) and left.remaining_fen == interest + fee and left.receivable_id == "RCV-A"
    assert w.fac("FAC-IF100").drawn_fen == interest + fee and s.cash_fen == cash
    check_lots(s)
    assert w.receive("RCV-A", 100).status == REFUSED  # nothing is owed on the invoice
    # nothing accrues: weeks later the amount owed is the same
    w.move(80)
    assert w.state.lots[0].remaining_fen == interest + fee
    # the agent repays part, the owner the rest; no interest on top
    cash = w.state.cash_fen
    r1 = w.run(RepayFacility, Actor.AGENT, facility_id="FAC-IF100", amount_fen=100_000)
    assert r1.status == EXECUTED, r1.message
    r2 = w.run(RepayFacility, Actor.OWNER, facility_id="FAC-IF100", amount_fen=interest + fee - 100_000)
    assert r2.status == EXECUTED, r2.message
    s = w.state
    assert s.cash_fen == cash - (interest + fee) and s.lots == [] and w.fac("FAC-IF100").drawn_fen == 0
    check_lots(s)


def test_f3_on_receipt_repayment_is_only_for_what_is_left_on_settled_invoices() -> None:
    w = _full_face_world()
    before = w.state
    r = w.run(RepayFacility, Actor.OWNER, facility_id="FAC-IF100", amount_fen=1_000)
    assert r.status == REFUSED and "not on demand" in r.message and w.state == before  # RCV-A is still FINANCED
    w.receive("RCV-A", 42_000_000)
    owed = w.state.lots[0].remaining_fen
    before = w.state
    r = w.run(RepayFacility, Actor.OWNER, facility_id="FAC-IF100", amount_fen=owed + 1)
    assert r.status == REFUSED and "exceeds" in r.message and w.state == before


def test_f3_a_final_receipt_short_of_the_principal_bills_the_charges_once() -> None:
    """The second case: an invoice settled by a receipt that does not cover the remaining principal (possible only
    when a receipt settled more face than it paid, e.g. an early-payment discount). The rest, principal and the
    charges billed to today, is a fixed amount; a non-final receipt of the same size keeps the charges deferred."""
    w = _full_face_world()
    f, lot = w.fac("FAC-IF100"), w.state.lots[0]
    interest, fee, _ = finance_invoice_charges(f, 42_000_000, 32 - lot.arrival_day)
    a = apply_receipt(f, lot, 40_000_000, 32, final=True)
    assert a.applied == 40_000_000 and a.lot is not None and is_fixed_remainder(a.lot)
    assert a.lot.remaining_fen == 2_000_000 + interest + fee
    b = apply_receipt(f, lot, 40_000_000, 32)
    assert b.lot is not None and (b.lot.principal_fen, b.lot.remaining_fen) == (42_000_000, 2_000_000)


@pytest.mark.skip(reason="projection side of F3: runs after fix/router-admission-agree merges (the carried-advance "
                         "code repays an orphaned lot today, with no further charges)")
def test_f3_the_projection_repays_an_orphaned_fixed_amount_today_without_charges() -> None:
    w = _full_face_world()
    w.receive("RCV-A", 42_000_000)
    owed = w.state.lots[0].remaining_fen
    t = project(w.state, [], [], C, 120)
    ev = [(p.day, e.kind, e.amount_fen) for p in t.days for e in p.events if e.ref == "FAC-IF100"]
    assert ev == [(32, LedgerEventKind.REPAYMENT, -owed)]


@pytest.mark.skip(reason="admission side of F3: the engine's REPAY accepts an ON_RECEIPT facility's orphaned lots only "
                         "after fix/router-admission-agree merges (see INTERFACE_CHANGE_REQUESTS)")
def test_f3_repaying_an_orphaned_lot_passes_the_runtime_admission_check() -> None:
    from app.books import current_books
    from app.funding.admission import admit

    w = _full_face_world()
    w.receive("RCV-A", 42_000_000)
    owed = w.state.lots[0].remaining_fen
    rp = op(RepayFacility, w.clock, actor=Actor.OWNER, facility_id="FAC-IF100", amount_fen=owed)
    assert admit(rp, current_books(w.state, w.store.commitments()), w.store.get_mandate()).violations == []


# ================================================================ F4: the default early-pay day is today + lead


@pytest.mark.parametrize("today", [0, 1, 3, 10])
def test_f4_default_settlement_day_is_today_plus_the_lead_time(today: int) -> None:
    state = seeded_store().get_state().model_copy(update={"as_of_day": today})
    lead = early_pay_lead(state.model_copy(update={"as_of_day": 0}), "BUYER-1")
    assert early_pay_lead(state, "BUYER-1") == today + lead
    ob = early_pay(receivable_id="RCV-A")
    assert ob.effective_day is None
    t = project(state, [ob], [], C, 60)
    days = [p.day for p in t.days for e in p.events if e.kind == LedgerEventKind.EARLY_RECEIPT and e.ref == "RCV-A"]
    assert days == [today + lead]


# ================================================================ F5: receipts are facts


def test_f5_bank_feed_and_owner_book_receipts_after_the_mandate_expires() -> None:
    store = seeded_store()
    m = store.get_mandate()
    clock = Clock(m.expires_day + 1)
    ex = make_executor(store, clock)
    cash = store.get_state().cash_fen
    agent = ex.execute(op(ReceivePayment, clock, actor=Actor.AGENT, receivable_id="RCV-A", amount_fen=1_000_000))
    assert agent.status == REFUSED and ViolationCode.MANDATE_EXPIRED in codes(agent)
    assert store.get_state().cash_fen == cash
    bank = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=1_000_000))
    assert bank.status == EXECUTED, bank.message
    owner = ex.execute(op(ReceivePayment, clock, actor=Actor.OWNER, receivable_id="RCV-A", amount_fen=2_000_000))
    assert owner.status == EXECUTED, owner.message
    s = store.get_state()
    assert s.cash_fen == cash + 3_000_000 and rcv(s, "RCV-A").settled_fen == 3_000_000


def test_f5_a_revoked_or_newer_mandate_does_not_stop_a_bank_receipt_but_a_bad_signature_does() -> None:
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    store.put_mandate(revoke(load_signed_mandate(), load_demo_owner_key()["private_key_hex"]))
    r = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=1_000_000,
                      mandate_version=7))
    assert r.status == EXECUTED, r.message
    assert rcv(store.get_state(), "RCV-A").settled_fen == 1_000_000
    from nacl.signing import SigningKey

    store.put_mandate(sign(load_signed_mandate(), SigningKey.generate().encode().hex()))
    before = store.get_state()
    bad = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=1_000_000))
    assert bad.status == REFUSED and codes(bad) == [ViolationCode.BAD_SIGNATURE] and store.get_state() == before


# ================================================================ F6: one key, one operation


def test_f6_a_key_reused_for_a_different_operation_is_refused_and_the_receipt_books_on_its_own_key() -> None:
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    seed_offer(store, ex, "OFF-R")
    rej = ex.execute(op(RejectOffer, clock, key="K-SHARED", offer_id="OFF-R", reason_codes=[]))
    assert rej.status == EXECUTED
    before, events = store.get_state(), len(store.security_events())
    rx = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, key="K-SHARED", receivable_id="RCV-A",
                       amount_fen=42_000_000))
    assert rx.status == REFUSED and codes(rx) == [ViolationCode.REPLAY]
    assert "different operation" in rx.message and store.get_state() == before
    assert [e.kind for e in store.security_events()[events:]] == [SecurityEventKind.REPLAY]
    again = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, key="K-RX", receivable_id="RCV-A",
                          amount_fen=42_000_000))
    assert again.status == EXECUTED and rcv(store.get_state(), "RCV-A").status == "SETTLED"
    assert store.verify_chain()


def test_f6_the_same_operation_resent_later_is_a_duplicate_and_runs_once() -> None:
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    first = op(ReceivePayment, clock, actor=Actor.SYSTEM, key="K-1", receivable_id="RCV-A", amount_fen=1_000_000)
    assert ex.execute(first).status == EXECUTED
    clock.day = 1
    resent = ex.execute(first.model_copy(update={"day": 1}))  # a bank feed retry the next day
    assert resent.status == DUPLICATE
    assert rcv(store.get_state(), "RCV-A").settled_fen == 1_000_000
    # the same key and fields from another requester is not the same operation
    other = ex.execute(first.model_copy(update={"day": 1, "requested_by": Actor.OWNER}))
    assert other.status == REFUSED and codes(other) == [ViolationCode.REPLAY]
    assert rcv(store.get_state(), "RCV-A").settled_fen == 1_000_000


def test_f6_rejecting_or_countering_an_offer_that_does_not_exist_is_refused() -> None:
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    rej = ex.execute(op(RejectOffer, clock, offer_id="nothing", reason_codes=[]))
    ctr = ex.execute(op(CounterOffer, clock, offer_id="nothing", counter_id="CTR-A"))
    assert rej.status == REFUSED and codes(rej) == [ViolationCode.PRECONDITION_FAILED]
    assert ctr.status == REFUSED and codes(ctr) == [ViolationCode.PRECONDITION_FAILED]


# ================================================================ F7: the cap is released when the invoices are paid


def test_f7_one_invoice_agreements_over_time_stay_under_the_aggregate_cap() -> None:
    w = World()
    cap = w.store.get_mandate().max_aggregate_forward_concession_fen
    value = cap * 3 // 8  # two fit under the cap, three do not
    r1 = accept_as_owner(w, "OFF-S1", [next_invoice("OB-1")], value)
    assert r1.status == EXECUTED, r1.message
    (c1,) = [c for c in w.store.commitments() if c.status == CommitmentStatus.ACTIVE]
    w.move(3)  # RI:BUYER-1:2 issued with the extension: the adjustment is consumed, the concession is still ahead
    assert w.state.invoice_adjustments == [] and rcv(w.state, "RI:BUYER-1:2").terms_days == 60
    assert w.store.get_commitment(c1.id).status == CommitmentStatus.ACTIVE
    assert [fc.value_fen for fc in w.state.forward_concessions] == [value]
    assert accept_as_owner(w, "OFF-S2", [next_invoice("OB-2")], value).status == EXECUTED
    w.move(33)
    r3 = accept_as_owner(w, "OFF-S3", [next_invoice("OB-3")], value)
    assert r3.status == REFUSED and "Aggregate forward-concession cap" in r3.message
    assert sum(fc.value_fen for fc in w.state.forward_concessions) == 2 * value
    # the buyer pays the first invoice: the first agreement is fulfilled when the clock closes the day
    w.receive("RI:BUYER-1:2", rcv(w.state, "RI:BUYER-1:2").outstanding_fen)
    w.move(34)
    assert w.store.get_commitment(c1.id).status == CommitmentStatus.FULFILLED
    (left,) = w.state.forward_concessions
    assert left.commitment_id != c1.id and left.value_fen == value


def test_f7_revocation_still_releases_at_once() -> None:
    w = World()
    assert accept_as_owner(w, "OFF-V", [next_invoice()], 100_000).status == EXECUTED
    (c,) = [c for c in w.store.commitments() if c.status == CommitmentStatus.ACTIVE]
    w.move(3)
    assert w.ex.revoke_commitment(c.id, Actor.OWNER).status == EXECUTED
    assert w.state.forward_concessions == [] and w.store.get_commitment(c.id).status == CommitmentStatus.REVOKED
