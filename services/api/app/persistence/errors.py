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


class ConcurrentWriteConflict(PersistenceError):
    """Another writer committed first (compare-and-swap lost). Nothing of this unit of work was kept;
    re-reading and running it again gives the serial outcome. Raised for a moved log head inside a
    unit of work and for a unique key another writer claimed between this unit's check and its write."""


class StateVersionConflict(ConcurrentWriteConflict):
    """`put_state(state, expected_version=v)` found a stored state whose version is not `v`: the books
    this write was computed from are no longer the current books."""


# SQLSTATEs a database uses for "run the transaction again": serialization_failure, deadlock_detected.
_RETRYABLE_SQLSTATES = frozenset({"40001", "40P01"})


def is_retryable(exc: BaseException) -> bool:
    """True when `exc` means a concurrent writer won and the unit of work may simply run again."""
    if isinstance(exc, ConcurrentWriteConflict):
        return True
    orig = getattr(exc, "orig", None)
    code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return code in _RETRYABLE_SQLSTATES
