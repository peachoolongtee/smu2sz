"""Template verbaliser for buyer replies (en + zh), with an optional, fenced LLM hook.

The decision and every number are fixed before any wording happens. `PublicMessageFields` holds
only already-decided public fields (reply kind, round, the proposal labels and pre-formatted
clause strings); no reservation value can reach it. The template renders those fields and
records the character range of each clause, so typed obligations can carry an exact span.

An optional hook (e.g. an LLM) may rephrase the message. Its output is used only if it keeps
every clause verbatim and introduces no number that the template text does not already
contain; otherwise the template text is used. The hook can only verbalise.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.domain.models import Contract

Lang = Literal["en", "zh"]
LANGS: tuple[Lang, ...] = ("en", "zh")

# "early_settlement_named" names the invoice in words ("the ¥300,000.00 invoice dated 29 Sep 2026") and the settlement by its calendar
# date: the buyer's reply on books the owner opened, whose invoices carry no number the buyer knows (app/counterparties/books.py).
ClauseKey = Literal["early_settlement", "early_settlement_named", "terms", "rebate"]


class ReplyKind(StrEnum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"
    REJECT = "REJECT"  # nothing acceptable and nothing to counter with
    REJECT_FINAL = "REJECT_FINAL"  # last allowed round
    REJECT_EXHAUSTED = "REJECT_EXHAUSTED"  # round > max_rounds


class Clause(Contract):
    """One public clause of a counter-proposal; params are pre-formatted display strings."""

    key: ClauseKey
    params: dict[str, str]


class PublicMessageFields(Contract):
    """The only input a verbaliser (template or LLM) ever receives."""

    kind: ReplyKind
    round: int = Field(ge=1)
    labels: list[str]
    clauses: list[Clause] = Field(default_factory=list)


_OPENERS: dict[Lang, dict[ReplyKind, str]] = {
    "en": {
        ReplyKind.ACCEPT: "Round {round}. We accept {labels} as proposed.",
        ReplyKind.COUNTER: "Round {round}. We have considered {labels} and cannot accept as proposed. We propose: ",
        ReplyKind.REJECT: "Round {round}. We cannot accept {labels} and will keep our existing terms.",
        ReplyKind.REJECT_FINAL: (
            "Round {round}. We cannot accept {labels}. This is our final round, "
            "so we will keep our existing terms."
        ),
        ReplyKind.REJECT_EXHAUSTED: (
            "Round {round}. The negotiation window has closed, so we cannot consider {labels}. "
            "We will keep our existing terms."
        ),
    },
    "zh": {
        ReplyKind.ACCEPT: "第{round}轮。我方接受{labels}。",
        ReplyKind.COUNTER: "第{round}轮。我方已考虑{labels}，无法按此接受。我方提议：",
        ReplyKind.REJECT: "第{round}轮。我方无法接受{labels}，将维持现有条款。",
        ReplyKind.REJECT_FINAL: "第{round}轮。我方无法接受{labels}。本轮为最后一轮，我方将维持现有条款。",
        ReplyKind.REJECT_EXHAUSTED: "第{round}轮。谈判轮次已用完，我方无法考虑{labels}，将维持现有条款。",
    },
}

_CLAUSES: dict[Lang, dict[str, str]] = {
    "en": {
        "early_settlement": "early settlement of invoice {receivable} ({face}) on day {day} at a {rate} discount",
        "early_settlement_named": "early settlement of {invoice_en} on {when_en} at a {rate} discount",
        "terms": "{days}-day payment terms on future invoices",
        "rebate": "a {rate} rebate on next quarter's purchases of up to {base}",
    },
    "zh": {
        "early_settlement": "第{day}天提前结算发票{receivable}（{face}），折扣{rate}",
        "early_settlement_named": "{when_zh}提前结算{invoice_zh}，折扣{rate}",
        "terms": "今后发票账期{days}天",
        "rebate": "下季度采购（上限{base}）返利{rate}",
    },
}

_SEP: dict[Lang, str] = {"en": "; ", "zh": "；"}
_END: dict[Lang, str] = {"en": ".", "zh": "。"}
_LABEL_JOIN: dict[Lang, str] = {"en": " or ", "zh": "或"}

YOUR_PROPOSAL = "your proposal"
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9 \-]{1,40}$")
_OPTION = re.compile(r"^Option ([A-Za-z0-9]{1,4})$")


def public_label(label: str | None) -> str:
    """Echo a proposal label only if it is a short, plain label; anything else is generic."""
    if label and _SAFE_LABEL.match(label):
        return label
    return YOUR_PROPOSAL


def _label(label: str, lang: Lang) -> str:
    if lang == "en":
        return label
    if label == YOUR_PROPOSAL:
        return "贵方提议"
    m = _OPTION.match(label)
    return f"方案{m.group(1)}" if m else label


@dataclass(frozen=True)
class Rendered:
    text: str
    clause_spans: tuple[tuple[int, int], ...]  # one (start, end) per clause, in order
    source: Literal["template", "hook"] = "template"


def render(fields: PublicMessageFields, lang: Lang) -> Rendered:
    """Deterministic template rendering with exact clause offsets."""
    labels = _LABEL_JOIN[lang].join(_label(label, lang) for label in fields.labels) or _label(
        YOUR_PROPOSAL, lang
    )
    text = _OPENERS[lang][fields.kind].format(round=fields.round, labels=labels)
    spans: list[tuple[int, int]] = []
    if fields.kind is ReplyKind.COUNTER:
        for i, clause in enumerate(fields.clauses):
            if i:
                text += _SEP[lang]
            piece = _CLAUSES[lang][clause.key].format(**clause.params)
            spans.append((len(text), len(text) + len(piece)))
            text += piece
        text += _END[lang]
    return Rendered(text=text, clause_spans=tuple(spans))


VerbaliserHook = Callable[[PublicMessageFields, Lang], str]

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_MAX_HOOK_CHARS = 2000


def verbalise(fields: PublicMessageFields, lang: Lang, hook: VerbaliserHook | None = None) -> Rendered:
    """Template text, or the hook's rephrasing if it passes the fence (see module docstring)."""
    base = render(fields, lang)
    if hook is None:
        return base
    try:
        candidate = hook(fields, lang)
    except Exception:  # noqa: BLE001 - a failing verbaliser never changes the decision
        return base
    if not isinstance(candidate, str) or not candidate.strip() or len(candidate) > _MAX_HOOK_CHARS:
        return base
    if not set(_NUMBER.findall(candidate)) <= set(_NUMBER.findall(base.text)):
        return base
    spans: list[tuple[int, int]] = []
    pos = 0
    for start, end in base.clause_spans:
        piece = base.text[start:end]
        at = candidate.find(piece, pos)
        if at < 0:
            return base
        spans.append((at, at + len(piece)))
        pos = at + len(piece)
    return Rendered(text=candidate, clause_spans=tuple(spans), source="hook")
