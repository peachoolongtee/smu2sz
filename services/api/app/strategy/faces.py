"""The face FLOW would actually send for an early payment on one receivable: the face of the verifier's own Option A
counter (docs/STRATEGY_MVP_BRIEF.md sections 5.1 and 5.3).

Found the way the Safe Deal Envelope finds it: ask for the largest early-payment rate in the grid on the whole
outstanding invoice, evaluate the offer under the router's committed plan, and read the face of the early-pay counter
the verifier answers with. One evaluation; read-only and pure in (books, mandate, day, receivable, commitments).
One early-payment figure per invoice across the pages is the point: collections and the Deals card quote this face.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Sequence

from app.books import Books
from app.domain.models import Commitment, Mandate, ObligationType
from app.verifier import evaluate
from app.verifier.bind import early_pay_lead
from app.whatif.offer import EarlyPayContext, build
from app.whatif.params import DISCOUNT_MAX_BP, RATE_STEP_BP, TERMS_MIN, WhatIfParams

_CACHE_SIZE = 64
_CACHE: OrderedDict[str, int | None] = OrderedDict()
_LOCK = threading.Lock()


def clear_face_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _key(books: Books, mandate: Mandate, receivable_id: str, day: int, commitments: Sequence[Commitment]) -> str:
    held = "|".join(c.model_dump_json() for c in commitments)
    raw = f"{books.state.model_dump_json()}|{mandate.model_dump_json()}|{day}|{receivable_id}|{held}"
    return hashlib.sha256(raw.encode()).hexdigest()


def option_a_face(books: Books, mandate: Mandate, receivable_id: str, *, trusted_owner_key_hex: str, day: int,
                  commitments: Sequence[Commitment] = ()) -> int | None:
    """The early-pay face (fen) of the verifier's counter to an ask of the top early-pay rate on the whole outstanding
    invoice of `receivable_id`; None when the receivable cannot be paid early or the verifier offers no early-pay
    counter on a part of the invoice (every early rate on the whole of it passes, or none has a counter)."""
    key = _key(books, mandate, receivable_id, day, commitments)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    face = _face(books, mandate, receivable_id, trusted_owner_key_hex, day, commitments)
    with _LOCK:
        _CACHE[key] = face
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return face


def _face(books: Books, mandate: Mandate, receivable_id: str, key: str, day: int,
          commitments: Sequence[Commitment]) -> int | None:
    state = books.state
    r = next((x for x in state.receivables if x.id == receivable_id), None)
    if r is None or r.status != "OPEN" or r.outstanding_fen <= 0 or r.due_day < day:
        return None
    if r.due_day - early_pay_lead(state, r.counterparty_id) <= 0:
        return None  # settled before it is due, or not an early payment at all (the verifier's `_early_pay_legs`)
    cap = DISCOUNT_MAX_BP if mandate.max_immediate_discount_bp is None else min(DISCOUNT_MAX_BP, mandate.max_immediate_discount_bp)
    top = cap - cap % RATE_STEP_BP
    if top <= 0:
        return None
    whole = r.model_copy(update={"face_fen": r.outstanding_fen})  # an invoice paid in part is asked about for what it owes
    ctx = EarlyPayContext(r.counterparty_id, whole, None)
    offer, _ = build(WhatIfParams(terms_days=TERMS_MIN, discount_bp=top, rebate_bp=0), ctx, day)
    verdict = evaluate(offer, state, mandate, trusted_owner_key_hex=key, day=day, commitments=commitments,
                       plans="committed").verdict
    for counter in verdict.counters:
        for o in counter.obligations:
            if (o.type == ObligationType.IMMEDIATE_DISCOUNT and o.rate_bp and o.days_delta is None
                    and o.base.amount_fen is not None and o.base.amount_fen != r.outstanding_fen):
                return o.base.amount_fen
    return None


__all__ = ["clear_face_cache", "option_a_face"]
