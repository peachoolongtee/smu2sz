"""Capex mode (flag FEATURE_CAPEX): NPV, payback and the financing-structure comparison (spec v2 §7.7).

Public interface: `evaluate_capex()`, `capex_enabled()`, `CapexDisabled`, and the contracts
`CapexRequest`, `CapexCandidate`, `CapexResult`, `CapexStructure`, `DscrMonth`, `Working`.
"""

from app.capex.evaluate import CASH_LINE_ID, CapexDisabled, capex_enabled, evaluate_capex
from app.capex.models import (
    DEFAULT_CANDIDATES,
    OWNER_ESTIMATE,
    CapexCandidate,
    CapexRequest,
    CapexResult,
    CapexStructure,
    DscrMonth,
    Working,
)

__all__ = [
    "CASH_LINE_ID",
    "DEFAULT_CANDIDATES",
    "OWNER_ESTIMATE",
    "CapexCandidate",
    "CapexDisabled",
    "CapexRequest",
    "CapexResult",
    "CapexStructure",
    "DscrMonth",
    "Working",
    "capex_enabled",
    "evaluate_capex",
]
