"""Errors raised by the financial engine. All are ValueErrors so callers can catch one type."""

from __future__ import annotations

from app.domain.models import FacilityStatus, Mode


class EngineError(ValueError):
    """An input the engine cannot project or value without guessing."""


class ObligationError(EngineError):
    """An obligation is missing a field the engine needs, or cannot be bound to state."""


class FundingActionError(EngineError):
    """A funding action is malformed or breaks a facility's limit, kind or timing rules."""


class UncommittedFacilityError(FundingActionError):
    """An action uses a facility the mode may not rely on (INVARIANT 4).

    CONSERVATIVE accepts only COMMITTED facilities; EXPECTED also accepts PENDING ones.
    """

    def __init__(self, facility_id: str, status: FacilityStatus, mode: Mode) -> None:
        self.facility_id = facility_id
        self.status = status
        self.mode = mode
        super().__init__(
            f"facility {facility_id} is {status.value}; {mode.value} mode may not use it"
        )
