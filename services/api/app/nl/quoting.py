"""The quote of a plan the owner is shown in chat (ADR-0011 section 2, QUOTED; wayfinder #65, ticket #84).

When a chat turn proposes a plan, the economics shown are fixed into a `QuotedFact` and kept beside the plan in the owner's session
(`PendingPlan.quote`), built from the same alert, router plan and cost lines the words were. The owner's later "go ahead" runs
those operations; the API layer (`app/api/nl.py`) then records the stored quote as the decision's QUOTED fact. Nothing here is written to
a store, and nothing is priced: a quote that cannot be built is simply absent, and the plan is proposed and run exactly as before.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from app.api import quotes
from app.decisions.facts import QuotedFact
from app.domain.models import FundingPlan
from app.nl.context import NlContext
from app.nl.sessions import PendingPlan

log = logging.getLogger("termsledger.decisions")


def stash(pending: PendingPlan, build: Callable[[], QuotedFact]) -> None:
    """Keep the quote beside the plan. A failure to build it is logged and leaves the plan without one."""
    try:
        pending.quote = build()
    except Exception:
        log.exception("the quote for a chat plan could not be built")


def of_plan(ctx: NlContext, ops: Sequence[Any], *, plan: FundingPlan | None = None, alert_kind: str = "OPERATION") -> QuotedFact:
    """The quote for `ops` that no alert produced: the router `plan` they were built from (one operation per action), or just the
    operations' own amounts and landing days (a direct draw, a repayment)."""
    did = quotes.decision_id_of(ops[0])
    if did is None:
        raise ValueError("the operations belong to no decision")
    books = ctx.books()
    return quotes.build_shown_quote(books.state, ctx.mandate(), ops, max(ctx.day, books.state.as_of_day), decision_id=did,
                                    alert_kind=alert_kind, plan=plan, obs=books.with_([]) if plan is not None else None,
                                    total_cost_fen=plan.total_cost_fen if plan is not None else None)


__all__ = ["of_plan", "stash"]
