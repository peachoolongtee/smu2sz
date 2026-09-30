"""Designed cases where the grid search beats "draw the line first, then the cheapest next source"."""

from __future__ import annotations

import pytest

from app.domain.models import FundingActionKind, Mode
from app.financial import project
from app.funding import plan
from app.funding.search import Search
from tests.funding import cases
from tests.funding.baseline import line_first_then_cheapest

# (case, expected router cost in fen, baseline admissible?)
DESIGNED = [
    ("bill_held", 102_690, True),  # discount ¥361,026.90 of bills: ¥1,026.90
    ("dear_line", 323_605, True),  # line ¥24,000 + IF ¥336,000
    ("cheap_early_pay", 108_325, True),  # early payment only, at 0.3%
    ("leverage_tight", 323_051, False),  # line + IF ¥50,000 + early pay; line-first breaks leverage
    ("no_new_borrowing", 437_247, False),  # early payment only; line-first borrows
    ("long_gap", 437_247, False),  # line-first breaks the clean-down
]


@pytest.mark.parametrize("name,cost,baseline_ok", DESIGNED)
def test_router_beats_line_first(name, cost, baseline_ok):
    s, m = getattr(cases, name)()
    p = plan(s, [], m)
    assert p.admissible
    assert p.total_cost_fen == cost
    assert sum(c.fen for c in p.costs) == p.total_cost_fen
    t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None
    base = line_first_then_cheapest(s, [], m)
    assert base.admissible is baseline_ok
    if baseline_ok:
        assert base.cost_fen is not None and p.total_cost_fen < base.cost_fen


def test_bill_held_uses_only_the_bill():
    s, m = cases.bill_held()
    p = plan(s, [], m)
    assert [a.kind for a in p.actions] == [FundingActionKind.DISCOUNT_BILL]


def test_dear_line_puts_most_of_the_gap_on_invoice_financing():
    s, m = cases.dear_line()
    p = plan(s, [], m)
    amounts = {a.facility_id: a.amount_fen for a in p.actions}
    assert amounts == {"FAC-IF": 33_600_000, "FAC-LINE": 2_400_000}  # IF capped at 80% of RCV-A


def test_leverage_tight_keeps_new_debt_within_the_covenant():
    s, m = cases.leverage_tight()
    p = plan(s, [], m)
    debt = sum(a.amount_fen for a in p.actions if a.kind != FundingActionKind.EARLY_PAY)
    assert debt <= 20_000_000
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
    monkeypatch.setattr(Search, "_beaten", lambda self, bound: False)
    full = Search(s, [], m, "COMMITTED")
    full.run()
    assert pruned.best is not None and full.best is not None
    assert pruned.best.rank() == full.best.rank()
