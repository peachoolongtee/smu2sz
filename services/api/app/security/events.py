"""Security-event helpers for compiler flags that no other module logs today.

The verifier's screen logs unknown counterparties, unevidenced claims and data requests. Authority
claims (fake SYSTEM lines, "the owner approved", "ignore previous instructions", urgency) are flagged
by the compiler but, as of this commit, never become a `SecurityEvent`, so the audit trail misses
injection attempts that the verifier then rejects on economics alone (evals/security finding F-09).
`flag_events` turns those flags into INJECTION events; the offer-evaluation route (or /nl) can append
them next to the verifier's events. Logging only: nothing here decides or refuses anything.

Depends on `app.domain` only.
"""

from __future__ import annotations

from collections import defaultdict

from app.domain.models import CompiledOffer, CompiledTermSheet, SecurityEvent, SecurityEventKind, SourceSpan

ACTION_TAKEN = "flagged; no authority granted, nothing booked by this flag"


def flag_events(item: CompiledOffer | CompiledTermSheet, day: int, counterparty_id: str | None = None) -> list[SecurityEvent]:
    """One INJECTION event per authority-claim kind (PRE_APPROVAL, PRIOR_AGREEMENT,
    INSTRUCTION_OVERRIDE, URGENCY, IMPERSONATION), carrying every span of that kind. Deterministic
    ids, so logging the same offer twice yields the same event ids."""
    if isinstance(item, CompiledOffer):
        ref, cp = f"{item.offer_id}-v{item.version}", counterparty_id or item.counterparty_id
    else:
        ref, cp = item.doc_id, counterparty_id
    by_kind: dict[str, list[SourceSpan]] = defaultdict(list)
    for claim in item.authority_claims:
        by_kind[claim.kind].append(claim.span)
    return [
        SecurityEvent(
            id=f"SEC-FLAG-{ref}-{kind}",
            day=day,
            kind=SecurityEventKind.INJECTION,
            counterparty_id=cp,
            action_taken=ACTION_TAKEN,
            detail=f"{kind}: {len(spans)} authority claim(s) in counterparty text; the text carries no authority",
            spans=spans,
        )
        for kind, spans in sorted(by_kind.items())
    ]
