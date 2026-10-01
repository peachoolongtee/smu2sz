"""Cash-flow alerts from the conservative trajectory, and receipt reconciliation (flag `alerts`).

Public interface: `alerts(state, mandate, store, day, *, obligations=())` -> list[Alert] and
`reconcile(store, day=None)` -> ReconciliationReport. Depends on `app.domain` and `app.financial`
only. Alerts suggest typed operations; nothing here executes one.
"""

from app.alerts.engine import alerts, committed_cure
from app.alerts.models import (
    Alert,
    AlertKind,
    MatchStatus,
    OutstandingReceivable,
    PromisedReceipt,
    PromiseStatus,
    ReceiptMatch,
    ReconciliationReport,
    Severity,
    SuggestedAction,
)
from app.alerts.reconcile import reconcile

__all__ = [
    "Alert",
    "AlertKind",
    "MatchStatus",
    "OutstandingReceivable",
    "PromiseStatus",
    "PromisedReceipt",
    "ReceiptMatch",
    "ReconciliationReport",
    "Severity",
    "SuggestedAction",
    "alerts",
    "committed_cure",
    "reconcile",
]
