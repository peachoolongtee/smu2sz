"""Builders for executor tests: a seeded store, a settable clock, typed operations, offers and verdicts."""

from __future__ import annotations

import itertools
from typing import Any

from app.domain.fixtures import load_scenario
from app.domain.models import (
    Actor,
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    CounterProposal,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
    Tier,
    Verdict,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.operations import Executor
from app.persistence import InMemoryLedgerStore, SqlLedgerStore

BUYER = "BUYER-1"
_ids = itertools.count(1)


class Clock:
    """The simulated current day. Tests move it by assigning `day`."""

    def __init__(self, day: int = 0) -> None:
        self.day = day

    def __call__(self) -> int:
        return self.day


def seeded_store(kind: str = "memory", url: str = "sqlite://") -> Any:
    store: Any = InMemoryLedgerStore() if kind == "memory" else SqlLedgerStore(url)
    state, _ = load_scenario()
    store.put_state(state)
    store.put_mandate(load_signed_mandate())
    return store


def make_executor(store: Any, clock: Clock) -> Executor:
    return Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=clock)


def op(cls: type, clock: Clock, *, actor: Actor = Actor.AGENT, key: str | None = None, **fields: Any) -> Any:
    """A typed operation dated today, with fresh op id and idempotency key unless given."""
    n = next(_ids)
    base = {
        "op_id": f"OP-{n}",
        "idempotency_key": key or f"KEY-{n}",
        "mandate_version": 1,
        "requested_by": actor,
        "day": clock.day,
    }
    return cls(**{**base, **fields})


def span(text: str = "1% rebate on next quarter's purchases") -> SourceSpan:
    return SourceSpan(doc_id="DOC-1", start=0, end=len(text), text=text)


def rebate(oid: str = "OB-R", rate_bp: int = 100, cap_fen: int = 30_000_000) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.CONTINGENT_REBATE,
        counterparty_id=BUYER,
        rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=cap_fen),
        contingency=Contingency.CONTINGENT,
        duration=Duration(kind=DurationKind.ONE_OFF),
        spans=[span()],
        confidence=0.9,
    )


def extension(oid: str = "OB-T", days_delta: int = 15) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.TERMS_EXTENSION,
        counterparty_id=BUYER,
        days_delta=days_delta,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3),
        spans=[span("extend terms to 60 days")],
        confidence=0.9,
    )


def offer(offer_id: str, obligations: list[Obligation], counterparty_id: str = BUYER) -> CompiledOffer:
    return CompiledOffer(
        offer_id=offer_id,
        counterparty_id=counterparty_id,
        doc_ids=["DOC-1"],
        received_day=0,
        status=CompileStatus.COMPILED,
        obligations=obligations,
        compiler="fixture-cache",
        prompt_version="test",
    )


def verdict(
    verdict_id: str,
    offer_id: str,
    *,
    outcome: Outcome = Outcome.ACCEPT,
    value_fen: int = 300_000,
    tier: Tier = Tier.TIER_1,
    counters: list[CounterProposal] | None = None,
    mandate_version: int = 1,
) -> Verdict:
    return Verdict(
        id=verdict_id,
        offer_id=offer_id,
        offer_version=1,
        outcome=outcome,
        forward_concession_total_fen=value_fen,
        counters=counters or [],
        required_tier=tier,
        mandate_version=mandate_version,
        state_version=1,
        calc_version="test",
        summary="test verdict",
    )


def counter(counter_id: str = "CTR-A", obligations: list[Obligation] | None = None, cost_fen: int = 200_000) -> CounterProposal:
    return CounterProposal(
        id=counter_id,
        label="Option A",
        text="We can offer a 0.85% early-payment discount on invoice RCV-A.",
        obligations=obligations or [rebate("OB-C", rate_bp=50)],
        supplier_cost_fen=cost_fen,
        rationale="priced below break-even",
        formula="d/(1-d) < c",
    )


def seed_offer(store: Any, ex: Executor, offer_id: str = "OFF-1", *, obligations: list[Obligation] | None = None,
               value_fen: int = 300_000, tier: Tier = Tier.TIER_1, expires_day: int = 5,
               nonce: str | None = None) -> Any:
    """Store an offer and an ACCEPT verdict, and propose its commitment. Returns the commitment."""
    store.put_offer(offer(offer_id, obligations or [rebate()]))
    store.put_verdict(verdict(f"V-{offer_id}", offer_id, value_fen=value_fen, tier=tier))
    return ex.propose_commitment(f"V-{offer_id}", expires_day=expires_day, nonce=nonce or f"NONCE-{offer_id}")


def new_facility(lender: str = "BANK-1", fid: str = "FAC-NEW") -> Any:
    """A facility proposal modelled on FAC-LINE, not yet owner-approved."""
    state, _ = load_scenario()
    line = next(f for f in state.facilities if f.id == "FAC-LINE")
    return line.model_copy(update={"id": fid, "name": "New line", "lender_id": lender, "owner_approved": False,
                                   "covenants": []})
