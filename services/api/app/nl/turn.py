"""What one handler returns for one turn, before the reply is guarded and the response is built."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.models import Verdict
from app.egress import AllowedValue
from app.nl.models import Clarification, ClarifyOption, Intent, PlanStep, Slots
from app.nl.sessions import PendingClarification, PendingPlan


@dataclass
class Turn:
    intent: Intent
    reply: str
    plan: list[PlanStep] = field(default_factory=list)
    verdict: Verdict | None = None
    clarification: Clarification | None = None
    awaiting: bool = False
    pending: PendingPlan | None = None
    pending_clarification: PendingClarification | None = None
    clear_pending: bool = False
    negotiation: dict[str, Any] | None = None
    amended: bool = False
    recipient: str = "OWNER"
    allow: list[AllowedValue] = field(default_factory=list)
    guarded: bool = False  # the reply was already passed through the egress guard
    # Typed figures and ids the Business rewrite (app/nl/business.py) says in the owner's words; nothing in the engine reads them
    facts: dict[str, Any] = field(default_factory=dict)


def ask(intent: Intent, slot: str, question: str, options: list[tuple[str, str, Any]], slots: Slots) -> Turn:
    """One clarification question with options (id, label, typed value for `slot`)."""
    opts = [ClarifyOption(id=i, label=label) for i, label, _ in options]
    pc = PendingClarification(intent=intent, slot=slot, options=opts, slots=slots,
                              values={i: v for i, _, v in options})
    text = question + " " + " ".join(f"({i}) {label}" for i, label, _ in options)
    return Turn(intent=Intent.AMBIGUOUS, reply=text, clarification=Clarification(question=question, options=opts),
                pending_clarification=pc)
