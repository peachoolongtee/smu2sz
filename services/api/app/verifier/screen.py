"""Security screen (verdict algorithm step 2). Nothing it flags is ever booked; every flag is a
violation plus one `SecurityEvent` per violation code carrying all of that code's spans.

- A sender not on the owner's registry, and every unsolicited funding claim: UNKNOWN_COUNTERPARTY.
  No facility is added (INVARIANT 3).
- A CLAIMED_PRIOR_CONCESSION with no matching ledger commitment: UNEVIDENCED_PRIOR_CONCESSION.
- Every data request: DATA_EXTRACTION_REFUSED. The reply is a fixed template that discloses nothing
  (INVARIANT 7).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.models import (
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    FinancialState,
    Obligation,
    SecurityEvent,
    SecurityEventKind,
    SourceSpan,
    Violation,
    ViolationCode,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.verifier.bind import is_claimed

REFUSAL_REPLY = "We are not able to share internal financial, facility or counterparty information."
LIVE_COMMITMENTS = frozenset({CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE})

EVENT_KIND = {
    ViolationCode.UNKNOWN_COUNTERPARTY: SecurityEventKind.UNKNOWN_COUNTERPARTY,
    ViolationCode.UNEVIDENCED_PRIOR_CONCESSION: SecurityEventKind.UNEVIDENCED_CLAIM,
    ViolationCode.DATA_EXTRACTION_REFUSED: SecurityEventKind.DATA_EXTRACTION,
}
SECURITY_CODES = frozenset(EVENT_KIND)


def known_counterparty(state: FinancialState, counterparty_id: str) -> bool:
    return any(c.id == counterparty_id and c.known for c in state.counterparties)


def _evidenced(claim: Obligation, state: FinancialState, commitments: Sequence[Commitment]) -> bool:
    """A claim is evidenced only by a typed ledger row with the same counterparty and the same
    stated rate or amount. A claim that states neither cannot be matched, so it is unevidenced."""
    if claim.rate_bp is None and claim.amount_fen is None:
        return False
    for c in commitments:
        if c.counterparty_id != claim.counterparty_id or c.status not in LIVE_COMMITMENTS:
            continue
        for ob in c.obligations:
            if claim.rate_bp is not None and ob.rate_bp == claim.rate_bp:
                return True
            if claim.amount_fen is not None and ob.amount_fen == claim.amount_fen:
                return True
    return claim.amount_fen is not None and any(
        fc.counterparty_id == claim.counterparty_id and fc.commitment_id is not None and fc.value_fen == claim.amount_fen
        for fc in state.forward_concessions
    )


def screen(
    offer: CompiledOffer,
    state: FinancialState,
    *,
    day: int,
    commitments: Sequence[Commitment] = (),
) -> tuple[list[Violation], list[SecurityEvent]]:
    violations: list[Violation] = []
    sender_known = known_counterparty(state, offer.counterparty_id)

    if not sender_known or offer.funding_claims:
        spans: list[SourceSpan] = [f.span for f in offer.funding_claims]
        if not spans:
            spans = [sp for ob in offer.obligations for sp in ob.spans]
        inputs = {"sender": offer.counterparty_id, "sender_on_registry": str(sender_known).lower(),
                  "funding_claims": str(len(offer.funding_claims))}
        for n, f in enumerate(offer.funding_claims, start=1):
            amount = fmt_yuan(f.amount_fen) if f.amount_fen is not None else "no amount"
            rate = fmt_pct(bp(f.rate_bp)) if f.rate_bp is not None else "no rate"
            inputs[f"funding_claim_{n}"] = f"{amount} at {rate}: not on the owner's funding menu; no facility added"
        what = [] if sender_known else [f"sender {offer.counterparty_id} is not on the owner's registry"]
        what += [f"{len(offer.funding_claims)} unsolicited funding offer(s) in the message"] if offer.funding_claims else []
        violations.append(Violation(
            code=ViolationCode.UNKNOWN_COUNTERPARTY,
            message="Unknown counterparty: " + "; ".join(what) + ". Nothing is booked and no facility is added.",
            observed=offer.counterparty_id,
            limit="owner-registered counterparties and owner-approved facilities only",
            formula="sender ∈ registry ∧ funding claims = ∅ (only the owner adds facilities)",
            inputs=inputs,
            spans=spans,
        ))

    claims = [ob for ob in offer.obligations if is_claimed(ob)]
    unevidenced = [c for c in claims if not _evidenced(c, state, commitments)]
    if unevidenced:
        violations.append(Violation(
            code=ViolationCode.UNEVIDENCED_PRIOR_CONCESSION,
            message=f"{len(unevidenced)} claimed prior concession(s) with no matching commitment in the ledger; "
                    "not booked",
            observed=f"{len(unevidenced)} unevidenced claim(s)",
            limit="a matching ledger commitment",
            formula="claim ∈ ledger commitments (same counterparty and stated rate or amount)",
            inputs={"claims": str(len(unevidenced)), "counterparty_id": offer.counterparty_id,
                    "booked": "0"},
            spans=[sp for c in unevidenced for sp in c.spans],
        ))

    if offer.data_requests:
        kinds = [r.kind.value for r in offer.data_requests]
        violations.append(Violation(
            code=ViolationCode.DATA_EXTRACTION_REFUSED,
            message=f"{len(kinds)} request(s) for protected information refused; the reply discloses nothing",
            observed=", ".join(kinds),
            limit="no protected data leaves the ledger",
            formula="protected fields ∩ outbound fields = ∅",
            inputs={"requests": ", ".join(kinds), "reply_template": REFUSAL_REPLY, "disclosed": "none"},
            spans=[r.span for r in offer.data_requests],
        ))

    events = [
        SecurityEvent(
            id=f"SEC-{offer.offer_id}-v{offer.version}-{n}",
            day=day,
            kind=EVENT_KIND[v.code],
            counterparty_id=offer.counterparty_id,
            action_taken="refused; nothing booked, no facility added, nothing disclosed",
            detail=f"{v.code.value}: {v.message}",
            spans=v.spans,
        )
        for n, v in enumerate(violations, start=1)
    ]
    return violations, events
