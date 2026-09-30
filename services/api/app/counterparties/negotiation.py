"""Bounded negotiation between the supplier's counters and the buyer kernel.

Round 1 answers every supplier counter at once; each later round answers the single proposal
`supplier_next` returns for the buyer's last response. The negotiation ends with ACCEPT (naming
the accepted counter) or NO_DEAL: when the buyer's rounds run out, or the supplier has nothing
further to offer. It is deterministic: the same inputs give the same transcript and hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import Field, model_validator

from app.counterparties.buyer import BuyerDecision, BuyerKernel, BuyerResponse
from app.domain.models import Contract, CounterProposal, Outcome

SUPPLIER_WITHDREW = "supplier has no further proposal"
BUYER_ACCEPTED = "buyer accepted"
BUYER_ROUNDS_ENDED = "buyer's rounds ended without an acceptable package"

SupplierNext = Callable[[BuyerResponse], CounterProposal | None]


class NegotiationMessage(Contract):
    """One message in the transcript. Supplier text is the counter's outbound template text."""

    round: int = Field(ge=1)
    sender: Literal["SUPPLIER", "BUYER"]
    counter_id: str | None = None  # supplier messages: which counter
    decision: BuyerDecision | None = None  # buyer messages
    text_en: str
    text_zh: str | None = None


class NegotiationRound(Contract):
    round: int = Field(ge=1)
    supplier_counter_ids: list[str]
    response: BuyerResponse


class NegotiationTranscript(Contract):
    counterparty_id: str
    rounds: list[NegotiationRound]
    messages: list[NegotiationMessage]
    outcome: Outcome  # ACCEPT or NO_DEAL
    accepted_counter_id: str | None = None
    ended_reason: str
    transcript_hash: str

    @model_validator(mode="after")
    def _terminal(self) -> NegotiationTranscript:
        if self.outcome not in (Outcome.ACCEPT, Outcome.NO_DEAL):
            raise ValueError("a negotiation ends in ACCEPT or NO_DEAL")
        if (self.outcome is Outcome.ACCEPT) != (self.accepted_counter_id is not None):
            raise ValueError("ACCEPT names the accepted counter; NO_DEAL names none")
        return self

    @property
    def rounds_used(self) -> int:
        return len(self.rounds)


def _hash(body: dict[str, object]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def negotiate(
    supplier_counters: Sequence[CounterProposal],
    profile_id: str,
    supplier_next: SupplierNext,
    *,
    kernel: BuyerKernel | None = None,
) -> NegotiationTranscript:
    """Run bounded rounds (the buyer profile's `max_rounds`) and return the transcript."""
    if not supplier_counters:
        raise ValueError("a negotiation starts with at least one supplier counter")
    kernel = kernel or BuyerKernel()
    max_rounds = kernel.max_rounds(profile_id)

    rounds: list[NegotiationRound] = []
    messages: list[NegotiationMessage] = []
    offered: list[CounterProposal] = list(supplier_counters)
    accepted: str | None = None
    ended = BUYER_ROUNDS_ENDED
    counterparty_id = ""

    round_no = 1
    while True:
        for c in offered:
            messages.append(NegotiationMessage(round=round_no, sender="SUPPLIER", counter_id=c.id, text_en=c.text))
        response = kernel.respond_to_many(profile_id, offered, round_no)
        counterparty_id = response.counterparty_id
        rounds.append(
            NegotiationRound(round=round_no, supplier_counter_ids=[c.id for c in offered], response=response)
        )
        messages.append(
            NegotiationMessage(
                round=round_no,
                sender="BUYER",
                decision=response.decision,
                text_en=response.reply_en,
                text_zh=response.reply_zh,
            )
        )
        if response.decision is BuyerDecision.ACCEPT:
            accepted, ended = response.accepted_counter_id, BUYER_ACCEPTED
            break
        if response.decision is BuyerDecision.REJECT or round_no >= max_rounds:
            ended = BUYER_ROUNDS_ENDED
            break
        nxt = supplier_next(response)
        if nxt is None:
            ended = SUPPLIER_WITHDREW
            break
        offered = [nxt]
        round_no += 1

    outcome = Outcome.ACCEPT if accepted is not None else Outcome.NO_DEAL
    body = {
        "counterparty_id": counterparty_id,
        "rounds": [r.model_dump(mode="json") for r in rounds],
        "messages": [m.model_dump(mode="json") for m in messages],
        "outcome": outcome.value,
        "accepted_counter_id": accepted,
        "ended_reason": ended,
    }
    return NegotiationTranscript(
        counterparty_id=counterparty_id,
        rounds=rounds,
        messages=messages,
        outcome=outcome,
        accepted_counter_id=accepted,
        ended_reason=ended,
        transcript_hash=_hash(body),
    )
