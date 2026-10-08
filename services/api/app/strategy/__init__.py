"""The strategy MVP: read-only answers over the kernel on labelled copies of the books (docs/STRATEGY_MVP_BRIEF.md).

The envelope's function stays at `app.strategy.envelope.envelope`: exporting it here would shadow the submodule's name."""

from __future__ import annotations

from app.strategy.envelope import EnvelopeAnswer
from app.strategy.impact import marginal_impact, scenario_inflow, scenario_received
from app.strategy.types import CandidatePackage, MarginalImpact, ScenarioState

__all__ = [
    "CandidatePackage",
    "EnvelopeAnswer",
    "MarginalImpact",
    "ScenarioState",
    "marginal_impact",
    "scenario_inflow",
    "scenario_received",
]
