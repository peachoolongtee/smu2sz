"""The egress guard: the last deterministic check before any text reaches a counterparty.

Outbound text is already template-filled from an allow-list of fields (INVARIANTS 7). This guard is
defence in depth behind that: it scans the final text for every protected value the recipient is not
entitled to and, on any leak, blocks the whole message. The recipient then gets a fixed safe
template, and a DATA_EXTRACTION security event records the protected labels (never the values).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import CounterProposal, Obligation, SecurityEvent, SecurityEventKind
from app.egress.protected import Leak, ProtectedSet, scan
from app.egress.values import AllowedValue, Category

Lang = Literal["en", "zh"]

SAFE_TEMPLATES: dict[Lang, str] = {
    "en": "We can't share internal financial details. Our offer stands as stated.",
    "zh": "我方无法提供内部财务信息。我方报价以已说明的条款为准。",
}
ACTION_TAKEN = "outbound message blocked"


class GuardResult(BaseModel):
    """`text_out` is the text to send: the original when `ok`, otherwise the safe template."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    ok: bool
    text_out: str
    leaks: list[Leak]
    security_event: SecurityEvent | None = None


def _detect_lang(text: str) -> Lang:
    cjk = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "zh" if cjk > latin else "en"


def _event(leaks: list[Leak], recipient_id: str, day: int, trace_id: str | None) -> SecurityEvent:
    labels = sorted({leak.label for leak in leaks})
    canaries = [x for x in labels if x.startswith("canary.")]
    basis = "|".join([recipient_id, str(day), trace_id or "", *labels])
    event_id = "SEC-EGRESS-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    detail = (
        f"Outbound message to {recipient_id} withheld: it stated {len(labels)} protected value(s) "
        f"({', '.join(labels)}). The safe template was sent instead."
    )
    if canaries:
        detail += f" Canary tripped: {', '.join(canaries)}."
    return SecurityEvent(
        id=event_id,
        day=day,
        kind=SecurityEventKind.DATA_EXTRACTION,
        counterparty_id=recipient_id,
        action_taken=ACTION_TAKEN,
        detail=detail,
        trace_id=trace_id,
    )


def guard(
    text: str,
    protected: ProtectedSet,
    *,
    recipient_id: str,
    allow: Iterable[AllowedValue] = (),
    day: int,
    trace_id: str | None = None,
    lang: Lang | None = None,
) -> GuardResult:
    """Pass `text` through unchanged, or block it whole if it leaks a protected value.

    `allow` lists what this specific message may state (the counter's own rate and face, the
    recipient's own invoice amount); values the recipient owns are allowed automatically.
    `lang` picks the safe template; by default it follows the text's script.
    """
    leaks = scan(text, protected, recipient_id=recipient_id, allow=allow)
    if not leaks:
        return GuardResult(ok=True, text_out=text, leaks=[])
    template = SAFE_TEMPLATES[lang or _detect_lang(text)]
    return GuardResult(ok=False, text_out=template, leaks=leaks,
                       security_event=_event(leaks, recipient_id, day, trace_id))


def allowed_from_obligations(obligations: Iterable[Obligation]) -> list[AllowedValue]:
    """The rates and amounts a message stating these obligations is entitled to repeat."""
    out: list[AllowedValue] = []
    for o in obligations:
        if o.rate_bp:
            out.append(AllowedValue.rate_bp(o.rate_bp))
        if o.amount_fen:
            out.append(AllowedValue.money(abs(o.amount_fen)))
        if o.base.amount_fen:
            out.append(AllowedValue.money(o.base.amount_fen))
    return out


def allowed_for_counter(counter: CounterProposal) -> list[AllowedValue]:
    """Allow-list for a counter's own outbound text: its obligations' rates, faces and amounts."""
    return allowed_from_obligations(counter.obligations)


def is_canary(leak: Leak) -> bool:
    return leak.category is Category.CANARY
