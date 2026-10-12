"""The customer-inputs routes (map #88 Phase 1; flag `exposure`; brief H.4 and H.5).

    POST /buyers/{buyer_id}/inputs   body {field, value, provenance, source_ref}: one fact about a buyer
    POST /firm/inputs                the same for a firm-level field (VAT rate, company gross margin)
    GET  /buyers/{buyer_id}/inputs   the row in force for each field, with provenance in words, and the Inputs sheet (ticket #97):
                                     `fields` and `firm` (label, value_display, input_text, provenance_text, entered_day_text, editable),
                                     `vat_note`, `consistency`, `economics_on` with `economics_off_text`, and `context.back` to the
                                     customer's page (built from `decision`, `path`, `invoice` in the query, as the overview builds it)
    GET  /firm/inputs                the firm's rows (company gross margin, VAT rate) with the same words

A write takes `value` (the stored type) or `value_text` (what the owner typed: "¥5,460,000", "20%", "Strategic"), which the server parses
(`app.api.inputs_sheet.parse_text`): the browser computes nothing. A refusal says why in the language asked for.

Phase 1 takes two fields, `aggregate` and `typical_delay_days`. The six economics fields (annual sales, margin, margin basis,
classification, VAT rate, company gross margin) belong to a later phase: they are refused with a 422 naming it until
FEATURE_CUSTOMER_ECONOMICS is on (default off).

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

from app.api.exposure_words import customer_back
from app.api.features import require_feature
from app.api.inputs_sheet import TextRejected, check_choice, parse_text, rule_words, sheet
from app.api.presentation import Lang, t
from app.api.runtime import get_runtime
from app.config import get_settings
from app.persistence.records import CustomerInputRecord, InputField, InputProvenance
from app.strategy.inputs import (
    InputRejected,
    InputValue,
    field_label,
    input_view,
    inputs_from_store,
    is_firm_field,
    parse_value,
    value_json,
)

router = APIRouter()
ENTERED_BY = "OWNER"
PHASE_1_FIELDS = frozenset({InputField.AGGREGATE, InputField.TYPICAL_DELAY_DAYS})  # the rest wait for FEATURE_CUSTOMER_ECONOMICS


class InputBody(BaseModel):
    """What the owner sends. `value` is checked for its field after the type check here (a string is never coerced)."""

    model_config = ConfigDict(extra="forbid")

    field: InputField
    value: StrictBool | StrictInt | StrictStr | None = None
    value_text: StrictStr | None = Field(default=None, max_length=64)  # what the owner typed; the server parses it
    provenance: InputProvenance
    source_ref: str = Field(default="", max_length=256)


def _refused(f: InputField, why: str, lang: Lang, why_zh: str | None = None) -> HTTPException:
    label = field_label(f.value, lang)
    return HTTPException(422, detail={
        "code": "INPUT_REJECTED", "field": f.value, "reason": why,
        "message": t(lang, f"{label} was not saved: {why}.", f"“{label}”未保存：该值不符合要求（{why_zh or why}）。")})


LATER_PHASE = ("it belongs to a later phase (customer economics), which is switched off (FEATURE_CUSTOMER_ECONOMICS)",
               "它属于后续阶段（客户盈利分析），目前未开启（FEATURE_CUSTOMER_ECONOMICS）")


def _later_phase(f: InputField, lang: Lang) -> HTTPException:
    return _refused(f, LATER_PHASE[0], lang, LATER_PHASE[1])


def economics_off_text(lang: Lang) -> str:
    """The sheet's quiet notice while the economics fields are refused: the same reason the 422 gives."""
    return t(lang, "Customer economics is not switched on yet, so these facts cannot be saved.", "客户盈利分析尚未开启，因此这些信息暂时无法保存。")


def _value(body: InputBody, lang: Lang) -> InputValue:
    """The value to store: `value_text` parsed, else `value` checked for its field; either refusal is worded in both languages."""
    if (body.value is None) == (body.value_text is None):
        raise _refused(body.field, "send either value or value_text", lang, "请只提供 value 或 value_text 其中之一")
    try:
        if body.value_text is not None:
            return parse_text(body.field, body.value_text)
        value = parse_value(body.field, body.value)
        check_choice(body.field, value)
        return value
    except TextRejected as exc:
        raise _refused(body.field, exc.en, lang, exc.zh) from None
    except InputRejected:
        en, zh = rule_words(body.field)
        raise _refused(body.field, en, lang, zh) from None


def _write(counterparty_id: str | None, body: InputBody, lang: Lang) -> dict[str, Any]:
    if body.field not in PHASE_1_FIELDS and not get_settings().features.customer_economics:
        raise _later_phase(body.field, lang)
    if is_firm_field(body.field) != (counterparty_id is None):
        which = "firm" if is_firm_field(body.field) else "buyer"
        route = "/firm/inputs" if is_firm_field(body.field) else "/buyers/{buyer_id}/inputs"
        raise _refused(body.field, f"it is a {which} field; send it to {route}", lang)
    value = _value(body, lang)
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
def get_buyer_inputs(buyer_id: str, lang: Literal["en", "zh"] = Query("en"), decision: str | None = Query(None, max_length=120),
                     path: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120)) -> dict[str, Any]:
    require_feature("exposure")
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        if not any(c.id == buyer_id for c in state.counterparties):
            raise HTTPException(404, detail={"code": "BUYER_NOT_FOUND",
                                             "message": t(lang, f"There is no buyer {buyer_id} on the books.", "您的账目中没有这位客户。")})
        history = rt.store.customer_inputs(buyer_id)
        inputs = inputs_from_store(rt.store)
        back = customer_back(rt, state, lang, customer=buyer_id, invoice=invoice, decision=decision, path=path)
        day = rt.day
    latest: dict[str, CustomerInputRecord] = {}
    for row in history:  # oldest first: the last one stored for a field is in force
        latest[row.field] = row
    order = [f.value for f in InputField]
    rows = sorted(latest.values(), key=lambda r: order.index(r.field))
    on = get_settings().features.customer_economics
    return {"buyer_id": buyer_id, "inputs": [input_view(r, lang) for r in rows], "rows_stored": len(history),
            **sheet(state, inputs, buyer_id, max(day, state.as_of_day), lang, on),
            "economics_on": on, "economics_off_text": None if on else economics_off_text(lang),
            "context": {"back": back}, "state_version": state.state_version, "day": day}


@router.get("/firm/inputs")
def get_firm_inputs(lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    """The firm's rows (company gross margin, VAT rate), worded as the sheet words them."""
    require_feature("exposure")
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        inputs = inputs_from_store(rt.store)
        day = rt.day
    buyer = next((c.id for c in state.counterparties if c.role == "BUYER"), None)
    on = get_settings().features.customer_economics
    off = None if on else economics_off_text(lang)
    if buyer is None:
        return {"firm": [], "vat_note": None, "economics_on": on, "economics_off_text": off, "state_version": state.state_version,
                "day": day}
    read = sheet(state, inputs, buyer, max(day, state.as_of_day), lang, on)
    return {"firm": read["firm"], "vat_note": read["vat_note"], "economics_on": on, "economics_off_text": off,
            "state_version": state.state_version, "day": day}
