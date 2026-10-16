"""What happens if the buyer refuses: the funding a refused send runs, read without running it.

A send that ends without a deal runs the Debt Desk's plan for the gap on the books as they stand (`decide._negotiate_locked`, its no-deal branch):
the router's committed plan, executed leg by leg when every leg can be run today. This module is that branch's own plan and runnability check, taken
out so the route and the picture read one function, plus the sentence the picture says about it. Nothing here executes, stores or logs anything."""

from __future__ import annotations

from typing import Any

from app.api.presentation import t as say
from app.api.presentation import when_text, whole
from app.books import current_books
from app.domain.models import FundingActionKind
from app.domain.money import fmt_yuan
from app.funding import plan
from app.strategy.cache import AnswerCache, cache_key


def refusal_plan(state: Any, commitments: Any, mandate: Any) -> Any:
    """The plan a refused send funds the near-term gap with: the router's committed plan on the books as they stand, with no new terms."""
    books = current_books(state, commitments)
    return plan(books.state, books.with_([]), mandate)


_PLANS: AnswerCache[Any] = AnswerCache(8)


def clear_cache() -> None:
    _PLANS.clear()


def cached_refusal_plan(state: Any, commitments: Any, mandate: Any) -> Any:
    """`refusal_plan`, for the reads (the picture): it is a router search over the whole book, the same for every offer and in either language
    (it has no words), so it is cached by the books, the commitments and the mandate with single-flight, and the plan is only read. The send
    that really runs the plan (`decide`) calls `refusal_plan` itself."""
    commitments = tuple(commitments)
    key = cache_key(state, mandate, state.as_of_day, commitments, "refusal-plan")
    return _PLANS.get_or_compute(key, lambda: refusal_plan(state, commitments, mandate))


def runnable(gap_plan: Any) -> str | None:
    """Why the gap plan is not run today ('' never): the router's own "cannot run today" reason, or a leg no
    operation can run. None when every leg can be sent."""
    if not gap_plan.actions:
        return None
    if not gap_plan.executable_now:
        return gap_plan.not_executable_reason or "it cannot run today"
    if any(a.kind not in (FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE) or
           (a.kind == FundingActionKind.FINANCE_INVOICE and not a.receivable_id) for a in gap_plan.actions):
        return "it relies on a step no operation can run (a buyer paying early or a bill discount)"
    return None


def if_refused_text(gap_plan: Any, state: Any, buyer: str, today: int, lang: str) -> str | None:
    """What FLOW will do if the buyer refuses, with the amounts: each leg the refused send would run, its facility, its landing day and the plan's
    funding cost. None when nothing would run (the books need no funding, or the plan cannot run today)."""
    if not gap_plan.actions or runnable(gap_plan) is not None:
        return None
    legs = []
    for a in gap_plan.actions:
        when = when_text(a.lands_day if a.lands_day is not None else a.day, today, lang)
        if a.kind == FundingActionKind.DRAW:
            legs.append(say(lang, f"a {whole(a.amount_fen)} credit-line draw {when}", f"信用额度提款 {whole(a.amount_fen)}（{when}）"))
        else:
            legs.append(say(lang, f"{whole(a.amount_fen)} of invoice financing {when}", f"发票融资 {whole(a.amount_fen)}（{when}）"))
    cost = fmt_yuan(gap_plan.total_cost_fen)
    joined = say(lang, " and ", "、").join(legs)
    return say(lang, f"If {buyer} refuses, FLOW will fund the gap on its own: {joined}. The funding costs {cost}.",
               f"如果{buyer}拒绝，FLOW 将自行为缺口融资：{joined}。融资成本为 {cost}。")
