"""Verifier: the verdict algorithm, reason codes with formulas, and counters priced from the
marginal cost of funds. Reads typed contracts only, never free text (INVARIANT 2); conservative
mode alone decides (INVARIANT 11).

Public interface: `bind()`, `evaluate()` (-> VerdictBundle), `evaluate_verdict()` (-> Verdict),
`evaluate_many()`, `evaluate_term_sheet()`, `counters()`, and `Verifier`, which satisfies
`app.domain.ports.Verifier`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.models import Commitment, CompiledOffer, CounterProposal, FinancialState, Mandate, Verdict
from app.verifier.bind import bind
from app.verifier.counters import counters
from app.verifier.evaluate import evaluate, evaluate_many, evaluate_term_sheet, evaluate_verdict
from app.verifier.models import CALC_VERSION, BindNote, PassedCheck, VerdictBundle
from app.verifier.screen import REFUSAL_REPLY


class Verifier:
    """Satisfies `app.domain.ports.Verifier`. The owner's key is pinned at construction, like the
    executor's: a mandate signed by any other key is rejected without evaluation."""

    def __init__(
        self,
        *,
        trusted_owner_key_hex: str,
        day: int = 0,
        owner_declared: Mapping[str, Any] | None = None,
        commitments: Sequence[Commitment] = (),
    ) -> None:
        if not trusted_owner_key_hex:
            raise ValueError("the verifier needs the owner's public key")
        self.trusted_owner_key_hex = trusted_owner_key_hex
        self.day = day
        self.owner_declared = owner_declared
        self.commitments = commitments

    def evaluate_bundle(self, offer: CompiledOffer, state: FinancialState, mandate: Mandate) -> VerdictBundle:
        return evaluate(offer, state, mandate, trusted_owner_key_hex=self.trusted_owner_key_hex, day=self.day,
                        owner_declared=self.owner_declared, commitments=self.commitments)

    def evaluate(self, offer: CompiledOffer, state: FinancialState, mandate: Mandate) -> Verdict:
        return self.evaluate_bundle(offer, state, mandate).verdict

    def counters(
        self, offer: CompiledOffer, verdict: Verdict, state: FinancialState, mandate: Mandate
    ) -> list[CounterProposal]:
        return counters(offer, verdict, state, mandate, owner_declared=self.owner_declared)


__all__ = [
    "CALC_VERSION",
    "REFUSAL_REPLY",
    "BindNote",
    "PassedCheck",
    "VerdictBundle",
    "Verifier",
    "bind",
    "counters",
    "evaluate",
    "evaluate_many",
    "evaluate_term_sheet",
    "evaluate_verdict",
]
