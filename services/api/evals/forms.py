"""The "form" baseline: a perfect structured form, i.e. the hand labels typed straight into
CompiledOffer obligations (no language understanding involved). Also used to build typed offers for
the boundary cases.

A label obligation is a dict with `type` and any of: rate_bp, amount_fen, base_amount_fen,
receivable_id, days_delta, target_terms_days, duration (ONE_OFF | RECURRING_PERPETUAL |
RECURRING_BOUNDED), invoices, contingency (FIRM | CONTINGENT | CLAIMED_UNEVIDENCED), events_per_year.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceDocument,
    SourceSpan,
)

DEFAULT_BASE = {
    ObligationType.IMMEDIATE_DISCOUNT: BaseKind.INVOICE,
    ObligationType.TERMS_EXTENSION: BaseKind.FUTURE_INVOICES,
    ObligationType.CONTINGENT_REBATE: BaseKind.PERIOD_PURCHASES,
    ObligationType.PRICE_ADJUSTMENT: BaseKind.FUTURE_INVOICES,
    ObligationType.OPERATIONAL_CONCESSION: BaseKind.PER_EVENT,
    ObligationType.VOLUME_COMMITMENT: BaseKind.PERIOD_PURCHASES,
    ObligationType.CLAIMED_PRIOR_CONCESSION: BaseKind.UNSPECIFIED,
}
DEFAULT_CONTINGENCY = {
    ObligationType.CONTINGENT_REBATE: Contingency.CONTINGENT,
    ObligationType.CLAIMED_PRIOR_CONCESSION: Contingency.CLAIMED_UNEVIDENCED,
}
DEFAULT_DURATION = {
    ObligationType.TERMS_EXTENSION: DurationKind.RECURRING_PERPETUAL,
    ObligationType.PRICE_ADJUSTMENT: DurationKind.RECURRING_PERPETUAL,
    ObligationType.OPERATIONAL_CONCESSION: DurationKind.RECURRING_PERPETUAL,
}


def obligation(label: dict[str, Any], counterparty_id: str, idx: int, span: SourceSpan) -> Obligation:
    t = ObligationType(label["type"])
    dur = DurationKind(label.get("duration") or DEFAULT_DURATION.get(t, DurationKind.ONE_OFF))
    base = ObligationBase(kind=BaseKind(label.get("base_kind") or DEFAULT_BASE[t]),
                          amount_fen=label.get("base_amount_fen"), receivable_id=label.get("receivable_id"),
                          events_per_year=label.get("events_per_year"))
    return Obligation(
        id=f"FORM-O{idx}", type=t, counterparty_id=counterparty_id, rate_bp=label.get("rate_bp"),
        amount_fen=label.get("amount_fen"), days_delta=label.get("days_delta"),
        target_terms_days=label.get("target_terms_days"), effective_day=label.get("effective_day"), base=base,
        contingency=Contingency(label.get("contingency") or DEFAULT_CONTINGENCY.get(t, Contingency.FIRM)),
        duration=Duration(kind=dur, invoices=label.get("invoices")), spans=[span], confidence=1.0,
    )


def form_offer(docs: list[SourceDocument], counterparty_id: str, labels: list[dict[str, Any]],
               status: CompileStatus = CompileStatus.COMPILED, offer_id: str | None = None) -> CompiledOffer:
    d0 = docs[0]
    span = SourceSpan(doc_id=d0.doc_id, start=0, end=len(d0.text), text=d0.text)
    oid = offer_id or "FORM-" + hashlib.sha256("|".join(d.text for d in docs).encode()).hexdigest()[:12]
    return CompiledOffer(
        offer_id=oid, counterparty_id=counterparty_id, doc_ids=[d.doc_id for d in docs], received_day=d0.received_day,
        status=status, obligations=[obligation(lb, counterparty_id, i + 1, span) for i, lb in enumerate(labels)],
        compiler="form-baseline", prompt_version="form",
    )


def doc(text: str, sender_id: str = "BUYER-1", doc_id: str = "EVAL-doc") -> SourceDocument:
    return SourceDocument(doc_id=doc_id, channel="chat", sender_id=sender_id, received_day=0, text=text)
