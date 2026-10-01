"""Turn an alert's suggested cure into typed operations for the executor. Pure: nothing here executes anything.

Only the three kinds an agent may submit on a click are mapped; the executor computes each one's tier."""

from __future__ import annotations

from typing import Any

from app.alerts.models import Alert
from app.domain.models import Actor, ApplyForFacility, DrawFacility, Operation, SubmitInvoiceForFinancing


def cure_operations(alert: Alert, *, day: int, mandate_version: int, state_version: int) -> list[Operation]:
    out: list[Operation] = []
    for i, s in enumerate(alert.suggested):
        key = f"alert:{alert.id}:v{state_version}:{i}"
        common: dict[str, Any] = {"op_id": key, "idempotency_key": key, "mandate_version": mandate_version,
                                  "requested_by": Actor.AGENT, "day": day}
        if s.operation_kind == "DRAW_FACILITY" and s.facility_id and s.amount_fen:
            out.append(DrawFacility(**common, facility_id=s.facility_id, amount_fen=s.amount_fen))
        elif (s.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING" and s.facility_id and s.receivable_id
              and s.amount_fen):
            out.append(SubmitInvoiceForFinancing(**common, facility_id=s.facility_id, receivable_id=s.receivable_id,
                                                 advance_fen=s.amount_fen))
        elif s.operation_kind == "APPLY_FOR_FACILITY" and s.facility_id and s.amount_fen is not None:
            out.append(ApplyForFacility(**common, facility_id=s.facility_id, amount_fen=s.amount_fen))
    return out
