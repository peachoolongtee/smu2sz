"""The what-if sandbox: run the real verifier on a hypothetical package and return display views.

DISPLAY-ONLY. `simulate()` never executes an operation, never writes state and never touches a
store: it takes a state and a mandate by value and returns a view labelled `hypothetical`. Every
number is computed here by the same engine, router and verifier that decide real offers
(conservative mode, INVARIANT 11) and ships as integer fen plus a server-formatted display string
(INVARIANT 13).

Results are cached (LRU) by (state, mandate, day, params): the engine is deterministic, so the same
key always gives the same view.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.display import displayed
from app.api.views import trajectory_view
from app.books import current_books
from app.domain.models import (
    Commitment,
    FinancialState,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    ObligationType,
    Violation,
    ViolationCode,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.financial import project
from app.funding import NoPermanentSourceError, break_even_discount
from app.verifier import VerdictBundle, evaluate
from app.whatif.offer import DOC_ID, Context, build, context
from app.whatif.params import PRESETS, RATE_STEP_BP, WhatIfParamError, WhatIfParams, grid

CACHE_SIZE = 256
FACE_STOP_FEN = 1_000_000  # face slider stops every ¥10,000, plus the whole invoice and preset faces
HYPOTHETICAL_NOTE = "Hypothetical: nothing is booked, sent or executed. The same verifier decides real offers."

COVENANT_CODES = {"DSCR_MIN": ViolationCode.DSCR_BREACH, "LEVERAGE_MAX": ViolationCode.LEVERAGE_BREACH,
                  "CLEAN_DOWN": ViolationCode.CLEAN_DOWN_BREACH}
OBLIGATION_LABELS = {
    ObligationType.IMMEDIATE_DISCOUNT: "Early-settlement discount",
    ObligationType.TERMS_EXTENSION: "Payment-terms change",
    ObligationType.CONTINGENT_REBATE: "Next-quarter rebate (counted at maximum)",
    ObligationType.PRICE_ADJUSTMENT: "Price adjustment",
}


class WhatIfResult(BaseModel):
    """Display view of one hypothetical evaluation. Money fields carry `*_display` siblings."""

    hypothetical: Literal[True] = True
    note: str = HYPOTHETICAL_NOTE
    key: str
    params: dict[str, Any]
    description: dict[str, Any]
    outcome: str
    required_tier: str
    codes: list[str]
    summary: str
    violations: list[dict[str, Any]]
    reserve: dict[str, Any]
    trajectory: dict[str, Any] | None
    funded: dict[str, Any] | None
    forward: dict[str, Any]
    covenants: list[dict[str, Any]]
    plan: dict[str, Any] | None
    break_even: dict[str, Any] | None
    counters: list[dict[str, Any]]
    notes: list[str] = Field(default_factory=list)
    compute_ms: int = 0
    cached: bool = False


# ---------------------------------------------------------------- cache


class _Lru:
    def __init__(self, size: int) -> None:
        self.size = size
        self.data: OrderedDict[str, WhatIfResult] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> WhatIfResult | None:
        with self.lock:
            hit = self.data.get(key)
            if hit is not None:
                self.data.move_to_end(key)
            return hit

    def put(self, key: str, value: WhatIfResult) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.data.clear()


_cache = _Lru(CACHE_SIZE)


def clear_cache() -> None:
    _cache.clear()


def _normalise(params: WhatIfParams, ctx: Context) -> WhatIfParams:
    """Drop what cannot change the result, so equivalent slider positions share one cache entry."""
    face = params.settle_face_fen
    if params.discount_bp == 0 or face == ctx.receivable.face_fen:
        face = None
    return params.model_copy(update={"settle_face_fen": face})


def cache_key(state: FinancialState, mandate: Mandate, day: int, params: WhatIfParams,
              live: Sequence[Obligation] = (), buyer_id: str | None = None) -> str:
    """The commitments in force change the books, so their obligations are part of the key; so is the buyer the sandbox runs on when one is named."""
    h = hashlib.sha256()
    parts = [state.model_dump_json(), mandate.model_dump_json(), str(day), params.model_dump_json()]
    if live:
        parts.append("|".join(o.model_dump_json() for o in live))
    if buyer_id is not None:
        parts.append("buyer:" + buyer_id)
    for part in parts:
        h.update(part.encode())
        h.update(b"|")
    return h.hexdigest()[:20]


# ---------------------------------------------------------------- views


def _dump(x: BaseModel) -> Any:
    return json.loads(x.model_dump_json())


def _violation_view(v: Violation) -> dict[str, Any]:
    return displayed({
        "code": v.code.value, "message": v.message, "day": v.day, "month": v.month, "observed": v.observed,
        "limit": v.limit, "curable": v.curable, "cure_cost_fen": v.cure_cost_fen, "cure_note": v.cure_note,
        "formula": v.formula,
    })


def _plan_view(p: FundingPlan | None, state: FinancialState) -> dict[str, Any] | None:
    if p is None:
        return None
    names = {f.id: f.name for f in state.facilities}
    return displayed({
        "label": p.label, "basis": p.basis, "admissible": p.admissible, "need_fen": p.need_fen,
        "total_cost_fen": p.total_cost_fen,
        "actions": [{"kind": a.kind.value, "facility_id": a.facility_id, "facility": names.get(a.facility_id, ""),
                     "day": a.day, "amount_fen": a.amount_fen, "repay_day": a.repay_day} for a in p.actions],
        "costs": [{"label": c.label, "fen": c.fen, "formula": c.formula} for c in p.costs],
    })


def _series(traj_days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The cash line only: day, closing Money {fen (axis), text (display)}, below_floor (server-decided)."""
    return [{k: d[k] for k in ("day", "closing", "below_floor")} for d in traj_days]


def _covenants(b: VerdictBundle) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for code, breach in COVENANT_CODES.items():
        v = next((v for v in b.verdict.violations if v.code == breach), None)
        if v is not None:
            out.append({"code": code, "label": v.message, "observed": v.observed or "", "limit": v.limit or "",
                        "ok": False, "formula": v.formula or ""})
            continue
        p = next((p for p in b.passed_checks if p.code == code), None)
        if p is not None:
            out.append({"code": code, "label": p.label, "observed": p.observed, "limit": p.limit, "ok": True,
                        "formula": p.formula})
    return out


def _forward(b: VerdictBundle, state: FinancialState, mandate: Mandate) -> dict[str, Any]:
    v = b.verdict
    total = v.forward_concession_total_fen
    cap = mandate.max_aggregate_forward_concession_fen
    existing = sum(fc.value_fen for fc in state.forward_concessions)
    types = {o.id: o.type for o in b.bound_obligations}
    items = []
    for cv in v.concession_values:
        t = types.get(cv.obligation_id)
        items.append({"obligation_type": t.value if t else "", "label": OBLIGATION_LABELS.get(t, str(t)) if t else "",
                      "value_fen": cv.value_fen, "per_invoice_fen": cv.per_invoice_fen, "formula": cv.formula,
                      "basis": cv.basis})
    return displayed({
        "total_fen": total, "cap_fen": cap, "existing_fen": existing, "headroom_fen": cap - total,
        "over_cap": total > cap, "items": items,
    })


def _break_even(params: WhatIfParams, state: FinancialState, mandate: Mandate) -> dict[str, Any] | None:
    try:
        d, floor_bp = break_even_discount(state, mandate)
    except NoPermanentSourceError:
        return None
    offered = bp(params.discount_bp)
    return {
        "bp": floor_bp, "display": fmt_pct(d.value), "exact": fmt_pct(d.value, 4),
        "discount_display": fmt_pct(offered),
        "discount_above": params.discount_bp > 0 and offered >= d.value,
        "formula": "d/(1−d) < c, c = marginal all-in rate × 30/365; d = c/(1+c)",
    }


def _reserve(v: Violation | None, traj: dict[str, Any] | None) -> dict[str, Any]:
    """The reserve verdict. `breach_day` and its siblings are the verifier's: a breach the hypothetical package CAUSES (none when the books are
    already below the minimum without it). `below_days` is the cash line's own: how many days of the horizon close below the minimum, whatever the
    cause, so the word beside "lowest cash" can follow that lowest cash (`stays_above` is its negation; both null without a trajectory)."""
    below = sum(1 for d in traj["days"] if d["below_floor"]) if traj else None
    own = {"below_days": below, "stays_above": below == 0 if below is not None else None}
    if v is None:
        return {"breach_day": None, "curable": None, "cure_cost_fen": None, "cure_cost_display": None,
                "observed": None, "first_unfunded_day": traj["first_breach_day"] if traj else None, **own}
    return displayed({"breach_day": v.day, "curable": v.curable, "cure_cost_fen": v.cure_cost_fen,
                      "observed": v.observed, "cure_note": v.cure_note,
                      "first_unfunded_day": traj["first_breach_day"] if traj else None, **own})


def _view(b: VerdictBundle, params: WhatIfParams, ctx: Context, text: str, key: str,
          state: FinancialState, mandate: Mandate, live: Sequence[Obligation] = ()) -> WhatIfResult:
    v = b.verdict
    floor = mandate.min_cash_fen
    traj = funded = None
    if b.trajectory is not None:
        tv = _dump(trajectory_view(b.trajectory, floor))
        days = _series(tv.pop("days"))
        traj = {**displayed(tv), "days": days}
        pc = b.plan_committed
        if pc is not None and pc.admissible and pc.actions:
            ft = project(state, [*live, *b.bound_obligations], pc.actions, Mode.CONSERVATIVE, mandate.horizon_days, floor)
            fv = _dump(trajectory_view(ft, floor))
            funded = {**displayed({"label": pc.label, "min_cash": fv["min_cash"], "min_cash_day": fv["min_cash_day"],
                                   "first_breach_day": fv["first_breach_day"]}), "days": _series(fv["days"])}
    reserve_v = next((x for x in v.violations if x.code == ViolationCode.RESERVE_BREACH), None)
    spans = [{"obligation_type": o.type.value, "label": OBLIGATION_LABELS.get(o.type, o.type.value),
              "span": _dump(o.spans[0])} for o in b.bound_obligations]
    p = params.model_dump()
    p.update({"current_terms_days": ctx.recurring.terms_days, "receivable_id": ctx.receivable.id,
              "receivable_face_fen": ctx.receivable.face_fen,
              "effective_face_fen": (params.settle_face_fen or ctx.receivable.face_fen) if params.discount_bp else None,
              "order_fen": ctx.order.amount_fen if ctx.order else None})
    return WhatIfResult(
        key=key, params=displayed(p),
        description={"doc_id": DOC_ID, "text": text, "obligations": spans},
        outcome=v.outcome.value, required_tier=v.required_tier.value,
        codes=list(dict.fromkeys(x.code.value for x in v.violations)), summary=v.summary,
        violations=[_violation_view(x) for x in v.violations], reserve=_reserve(reserve_v, traj),
        trajectory=traj, funded=funded, forward=_forward(b, state, mandate), covenants=_covenants(b),
        plan=_plan_view(b.plan_committed, state), break_even=_break_even(params, state, mandate),
        counters=[displayed({"label": c.label, "text": c.text, "supplier_cost_fen": c.supplier_cost_fen,
                             "forward_value_fen": c.forward_value_fen, "rationale": c.rationale})
                  for c in v.counters],
        notes=[n.message for n in b.notes],
    )


# ---------------------------------------------------------------- entry point


def simulate(
    state: FinancialState,
    mandate: Mandate,
    params: WhatIfParams,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    commitments: Sequence[Commitment] = (),
    buyer_id: str | None = None,
) -> WhatIfResult:
    """Evaluate the hypothetical package `params` against current books (`state` plus the obligations of
    the live `commitments`) under `mandate`, on `buyer_id`'s recurring invoice and earliest open receivable (without one: the books' first
    buyer with a recurring invoice). Pure: reads its arguments only and writes nothing. Raises WhatIfParamError when the params do not fit the
    state, or when the buyer has no recurring invoice to extend."""
    started = time.perf_counter()
    ctx = resolve(state, day, buyer_id)
    params = _normalise(params, ctx)
    live = current_books(state, commitments).obligations
    key = cache_key(state, mandate, day, params, live, buyer_id)
    hit = _cache.get(key)
    if hit is not None:
        return hit.model_copy(update={"cached": True,
                                      "compute_ms": int((time.perf_counter() - started) * 1000)})
    offer, text = build(params, ctx, day)
    bundle = evaluate(offer, state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                      commitments=commitments, plans="committed")
    result = _view(bundle, params, ctx, text, key, state, mandate, live)
    result = result.model_copy(update={"compute_ms": int((time.perf_counter() - started) * 1000)})
    _cache.put(key, result)
    return result


def resolve(state: FinancialState, day: int = 0, buyer_id: str | None = None) -> Context:
    """The rows the sliders act on: the buyer's recurring invoice and earliest open receivable not yet past due (`buyer_id`), else the books'
    first buyer with both. A buyer the sandbox cannot value as a whole (no recurring invoice: only an early payment, or only a rebate, can be
    valued) is refused with the reason, since the sliders move terms, price and rebate on a recurring invoice."""
    if buyer_id is None:
        return context(state, day)
    found = context(state, day, buyer_id)
    if not isinstance(found, Context):
        name = next((c.name for c in state.counterparties if c.id == buyer_id), buyer_id)
        raise WhatIfParamError(f"{name} has no recurring invoice to extend; the sandbox needs one")
    return found


def presets(state: FinancialState, day: int = 0, buyer_id: str | None = None) -> dict[str, Any]:
    """Preset slider positions, the slider grid, and server-formatted labels for every slider stop,
    so the UI shows readouts without formatting a rate or an amount itself (INVARIANT 13). On `buyer_id`'s invoice when one is named."""
    ctx = resolve(state, day, buyer_id)
    face = ctx.receivable.face_fen
    g = grid(face)
    rate_max = max(g[k]["max"] for k in ("discount_bp", "rebate_bp", "price_adjustment_bp"))
    faces = set(range(FACE_STOP_FEN, face, FACE_STOP_FEN)) | {face}
    faces |= {p.settle_face_fen for p in PRESETS.values() if p.settle_face_fen is not None and p.settle_face_fen <= face}
    return {
        **displayed({
            "presets": {k: v.model_dump() for k, v in PRESETS.items()},
            "grid": g,
            "current_terms_days": ctx.recurring.terms_days,
            "receivable_id": ctx.receivable.id,
            "receivable_face_fen": face,
        }),
        "rate_labels": {str(b): fmt_pct(bp(b)) for b in range(0, rate_max + 1, RATE_STEP_BP)},
        "face_stops": [{"fen": f, "display": fmt_yuan(f)} for f in sorted(faces)],
        "note": HYPOTHETICAL_NOTE,
    }
