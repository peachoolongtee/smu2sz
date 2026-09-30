"""Debt Desk: funding menu, same-basis costing, grid-search router, marginal cost, break-even.

Public interface: `menu_view()`, `plan()`, `compare()`, `marginal_cost()`, `break_even_discount()`,
`extension_cost_bases()`, and `Router`, which satisfies `app.domain.ports.FundingRouter`.
The router never computes cash itself: every candidate runs through `financial.project`.
"""

from app.funding.extension import extension_cost_bases
from app.funding.menu import menu_view
from app.funding.models import ComparisonResult, ComparisonRow, MenuRow
from app.funding.rates import NoPermanentSourceError, all_in_rate, break_even_discount, marginal_cost
from app.funding.router import Router, compare, plan

__all__ = [
    "ComparisonResult",
    "ComparisonRow",
    "MenuRow",
    "NoPermanentSourceError",
    "Router",
    "all_in_rate",
    "break_even_discount",
    "compare",
    "extension_cost_bases",
    "marginal_cost",
    "menu_view",
    "plan",
]
