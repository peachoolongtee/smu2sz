"""Storage errors. They report integrity problems; they never decide anything."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base class for every storage error."""


class NotFound(PersistenceError, LookupError):
    """A required row (state, mandate, approval) does not exist."""


class AppendOnlyViolation(PersistenceError):
    """Something tried to update or delete a row of the append-only operations log."""


class NonceAlreadyUsed(PersistenceError):
    """`mark_nonce_used` was called for a nonce that is already recorded."""


class ApprovalAlreadyDecided(PersistenceError):
    """`decide_approval` was called on an approval that is no longer PENDING."""


class InvalidPayload(PersistenceError, ValueError):
    """A payload that must be JSON text is not valid JSON."""


class OfferVersionConflict(PersistenceError):
    """`put_offer` was called for an (offer_id, version) already stored with other terms. A stored
    offer version is immutable; new terms need a new version (F-07)."""
