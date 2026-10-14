"""Permission tiers, computed from the typed operation only (INVARIANTS 6 and 12).

Nothing a caller supplies as a "tier" is read. The only caller-supplied inputs are two facts the
operation object cannot carry, and each can only *raise* the tier:
- `accepts_terms_change`: the commitment an AcceptOffer/RecordCommitment accepts or records
  contains a TERMS_EXTENSION that lengthens terms, `days_delta > 0` (-> Tier 2). A shortening
  (`days_delta < 0`) is a gain to the supplier and does not set it. Callers pass True for an
  unbound delta (`None`): it cannot be shown to shorten, and the flag can only raise the tier.
- `commitment_value_fen`: the value of the commitment an AcceptOffer/RecordCommitment creates
  (-> Tier 2 above `tier2_single_commitment_fen`).
An operation type this function does not know is Tier 3 (fail closed).

A receipt (`ReceivePayment`) is Tier 1 only from the bank feed (SYSTEM) or the owner. Reported by
the agent or a counterparty ("we've paid, mark it settled") it is Tier 2: the owner confirms it
before any cash is booked (F-02).
"""

from __future__ import annotations

from app.domain.models import (
    AcceptOffer,
    Actor,
    AddFacility,
    ApplyForFacility,
    ChangeMandate,
    CommitPurchase,
    CounterOffer,
    DrawFacility,
    FacilityStatus,
    FinancialState,
    IssueEquity,
    Mandate,
    PledgeCollateral,
    ReceivePayment,
    RecordCommitment,
    RejectOffer,
    RepayFacility,
    RequestOwnerApproval,
    SignPersonalGuarantee,
    SubmitInvoiceForFinancing,
    Tier,
)

_ALWAYS_TIER3 = (SignPersonalGuarantee, PledgeCollateral, IssueEquity, ChangeMandate)
_ALWAYS_TIER2 = (ApplyForFacility, CommitPurchase)  # ADR-0013: buying equipment is always the owner's decision
_TIER1_BASE = (
    AcceptOffer,
    CounterOffer,
    RejectOffer,
    RecordCommitment,
    DrawFacility,
    RepayFacility,
    SubmitInvoiceForFinancing,
    ReceivePayment,
    RequestOwnerApproval,
)


def _is_committed(state: FinancialState, facility_id: str) -> bool:
    """A facility is usable at Tier 1 only if it is on the owner's menu, owner-approved and
    COMMITTED. An unknown id is treated as not committed."""
    f = next((f for f in state.facilities if f.id == facility_id), None)
    return f is not None and f.owner_approved and f.status == FacilityStatus.COMMITTED


# Who may record a receipt without owner confirmation: the bank feed and the owner.
RECEIPT_TIER1_ACTORS = frozenset({Actor.SYSTEM, Actor.OWNER})


def _commitment_amount(operation: object) -> int | None:
    """The new commitment an operation creates, in fen. Operating an existing COMMITTED facility
    (draw, invoice submission) is Tier 1 at any size within its owner-approved limit (spec v2
    §5.3); the size threshold applies to new commitments. Repayments and receipts reduce
    exposure and are not commitments."""
    if isinstance(operation, ApplyForFacility):
        return operation.amount_fen
    return None


def tier_for(
    operation: object,
    mandate: Mandate,
    state: FinancialState,
    *,
    accepts_terms_change: bool = False,
    commitment_value_fen: int | None = None,
    accepts_beyond_early_pay: bool = False,
) -> Tier:
    if isinstance(operation, _ALWAYS_TIER3):
        return Tier.TIER_3
    if isinstance(operation, AddFacility):
        return Tier.TIER_2 if operation.requested_by == Actor.OWNER else Tier.TIER_3
    if isinstance(operation, _ALWAYS_TIER2):
        return Tier.TIER_2
    if not isinstance(operation, _TIER1_BASE):
        return Tier.TIER_3

    if isinstance(operation, ReceivePayment) and operation.requested_by not in RECEIPT_TIER1_ACTORS:
        return Tier.TIER_2
    if isinstance(operation, DrawFacility | SubmitInvoiceForFinancing) and not _is_committed(
        state, operation.facility_id
    ):
        return Tier.TIER_2
    amount = _commitment_amount(operation)
    if amount is not None and amount > mandate.tier2_single_commitment_fen:
        return Tier.TIER_2
    if isinstance(operation, AcceptOffer | RecordCommitment):
        # Autonomous (Tier 1) acceptance is limited to spec §5.3's example: early payment of a named
        # invoice at a discount, nothing else changed. Any other promise (rebates, terms, price, volume,
        # operational concessions) waits for the owner, so a misread message can never commit the
        # business on its own (evaluation findings EV-01/EV-02; INVARIANT 10).
        if accepts_terms_change or accepts_beyond_early_pay:
            return Tier.TIER_2
        if commitment_value_fen is not None and commitment_value_fen > mandate.tier2_single_commitment_fen:
            return Tier.TIER_2
    return Tier.TIER_1
