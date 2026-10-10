"""The guided Demo's one synthetic bank event (wayfinder #65, ticket #75).

The simulated clock never records a receipt (ADR-0006 section 2). The late-payment story needs the buyer's agreed early
payment to arrive once, from the bank feed, so the web Demo asks for it here instead of holding the bank-feed key in the
browser. The route is owner-only and exists only under DEMO_MODE. It posts exactly the operation the bank feed would post
(RECEIVE_PAYMENT, requested by SYSTEM) for the one early payment the books are still waiting for, in the amount the books
promised, with a bank reference that says it is synthetic. It decides nothing about money: the amount is the promise's own."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import reconcile
from app.alerts.models import PromiseStatus
from app.api.auth import demo_mode, require_owner
from app.api.runtime import get_runtime
from app.domain.models import Actor, ReceivePayment

router = APIRouter(dependencies=[Depends(require_owner)])

#: The bank reference of the synthetic receipt; Activity words any `DEMO-` reference as a synthetic bank event.
DEMO_BANK_REFERENCE = "DEMO-RCPT-1"


@router.post("/demo/bank-receipt")
def demo_bank_receipt() -> dict:
    if not demo_mode():
        raise HTTPException(403, {"code": "DEMO_ONLY", "message": "the synthetic bank event exists only in demo mode"})
    rt = get_runtime()
    with rt.lock:
        report = reconcile(rt.store, day=rt.day)
        promise = next((p for p in report.promised if p.status == PromiseStatus.AWAITED), None)
        if promise is None:
            raise HTTPException(409, {"code": "NO_PROMISED_RECEIPT", "message": "no agreed early payment is waiting for the bank"})
        key = f"demo-bank-receipt:{promise.commitment_id}"
        op = ReceivePayment(op_id=key, idempotency_key=key, mandate_version=rt.store.get_mandate().version,
                            requested_by=Actor.SYSTEM, day=rt.day, receivable_id=promise.receivable_id,
                            amount_fen=promise.expected_fen, bank_reference=DEMO_BANK_REFERENCE)
        result = rt.executor.execute(op)
    return {"synthetic": True, "bank_reference": DEMO_BANK_REFERENCE, "day": rt.day, "op_id": key,
            "result": json.loads(result.model_dump_json())}
