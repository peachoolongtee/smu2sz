"""The three facts the decision record keeps (ADR-0011 section 2): what the stores cannot re-derive later.

Each is a strict model: ids, integer fen, integer days, enums and exact `Ratio` rates, and nothing else. No sentence is
stored (the server writes every sentence per request and language, INVARIANT 13), no buyer text, no model output. Unknown
fields are refused, so a fact cannot quietly grow a free-text field. The body of a stored fact is the model's canonical JSON
(sorted keys, compact separators), the same serialisation as the rest of the ledger.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol

from pydantic import ValidationError

from app.domain.models import Contract, Outcome
from app.domain.money import Ratio
from app.persistence.records import DecisionFactRecord

Family = Literal["DEAL", "FUNDING"]
FactName = Literal["EVALUATED", "SENT", "QUOTED"]


class EvaluatedFact(Contract):
    """EVALUATED (DEAL; fact_key = verdict_id). Gives a verdict the day it was made, which Verdict does not carry."""

    offer_id: str
    offer_version: int
    verdict_id: str
    outcome: Outcome
    counter_ids: list[str]
    recommended_counter_id: str | None
    mandate_version: int


class CounterEconomics(Contract):
    """The parts behind the sent counter's cost as `counter_economics()` gave them at send time. The basis is the
    facility and exact rate the figures were priced at, not a sentence: the server words the label when it shows it."""

    supplier_cost_fen: int
    forward_value_fen: int
    funding_cost_fen: int
    offset_fen: int
    net_fen: int
    basis_facility_id: str | None = None
    basis_rate: Ratio | None = None


class GapLeg(Contract):
    kind: str  # a FundingActionKind value
    facility_id: str | None
    receivable_id: str | None
    amount_fen: int
    lands_day: int | None


class GapPlan(Contract):
    need_fen: int
    total_cost_fen: int | None
    legs: list[GapLeg]


class SentFact(Contract):
    """SENT (DEAL; fact_key = "accept-{commitment_id}" when the buyer accepted, else "nodeal:{verdict_id}:{buyer_profile}").
    What was sent, what the simulated buyer answered, and which operations followed."""

    offer_id: str
    verdict_id: str
    state_version_shown: int | None
    chosen_counter_id: str | None  # None for an unbound send
    counter_ids_sent: list[str]  # in round order
    buyer_profile: str
    simulated: Literal[True] = True
    outcome: Literal["DEAL", "NO_DEAL"]
    accepted_counter_id: str | None
    transcript_hash: str
    commitment_id: str | None
    accept_op_id: str | None
    funding_op_ids: list[str]
    funding_blocked: str | None  # the router's reason code, when the gap was not funded
    counter_economics: CounterEconomics | None
    gap_plan: GapPlan | None


class QuotedLeg(Contract):
    op_id: str
    kind: str  # the operation kind the leg runs as
    facility_id: str | None
    receivable_id: str | None
    amount_fen: int
    cost_fen: int | None
    annual_rate: Ratio | None
    cost_days: int | None
    cost_end_day: int | None
    lands_day: int | None
    above_ceiling: bool


class IfDecline(Contract):
    """What the books show if the owner does not act, as the home showed it when the action was offered."""

    kind: Literal["below_reserve", "below_zero", "closed"]
    day: int | None
    zero_day: int | None
    shortfall_fen: int | None
    max_shortfall_fen: int | None
    worst_day: int | None


class QuotedFact(Contract):
    """QUOTED (FUNDING; fact_key = decision_id). The economics the owner was shown when an action was queued or run,
    copied from the alert's pricing and the router plan's cost lines; nothing is priced for the fact."""

    alert_id: str
    alert_kind: str  # an AlertKind value
    alert_day: int | None
    state_version_shown: int
    source: Literal["cure", "router"]
    legs: list[QuotedLeg]
    total_cost_fen: int | None  # None when the engine gave no total
    cost_note: Literal["draw_interest_excluded"] | None
    needs_owner: bool
    max_apr_bp: int
    restores_reserve: bool
    after_first_short_day: int | None  # None = safe through the horizon
    horizon_days: int
    if_decline: IfDecline | None
    residual_shortfall_fen: int | None


Fact = EvaluatedFact | SentFact | QuotedFact

_MODELS: dict[str, type[Contract]] = {"EVALUATED": EvaluatedFact, "SENT": SentFact, "QUOTED": QuotedFact}
FAMILY_OF: dict[str, Family] = {"EVALUATED": "DEAL", "SENT": "DEAL", "QUOTED": "FUNDING"}


def body_json(fact: Fact) -> str:
    """The stored body: the model's canonical JSON (sorted keys, compact separators, UTF-8 kept as is)."""
    return json.dumps(fact.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def record_for(decision_id: str, fact_key: str, fact: Fact, *, state_version: int, day: int) -> DecisionFactRecord:
    """The row to store for `fact`: its name and family follow the model, the body is canonical."""
    name = next(n for n, model in _MODELS.items() if type(fact) is model)
    return DecisionFactRecord(
        decision_id=decision_id, family=FAMILY_OF[name], fact=name, fact_key=fact_key, state_version=state_version,
        day=day, body_json=body_json(fact),
    )


def parse_fact(record: DecisionFactRecord) -> Fact | None:
    """The typed fact in a stored row, or None when the row does not parse as its model (a row from another version or a
    damaged one is skipped, never a crash: the record then reads as having no such fact)."""
    model = _MODELS.get(record.fact)
    if model is None:
        return None
    try:
        parsed = model.model_validate_json(record.body_json)
    except (ValidationError, ValueError):
        return None
    assert isinstance(parsed, (EvaluatedFact, SentFact, QuotedFact))
    return parsed


class DecisionFactStore(Protocol):
    """What the routes need from a store: both `LedgerStore` implementations provide it; it is not in the `LedgerStore` port."""

    def add_decision_fact(self, record: DecisionFactRecord) -> DecisionFactRecord: ...

    def decision_facts(self, decision_id: str | None = None) -> list[DecisionFactRecord]: ...


__all__ = [
    "FAMILY_OF",
    "CounterEconomics",
    "DecisionFactStore",
    "EvaluatedFact",
    "Fact",
    "GapLeg",
    "GapPlan",
    "IfDecline",
    "QuotedFact",
    "QuotedLeg",
    "SentFact",
    "body_json",
    "parse_fact",
    "record_for",
]
