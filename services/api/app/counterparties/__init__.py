"""Counterparty simulators: a deterministic buyer kernel with hidden reservations, bounded
negotiation, a template verbaliser (en + zh) and mock lenders from the fixture registry.

Depends on `app.domain` only. Buyer profiles are hidden state (INVARIANTS 7): only
`public_view` (name, role) leaves this package.
"""

from app.counterparties.buyer import BuyerDecision, BuyerKernel, BuyerResponse
from app.counterparties.errors import (
    CounterpartyError,
    HiddenStateError,
    UnknownBuyerProfile,
    UnknownFacility,
    UnknownLender,
)
from app.counterparties.lenders import (
    LenderDecision,
    LenderDecisionStatus,
    MockLender,
    known_lender_ids,
    lender_for,
    term_sheet_text,
)
from app.counterparties.negotiation import (
    NegotiationMessage,
    NegotiationRound,
    NegotiationTranscript,
    negotiate,
)
from app.counterparties.profiles import CounterpartyPublicView, public_view
from app.counterparties.verbaliser import PublicMessageFields, VerbaliserHook

__all__ = [
    "BuyerDecision",
    "BuyerKernel",
    "BuyerResponse",
    "CounterpartyError",
    "CounterpartyPublicView",
    "HiddenStateError",
    "LenderDecision",
    "LenderDecisionStatus",
    "MockLender",
    "NegotiationMessage",
    "NegotiationRound",
    "NegotiationTranscript",
    "PublicMessageFields",
    "UnknownBuyerProfile",
    "UnknownFacility",
    "UnknownLender",
    "VerbaliserHook",
    "known_lender_ids",
    "lender_for",
    "negotiate",
    "public_view",
    "term_sheet_text",
]
