"""Add a customer who is not yet on the books, from Attach deals (the owner's request of 17 Oct).

    POST /customers   the owner adds a customer by name: the next free BUYER-n on the registry, `known`, with no terms,
                      invoices, receivables, limits or channel key. One ADD_CUSTOMER entry in the hash chain records it,
                      with the request's idempotency key; the same key again answers with the same customer.

Owner only: the agent key, a buyer's channel key or no credential are refused by `require_owner` and logged like every
refused credential. A buyer message or a document's text never reaches this route, so neither can create a customer.

Like the setup's OPEN_BOOKS, this is an owner act with no money effect written at the API layer: the new books (the state with
one more counterparty, compare-and-swap on its version) and the log entry land in one unit of work, under the runtime lock.
Nothing else in the books changes, so the forecast is the same. The name is data: trimmed, no control or format characters,
compared with the party check's normaliser (`app.contracts.parties.normalise`), and only ever quoted in a sentence.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import counterparty_keys, require_owner
from app.api.presentation import customer_added_words, t
from app.api.runtime import get_runtime
from app.contracts.parties import normalise, taken_names
from app.domain.models import Actor, Counterparty, OperationResult, OperationStatus, Tier
from app.domain.ports import LedgerStore

router = APIRouter(dependencies=[Depends(require_owner)])
Lang = Literal["en", "zh"]

ADD_CUSTOMER_KIND = "ADD_CUSTOMER"
MAX_NAME = 120
MAX_SHORT_NAME = 40
_BUYER_ID = re.compile(r"^BUYER-(\d+)$")
# Control (Cc), format (Cf: zero-width and direction marks), surrogate, private-use and unassigned characters, and the line and
# paragraph separators: none belongs in a company name, and some reorder or hide what the owner reads.
_BAD_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=400)
    short_name: str | None = Field(default=None, max_length=400)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[!-~]+$")


def _invalid(field: str, en: str, zh: str, lang: Lang) -> HTTPException:
    return HTTPException(422, {"code": "INVALID_CUSTOMER", "field": field, "message": t(lang, en, zh)})


def _clean(raw: str | None, field: str, limit: int, what: tuple[str, str], lang: Lang, *, required: bool) -> str | None:
    """The name as it will be kept: trimmed; refused when empty (if required), too long, holding a control or format character,
    or made of punctuation only."""
    value = (raw or "").strip()
    if not value:
        if required:
            raise _invalid(field, f"Type the {what[0]}.", f"请填写{what[1]}。", lang)
        return None
    if any(unicodedata.category(ch) in _BAD_CATEGORIES for ch in value):
        raise _invalid(field, f"The {what[0]} holds a character that cannot be kept (a line break, tab or hidden mark).",
                       f"{what[1]}中含有无法保存的字符（换行、制表符或隐藏符号）。", lang)
    if len(value) > limit:
        raise _invalid(field, f"The {what[0]} can be at most {limit} characters.", f"{what[1]}最多 {limit} 个字符。", lang)
    if not normalise(value):
        raise _invalid(field, f"The {what[0]} needs letters or digits.", f"{what[1]}需要包含文字或数字。", lang)
    return value


def added_short_names(store: LedgerStore) -> dict[str, list[str]]:
    """customer id -> the short name the owner gave it when adding it, from the ADD_CUSTOMER entries (the counterparty record
    holds only the name)."""
    out: dict[str, list[str]] = {}
    for r in store.operations():
        if r.kind != ADD_CUSTOMER_KIND:
            continue
        try:
            p = json.loads(r.payload_json)
        except ValueError:
            continue
        if isinstance(p, dict) and isinstance(p.get("customer_id"), str) and isinstance(p.get("short_name"), str):
            out.setdefault(p["customer_id"], []).append(p["short_name"])
    return out


def _next_buyer_id(rt: Any) -> str:
    """The next free BUYER-n: past every BUYER id the books, the documents and the configured channel keys name, so a new
    customer never inherits a channel key, a document or an offer meant for an id that was used before."""
    state = rt.store.get_state()
    ids = {c.id for c in state.counterparties} | set(counterparty_keys())
    ids |= {r.counterparty_id for r in state.receivables}
    ids |= {r.counterparty_id for r in rt.store.contract_guard_rows()}
    ids |= {e.counterparty_id for e in rt.store.security_events() if e.counterparty_id}
    n = max((int(m.group(1)) for i in ids if (m := _BUYER_ID.match(i))), default=0)
    return f"BUYER-{n + 1}"


def _view(cp: Counterparty) -> dict[str, Any]:
    return {"id": cp.id, "name": cp.name, "role": cp.role, "known": cp.known}


def _answer(entry_payload: dict[str, Any], state: Any, created: bool, lang: Lang) -> dict[str, Any]:
    cid = entry_payload["customer_id"]
    cp = next((c for c in state.counterparties if c.id == cid), None) or Counterparty(
        id=cid, name=entry_payload["name"], role="BUYER", known=True)
    return {"customer": _view(cp), "created": created, "event_text": customer_added_words(cp.name, lang)}


@router.post("/customers")
def add_customer(body: CustomerIn, lang: Lang = "en") -> dict[str, Any]:
    from app.persistence.canonical import canonical_json

    rt = get_runtime()
    name = _clean(body.name, "name", MAX_NAME, ("customer's name", "客户名称"), lang, required=True)
    short = _clean(body.short_name, "short_name", MAX_SHORT_NAME, ("short name", "简称"), lang, required=False)
    assert name is not None
    key = f"{ADD_CUSTOMER_KIND}:{body.idempotency_key}"
    with rt.lock:
        earlier = rt.store.find_by_idempotency_key(key)
        if earlier is not None:  # the same request again: the same customer, nothing appended
            return _answer(json.loads(earlier.payload_json), rt.store.get_state(), False, lang)
        state = rt.store.get_state()
        extra = added_short_names(rt.store)
        wanted = {normalise(name), *([normalise(short)] if short else [])}
        for cp in state.counterparties:
            if wanted & taken_names(cp, extra.get(cp.id, ())):
                raise HTTPException(409, {"code": "CUSTOMER_EXISTS", "existing_id": cp.id, "message": t(
                    lang, f"{cp.name} is already on your books, so no customer was added.",
                    f"{cp.name}已在您的账簿中，因此没有添加客户。")})
        cid = _next_buyer_id(rt)
        customer = Counterparty(id=cid, name=name, role="BUYER", known=True)
        books = state.model_copy(update={"counterparties": [*state.counterparties, customer],
                                         "state_version": state.state_version + 1})
        day = rt.day
        op_id = f"ADD-CUSTOMER-{cid}-{day}-{len(rt.store.operations()) + 1}"
        payload = {"kind": ADD_CUSTOMER_KIND, "op_id": op_id, "customer_id": cid, "name": name, "short_name": short,
                   "idempotency_key": body.idempotency_key, "requested_by": Actor.OWNER.value, "day": day,
                   "state_version": books.state_version}
        result = OperationResult(op_id=op_id, kind=ADD_CUSTOMER_KIND, status=OperationStatus.EXECUTED, tier=Tier.TIER_2,
                                 effective_day=day, message=customer_added_words(name, "en"))
        with rt.store.transaction():  # the books with the new customer and the entry that records it, together or not at all
            rt.store.put_state(books, expected_version=state.state_version)
            rt.store.append_operation(op_id, ADD_CUSTOMER_KIND, key, canonical_json(payload), canonical_json(result))
        return _answer(payload, books, True, lang)


__all__ = ["ADD_CUSTOMER_KIND", "added_short_names", "router"]
