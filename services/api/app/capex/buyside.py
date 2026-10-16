"""The buy side of one capex contract (ADR-0013, phase 3): the contract's payment schedule, the capex screen run on it, and
the vendor's early-payment discount priced the way the sell side prices one (ADR-0007, mirrored).

Read-only: nothing is stored, booked or queued. The schedule is derived by code (`app.capex.schedule`), the screen is
`evaluate_capex` unchanged apart from the dated payments, and the early-payment rule is the engine's:

- the discount d paid `days` early returns d / (1 − d) on what is paid (`app.funding.rates.early_pay_rate` annualises it);
- carrying that money for those days costs c, the marginal committed source's cost share for the tenor
  (`app.funding.rates.break_even_cost_share`, the same function the sell side's break-even discount uses);
- it is worth taking when d / (1 − d) > c, and it is taken only if some structure pays the early schedule without
  breaking the reserve (the screen re-run on that schedule selects one).
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from pydantic import Field

from app.capex.appraisal import payment_month
from app.capex.evaluate import evaluate_capex, is_term_facility
from app.capex.models import CapexCandidate, CapexPayment, CapexRequest, CapexResult
from app.capex.schedule import (
    EarlyPayOption,
    PaymentSchedule,
    ScheduleResult,
    Timeline,
    derive_schedule,
    early_schedule,
)
from app.domain.models import (
    Commitment,
    Contract,
    ContractRecord,
    DocumentKind,
    DocumentStatus,
    FacilityStatus,
    FinancialState,
    Mandate,
)
from app.domain.money import BP_DENOM, Ratio, fmt_pct, fmt_yuan
from app.funding.rates import NoPermanentSourceError, break_even_cost_share, marginal_cost


class CapexEstimate(Contract):
    """The owner's estimate for a contract's purchase: what the equipment earns and the tests to apply. The price and
    the payment days come from the contract, never from here."""

    monthly_uplift_fen: int = Field(default=2_200_000, ge=0)
    uplift_start_month: int | None = Field(default=None, ge=1)  # None: the month after acceptance (or delivery)
    life_months: int = Field(default=60, ge=1, le=600)
    hurdle_bp: int = Field(default=1000, ge=0)
    payback_limit_months: int = Field(default=36, ge=1)
    # None: every owner-approved term facility on the funding menu at its own term (so a catalogue loan the owner added
    # from the eligibility read is screened too); hypothetical terms are the capex screen's illustrations, not used here
    candidates: list[CapexCandidate] | None = None
    include_cash_line: bool = True


class EarlyPayDecision(Contract):
    option: EarlyPayOption
    return_share: Ratio  # d / (1 − d): what the discount returns on what is paid early
    cost_share: Ratio | None  # c: what the marginal committed source charges to carry it for the days; None: no source
    marginal_rate: Ratio | None
    marginal_facility_id: str | None
    worth_it: bool  # return_share > cost_share
    liquidity_ok: bool  # some structure pays the early schedule without breaking the reserve
    take: bool
    text: str
    formula: str


class BuySideEvaluation(Contract):
    document_id: str
    doc_hash: str
    title: str
    counterparty_id: str
    reading_confirmed: bool  # an unconfirmed reading may be screened, never committed
    timeline: Timeline
    uplift_start_month: int | None  # the month used (the owner's, or derived)
    uplift_start_basis: str | None
    schedule: ScheduleResult
    evaluation: CapexResult | None = None  # on the contract's own schedule
    early_pay: EarlyPayDecision | None = None
    early_pay_evaluation: CapexResult | None = None  # on the schedule with the early payment taken
    early_pay_schedule: PaymentSchedule | None = None  # that schedule (with its own hash, to commit it)
    summary: str


class NotACapexContract(ValueError):
    code = "NOT_A_CAPEX_CONTRACT"


def _start_month(estimate: CapexEstimate, timeline: Timeline, today: int) -> tuple[int, str]:
    """The uplift's first month: the owner's, else the month after the equipment is accepted (or delivered)."""
    if estimate.uplift_start_month is not None:
        return estimate.uplift_start_month, "your estimate"
    for name, day in (("acceptance", timeline.acceptance_day), ("delivery", timeline.delivery_day)):
        if day is not None:
            return payment_month(day, today) + 1, f"the month after {name} (day {day})"
    return CapexRequest.model_fields["uplift_start_month"].default, "the default (no delivery or acceptance day given)"


def menu_candidates(state: FinancialState) -> list[CapexCandidate]:
    """Every owner-approved term facility on the funding menu that can still be used or applied for, at its own term."""
    usable = (FacilityStatus.NOT_APPLIED, FacilityStatus.PENDING, FacilityStatus.COMMITTED)
    return [CapexCandidate(facility_id=f.id, term_months=f.term_months) for f in state.facilities
            if f.owner_approved and f.status in usable and is_term_facility(f) and f.term_months]


def _request(record: ContractRecord, schedule: PaymentSchedule, estimate: CapexEstimate, start: int,
             state: FinancialState) -> CapexRequest:
    candidates = estimate.candidates if estimate.candidates is not None else menu_candidates(state)
    return CapexRequest(
        label=record.title, price_fen=schedule.price_fen, monthly_uplift_fen=estimate.monthly_uplift_fen,
        uplift_start_month=start, life_months=estimate.life_months, hurdle_bp=estimate.hurdle_bp,
        payback_limit_months=estimate.payback_limit_months, candidates=list(candidates),
        include_cash_line=estimate.include_cash_line, extension_target_terms_days=None,
        payments=[CapexPayment(day=p.day, amount_fen=p.amount_fen, label=p.label) for p in schedule.payments])


def _early_decision(option: EarlyPayOption, early: CapexResult, state: FinancialState,
                    mandate: Mandate) -> EarlyPayDecision:
    d = Fraction(option.rate_bp, BP_DENOM)
    ret = d / (1 - d)
    days = option.days_earlier
    try:
        rate, fid = marginal_cost(state, mandate)
    except NoPermanentSourceError:
        rate, fid = None, None
    if days <= 0:  # paying within the window is not earlier than the payment's own day: the discount costs no time
        cost: Fraction | None = Fraction(0)
    elif rate is not None:
        cost = break_even_cost_share(state, mandate, days)[0]
    else:
        cost = None
    worth = cost is not None and ret > cost
    liquid = early.selected_id is not None
    take = worth and liquid
    pct = fmt_pct(d)
    if cost is None:
        text = (f"The {pct} discount returns {fmt_pct(ret)} on what is paid early, but no committed source can carry a "
                f"permanent need, so its cost cannot be priced; it is not recommended.")
    elif not worth:
        text = (f"Not worth it: paying {fmt_yuan(option.pay_early_fen)} {days} days early returns {fmt_pct(ret)}, less "
                f"than the {fmt_pct(cost)} it costs to carry that money for those days.")
    elif not liquid:
        text = (f"Worth it on price ({fmt_pct(ret)} return against a {fmt_pct(cost)} cost), but no structure pays it "
                f"early without breaking the reserve, so it is not taken.")
    else:
        text = (f"Take it: paying {fmt_yuan(option.pay_early_fen)} by day {option.pay_by_day} instead of "
                f"{fmt_yuan(option.pay_early_fen + option.discount_fen)} on day {option.due_day} saves "
                f"{fmt_yuan(option.discount_fen)}, a {fmt_pct(ret)} return against a {fmt_pct(cost)} cost of carrying it.")
    formula = (f"take when d / (1 − d) > c and a structure pays the early schedule: d / (1 − d) = {fmt_pct(ret, 4)}; "
               + (f"c = the marginal committed source's cost share for {days} days = {fmt_pct(cost, 4)}"
                  if cost is not None and days > 0 else
                  "c = 0 (no days earlier)" if cost is not None else "c unknown (no committed source)"))
    return EarlyPayDecision(
        option=option, return_share=Ratio.of(ret), cost_share=Ratio.of(cost) if cost is not None else None,
        marginal_rate=rate, marginal_facility_id=fid, worth_it=worth, liquidity_ok=liquid, take=take, text=text,
        formula=formula)


def evaluate_contract(record: ContractRecord, timeline: Timeline, estimate: CapexEstimate, state: FinancialState,
                      mandate: Mandate, *, commitments: Sequence[Commitment] = ()) -> BuySideEvaluation:
    """The screen of one capex contract on the owner's timeline. Raises NotACapexContract for any other document."""
    if record.kind != DocumentKind.CAPEX_CONTRACT or record.contract is None:
        raise NotACapexContract(f"{record.id} is a {record.kind.value.lower().replace('_', ' ')}, not a capex contract")
    today = state.as_of_day
    start, basis = _start_month(estimate, timeline, today)
    result = derive_schedule(record.contract, timeline, anchor_iso=state.as_of, today=today)
    base = BuySideEvaluation(
        document_id=record.id, doc_hash=record.doc_hash, title=record.title, counterparty_id=record.counterparty_id,
        reading_confirmed=record.status == DocumentStatus.CONFIRMED, timeline=timeline, uplift_start_month=start,
        uplift_start_basis=basis, schedule=result, summary="No payment schedule: " + " ".join(result.reasons))
    if not result.derivable or result.schedule is None:
        return base
    schedule = result.schedule
    evaluation = evaluate_capex(_request(record, schedule, estimate, start, state), state, mandate,
                                commitments=commitments)
    decision: EarlyPayDecision | None = None
    early_eval: CapexResult | None = None
    taken: PaymentSchedule | None = None
    if schedule.early_pay is not None:
        taken = early_schedule(schedule)
        assert taken is not None
        early_eval = evaluate_capex(_request(record, taken, estimate, start, state), state, mandate,
                                    commitments=commitments)
        decision = _early_decision(schedule.early_pay, early_eval, state, mandate)
    summary = evaluation.recommendation + (f" Early payment: {decision.text}" if decision is not None else "")
    return base.model_copy(update={"evaluation": evaluation, "early_pay": decision, "early_pay_evaluation": early_eval,
                                   "early_pay_schedule": taken, "summary": summary})


__all__ = ["BuySideEvaluation", "CapexEstimate", "EarlyPayDecision", "NotACapexContract", "evaluate_contract"]
