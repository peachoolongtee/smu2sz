"""Deals tools: what waits for the owner, and the approvals queue."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers.answers import a_approvals, a_waiting
from app.nl.router.tools.common import Spec, obj, writer


def waiting_for_me(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_waiting(writer(ctx, lang), "")


def approvals_pending(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_approvals(writer(ctx, lang), "")


SPECS: tuple[Spec, ...] = (
    Spec("waiting_for_me", "What is waiting for the owner: a plan to approve, approvals, late customers and deals that need them.",
         obj(), waiting_for_me),
    Spec("approvals_pending", "Whether any operation is waiting for the owner's approval, and what each one is.", obj(),
         approvals_pending),
)
