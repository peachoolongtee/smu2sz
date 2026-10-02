"""Errors raised by the counterparty simulators."""

from __future__ import annotations


class CounterpartyError(Exception):
    """Base class for counterparty simulator errors."""


class UnknownBuyerProfile(CounterpartyError, KeyError):
    """The buyer profile id is not in fixtures/counterparties/buyers.yaml."""


class HiddenStateError(CounterpartyError, TypeError):
    """Something tried to serialise a buyer's hidden profile (INVARIANTS 7)."""
