"""The one shared "no committed plan" state of the three strategy routes (map #58, ticket #79).

Every price in the strategy answers is read against the router's COMMITTED plan for the books as they stand: the curve's
value of earlier cash, a receivable's saving, the envelope's cost line. When the router finds no admissible plan (the
breach starts today and no committed facility lands in time, the state the alerts call "No committed facility can cure
it"), `FundingPlan.admissible` is false and its cost is read as 0. A cost of 0 is not a price: it made the curve go flat,
every worth row read "saves nothing extra" and every envelope cost line read ¥0.00 while the owner was already below the
floor. The state is named here once; each route turns it into its own sentence (price_curve, collections, envelope).

Read-only: it asks the planner the question the routes already ask, and nothing else.
"""

from __future__ import annotations

from app.books import Books
from app.domain.models import FundingPlan, Mandate
from app.funding import plan
from app.funding.router import shared_runs


def plan_is_missing(committed: FundingPlan) -> bool:
    """Whether this committed plan is not one: the router found no admissible plan that restores the reserve."""
    return not committed.admissible


def no_committed_plan(books: Books, mandate: Mandate) -> bool:
    """Whether the router finds no committed plan for these books (no obligations added), i.e. nothing to price against."""
    with shared_runs():
        return plan_is_missing(plan(books.state, books.with_([]), mandate))


__all__ = ["no_committed_plan", "plan_is_missing"]
