"""Counterparty simulators: a deterministic buyer kernel with hidden reservations, bounded
negotiation and a template verbaliser (en + zh).

Depends on `app.domain` only. Buyer profiles are hidden state (INVARIANTS 7): only
`public_view` (name, role) leaves this package.
"""

from app.counterparties.buyer import BuyerDecision, BuyerKernel, BuyerResponse
from app.counterparties.errors import (
    CounterpartyError,
    HiddenStateError,
    UnknownBuyerProfile,
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
    "NegotiationMessage",
    "NegotiationRound",
    "NegotiationTranscript",
    "PublicMessageFields",
    "UnknownBuyerProfile",
    "VerbaliserHook",
    "negotiate",
    "public_view",
]
