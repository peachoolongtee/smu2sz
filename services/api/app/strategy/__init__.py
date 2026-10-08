"""The strategy MVP: read-only answers over the kernel on labelled copies of the books (docs/STRATEGY_MVP_BRIEF.md)."""

from __future__ import annotations

from app.strategy.impact import marginal_impact, scenario_inflow, scenario_received
from app.strategy.price_curve import PriceBand, PriceCurve, money_line, price_curve, price_sentence
from app.strategy.types import CandidatePackage, MarginalImpact, ScenarioState

__all__ = [
    "CandidatePackage",
    "MarginalImpact",
    "PriceBand",
    "PriceCurve",
    "ScenarioState",
    "marginal_impact",
    "money_line",
    "price_curve",
    "price_sentence",
    "scenario_inflow",
    "scenario_received",
]
