"""The strategy MVP: read-only answers over the kernel on labelled copies of the books (docs/STRATEGY_MVP_BRIEF.md)."""

from __future__ import annotations

from app.strategy.collections import (
    Ceiling,
    Effect,
    ReceivableWorth,
    WorthAnswer,
    early_pay_vs_plan,
    receivables_worth,
    saving_text,
)
from app.strategy.impact import marginal_impact, scenario_inflow, scenario_received
from app.strategy.types import CandidatePackage, MarginalImpact, ScenarioState

__all__ = [
    "CandidatePackage",
    "Ceiling",
    "Effect",
    "MarginalImpact",
    "ReceivableWorth",
    "ScenarioState",
    "WorthAnswer",
    "early_pay_vs_plan",
    "marginal_impact",
    "receivables_worth",
    "saving_text",
    "scenario_inflow",
    "scenario_received",
]
