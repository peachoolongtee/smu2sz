"""Balances already drawn at day 0 (after executed operations) are repaid in the projection, with interest
and fees from the shared charge helpers, instead of being carried as free cash."""

from __future__ import annotations

import pytest

from app.domain.models import FacilityStatus, FundingAction, FundingActionKind, LedgerEventKind, Mode
from app.financial import FundingActionError, finance_invoice_charges, line_interest, project
from app.financial.debts import debt_payments
from tests.financial.builders import finance

C, E = Mode.CONSERVATIVE, Mode.EXPECTED
FLOOR = 30_000_000


def drawn(state, fid: str, amount: int, *, cash: bool = True, **facility):
    """`state` after `amount` was drawn on `fid` before day 0 (the cash landed in the balance)."""
    facs = [f.model_copy(update={"drawn_fen": amount, **facility}) if f.id == fid else f for f in state.facilities]
    return state.model_copy(update={"facilities": facs, "cash_fen": state.cash_fen + (amount if cash else 0)})


def financed(state, rid: str = "RCV-A"):
    rcvs = [r.model_copy(update={"status": "FINANCED"}) if r.id == rid else r for r in state.receivables]
    return state.model_copy(update={"receivables": rcvs})


def events(t, kind: LedgerEventKind, ref: str) -> list[tuple[int, int]]:
    return [(p.day, e.amount_fen) for p in t.days for e in p.events if e.kind == kind and e.ref == ref]


def debt(t, day: int, state) -> int:
    """Facility debt outstanding on `day`: the day's total less the state's other debt positions, which are paid down
    on their own schedule (`app.financial.debts`)."""
    existing = sum(d.principal_fen - sum(p.principal for p in debt_payments(d, state.as_of_day, day + 1))
                   for d in state.debts)
    return t.days[day].debt_outstanding_fen - existing


def fac(state, fid: str):
    return next(f for f in state.facilities if f.id == fid)


# ---------------------------------------------------------------- the credit line


def test_the_drawn_line_is_repaid_on_the_first_receipt_that_keeps_cash_above_the_floor(state):
    s = drawn(state, "FAC-LINE", 15_000_000)
    t = project(s, [], [], C, 120, FLOOR)
    interest = line_interest(15_000_000, fac(s, "FAC-LINE").rate_bp, 32)
    # RCV-A (issued day −13 on 45-day terms) pays ¥420,000 on day 32; repaying ¥150,000 + interest then
    # keeps every later day at or above the ¥300,000 floor.
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-LINE") == [(32, -15_000_000)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-LINE") == [(32, -interest)]
    assert t.interest_posted_fen == interest
    assert debt(t, 31, s) == 15_000_000 and debt(t, 32, s) == 0
    assert min(p.closing_fen for p in t.days[32:]) >= FLOOR
    # the day before the receipt could not have carried the repayment
    before = project(s, [], [], C, 120)
    assert before.days[31].closing_fen - 15_000_000 < FLOOR


def test_with_no_receipt_that_keeps_the_floor_the_line_is_repaid_on_the_last_day(state):
    s = drawn(state, "FAC-LINE", 15_000_000)
    t = project(s, [], [], C, 120, 10**12)
    h = t.horizon_days
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-LINE") == [(h, -15_000_000)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-LINE") == [(h, -line_interest(15_000_000, 640, h))]
    assert debt(t, h, s) == 0 and debt(t, h - 1, s) == 15_000_000


def test_a_repay_action_repays_the_carried_balance_and_nothing_is_repaid_twice(state):
    s = drawn(state, "FAC-LINE", 15_000_000)
    repay = FundingAction(kind=FundingActionKind.REPAY, facility_id="FAC-LINE", day=5, amount_fen=10_000_000)
    t = project(s, [], [repay], C, 120, FLOOR)
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-LINE") == [(5, -10_000_000), (32, -5_000_000)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-LINE") == [
        (5, -line_interest(10_000_000, 640, 5)), (32, -line_interest(5_000_000, 640, 32))]
    with pytest.raises(FundingActionError):  # more than is drawn
        project(s, [], [repay.model_copy(update={"amount_fen": 15_000_001})], C, 120, FLOOR)


def test_the_carried_balance_counts_against_the_limit_until_repaid(state):
    s = drawn(state, "FAC-LINE", 15_000_000)  # the ¥150,000 line is fully drawn
    more = FundingAction(kind=FundingActionKind.DRAW, facility_id="FAC-LINE", day=0, amount_fen=1, repay_day=10)
    with pytest.raises(FundingActionError, match="above its limit"):
        project(s, [], [more], C, 120, FLOOR)


def test_a_term_bullet_loan_is_repaid_at_maturity(state):
    s = drawn(state, "FAC-GGL", 10_000_000, status=FacilityStatus.COMMITTED, owner_approved=True)
    t = project(s, [], [], E, 120, FLOOR)
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-GGL") == [(360, -10_000_000)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-GGL") == [(360, -line_interest(10_000_000, 500, 360))]
    assert t.horizon_days == 361


def test_an_amortising_balance_amortises_from_day_0(state):
    s = drawn(state, "FAC-ETL", 36_000_000, status=FacilityStatus.COMMITTED, owner_approved=True)
    t = project(s, [], [], E, 120, FLOOR)
    principal = events(t, LedgerEventKind.REPAYMENT, "FAC-ETL")
    assert [d for d, _ in principal][:3] == [30, 60, 90] and all(a < 0 for _, a in principal)
    assert debt(t, 29, s) == 36_000_000 and debt(t, 30, s) == 36_000_000 + principal[0][1]


# ---------------------------------------------------------------- invoice financing


def test_a_financed_receivable_repays_its_advance_on_its_due_day(state):
    f = fac(state, "FAC-IF")
    advance = 33_600_000  # 80% of RCV-A's ¥420,000
    s = drawn(financed(state), "FAC-IF", advance)
    t = project(s, [], [], C, 120, FLOOR)
    interest, fee, _periods = finance_invoice_charges(f, advance, 32)
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-IF") == [(32, -advance)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-IF") == [(32, -interest)]
    assert events(t, LedgerEventKind.FEE, "FAC-IF") == [(32, -fee)]
    assert events(t, LedgerEventKind.RECEIPT, "RCV-A") == [(32, 42_000_000)]  # the buyer still pays the face
    assert debt(t, 31, s) == advance and debt(t, 32, s) == 0
    with pytest.raises(FundingActionError, match="already financed"):
        project(s, [], [finance(1_000_000)], C, 120, FLOOR)


def test_an_advance_no_financed_receivable_explains_is_repaid_at_the_horizon_end(state):
    s = drawn(state, "FAC-IF", 5_000_000)
    t = project(s, [], [], C, 120, FLOOR)
    h = t.horizon_days
    interest, fee, _ = finance_invoice_charges(fac(s, "FAC-IF"), 5_000_000, h)
    assert events(t, LedgerEventKind.REPAYMENT, "FAC-IF") == [(h, -5_000_000)]
    assert events(t, LedgerEventKind.INTEREST, "FAC-IF") == [(h, -interest)]
    assert events(t, LedgerEventKind.FEE, "FAC-IF") == [(h, -fee)]


def test_nothing_changes_when_nothing_is_drawn(state):
    assert project(state, [], [], C, 120, FLOOR).days == project(state, [], [], C, 120).days
