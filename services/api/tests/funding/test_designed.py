"""Designed cases where the grid search beats "draw the line first, then the cheapest next source"."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app.funding.router as router_mod
from app.domain.models import FundingActionKind, Mode
from app.financial import project
from app.funding import plan
from app.funding.search import Search
from tests.funding import cases
from tests.funding.baseline import line_first_then_cheapest
from tests.funding.variants import pricing_only

# (case, expected router cost in fen, baseline admissible?). The golden gap is ¥405,000: 340,000 + 120,000 + the
# existing loan's ¥45,000 day-30 payment + the 300,000 reserve − 400,000 cash (FINANCIAL_SEMANTICS §5).
DESIGNED = [
    # the whole ¥400,000 of bills at 0.58% for 179 days: 400,000 × 0.58% × 179/365 = 1,137.75 (nets 398,862.25);
    # the line carries the other 6,137.75 for 32 days at 6.4%: 34.44. Total 1,172.19
    ("bill_held", 117_219, True),
    # IF capped at 80% of RCV-A, 336,000: 336,000 × 7.8% × 30/365 = 2,154.08 + fee 840.00; the line the other
    # 69,000 at 11.5% for 32 days: 695.67. Total 3,689.75
    ("dear_line", 368_975, True),
    # early payment only, at 0.3%: face 405,000 / 0.997 = 406,218.66, discount 1,218.66
    ("cheap_early_pay", 121_866, True),
    # line 150,000 (841.64) + IF 90,000 (576.99 + fee 225.00) + early pay netting 165,000 at 1.2% (face
    # 167,004.05, discount 2,004.05). Total 3,647.68; line-first breaks leverage
    ("leverage_tight", 364_768, False),
    # early payment only: face 405,000 / 0.988 = 409,919.03, discount 4,919.03; line-first borrows
    ("no_new_borrowing", 491_903, False),
    # no existing loan in this case (cases.long_gap): the ¥360,000 gap, early payment face 364,372.47 at 1.2% =
    # 4,372.47; line-first breaks the clean-down
    ("long_gap", 437_247, False),
]


PRICING = pricing_only(Search)  # the search's arithmetic, with early pay and bills priced as runnable legs


def _priced(s, m):
    with patch.object(router_mod, "Search", PRICING):
        return plan(s, [], m)


@pytest.mark.parametrize("name,cost,baseline_ok", DESIGNED)
def test_router_beats_line_first(name, cost, baseline_ok):
    s, m = getattr(cases, name)()
    p = _priced(s, m)
    assert p.admissible
    assert p.total_cost_fen == cost
    assert sum(c.fen for c in p.costs) == p.total_cost_fen
    t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None
    base = line_first_then_cheapest(s, [], m)
    assert base.admissible is baseline_ok
    if baseline_ok:
        assert base.cost_fen is not None and p.total_cost_fen < base.cost_fen


def test_bill_held_uses_the_whole_bill_and_the_line_only_for_the_rest():
    s, m = cases.bill_held()
    p = _priced(s, m)
    # the ¥400,000 of bills nets 398,862.25 < the 405,000 gap: the line carries the 6,137.75 left
    assert sorted((a.kind, a.amount_fen) for a in p.actions) == [
        (FundingActionKind.DISCOUNT_BILL, 40_000_000), (FundingActionKind.DRAW, 613_775)]


# Red team d, F1: no operation discounts a bill or asks a buyer to pay early, so a plan holding such a leg cannot run
# today; the router ranks a plan that can run first. Where one exists (the line and the invoice advance) it is the
# plan, at the golden ¥3,113.93; where none does, the cheapest plan is still shown, flagged "cannot run today".
RUNNABLE = [("bill_held", 311_393, True), ("cheap_early_pay", 311_393, True), ("dear_line", 368_975, True),
            ("leverage_tight", 364_768, False), ("no_new_borrowing", 491_903, False), ("long_gap", 437_247, False)]


@pytest.mark.parametrize("name,cost,runnable", RUNNABLE)
def test_a_plan_that_can_run_ranks_before_a_cheaper_one_that_cannot(name, cost, runnable):
    s, m = getattr(cases, name)()
    p = plan(s, [], m)
    assert p.admissible and p.total_cost_fen == cost and p.executable_now is runnable
    priced = (FundingActionKind.EARLY_PAY, FundingActionKind.DISCOUNT_BILL)
    assert any(a.kind in priced for a in p.actions) is (not runnable)
    if not runnable:
        assert "needs the buyer's agreement to pay early" in p.not_executable_reason
        assert all(c.executable_now == (c.facility_id != "FAC-EARLYPAY") for c in p.costs)
    t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None


def test_dear_line_puts_most_of_the_gap_on_invoice_financing():
    s, m = cases.dear_line()
    p = plan(s, [], m)
    amounts = {a.facility_id: a.amount_fen for a in p.actions}
    assert amounts == {"FAC-IF": 33_600_000, "FAC-LINE": 6_900_000}  # IF capped at 80% of RCV-A; 405,000 − 336,000


def test_leverage_tight_keeps_new_debt_within_the_covenant():
    s, m = cases.leverage_tight()
    p = plan(s, [], m)
    # limit 2.5 × 12 × 90,000 = 2,700,000; month-1 end debt = 2,500,000 − 45,000 (the existing loan's day-30
    # payment) + new debt, so at most 245,000 of new debt
    debt = sum(a.amount_fen for a in p.actions if a.kind != FundingActionKind.EARLY_PAY)
    assert debt <= 24_500_000
    assert any(a.kind == FundingActionKind.EARLY_PAY for a in p.actions)


def test_no_new_borrowing_uses_no_debt():
    s, m = cases.no_new_borrowing()
    p = plan(s, [], m)
    assert p.actions and all(a.kind == FundingActionKind.EARLY_PAY for a in p.actions)


@pytest.mark.parametrize("name", ["bill_held", "dear_line", "cheap_early_pay", "leverage_tight"])
def test_pruning_does_not_change_the_optimum(name, monkeypatch):
    s, m = getattr(cases, name)()
    pruned = Search(s, [], m, "COMMITTED")
    pruned.run()
    monkeypatch.setattr(Search, "_beaten", lambda self, bound, flagged=False: False)
    full = Search(s, [], m, "COMMITTED")
    full.run()
    assert pruned.best is not None and full.best is not None
    assert pruned.best.rank() == full.best.rank()
