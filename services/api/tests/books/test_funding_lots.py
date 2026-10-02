"""ADR-0010: funding lots with dates. Cash lands after the lead time in the projection, the executor and the clock
alike; interest runs from the landing day; the clock posts contractual instalments and maturities; nothing is ever
posted into a closed day. Also the receipt rule on a financed invoice (red-team p03): the lender is paid first, from
the receipt only."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.clock import advance as advance_clock
from app.clock import close_days
from app.domain.models import (
    Actor,
    DrawFacility,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    FundingLot,
    LedgerEventKind,
    Mode,
    OperationStatus,
    Receivable,
    ReceivePayment,
    RepayFacility,
    Repayment,
    SubmitInvoiceForFinancing,
    ViolationCode,
)
from app.financial import finance_invoice_charges, line_interest, project
from app.financial.lots import apply_receipt, ensure_lots
from tests.operations.builders import Clock, make_executor, op, seeded_store

C = Mode.CONSERVATIVE
LINE, LAG, TERM, AMORT, IF = "FAC-LINE", "FAC-LAG", "FAC-TERM", "FAC-AM", "FAC-IF"


# ---------------------------------------------------------------- builders


def _facilities(state: FinancialState) -> list[Facility]:
    line = next(f for f in state.facilities if f.id == LINE)
    common = {"status": FacilityStatus.COMMITTED, "owner_approved": True, "covenants": [], "drawn_fen": 0,
              "limit_fen": 50_000_000}
    return [
        line.model_copy(update={**common, "id": LAG, "name": "Lagged line", "lead_time_days": 2}),
        line.model_copy(update={**common, "id": TERM, "name": "Term bullet", "kind": FacilityKind.GOV_GUARANTEED_LOAN,
                                "repayment": Repayment.BULLET, "term_months": 3, "lead_time_days": 5, "rate_bp": 500,
                                "upfront_fee_bp": 50}),
        line.model_copy(update={**common, "id": AMORT, "name": "Amortising loan",
                                "kind": FacilityKind.EQUIPMENT_TERM_LOAN, "repayment": Repayment.AMORTISING,
                                "term_months": 6, "lead_time_days": 2, "rate_bp": 560}),
    ]


class World:
    """A seeded store, the executor on it, and a clock that moves only through `app.clock.advance`."""

    def __init__(self, receivables: list[Receivable] | None = None) -> None:
        self.store: Any = seeded_store("memory")
        s = self.store.get_state()
        # ¥5m more cash, so a repayment is never refused for want of cash after payroll
        update: dict[str, Any] = {"facilities": [*s.facilities, *_facilities(s)], "cash_fen": s.cash_fen + 500_000_000}
        if receivables is not None:
            update["receivables"] = [*s.receivables, *receivables]
        self.store.put_state(s.model_copy(update=update))
        self.clock = Clock(0)
        self.ex = make_executor(self.store, self.clock)

    @property
    def state(self) -> FinancialState:
        return self.store.get_state()

    def move(self, day: int) -> Any:
        adv = advance_clock(self.store, day)
        self.clock.day = self.state.as_of_day
        return adv

    def run(self, cls: type, actor: Actor = Actor.AGENT, **fields: Any) -> Any:
        return self.ex.execute(op(cls, self.clock, actor=actor, **fields))

    def receive(self, rid: str, amount: int) -> Any:
        return self.run(ReceivePayment, Actor.SYSTEM, receivable_id=rid, amount_fen=amount)

    def fac(self, fid: str) -> Facility:
        return next(f for f in self.state.facilities if f.id == fid)

    def rcv(self, rid: str) -> Receivable:
        return next(r for r in self.state.receivables if r.id == rid)


def check_lots(state: FinancialState) -> None:
    for f in state.facilities:
        assert sum(lot.remaining_fen for lot in state.lots if lot.facility_id == f.id) == f.drawn_fen, f.id


def check_projection(state: FinancialState) -> None:
    t = project(state, [], [], C, 60)
    today = state.as_of_day
    assert all(not p.events for p in t.days if p.day < today), "a posting in a closed day"
    assert t.days[today].opening_fen == state.cash_fen


def events(t: Any, kind: LedgerEventKind, ref: str) -> list[tuple[int, int]]:
    return [(p.day, e.amount_fen) for p in t.days for e in p.events if e.kind == kind and e.ref == ref]


# ---------------------------------------------------------------- 1. invariants over random sequences

step = st.one_of(
    st.tuples(st.just("draw"), st.sampled_from([LINE, LAG, TERM, AMORT]), st.integers(1, 5_000_000)),
    st.tuples(st.just("repay"), st.sampled_from([LINE, LAG]), st.integers(1, 100)),
    st.tuples(st.just("finance"), st.integers(1, 100)),
    st.tuples(st.just("receive"), st.integers(0, 3), st.integers(1, 100)),
    st.tuples(st.just("tick"), st.integers(1, 20)),
)


def _do(w: World, s: tuple) -> Any:
    name, state, day = s[0], w.state, w.clock.day
    if name == "draw":
        return w.run(DrawFacility, facility_id=s[1], amount_fen=s[2])
    if name == "repay":
        drawn = w.fac(s[1]).drawn_fen
        return w.run(RepayFacility, facility_id=s[1], amount_fen=max(1, drawn * s[2] // 100)) if drawn else None
    if name == "finance":
        open_ = [r for r in state.receivables if r.status == "OPEN" and r.due_day > day + 3 and r.outstanding_fen]
        if not open_:
            return None
        r = open_[0]
        return w.run(SubmitInvoiceForFinancing, facility_id=IF, receivable_id=r.id,
                     advance_fen=max(1, r.outstanding_fen * 8 // 10 * s[1] // 100))
    if name == "receive":
        owed = [r for r in state.receivables if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0]
        if not owed:
            return None
        r = owed[s[1] % len(owed)]
        return w.receive(r.id, max(1, r.outstanding_fen * s[2] // 100))
    return w.move(day + s[1])


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(steps=st.lists(step, min_size=1, max_size=25))
def test_lots_sum_to_drawn_and_cash_moves_only_by_logged_events(steps: list[tuple]) -> None:
    w = World()
    check_lots(ensure_lots(w.state))
    for s in steps:
        before, logged = w.state, len(w.store.operations())
        result = _do(w, s)
        after = w.state
        if result is None:
            assert after == before
            continue
        if getattr(result, "status", None) == OperationStatus.REFUSED:
            assert after == before
        if after.cash_fen != before.cash_fen:
            assert len(w.store.operations()) > logged, s
        check_lots(after)
        assert all(lot.remaining_fen > 0 for lot in after.lots)
        check_projection(after)


# ---------------------------------------------------------------- 2. the suffix property


def _suffix_base() -> FinancialState:
    """Day 3: a line draw, an amortising loan and a term bullet requested (2 and 5 days' lead), an advance on the
    invoice issued on day 2 (due day 47) requested; nothing has landed yet except the line."""
    w = World()
    w.move(3)
    assert w.run(DrawFacility, facility_id=LINE, amount_fen=5_000_000).status == "EXECUTED"
    assert w.run(DrawFacility, facility_id=AMORT, amount_fen=12_000_000).status == "EXECUTED"
    assert w.run(DrawFacility, facility_id=TERM, amount_fen=8_000_000).status == "EXECUTED"
    fin = w.run(SubmitInvoiceForFinancing, facility_id=IF, receivable_id="RI:BUYER-1:2", advance_fen=20_000_000)
    assert fin.status == "EXECUTED", fin.message
    return w.state


_BASE: list[FinancialState] = []


def _key(e: Any, day: int) -> tuple:
    return (day, e.kind, e.amount_fen, e.ref)


@settings(max_examples=60, deadline=None)
@given(d=st.integers(3, 100), k=st.integers(1, 40))
def test_closing_days_leaves_the_suffix_of_the_earlier_projection(d: int, k: int) -> None:
    dues = [32, 47, 77, 107, 137]  # RCV-A and the recurring invoices: no receipt may be expected in between
    assume(not any(d <= due < d + k for due in dues))
    if not _BASE:
        _BASE.append(_suffix_base())
    s_d, _ = close_days(_BASE[0], d)
    p1 = project(s_d, [], [], C, 120)
    s_dk, _ = close_days(s_d, d + k)
    p2 = project(s_dk, [], [], C, 120)
    end = p1.horizon_days - 1  # the horizon end carries horizon-dependent repayments
    # assumptions recomputed on every projection: the credit line's repayment day (ADR-0010 §5) and, once its
    # invoice is overdue (day 47), the advance repaid "today" on recourse
    assumed = {LINE} | ({IF} if d > 47 else set())
    first = sorted(_key(e, p.day) for p in p1.days if d + k <= p.day <= end for e in p.events if e.ref not in assumed)
    second = sorted(_key(e, p.day) for p in p2.days if d + k <= p.day <= end for e in p.events if e.ref not in assumed)
    assert first == second
    if not any(e.ref in assumed for p in p1.days if d <= p.day < d + k for e in p.events):
        assert s_dk.cash_fen == p1.days[d + k - 1].closing_fen
    check_lots(s_dk)


# ---------------------------------------------------------------- 3. lead time


def test_an_advance_requested_on_day_34_is_cash_on_day_37_and_costs_one_period() -> None:
    w = World()
    w.move(34)
    cash = w.state.cash_fen
    r = w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RI:BUYER-1:2",
              advance_fen=20_000_000)
    assert r.status == OperationStatus.EXECUTED, r.message
    assert "lands on day 37" in r.message
    s = w.state
    assert s.cash_fen == cash and w.rcv("RI:BUYER-1:2").status == "FINANCED"
    (lot,) = s.lots
    assert (lot.request_day, lot.arrival_day, lot.settled, lot.remaining_fen) == (34, 37, False, 20_000_000)
    t = project(s, [], [], C, 60)
    assert events(t, LedgerEventKind.ADVANCE, IF) == [(37, 20_000_000)]
    assert t.days[34].opening_fen == cash and t.days[36].closing_fen == cash  # no flow on 34..36
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 20_000_000, 10)
    assert interest + fee == 178_219  # ¥1,782.19: one 30-day period for the 10 days from landing to the due day
    assert events(t, LedgerEventKind.INTEREST, IF) == [(47, -interest)]
    adv = w.move(38)
    assert w.state.cash_fen == cash + 20_000_000 and w.state.lots[0].settled
    assert adv.settled_lot_ids == [lot.id]
    payload = w.store.operations()[-1].payload_json
    assert '"settled_lot_ids"' in payload and '"posted_debt_payments"' not in payload


def test_a_zero_lead_time_draw_is_cash_at_once() -> None:
    w = World()
    cash = w.state.cash_fen
    r = w.run(DrawFacility, facility_id=LINE, amount_fen=1_000_000)
    assert r.status == OperationStatus.EXECUTED and "lands" not in r.message
    assert w.state.cash_fen == cash + 1_000_000 and w.state.lots[0].settled


def test_a_lagged_draw_lands_net_of_its_upfront_fee_and_its_payload_is_logged() -> None:
    w = World()
    cash = w.state.cash_fen
    r = w.run(DrawFacility, facility_id=TERM, amount_fen=10_000_000)
    assert r.status == OperationStatus.EXECUTED and "lands on day 5" in r.message and "upfront fee ¥500.00" in r.message
    assert w.state.cash_fen == cash and w.fac(TERM).drawn_fen == 10_000_000
    (lot,) = w.state.lots
    assert lot.maturity_day == 5 + 90
    w.move(6)
    assert w.state.cash_fen == cash + 10_000_000 - 50_000
    t = project(w.state, [], [], C, 120)
    assert events(t, LedgerEventKind.REPAYMENT, TERM) == [(95, -10_000_000)]
    assert events(t, LedgerEventKind.INTEREST, TERM) == [(95, -line_interest(10_000_000, 500, 90))]
    before = w.state.cash_fen
    adv = w.move(96)  # the clock posts the maturity
    flows = adv.posted_net_fen
    assert w.state.cash_fen == before + flows - 10_000_000 - line_interest(10_000_000, 500, 90)
    assert w.fac(TERM).drawn_fen == 0 and w.state.lots == []
    assert [p["day"] for p in adv.posted_debt_payments] == [95]


def test_the_clock_never_repays_a_credit_line() -> None:
    w = World()
    w.run(DrawFacility, facility_id=LINE, amount_fen=1_000_000)
    adv = w.move(200)
    assert adv.posted_debt_payments == [] and w.fac(LINE).drawn_fen == 1_000_000


# ---------------------------------------------------------------- 4. F-FIN-02


def _bare(cash: int, day: int, remaining: int) -> FinancialState:
    s = seeded_store("memory").get_state()
    loan = _facilities(s)[2].model_copy(update={"id": "FAC-ZERO", "rate_bp": 0, "term_months": 12, "lead_time_days": 0,
                                                "drawn_fen": remaining, "limit_fen": 12_000_000})
    lot = FundingLot(id="L1", facility_id="FAC-ZERO", principal_fen=12_000_000, remaining_fen=remaining,
                     request_day=0, arrival_day=0, settled=True)
    return s.model_copy(update={"cash_fen": cash, "as_of_day": day, "flows": [], "receivables": [],
                                "recurring_invoices": [], "facilities": [loan], "lots": [lot]})


def test_ffin02_an_amortising_balance_is_not_reposted_into_closed_days() -> None:
    s61 = _bare(100_000_000, 61, 10_000_000)  # ¥1,000,000 cash; ¥120,000 lot, two instalments already paid
    t = project(s61, [], [], C, 120)
    assert t.days[61].opening_fen == 100_000_000 and t.days[61].closing_fen == 100_000_000
    principal = events(t, LedgerEventKind.REPAYMENT, "FAC-ZERO")
    assert principal[0] == (90, -1_000_000) and len(principal) == 10 and all(d >= 61 for d, _ in principal)

    s0 = _bare(102_000_000, 0, 12_000_000)
    s, adv = close_days(s0, 61)
    assert [p["day"] for p in adv.posted_debt_payments] == [30, 60]
    assert s.cash_fen == s61.cash_fen and s.lots == s61.lots and s.facilities == s61.facilities
    later = project(s, [], [], C, 120)
    assert [(p.day, [(e.kind, e.amount_fen) for e in p.events]) for p in later.days] == \
        [(p.day, [(e.kind, e.amount_fen) for e in p.events]) for p in t.days]


# ---------------------------------------------------------------- 5. executor and projection charge the same

SPANS = [1, 29, 30, 31, 60, 61]


@pytest.mark.parametrize("span", SPANS)
def test_line_interest_booked_equals_the_projection(span: int) -> None:
    w = World()
    w.run(DrawFacility, facility_id=LAG, amount_fen=10_000_000)  # lands day 2
    repay_day = 2 + span
    t = project(w.state, [], [FundingAction(kind=FundingActionKind.REPAY, facility_id=LAG, day=repay_day,
                                            amount_fen=10_000_000)], C, 120)
    projected = -sum(a for d, a in events(t, LedgerEventKind.INTEREST, LAG) if d == repay_day)
    w.move(repay_day)
    before = w.state.cash_fen
    r = w.run(RepayFacility, facility_id=LAG, amount_fen=10_000_000)
    assert r.status == OperationStatus.EXECUTED, r.message
    assert before - w.state.cash_fen - 10_000_000 == projected == line_interest(10_000_000, 640, span)


@pytest.mark.parametrize("span", SPANS)
def test_invoice_advance_charges_booked_equal_the_projection(span: int) -> None:
    due = 3 + span  # FAC-IF lands the advance on day 3
    rcv = Receivable(id="RCV-S", counterparty_id="BUYER-1", face_fen=30_000_000, issue_day=0, terms_days=due)
    w = World([rcv])
    assert w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-S",
                 advance_fen=20_000_000).status == "EXECUTED"
    t = project(w.state, [], [], C, 120)
    projected = -sum(a for d, a in events(t, LedgerEventKind.INTEREST, IF) + events(t, LedgerEventKind.FEE, IF)
                     if d == due)
    w.move(due)
    before = w.state.cash_fen
    assert w.receive("RCV-S", 30_000_000).status == "EXECUTED"
    booked = 30_000_000 - 20_000_000 - (w.state.cash_fen - before)
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 20_000_000, span)
    assert booked == projected == interest + fee


# ---------------------------------------------------------------- 6. what has not landed


def test_a_repayment_of_cash_that_has_not_landed_is_refused() -> None:
    w = World()
    w.run(DrawFacility, facility_id=LAG, amount_fen=3_000_000)
    before = w.state
    r = w.run(RepayFacility, facility_id=LAG, amount_fen=1_000_000)
    assert r.status == OperationStatus.REFUSED and [v.code for v in r.violations] == [ViolationCode.PRECONDITION_FAILED]
    assert "lands on day 2" in r.message and w.state == before
    w.move(3)
    assert w.run(RepayFacility, facility_id=LAG, amount_fen=1_000_000).status == "EXECUTED"


def test_a_receipt_before_the_advance_lands_cancels_it_with_no_charges() -> None:
    w = World()
    cash = w.state.cash_fen
    w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=30_000_000)
    w.clock.day = 1  # the executor's day; the books stay open from day 0
    r = w.receive("RCV-A", 42_000_000)
    assert r.status == OperationStatus.EXECUTED and "cancelled with no charges" in r.message
    assert w.state.cash_fen == cash + 42_000_000 and w.fac(IF).drawn_fen == 0 and w.state.lots == []
    assert w.rcv("RCV-A").status == "SETTLED"
    w.move(5)  # nothing lands later
    assert w.state.cash_fen == cash + 42_000_000


# ---------------------------------------------------------------- 7. receipts on a financed invoice (red-team p03)


def _financed(advance: int = 33_600_000) -> World:
    w = World()
    w.move(10)
    w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=advance)
    w.move(25)
    return w


def test_a_one_fen_receipt_goes_to_the_lender_and_the_invoice_stays_financed() -> None:
    w = _financed()
    cash = w.state.cash_fen
    r = w.receive("RCV-A", 1)
    assert r.status == OperationStatus.EXECUTED
    assert w.state.cash_fen == cash  # never down; the fen went to the lender
    assert (w.rcv("RCV-A").status, w.rcv("RCV-A").advance_fen) == ("FINANCED", 33_600_000 - 1)
    assert w.fac(IF).drawn_fen == 33_600_000 - 1
    check_lots(w.state)
    again = w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-A", advance_fen=1_000_000)
    assert again.status == OperationStatus.REFUSED
    # the projection repays the remaining advance from the remaining face on the due day
    t = project(w.state, [], [], C, 60)
    assert events(t, LedgerEventKind.REPAYMENT, IF) == [(32, -(33_600_000 - 1))]
    assert events(t, LedgerEventKind.RECEIPT, "RCV-A") == [(32, 42_000_000 - 1)]


def test_a_receipt_of_exactly_the_advance_and_charges_clears_it() -> None:
    w = _financed()
    lot = w.state.lots[0]
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 33_600_000, 25 - lot.arrival_day)
    cash = w.state.cash_fen
    r = w.receive("RCV-A", 33_600_000 + interest + fee)
    assert r.status == OperationStatus.EXECUTED and "repaid advance" in r.message
    assert w.state.cash_fen == cash and w.fac(IF).drawn_fen == 0 and w.state.lots == []
    assert w.rcv("RCV-A").status == "OPEN" and w.rcv("RCV-A").advance_fen == 0


def test_a_full_face_receipt_repays_the_advance_and_charges_and_the_rest_is_cash() -> None:
    w = _financed()
    lot = w.state.lots[0]
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 33_600_000, 25 - lot.arrival_day)
    cash = w.state.cash_fen
    assert w.receive("RCV-A", 42_000_000).status == "EXECUTED"
    assert w.state.cash_fen == cash + 42_000_000 - 33_600_000 - interest - fee
    assert w.rcv("RCV-A").status == "SETTLED" and w.fac(IF).drawn_fen == 0


def test_two_partial_receipts_then_the_rest_charge_the_advance_once() -> None:
    w = _financed()
    lot = w.state.lots[0]
    cash = w.state.cash_fen
    w.receive("RCV-A", 10_000_000)
    check_lots(w.state)
    w.move(28)
    cash = w.state.cash_fen
    w.receive("RCV-A", 10_000_000)
    check_lots(w.state)
    assert w.state.cash_fen == cash and w.fac(IF).drawn_fen == 13_600_000 and w.rcv("RCV-A").status == "FINANCED"
    w.move(32)
    cash = w.state.cash_fen
    assert w.receive("RCV-A", 22_000_000).status == "EXECUTED"
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 33_600_000, 32 - lot.arrival_day)
    assert w.state.cash_fen == cash + 22_000_000 - 13_600_000 - interest - fee
    assert w.rcv("RCV-A").status == "SETTLED" and w.fac(IF).drawn_fen == 0 and w.state.lots == []


def test_a_receipt_that_repays_the_principal_but_not_the_charges_keeps_them_due() -> None:
    w = _financed()
    lot = w.state.lots[0]
    interest, fee, _ = finance_invoice_charges(w.fac(IF), 33_600_000, 25 - lot.arrival_day)
    cash = w.state.cash_fen
    w.receive("RCV-A", 33_600_000 + 100)
    s = w.state
    assert s.cash_fen == cash and w.rcv("RCV-A").status == "FINANCED"
    (left,) = s.lots
    # red team F3: the unpaid charges are a fixed amount (principal 0, dates kept), never charged again
    assert left.remaining_fen == interest + fee - 100 and left.principal_fen == 0 and left.arrival_day == lot.arrival_day
    assert w.fac(IF).drawn_fen == left.remaining_fen
    a = apply_receipt(w.fac(IF), left, 10**9, 32)
    assert a.lot is None and a.applied == left.remaining_fen and (a.interest, a.fee) == (0, 0)


def test_ensure_lots_dates_an_older_balance_to_today_and_states_without_lots_serialise_unchanged() -> None:
    s = seeded_store("memory").get_state()
    assert '"lots"' not in s.model_dump_json()
    drawn = s.model_copy(update={"facilities": [f.model_copy(update={"drawn_fen": 5_000_000}) if f.id == LINE else f
                                                for f in s.facilities]})
    (lot,) = ensure_lots(drawn).lots
    assert (lot.arrival_day, lot.settled, lot.assumed_date, lot.remaining_fen) == (0, True, True, 5_000_000)
    later = ensure_lots(drawn.model_copy(update={"as_of_day": 40})).lots[0]
    assert later.arrival_day == 40
    assert ensure_lots(s) is s


# ---------------------------------------------------------------- 7. N03: a settled financed invoice still owes its lot


def _fully_advanced_and_paid_in_full() -> World:
    """A 100% advance on an invoice whose buyer then pays the face: the receipt cannot cover the charges as well, so the
    lender takes it all and the unpaid charges stay on the lot. The invoice is FINANCED with nothing outstanding."""
    rcv = Receivable(id="RCV-S", counterparty_id="BUYER-1", face_fen=30_000_000, issue_day=0, terms_days=40)
    w = World([rcv])
    s = w.state
    w.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"advance_rate_bp": None}) if f.id == IF else f for f in s.facilities]}))
    assert w.run(SubmitInvoiceForFinancing, Actor.OWNER, facility_id=IF, receivable_id="RCV-S",
                 advance_fen=30_000_000).status == "EXECUTED"
    w.move(10)
    assert w.receive("RCV-S", 30_000_000).status == "EXECUTED"
    return w


def test_a_settled_financed_invoice_repays_its_open_lot_today_not_at_the_horizon() -> None:
    w = _fully_advanced_and_paid_in_full()
    assert w.rcv("RCV-S").status == "FINANCED" and w.rcv("RCV-S").outstanding_fen == 0
    (lot,) = [x for x in w.state.lots if x.receivable_id == "RCV-S"]
    assert lot.remaining_fen > 0 and w.fac(IF).drawn_fen == lot.remaining_fen
    t = project(w.state, [], [], C, 120)
    repaid = [(p.day, -e.amount_fen) for p in t.days for e in p.events
              if e.kind == LedgerEventKind.REPAYMENT and e.ref == IF]
    assert repaid == [(10, lot.remaining_fen)]  # today, by the overdue-invoice recourse convention; not day 120
    # the charge is one period on the capitalised balance, billed once on the day it is repaid
    interest, fee, _ = finance_invoice_charges(w.fac(IF), lot.principal_fen, 0)
    posted = [(p.day, -e.amount_fen) for p in t.days for e in p.events
              if e.kind in (LedgerEventKind.INTEREST, LedgerEventKind.FEE) and e.ref == IF]
    assert posted == [(10, interest), *([(10, fee)] if fee else [])]
