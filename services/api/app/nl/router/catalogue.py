"""The tool catalogue of the Ask FLOW router: "the model routes, code answers; the model never sees the books".

`TOOLS` maps each tool's name to a `Tool`: a one-line description for the model, the JSON Schema (draft 2020-12) of its slots,
and the function that answers it from the books, in English or Chinese, read-only. `catalogue_for_prompt()` is what the
router sends the model: names, descriptions and slot schemas only, the same for every company and every day, with no name,
figure or id from the books. `validate_slots()` checks a model's slots against a tool's schema (the router's guard; the
tools also tolerate a missing optional slot).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from app.financial import EngineError
from app.nl.answers import AnswerReply
from app.nl.context import NlContext
from app.nl.router.tools import AREAS
from app.nl.router.tools.common import Spec, writer


@dataclass(frozen=True)
class Tool:
    name: str
    description: str  # one line for the model; no data
    slots_schema: dict[str, Any]  # JSON Schema object, additionalProperties: false, every field typed with enums/ranges
    answer: Callable[[NlContext, str, dict[str, Any]], AnswerReply]  # ctx, lang ("en"|"zh"), validated slots


def _tagged(spec: Spec) -> Callable[[NlContext, str, dict[str, Any]], AnswerReply]:
    """The tool's answer, tagged with the tool and its slots (`extra`), and honest when the books cannot be projected."""

    def answer(ctx: NlContext, lang: str, slots: dict[str, Any]) -> AnswerReply:
        lang = "zh" if lang == "zh" else "en"
        try:
            reply = spec.answer(ctx, lang, dict(slots or {}))
        except EngineError:
            w = writer(ctx, lang)
            reply = AnswerReply(text=w.t("I could not project the books just now, so I cannot answer that.",
                                         "暂时无法预测账目，因此无法回答。"),
                                metric_ids=[], figures={}, basis=w.basis("books"), question_id=spec.name, lang=lang)
        return replace(reply, extra={**reply.extra, "tool": spec.name, "slots": dict(slots or {})})

    answer.__name__ = spec.name
    return answer


def _build() -> dict[str, Tool]:
    out: dict[str, Tool] = {}
    for area in AREAS:
        for spec in area.SPECS:
            if spec.name in out:
                raise ValueError(f"two tools are named {spec.name}")
            out[spec.name] = Tool(spec.name, spec.description, spec.slots_schema, _tagged(spec))
    return out


TOOLS: dict[str, Tool] = _build()


def catalogue_for_prompt() -> list[dict[str, Any]]:
    """[{"name", "description", "parameters"}] for every tool: safe to send to the model (no books data)."""
    return [{"name": t.name, "description": t.description, "parameters": t.slots_schema} for t in TOOLS.values()]


class SlotError(ValueError):
    """A model's slots that do not fit the tool's schema. `code` is a fixed reason (unknown_slot, missing_slot, wrong_type,
    out_of_range, bad_value, malformed); the message may quote the model's own keys, so only the code is ever logged."""

    def __init__(self, message: str, code: str = "malformed") -> None:
        super().__init__(message)
        self.code = code


def validate_slots(tool: Tool | str, slots: Any) -> dict[str, Any]:
    """The slots, checked against the tool's schema (the subset of JSON Schema the catalogue uses: an object of integers, strings
    and booleans with bounds, lengths, enums, required fields and no other properties). Raises SlotError."""
    t = TOOLS[tool] if isinstance(tool, str) else tool
    schema = t.slots_schema
    if slots is None:
        slots = {}
    if not isinstance(slots, dict):
        raise SlotError("slots must be an object", "malformed")
    props: dict[str, Any] = schema.get("properties", {})
    extra = set(slots) - set(props)
    if extra and schema.get("additionalProperties") is False:
        raise SlotError(f"unknown slots: {sorted(extra)}", "unknown_slot")
    missing = [k for k in schema.get("required", []) if k not in slots]
    if missing:
        raise SlotError(f"missing slots: {missing}", "missing_slot")
    for key, value in slots.items():
        p = props[key]
        kind = p.get("type")
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise SlotError(f"{key} must be an integer", "wrong_type")
            if "minimum" in p and value < p["minimum"] or "maximum" in p and value > p["maximum"]:
                raise SlotError(f"{key} is out of range", "out_of_range")
        elif kind == "string":
            if not isinstance(value, str):
                raise SlotError(f"{key} must be a string", "wrong_type")
            if len(value) < p.get("minLength", 0) or len(value) > p.get("maxLength", len(value)):
                raise SlotError(f"{key} has the wrong length", "bad_value")
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise SlotError(f"{key} must be a boolean", "wrong_type")
        if "enum" in p and value not in p["enum"]:
            raise SlotError(f"{key} is not one of the allowed values", "bad_value")
    return dict(slots)


__all__ = ["TOOLS", "SlotError", "Tool", "catalogue_for_prompt", "validate_slots"]
