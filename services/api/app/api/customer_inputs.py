"""The customer-inputs routes (map #88 Phase 1; flag `exposure`; brief H.4 and H.5).

    POST /buyers/{buyer_id}/inputs   body {field, value, provenance, source_ref}: one fact about a buyer
    POST /firm/inputs                the same for a firm-level field (VAT rate, company gross margin)
    GET  /buyers/{buyer_id}/inputs   the row in force for each field, with provenance in words

Owner only (mounted through `app/api/strategy.py`). Append-only: a write stores a new row and the older ones stay; the latest
row per (counterparty, field) is the one in force. The row is context, not books: nothing here writes `FinancialState`, a
verdict, an approval, an execution or the hash chain, and nothing a row says changes what the mandate allows. A field this
route does not know, or a value of the wrong type or out of range, is a 422 and writes nothing. Every sentence is written per
request in the language asked for.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from app.api.features import require_feature
from app.api.presentation import Lang, t
from app.api.runtime import get_runtime
from app.persistence.records import CustomerInputRecord, InputField, InputProvenance
from app.strategy.inputs import InputRejected, field_label, input_view, is_firm_field, parse_value, value_json

router = APIRouter()
ENTERED_BY = "OWNER"


class InputBody(BaseModel):
    """What the owner sends. `value` is checked for its field after the type check here (a string is never coerced)."""

    model_config = ConfigDict(extra="forbid")

    field: InputField
    value: StrictBool | StrictInt | StrictStr
    provenance: InputProvenance
    source_ref: str = Field(default="", max_length=256)


def _refused(f: InputField, why: str, lang: Lang) -> HTTPException:
    label = field_label(f.value, lang)
    return HTTPException(422, detail={
        "code": "INPUT_REJECTED", "field": f.value, "reason": why,
        "message": t(lang, f"{label} was not saved: {why}.", f"“{label}”未保存：该值不符合要求（{why}）。")})


def _write(counterparty_id: str | None, body: InputBody, lang: Lang) -> dict[str, Any]:
    if is_firm_field(body.field) != (counterparty_id is None):
        which = "firm" if is_firm_field(body.field) else "buyer"
        route = "/firm/inputs" if is_firm_field(body.field) else "/buyers/{buyer_id}/inputs"
        raise _refused(body.field, f"it is a {which} field; send it to {route}", lang)
    try:
        value = parse_value(body.field, body.value)
    except InputRejected as exc:
        raise _refused(body.field, str(exc), lang) from None
    rt = get_runtime()
    with rt.lock:  # the books' org, version and the day are read together with the write
        state = rt.store.get_state()
        if counterparty_id is not None and not any(c.id == counterparty_id for c in state.counterparties):
            raise HTTPException(404, detail={"code": "BUYER_NOT_FOUND",
                                             "message": f"There is no buyer {counterparty_id} on the books."})
        row = rt.store.add_customer_input(CustomerInputRecord(
            org_id=state.org_id, counterparty_id=counterparty_id, field=body.field.value, value_json=value_json(value),
            provenance=body.provenance.value, source_ref=body.source_ref.strip(), entered_by=ENTERED_BY,
            entered_day=rt.day, state_version=state.state_version))
    return {"input": input_view(row, lang), "state_version": state.state_version, "day": rt.day}


@router.post("/buyers/{buyer_id}/inputs")
def post_buyer_input(buyer_id: str, body: InputBody, lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("exposure")
    return _write(buyer_id, body, lang)


@router.post("/firm/inputs")
def post_firm_input(body: InputBody, lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("exposure")
    return _write(None, body, lang)


@router.get("/buyers/{buyer_id}/inputs")
def get_buyer_inputs(buyer_id: str, lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("exposure")
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        if not any(c.id == buyer_id for c in state.counterparties):
            raise HTTPException(404, detail={"code": "BUYER_NOT_FOUND",
                                             "message": f"There is no buyer {buyer_id} on the books."})
        history = rt.store.customer_inputs(buyer_id)
    latest: dict[str, CustomerInputRecord] = {}
    for row in history:  # oldest first: the last one stored for a field is in force
        latest[row.field] = row
    order = [f.value for f in InputField]
    rows = sorted(latest.values(), key=lambda r: order.index(r.field))
    return {"buyer_id": buyer_id, "inputs": [input_view(r, lang) for r in rows], "rows_stored": len(history),
            "state_version": state.state_version, "day": rt.day}
