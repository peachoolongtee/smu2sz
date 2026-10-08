"""The strategy MVP: read-only answers over the kernel on labelled copies of the books (docs/STRATEGY_MVP_BRIEF.md).

The envelope's function stays at `app.strategy.envelope.envelope`: exporting it here would shadow the submodule's name."""

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
from app.strategy.envelope import EnvelopeAnswer
from app.strategy.impact import marginal_impact, scenario_inflow, scenario_received
from app.strategy.price_curve import PriceBand, PriceCurve, money_line, price_curve, price_sentence
from app.strategy.types import CandidatePackage, MarginalImpact, ScenarioState

__all__ = [
    "CandidatePackage",
    "Ceiling",
    "Effect",
    "EnvelopeAnswer",
    "MarginalImpact",
    "PriceBand",
    "PriceCurve",
    "ReceivableWorth",
    "ScenarioState",
    "WorthAnswer",
    "early_pay_vs_plan",
    "marginal_impact",
    "money_line",
    "price_curve",
    "price_sentence",
    "receivables_worth",
    "saving_text",
    "scenario_inflow",
    "scenario_received",
]
