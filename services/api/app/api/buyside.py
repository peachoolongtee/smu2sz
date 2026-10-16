"""The buy side's company-wide reads (ADR-0013): financial health, loan eligibility and long-term plans. Owner only, behind
FEATURE_CAPEX_CONTRACTS, read-only: nothing here writes the books or queues an operation, except where a route says so and
then only through the executor (Tier 2)."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_owner
from app.api.capex import _with_null_displays
from app.api.display import displayed as _displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.capex.plans import PlanRefused, PlanRequest, PlanResult
from app.capex.plans import plan as capex_plan
from app.deals.purchases import purchase_row, purchases
from app.domain.models import Actor, AddFacility, DocumentKind
from app.domain.money import Ratio, fmt_pct, fmt_yuan
from app.financial import EngineError
from app.health import FinancialHealth, HealthInputs, financial_health
from app.lending import Eligibility, EligibilityInputs, eligibility, facility_of
from app.lending import product as lending_product

router = APIRouter(dependencies=[Depends(require_owner)])


def displayed(x: Any) -> Any:
    """The server's display rule, and a null `<name>_display` beside every null `<name>_fen` (as the capex view does)."""
    return _with_null_displays(_displayed(x))


def _buy_side() -> None:
    require_feature("capex_contracts")


def _x(r: dict[str, Any] | None) -> None:
    """A ratio said as a multiple ("2.55×"): `displayed` adds `text`; this adds the × the owner reads."""
    if isinstance(r, dict) and "text" in r:
        r["display"] = f"{r['text']}×"


def _pct(r: Ratio | None) -> str | None:
    return fmt_pct(r.value) if r is not None else None


def health_view(h: FinancialHealth) -> dict[str, Any]:
    view: dict[str, Any] = displayed(json.loads(h.model_dump_json()))
    _x(view["coverage"].get("ratio"))
    for k in ("current_ratio", "quick_ratio"):
        _x(view["liquidity"].get(k))
    if view.get("covenants"):
        for k in ("worst_dscr", "min_dscr", "worst_leverage", "max_leverage"):
            _x(view["covenants"].get(k))
    return view


class HealthIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: HealthInputs = Field(default_factory=HealthInputs)


def _health(inputs: HealthInputs) -> dict[str, Any]:
    _buy_side()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            h = financial_health(state, mandate, commitments=rt.store.commitments(), inputs=inputs)
        except EngineError as exc:
            raise HTTPException(422, {"code": "CANNOT_PROJECT", "message": f"the books cannot be projected: {exc}"}) from None
    return health_view(h)


@router.get("/finance/health")
def get_finance_health() -> dict[str, Any]:
    """Cash, the 90-day cash coverage ratio, covenant room and borrowing capacity on current books."""
    return _health(HealthInputs())


@router.post("/finance/health")
def post_finance_health(body: HealthIn) -> dict[str, Any]:
    """The same, with the owner's balance-sheet entries, so the current and quick ratios can be read (OWNER_ESTIMATE)."""
    return _health(body.inputs)


# ---------------------------------------------------------------- loan eligibility (phase 6)


class EligibilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: EligibilityInputs = Field(default_factory=EligibilityInputs)


def eligibility_view(e: Eligibility) -> dict[str, Any]:
    view: dict[str, Any] = displayed(json.loads(e.model_dump_json()))
    for row, model in zip(view["products"], e.products, strict=True):
        row["all_in_rate_display"] = _pct(model.all_in_rate)
    if e.buyer_concentration is not None:
        view["buyer_concentration_display"] = _pct(e.buyer_concentration)
    return view


def _eligibility(inputs: EligibilityInputs) -> dict[str, Any]:
    _buy_side()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            e = eligibility(state, mandate, commitments=rt.store.commitments(), inputs=inputs)
        except EngineError as exc:
            raise HTTPException(422, {"code": "CANNOT_PROJECT", "message": f"the books cannot be projected: {exc}"}) from None
    return eligibility_view(e)


@router.get("/lending/eligibility")
def get_eligibility() -> dict[str, Any]:
    """Indicative eligibility for every catalogue product on current books (no months trading, no amount)."""
    return _eligibility(EligibilityInputs())


@router.post("/lending/eligibility")
def post_eligibility(body: EligibilityIn) -> dict[str, Any]:
    """The same with the owner's months trading and an amount to test."""
    return _eligibility(body.inputs)


class AddToMenuIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_fen: int | None = Field(default=None, gt=0)  # None: the largest eligible amount, else the product's maximum


@router.post("/lending/products/{product_id}/add-to-menu")
def post_add_to_menu(product_id: str, body: AddToMenuIn | None = None) -> dict[str, Any]:
    """Queue the owner's own AddFacility (Tier 2, INVARIANT 3) for a catalogue product: it enters the funding menu as a
    NOT_APPLIED facility (zero for every hard constraint, INVARIANT 4) carrying the product's DSCR and leverage covenants,
    once the owner approves it on /approvals/{id}. Applying for it is then the existing ApplyForFacility."""
    _buy_side()
    body = body or AddToMenuIn()
    p = lending_product(product_id)
    if p is None:
        raise HTTPException(404, {"code": "UNKNOWN_PRODUCT", "message": f"no catalogue product {product_id}"})
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        fac = facility_of(p)
        if any(f.id == fac.id for f in state.facilities):
            raise HTTPException(409, {"code": "ALREADY_ON_MENU", "message": f"{p.name} is already on your funding menu"})
        e = eligibility(state, mandate, commitments=rt.store.commitments(), products=[p])
        row = e.products[0]
        amount = body.amount_fen or row.max_eligible_fen or p.max_amount_fen
        if not p.min_amount_fen <= amount <= p.max_amount_fen:
            raise HTTPException(422, {"code": "AMOUNT_OUT_OF_RANGE",
                                      "message": f"{p.name} lends {fmt_yuan(p.min_amount_fen)} to "
                                                 f"{fmt_yuan(p.max_amount_fen)}"})
        op = AddFacility(op_id=f"add-{fac.id}-{rt.day}", idempotency_key=f"lending-add:{fac.id}:{amount}",
                         mandate_version=mandate.version, requested_by=Actor.OWNER, day=rt.day,
                         facility=facility_of(p, amount))
        result = rt.executor.execute(op)  # Tier 2: PENDING_APPROVAL until the owner approves it
    return {"approval_id": result.approval_id, "status": result.status.value, "facility_id": fac.id,
            "amount_fen": amount, "amount_display": fmt_yuan(amount), "eligibility": eligibility_view(e)["products"][0],
            "result": json.loads(result.model_dump_json())}


# ---------------------------------------------------------------- long-term plans (phase 7)


def plan_view(r: PlanResult) -> dict[str, Any]:
    view: dict[str, Any] = displayed(json.loads(r.model_dump_json()))
    for group in ([*view["best"], view["best_unconstrained"]] if view.get("best_unconstrained") else view["best"]):
        for month in group.get("months", []):
            _x(month.get("dscr"))
            _x(month.get("leverage"))
    return view


@router.post("/capex/plans")
def post_capex_plans(body: PlanRequest) -> dict[str, Any]:
    """The ranked permutations of several purchases, their start months and their financing: a monthly estimate
    (OWNER_ESTIMATE), never a hard constraint; the best plan's contracts are re-run through the daily capex screen."""
    _buy_side()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            r = capex_plan(body, state, mandate, rt.store.contract_records(), commitments=rt.store.commitments())
        except PlanRefused as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from None
    return plan_view(r)


# ---------------------------------------------------------------- the buying side of Deals (phase 8)


@router.get("/purchases")
def get_purchases(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    """Every capex contract, where it stands and the one thing to do next (also on GET /deals as `purchases`)."""
    _buy_side()
    rt = get_runtime()
    with rt.lock:
        return {"day": rt.day, "lang": lang, "purchases": purchases(rt.store, rt.day, lang)}


@router.get("/purchases/{document_id}")
def get_purchase(document_id: str, lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    _buy_side()
    rt = get_runtime()
    with rt.lock:
        rec = rt.store.get_contract_record(document_id)
        if rec is None or rec.kind != DocumentKind.CAPEX_CONTRACT:
            raise HTTPException(404, {"code": "UNKNOWN_PURCHASE", "message": f"no capex contract {document_id}"})
        return {"day": rt.day, "lang": lang, "purchase": purchase_row(rec, rt.store, rt.day, lang)}
