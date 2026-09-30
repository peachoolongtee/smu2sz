"""Buyer profiles: each buyer's hidden reservation, loaded from fixtures/counterparties/buyers.yaml.

A `BuyerProfile` is buyer-private state. It refuses to serialise (any `model_dump`, JSON dump or
nesting inside another model raises `HiddenStateError`) and its repr is redacted, so it cannot
reach an API response or a log by accident. Only `public_view` (name and role) may leave.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_serializer, model_validator

from app.counterparties.errors import HiddenStateError, UnknownBuyerProfile
from app.domain.fixtures import FIXTURES
from app.domain.models import Contract, ObligationType

BUYERS_YAML: Path = FIXTURES / "counterparties" / "buyers.yaml"
_HIDDEN = "BuyerProfile is hidden buyer state and is never serialised"


class DeclaredBenefit(Contract):
    """A non-price benefit the buyer itself declares for a named change (e.g. consolidation)."""

    id: str
    label: str
    obligation_type: ObligationType
    value_fen: int = Field(ge=0)  # annual value, as declared by the buyer


class BuyerAsk(Contract):
    """The buyer's opening position, from which it concedes one step per round."""

    discount_bp: int | None = Field(default=None, ge=0)  # early-pay discount it asks for
    terms_days: int | None = Field(default=None, gt=0)  # payment terms it asks for


class BuyerProfile(Contract):
    """One buyer's hidden reservation and preferences. Never serialised (INVARIANTS 7)."""

    profile_id: str
    counterparty_id: str
    name: str
    role: Literal["BUYER"]

    # what the buyer knows about its own payables
    receivable_id: str | None
    invoice_face_fen: int = Field(ge=0)
    invoice_due_day: int | None
    early_settlement_day: int
    invoices_per_year: int = Field(gt=0)
    current_terms_days: int = Field(gt=0)
    next_quarter_purchases_fen: int = Field(ge=0)

    # economics
    funding_cost_bp: int = Field(ge=0)  # the buyer's own annual cost of paying early
    payment_day_value_fen: int = Field(ge=0)  # value of one extra payment day, per invoice

    # reservation gates
    min_early_pay_discount_bp: int = Field(ge=0)
    requires_early_pay: bool
    insists_on_terms_extension: bool
    min_terms_days: int = Field(gt=0)
    max_rebate_bp: int = Field(ge=0)  # the rebate it asks for
    min_rebate_bp: int = Field(ge=0)
    declared_benefits: list[DeclaredBenefit] = Field(default_factory=list)
    min_surplus_fen: int

    # negotiation behaviour
    ask: BuyerAsk
    concession_step_bp: int = Field(gt=0)
    rebate_step_bp: int = Field(gt=0)
    max_rounds: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> BuyerProfile:
        if self.ask.discount_bp is not None and self.ask.discount_bp < (
            self.min_early_pay_discount_bp + self.concession_step_bp
        ):
            raise ValueError("ask discount must sit at least one step above the reservation")
        if self.min_rebate_bp and self.max_rebate_bp < self.min_rebate_bp + self.rebate_step_bp:
            raise ValueError("rebate ask must sit at least one step above the reservation")
        if self.insists_on_terms_extension and (self.ask.terms_days or 0) < self.min_terms_days:
            raise ValueError("a buyer that insists on terms must ask for at least its minimum")
        if self.requires_early_pay and (self.ask.discount_bp is None or self.receivable_id is None):
            raise ValueError("a buyer that requires early pay must ask for a discount on a receivable")
        return self

    # ---- hidden: never serialise, never print. The serializer covers nesting and TypeAdapters
    # (pydantic wraps the error); the overrides raise HiddenStateError directly.
    @model_serializer(mode="plain")
    def _refuse_serialisation(self) -> Any:
        raise HiddenStateError(_HIDDEN)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        raise HiddenStateError(_HIDDEN)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        raise HiddenStateError(_HIDDEN)

    def __repr_args__(self):  # type: ignore[override]
        yield "counterparty_id", self.counterparty_id
        yield "hidden", True


class CounterpartyPublicView(Contract):
    """Everything about a buyer that may leave the kernel."""

    name: str
    role: Literal["BUYER"]


@lru_cache
def load_buyer_profiles(path: Path = BUYERS_YAML) -> dict[str, BuyerProfile]:
    """Read the buyer fixtures (trusted, read-only), keyed by profile id."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles = [BuyerProfile.model_validate_json(json.dumps(b)) for b in raw["buyers"]]
    out = {p.profile_id: p for p in profiles}
    if len(out) != len(profiles):
        raise ValueError("duplicate buyer profile id")
    return out


def get_profile(profile_id: str) -> BuyerProfile:
    try:
        return load_buyer_profiles()[profile_id]
    except KeyError:
        raise UnknownBuyerProfile(profile_id) from None


def public_view(profile_id: str) -> CounterpartyPublicView:
    """Name and role only. No reservation, no preferences, not even the profile variant."""
    p = get_profile(profile_id)
    return CounterpartyPublicView(name=p.name, role=p.role)
