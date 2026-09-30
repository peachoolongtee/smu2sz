"""Small typed builders shared by the persistence and commitments tests."""

from __future__ import annotations

from app.domain.models import (
    BaseKind,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SecurityEvent,
    SecurityEventKind,
    SourceSpan,
    Tier,
    Verdict,
)

BUYER = "BUYER-1"
TEXT = (
    "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward "
    "and give us 1% off next quarter."
)


def span(fragment: str, doc_id: str = "EX01-msg") -> SourceSpan:
    start = TEXT.index(fragment)
    return SourceSpan(doc_id=doc_id, start=start, end=start + len(fragment), text=fragment)


def discount(
    oid: str = "OB-1",
    rate_bp: int = 120,
    day: int = 0,
    counterparty_id: str = BUYER,
    receivable_id: str = "AR-1",
    amount_fen: int = 42_000_000,
) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.IMMEDIATE_DISCOUNT,
        counterparty_id=counterparty_id,
        rate_bp=rate_bp,
        effective_day=day,
        base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=amount_fen, receivable_id=receivable_id),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.ONE_OFF),
        spans=[span("early at 1.2%")],
        confidence=0.95,
    )


def extension(oid: str = "OB-2", days_delta: int = 30, base: BaseKind = BaseKind.FUTURE_INVOICES) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.TERMS_EXTENSION,
        counterparty_id=BUYER,
        days_delta=days_delta,
        effective_day=0,
        base=ObligationBase(kind=base),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
        spans=[span("standard terms to 60 days")],
        confidence=0.9,
    )


def rebate(oid: str = "OB-3", rate_bp: int = 100) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.CONTINGENT_REBATE,
        counterparty_id=BUYER,
        rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=150_000_000),
        contingency=Contingency.CONTINGENT,
        duration=Duration(kind=DurationKind.RECURRING_BOUNDED, end_day=90),
        spans=[span("1% off next quarter")],
        confidence=0.85,
    )


def offer(offer_id: str = "OFF-1", version: int = 1, obligations: list[Obligation] | None = None) -> CompiledOffer:
    return CompiledOffer(
        offer_id=offer_id,
        version=version,
        counterparty_id=BUYER,
        doc_ids=["EX01-msg"],
        received_day=0,
        status=CompileStatus.COMPILED,
        obligations=obligations if obligations is not None else [discount(), extension(), rebate()],
        compiler="fixture-cache",
        prompt_version="p1",
    )


def verdict(verdict_id: str = "V-1", offer_id: str = "OFF-1") -> Verdict:
    return Verdict(
        id=verdict_id,
        offer_id=offer_id,
        offer_version=1,
        outcome=Outcome.REJECT,
        forward_concession_total_fen=2_645_562,
        required_tier=Tier.TIER_1,
        mandate_version=1,
        state_version=1,
        calc_version="test",
        summary="Rejected: aggregate forward concession cap exceeded.",
    )


def commitment(
    cid: str = "CMT-1", status: CommitmentStatus = CommitmentStatus.PROPOSED, expires_day: int = 10
) -> Commitment:
    from app.commitments import terms_hash

    obs = [discount()]
    return Commitment(
        id=cid,
        offer_id="OFF-1",
        offer_version=1,
        counterparty_id=BUYER,
        verdict_id="V-1",
        terms_hash=terms_hash(obs),
        obligations=obs,
        status=status,
        nonce="nonce-" + cid,
        expires_day=expires_day,
        mandate_version=1,
        forward_value_fen=0,
    )


def security_event(eid: str = "SEC-1") -> SecurityEvent:
    return SecurityEvent(
        id=eid,
        day=0,
        kind=SecurityEventKind.DATA_EXTRACTION,
        counterparty_id=BUYER,
        action_taken="refused; nothing booked",
        detail="asked for the reserve floor",
        spans=[span("early at 1.2%")],
    )
