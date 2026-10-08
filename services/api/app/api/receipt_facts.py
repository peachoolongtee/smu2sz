"""The four facts of a received early payment, named, and whether its early-payment window is open (F25, F15).

Pure reads of a `ReconciliationReport` and the books: nothing is stored and no figure is computed here beyond what the
reconciliation already carries (the face a receipt cleared is the cash received plus the agreed discount, the same
sum `app.alerts.reconcile` writes into the promise row). The Home change row has its own sentence (`home._part_arrived`);
this module gives the same five fields for each receipt row of `GET /reconciliation`."""

from __future__ import annotations

from typing import Any

from app.alerts.models import MatchStatus
from app.api.presentation import window_is_live
from app.domain.models import FinancialState
from app.domain.money import fmt_yuan


def window_open(promise: Any, live: frozenset[tuple[str, str]] | None, today: int) -> bool:
    """Whether the early-payment window of this promise is still open today: its day has not passed and the promise is still
    live in the books (`presentation.live_windows`: the obligation binds and has not been paid in full)."""
    return (promise.promised_day is not None and promise.promised_day >= today
            and window_is_live(live, promise.receivable_id, promise.commitment_id))


def receipt_facts(state: FinancialState, report: Any, live: frozenset[tuple[str, str]] | None, today: int) -> dict[int, dict[str, str]]:
    """For each receipt (by log seq) that paid an agreed early payment: `received_display`, `face_cleared_display`,
    `discount_display`, `remaining_display` (what the invoice still owes now; "¥0.00" once it is settled) and `window_state`
    ("open" or "ended"). Only a receipt that matched the agreed early payment exactly has an entry (a short, ignored or unexplained payment has no
    cleared-face reading to state, so it keeps the server's sentence alone)."""
    receivables = {r.id: r for r in state.receivables}
    out: dict[int, dict[str, str]] = {}
    for m in report.receipts:
        r = receivables.get(m.receivable_id)
        if r is None or m.status != MatchStatus.MATCHED or not m.commitment_id or m.agreed_discount_fen <= 0:
            continue
        promise = next((p for p in report.promised if p.commitment_id == m.commitment_id and p.receivable_id == m.receivable_id), None)
        out[m.seq] = {
            "received_display": fmt_yuan(m.received_fen),
            "face_cleared_display": fmt_yuan(m.received_fen + m.agreed_discount_fen),
            "discount_display": fmt_yuan(m.agreed_discount_fen),
            "remaining_display": fmt_yuan(r.outstanding_fen),
            "window_state": "open" if promise is not None and window_open(promise, live, today) else "ended",
        }
    return out
