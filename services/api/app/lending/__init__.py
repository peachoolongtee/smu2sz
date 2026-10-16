"""Loan eligibility against a synthetic catalogue (ADR-0013, phase 6; docs/capex_handover.md D7, D8).

Read-only and **indicative**: a lender decides, this only reads the lender's stated criteria against the company's own
books. For each catalogue product:

- the amount-dependent criteria are tested pro forma, with the product's own loan added: DSCR = EBITDA_m / (worst projected
  debt service + the loan's highest monthly service), leverage = (worst projected debt + the principal) / (12 × EBITDA_m),
  the service on the ADR-0008 rule (`app.capex.evaluate.term_service`). Both worsen as the principal grows, so the largest
  eligible principal is found by exact integer bisection (`app.health.largest_principal`) up to the product's maximum;
- the other criteria do not move with the amount: the 90-day cash coverage ratio (`app.health`), the share of the largest
  buyer in the open receivables, and the months trading, which only the owner can say (missing: UNKNOWN, never assumed);
- beside the lender's view, the amount the company's **own** limits allow (`app.health.facility_capacity`, the mandate's and
  committed facilities' DSCR and leverage room), and the Tier-3 actions the product needs (collateral, a personal
  guarantee), which the agent never takes.

A product is never usable from here (INVARIANT 4): "add to my funding menu" is the owner's own AddFacility (Tier 2, as a
NOT_APPLIED facility carrying the product's DSCR and leverage covenants), after which the existing capex screen and
`ApplyForFacility` take over.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from fractions import Fraction
from functools import lru_cache
from typing import Literal

from pydantic import Field

from app.capex.evaluate import term_service
from app.domain.fixtures import FIXTURES
from app.domain.models import (
    Commitment,
    Contract,
    Covenant,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    Mandate,
    Repayment,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan
from app.funding.rates import all_in_rate, tier3_reasons
from app.health import CovenantRoom, FinancialHealth, facility_capacity, financial_health, largest_principal

Status = Literal["ELIGIBLE", "ELIGIBLE_UP_TO", "NOT_ELIGIBLE", "UNKNOWN"]
INDICATIVE = ("Indicative only: read from a synthetic catalogue's stated criteria against your books, not a lender's "
              "decision.")


class Criteria(Contract):
    min_dscr_bp: int | None = None
    max_leverage_bp: int | None = None
    min_coverage_bp: int | None = None  # the 90-day cash coverage ratio
    max_buyer_concentration_bp: int | None = None  # the largest buyer's share of open receivables
    min_months_trading: int | None = None


class LoanProduct(Contract):
    id: str
    lender_id: str
    lender_name: str
    name: str
    facility_kind: FacilityKind
    repayment: Repayment
    rate_bp: int = Field(ge=0)
    upfront_fee_bp: int = Field(default=0, ge=0)
    term_months: int = Field(ge=1)
    lead_time_days: int = Field(ge=0)
    min_amount_fen: int = Field(gt=0)
    max_amount_fen: int = Field(gt=0)
    collateral: bool = False
    personal_guarantee: bool = False
    criteria: Criteria = Field(default_factory=Criteria)


class EligibilityInputs(Contract):
    months_trading: int | None = Field(default=None, ge=0)  # only the owner can say
    amount_fen: int | None = Field(default=None, gt=0)  # an amount to test as well as the largest eligible one


class CriterionResult(Contract):
    name: str
    required: str
    observed: str
    passes: bool | None  # None: cannot be read (the owner has not said)
    moves_with_amount: bool


class ProductEligibility(Contract):
    product: LoanProduct
    facility_id: str  # the id it would have on the funding menu
    on_menu: bool
    status: Status
    max_eligible_fen: int | None  # the largest principal the lender's amount criteria allow (None: not even the minimum)
    requested_fen: int | None
    requested_passes: bool | None
    criteria: list[CriterionResult]  # read at the largest eligible principal, else at the product's minimum
    monthly_payment_fen: int | None  # at the largest eligible principal
    all_in_rate: Ratio
    all_in_rate_formula: str
    own_limits_max_fen: int  # what the company's own DSCR, leverage and the product's maximum allow
    own_limits_binding: str
    tier3: list[str]  # Tier-3 actions the product needs: the agent never takes them
    text: str


class Eligibility(Contract):
    day: int
    state_version: int
    products: list[ProductEligibility]
    buyer_concentration: Ratio | None
    largest_buyer_id: str | None
    indicative: str = INDICATIVE
    assumptions: list[str]


@lru_cache(maxsize=1)
def _catalogue_raw() -> str:
    return (FIXTURES / "lending" / "catalogue.json").read_text(encoding="utf-8")


def load_catalogue() -> list[LoanProduct]:
    return [LoanProduct.model_validate_json(json.dumps(p)) for p in json.loads(_catalogue_raw())["products"]]


def facility_of(p: LoanProduct, amount_fen: int | None = None) -> Facility:
    """The product as it would sit on the funding menu: NOT_APPLIED, not yet owner-approved (the owner's AddFacility
    approves it), its limit the amount applied for, its DSCR and leverage criteria carried as covenants."""
    fid = f"FAC-{p.id.removeprefix('PRD-')}"
    covenants = []
    if p.criteria.min_dscr_bp is not None:
        covenants.append(Covenant(id=f"{fid}-DSCR", facility_id=fid, kind=CovenantKind.DSCR_MIN,
                                  threshold_bp=p.criteria.min_dscr_bp,
                                  definition="monthly EBITDA / scheduled debt service (principal + interest)",
                                  formula=f"EBITDA_m / DS_m >= {Ratio.of(bp(p.criteria.min_dscr_bp)).text}"))
    if p.criteria.max_leverage_bp is not None:
        covenants.append(Covenant(id=f"{fid}-LEV", facility_id=fid, kind=CovenantKind.LEVERAGE_MAX,
                                  threshold_bp=p.criteria.max_leverage_bp,
                                  definition="month-end debt / (12 x monthly EBITDA)",
                                  formula=f"Debt / (12 x EBITDA_m) <= {Ratio.of(bp(p.criteria.max_leverage_bp)).text}"))
    return Facility(
        id=fid, name=p.name, kind=p.facility_kind, lender_id=p.lender_id, status=FacilityStatus.NOT_APPLIED,
        owner_approved=False, limit_fen=amount_fen or p.max_amount_fen, rate_bp=p.rate_bp,
        upfront_fee_bp=p.upfront_fee_bp, lead_time_days=p.lead_time_days, term_months=p.term_months,
        repayment=p.repayment, collateral=p.collateral, personal_guarantee=p.personal_guarantee, covenants=covenants,
        source_note=f"Synthetic catalogue product {p.id} ({p.lender_name}); added by the owner from the eligibility read")


def concentration(state: FinancialState) -> tuple[Ratio | None, str | None]:
    """The largest buyer's share of the open receivables' outstanding face (None when nothing is open)."""
    by: dict[str, int] = {}
    for r in state.receivables:
        if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0:
            by[r.counterparty_id] = by.get(r.counterparty_id, 0) + r.outstanding_fen
    total = sum(by.values())
    if total <= 0:
        return None, None
    top = max(sorted(by), key=lambda k: by[k])
    return Ratio.of(Fraction(by[top], total)), top


def _x(v: Fraction) -> str:
    return f"{Ratio.of(v).text}×"


def _amount_criteria(p: LoanProduct, f: Facility, room: CovenantRoom, amount: int) -> list[CriterionResult]:
    out = []
    service = max(term_service(f, amount, p.term_months))
    if p.criteria.min_dscr_bp is not None:
        dscr = Fraction(room.ebitda_fen, room.worst_debt_service_fen + service)
        need = bp(p.criteria.min_dscr_bp)
        out.append(CriterionResult(
            name="DSCR with the loan", required=f"≥ {_x(need)}", passes=dscr >= need, moves_with_amount=True,
            observed=(f"{_x(dscr)} = {fmt_yuan(room.ebitda_fen)} / ({fmt_yuan(room.worst_debt_service_fen)} + "
                      f"{fmt_yuan(service)})")))
    if p.criteria.max_leverage_bp is not None:
        lev = Fraction(room.worst_debt_fen + amount, 12 * room.ebitda_fen)
        cap = bp(p.criteria.max_leverage_bp)
        out.append(CriterionResult(
            name="Leverage with the loan", required=f"≤ {_x(cap)}", passes=lev <= cap, moves_with_amount=True,
            observed=(f"{_x(lev)} = ({fmt_yuan(room.worst_debt_fen)} + {fmt_yuan(amount)}) / (12 × "
                      f"{fmt_yuan(room.ebitda_fen)})")))
    return out


def _fixed_criteria(p: LoanProduct, health: FinancialHealth, conc: Ratio | None, top: str | None,
                    inputs: EligibilityInputs) -> list[CriterionResult]:
    out = []
    c = p.criteria
    if c.min_coverage_bp is not None:
        cov = health.coverage.ratio
        need = bp(c.min_coverage_bp)
        out.append(CriterionResult(
            name="90-day cash coverage", required=f"≥ {_x(need)}", moves_with_amount=False,
            observed=_x(cov.value) if cov is not None else "nothing goes out",
            passes=True if cov is None else cov.value >= need))
    if c.max_buyer_concentration_bp is not None:
        cap = bp(c.max_buyer_concentration_bp)
        out.append(CriterionResult(
            name="Largest buyer's share of receivables", required=f"≤ {fmt_pct(cap)}", moves_with_amount=False,
            observed=f"{fmt_pct(conc.value)} ({top})" if conc is not None else "no open receivables",
            passes=True if conc is None else conc.value <= cap))
    if c.min_months_trading is not None:
        m = inputs.months_trading
        out.append(CriterionResult(
            name="Months trading", required=f"≥ {c.min_months_trading}", moves_with_amount=False,
            observed=str(m) if m is not None else "not given: tell FLOW how long the company has traded",
            passes=None if m is None else m >= c.min_months_trading))
    return out


def evaluate_product(p: LoanProduct, state: FinancialState, health: FinancialHealth, conc: Ratio | None,
                     top: str | None, inputs: EligibilityInputs) -> ProductEligibility:
    f = facility_of(p)
    rate, rate_formula = all_in_rate(f)
    tier3 = [c.value for c in tier3_reasons(f)]
    on_menu = any(x.id == f.id for x in state.facilities)
    fixed = _fixed_criteria(p, health, conc, top, inputs)
    room = health.covenants
    own = facility_capacity(f, room)
    if room is None:  # EBITDA <= 0: no lender ratio can pass
        ebitda = CriterionResult(name="Monthly EBITDA", required="> ¥0.00", observed=fmt_yuan(state.monthly_ebitda_fen),
                                 passes=False, moves_with_amount=False)
        crit = [*fixed, ebitda]
        return ProductEligibility(
            product=p, facility_id=f.id, on_menu=on_menu, status="NOT_ELIGIBLE", max_eligible_fen=None,
            requested_fen=inputs.amount_fen, requested_passes=False if inputs.amount_fen else None, criteria=crit,
            monthly_payment_fen=None, all_in_rate=Ratio.of(rate), all_in_rate_formula=rate_formula,
            own_limits_max_fen=0, own_limits_binding=own.binding, tier3=tier3,
            text=f"{p.name} ({p.lender_name}): not eligible while monthly EBITDA is not positive.")

    def fits(amount: int) -> bool:
        return all(c.passes for c in _amount_criteria(p, f, room, amount))

    cap = largest_principal(fits, p.max_amount_fen)
    reaches = cap >= p.min_amount_fen
    at = cap if reaches else p.min_amount_fen
    crit = [*_amount_criteria(p, f, room, at), *fixed]
    fixed_fail = any(c.passes is False for c in fixed)
    unknown = any(c.passes is None for c in fixed)
    if fixed_fail or not reaches:
        status: Status = "NOT_ELIGIBLE"
    elif unknown:
        status = "UNKNOWN"
    else:
        status = "ELIGIBLE" if cap == p.max_amount_fen else "ELIGIBLE_UP_TO"
    requested_passes: bool | None = None
    if inputs.amount_fen is not None:
        amount_ok = p.min_amount_fen <= inputs.amount_fen <= p.max_amount_fen and fits(inputs.amount_fen)
        requested_passes = False if not amount_ok or fixed_fail else None if unknown else True
    pay = max(term_service(f, cap, p.term_months)) if reaches else None
    failing = [c.name.lower() for c in crit if c.passes is False]
    if status == "NOT_ELIGIBLE":
        why = (", ".join(failing) if failing else "the minimum amount does not fit its ratio criteria")
        text = f"{p.name} ({p.lender_name}): not eligible on its stated criteria: {why}."
    elif status == "UNKNOWN":
        text = (f"{p.name} ({p.lender_name}): up to {fmt_yuan(cap)} on the ratios, but it also needs "
                + ", ".join(c.name.lower() for c in crit if c.passes is None) + ", which only you can give.")
    else:
        text = (f"{p.name} ({p.lender_name}): eligible "
                + (f"for its full {fmt_yuan(cap)}" if status == "ELIGIBLE" else f"up to {fmt_yuan(cap)}")
                + f" at {fmt_yuan(pay or 0)} a month, all-in {fmt_pct(rate)} a year.")
    if reaches and own.capacity_fen < cap:
        by = {"DSCR": "your DSCR minimum", "LEVERAGE": "your leverage maximum"}.get(own.binding, "the product")
        text += f" Your own limits allow {fmt_yuan(own.capacity_fen)} (set by {by})."
    if tier3:
        text += (" It needs " + " and ".join("a personal guarantee" if t == "TIER3_PERSONAL_GUARANTEE" else "collateral"
                                              for t in tier3) + ": a Tier-3 step FLOW never takes; only you can.")
    return ProductEligibility(
        product=p, facility_id=f.id, on_menu=on_menu, status=status, max_eligible_fen=cap if reaches else None,
        requested_fen=inputs.amount_fen, requested_passes=requested_passes, criteria=crit, monthly_payment_fen=pay,
        all_in_rate=Ratio.of(rate), all_in_rate_formula=rate_formula, own_limits_max_fen=own.capacity_fen,
        own_limits_binding=own.binding, tier3=tier3, text=text)


ASSUMPTIONS = (
    INDICATIVE,
    ("Each product is read on its own, with only its loan added to the worst projected month's debt service and debt; "
     "two loans together leave less room than either alone."),
    ("A product's DSCR and leverage criteria are the lender's; your own mandate's limits are shown beside them as the "
     "amount your own limits allow."),
    ("The largest buyer's share is read on the open receivables' outstanding face; months trading is what you say."),
)


def eligibility(state: FinancialState, mandate: Mandate, *, commitments: Sequence[Commitment] = (),
                inputs: EligibilityInputs | None = None, products: Sequence[LoanProduct] | None = None) -> Eligibility:
    inputs = inputs or EligibilityInputs()
    health = financial_health(state, mandate, commitments=commitments)
    conc, top = concentration(state)
    rows = [evaluate_product(p, state, health, conc, top, inputs) for p in (products or load_catalogue())]
    order = {"ELIGIBLE": 0, "ELIGIBLE_UP_TO": 1, "UNKNOWN": 2, "NOT_ELIGIBLE": 3}
    # best first: by status, then a product needing no Tier-3 step before one that does, then the cheaper all-in rate
    rows.sort(key=lambda r: (order[r.status], bool(r.tier3), r.all_in_rate.value, r.product.id))
    return Eligibility(day=state.as_of_day, state_version=state.state_version, products=rows, buyer_concentration=conc,
                       largest_buyer_id=top, assumptions=list(ASSUMPTIONS))


def product(product_id: str) -> LoanProduct | None:
    return next((p for p in load_catalogue() if p.id == product_id), None)


__all__ = ["INDICATIVE", "Criteria", "CriterionResult", "Eligibility", "EligibilityInputs", "LoanProduct",
           "ProductEligibility", "concentration", "eligibility", "evaluate_product", "facility_of", "load_catalogue",
           "product"]
