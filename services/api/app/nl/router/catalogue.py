"""The router's closed catalogue of read-only tools (ADR-0015). STUB: two tools only, so `feat/ask-router` runs on its own.

The full catalogue (about 30 to 45 tools and their en/zh writers) lives on `feat/ask-router-tools` and replaces this file. The
interface `route.py` codes to is fixed:

- `TOOLS: dict[str, Tool]`, where `Tool` is a frozen dataclass of `name`, `description` (one line, for the model), `slots_schema`
  (a JSON Schema object with `additionalProperties: false`, in the subset `app.nl.router.schema` validates) and
  `answer(ctx, lang, slots) -> AnswerReply` (ctx is the turn's `NlContext`, slots already validated);
- `catalogue_for_prompt() -> list[dict]`: `[{"name", "description", "parameters"}]`, with no data from the books: it is sent to
  the model.

Every tool reads; none writes, books, sends or executes. A customer named in a slot is free text the tool resolves itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.nl.answers.answers import AnswerReply, W, a_safe, a_total_debt
from app.nl.answers.metrics import Reading


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    slots_schema: dict[str, Any]
    answer: Callable[[Any, str, dict[str, Any]], AnswerReply]


def _w(ctx: Any, lang: str) -> W:
    return W(Reading.of(ctx), "zh" if lang == "zh" else "en")


def _cash_safety(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_safe(_w(ctx, lang), "")  # stub: the forecast horizon; the tools branch answers on the horizon asked


def _total_debt(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_total_debt(_w(ctx, lang), "")


_NO_SLOTS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("cash_safety", "Whether cash stays at or above the owner's minimum cash reserve over a horizon, and the lowest point.",
         {"type": "object", "additionalProperties": False,
          "properties": {"horizon_days": {"type": "integer", "minimum": 1, "maximum": 365,
                                          "description": "Days ahead the owner asks about; omit when not stated."}}},
         _cash_safety),
    Tool("total_debt", "How much the company owes in loans and drawn facilities, by loan and facility.", _NO_SLOTS, _total_debt),
)}


def catalogue_for_prompt() -> list[dict[str, Any]]:
    """What the model is shown: each tool's name, one-line description and slot schema. No figure, name or state."""
    return [{"name": t.name, "description": t.description, "parameters": t.slots_schema} for t in TOOLS.values()]
