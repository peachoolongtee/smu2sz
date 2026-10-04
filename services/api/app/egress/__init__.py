"""Egress guard (INVARIANTS 7): deterministic, no LLM.

Every text that leaves for a counterparty passes `guard()` last. It scans for every protected value
(mandate, facilities, balances, other counterparties' terms and names, concessions, reservation
values passed in by the caller, canaries) in all common surface forms, and blocks the whole message
on any leak the recipient is not entitled to.

Depends on `app.domain` only.
"""

from app.egress.canaries import CANARIES_YAML, Canary, canary, load_canaries
from app.egress.contracts import contract_private_values, protected_for
from app.egress.guard import (
    ACTION_TAKEN,
    SAFE_TEMPLATES,
    GuardResult,
    allowed_for_counter,
    allowed_from_obligations,
    guard,
)
from app.egress.harness import assert_no_leak
from app.egress.normalise import normalise
from app.egress.protected import Leak, ProtectedSet, canary_tripped, counterparty_aliases, scan
from app.egress.values import OWNER_ID, AllowedValue, Category, PrivateValue, ValueKind, renderings

__all__ = [
    "ACTION_TAKEN",
    "CANARIES_YAML",
    "OWNER_ID",
    "SAFE_TEMPLATES",
    "AllowedValue",
    "Canary",
    "Category",
    "GuardResult",
    "Leak",
    "PrivateValue",
    "ProtectedSet",
    "ValueKind",
    "allowed_for_counter",
    "allowed_from_obligations",
    "assert_no_leak",
    "canary",
    "canary_tripped",
    "contract_private_values",
    "counterparty_aliases",
    "guard",
    "load_canaries",
    "normalise",
    "protected_for",
    "renderings",
    "scan",
]
