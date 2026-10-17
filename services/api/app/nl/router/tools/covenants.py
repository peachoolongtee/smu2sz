"""Covenant tools: whether the loan covenants hold, where they would break, and whether FLOW's plan keeps them."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers.answers import a_breakpoints, a_covenants, a_plan_covenants
from app.nl.router.tools.common import Spec, obj, writer


def covenant_status(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_covenants(writer(ctx, lang), "")  # no breach or plan words: "are we inside?", on today's books


def covenant_breakpoints(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_breakpoints(writer(ctx, lang), "")


def plan_covenants(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_plan_covenants(writer(ctx, lang), "")


SPECS: tuple[Spec, ...] = (
    Spec("covenant_status", "Whether the loan covenants hold over the forecast: the worst debt service coverage and leverage "
         "against their limits.", obj(), covenant_status),
    Spec("covenant_breakpoints", "What would break the covenants: the most monthly debt service and total debt the company can "
         "carry.", obj(), covenant_breakpoints),
    Spec("plan_covenants", "Whether FLOW's funding plan would keep the loan covenants.", obj(), plan_covenants),
)
