"""Existing debt is real cash (docs/FINANCIAL_SEMANTICS.md §5, ADR-0010 "existing debt"): the golden books' D-EQUIP
(¥1,500,000, ¥45,000 every 30 days from day 30, rate 0 as a fixture assumption) leaves cash on its payment days in
the projection and in the clock alike, lowers the debt by the principal paid, and is never posted before today."""

from __future__ import annotations

import json
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.clock import advance as advance_clock
from app.clock import close_days
from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState, Mode
from app.financial import project
from tests.operations.builders import seeded_store

C = Mode.CONSERVATIVE
SERVICE = 4_500_000
PRINCIPAL = 150_000_000


def _state() -> FinancialState:
    return load_scenario()[0]


def _debt_events(t: Any) -> list[tuple[int, int]]:
    return [(p.day, e.amount_fen) for p in t.days for e in p.events if e.ref == "D-EQUIP"]


def test_closings_fall_by_the_service_on_each_payment_day() -> None:
    s = _state()
    with_debt = project(s, [], [], C, 120)
    without = project(s.model_copy(update={"debts": []}), [], [], C, 120)
    # day 30: one payment; day 60: two; day 90: three; day 120: four (each ¥45,000, all principal at rate 0)
    for day, paid in ((29, 0), (30, 1), (59, 1), (60, 2), (89, 2), (90, 3), (120, 4)):
        assert without.days[day].closing_fen - with_debt.days[day].closing_fen == paid * SERVICE, day
    assert _debt_events(with_debt) == [(30, -SERVICE), (60, -SERVICE), (90, -SERVICE), (120, -SERVICE)]
    ev = next(e for e in with_debt.days[30].events if e.ref == "D-EQUIP")
    assert ev.kind == "FLOW" and ev.label.startswith("Debt service (principal)")


def test_debt_outstanding_and_leverage_fall_by_the_principal_paid() -> None:
    t = project(_state(), [], [], C, 120)
    assert t.days[29].debt_outstanding_fen == PRINCIPAL
    assert t.days[30].debt_outstanding_fen == PRINCIPAL - SERVICE
    assert t.days[60].debt_outstanding_fen == PRINCIPAL - 2 * SERVICE
    assert t.days[120].debt_outstanding_fen == PRINCIPAL - 4 * SERVICE
    # month-end leverage debt follows; the ratio's service stays the fixed ¥45,000 (no double count)
    assert [m.total_debt_fen for m in t.months] == [PRINCIPAL - k * SERVICE for k in (1, 2, 3, 4)]
    assert [m.debt_service_fen for m in t.months] == [SERVICE] * 4
    assert t.interest_posted_fen == 0  # an existing debt's payments are not a cost of the plan


def test_the_ratio_service_stops_after_the_principal_is_cleared() -> None:
    s = _state()
    s = s.model_copy(update={"debts": [s.debts[0].model_copy(update={"principal_fen": 6_000_000})]})
    t = project(s, [], [], C, 120)
    # ¥60,000 left: ¥45,000 on day 30, the last ¥15,000 on day 60; months 1-2 keep the fixed service, 3-4 none
    assert _debt_events(t) == [(30, -SERVICE), (60, -1_500_000)]
    assert [m.debt_service_fen for m in t.months] == [SERVICE, SERVICE, 0, 0]


def test_the_clock_to_day_61_posts_two_payments_matching_the_projection() -> None:
    store: Any = seeded_store("memory")
    before = store.get_state()
    t = project(before, [], [], C, 120)
    adv = advance_clock(store, 61)
    after = store.get_state()
    assert adv.posted_debt_service == [
        {"debt_id": "D-EQUIP", "day": 30, "principal_fen": SERVICE, "interest_fen": 0},
        {"debt_id": "D-EQUIP", "day": 60, "principal_fen": SERVICE, "interest_fen": 0}]
    assert adv.debt_service_fen == 2 * SERVICE
    assert after.debts[0].principal_fen == PRINCIPAL - 2 * SERVICE == t.days[60].debt_outstanding_fen
    assert after.debts[0].next_payment_day == 90
    # nothing else happened (no receipt is ever assumed by the clock): cash is the projection's closing on day 60
    # less the receipts the projection expected on days 32 and 47, which only the bank feed may record
    receipts = sum(e.amount_fen for p in t.days[:61] for e in p.events if e.kind == "RECEIPT")
    assert after.cash_fen == t.days[60].closing_fen - receipts
    payload = json.loads(store.operations()[-1].payload_json)
    assert payload["posted_debt_service"] == adv.posted_debt_service
    assert payload["debt_service_fen"] == 2 * SERVICE
    assert "2 existing-debt payment(s) posted (−¥90,000.00)" in adv.result.message
    # the next projection starts after the closed days: the day-90 payment, never day 30 or 60 again
    t2 = project(after, [], [], C, 60)
    assert _debt_events(t2) == [(90, -SERVICE), (120, -SERVICE)]


def test_a_clock_move_with_no_payment_day_logs_no_debt_service() -> None:
    store: Any = seeded_store("memory")
    adv = advance_clock(store, 30)  # closes days 0..29: the first payment is due on day 30, still open
    assert adv.posted_debt_service == []
    assert "posted_debt_service" not in json.loads(store.operations()[-1].payload_json)
    assert store.get_state().debts[0].principal_fen == PRINCIPAL


def _no_receipts() -> FinancialState:
    """The golden books with the receivables and recurring invoices taken out, so the clock and the projection
    disagree on nothing but what this file tests."""
    return _state().model_copy(update={"receivables": [], "recurring_invoices": []})


@settings(max_examples=40, deadline=None)
@given(d=st.integers(0, 150), k=st.integers(1, 120))
def test_closing_days_then_projecting_is_the_suffix_and_cash_matches(d: int, k: int) -> None:
    assume(d + k <= 200)
    base = _no_receipts()
    s_d, _ = close_days(base, d)
    p1 = project(s_d, [], [], C, 240)
    s_dk, adv = close_days(s_d, d + k)
    p2 = project(s_dk, [], [], C, 240)
    key = lambda p, e: (p.day, e.kind, e.amount_fen, e.ref)  # noqa: E731
    first = sorted(key(p, e) for p in p1.days if d + k <= p.day <= p1.horizon_days for e in p.events)
    second = sorted(key(p, e) for p in p2.days if d + k <= p.day <= p1.horizon_days for e in p.events)
    assert first == second
    assert s_dk.cash_fen == p1.days[d + k - 1].closing_fen
    assert s_dk.debts[0].principal_fen == p1.days[d + k - 1].debt_outstanding_fen
    assert all(pay["day"] >= d for pay in adv.posted_debt_service)
