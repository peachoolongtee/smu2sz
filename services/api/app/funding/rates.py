"""Same-basis costing (spec §7.3): every source as an all-in simple annual rate, plus time to cash.

- Credit line and loans: rate + upfront fee spread over the term (12/term_months a year).
- Invoice financing: rate + per-period fee × 365/period (financial.if_all_in_rate).
- Buyer early payment: d/(1−d) × 365/days-early.
- Bank-acceptance bill: the bill's discount rate.
- Equity: no rate (Tier 3, reference only).

Also the marginal cost of funds and the break-even early-pay discount. Exact Fractions throughout;
display strings are rounded half-up by app.domain.money.
"""

from __future__ import annotations

from fractions import Fraction

from app.covenants import line_can_carry_permanent_need
from app.domain.models import (
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingActionKind,
    Mandate,
    ViolationCode,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan, round_half_up
from app.financial import advance_effective_rate, finance_invoice_charges, if_all_in_rate
from app.mandate import check_apr

MONTH_DAYS = 30
BREAK_EVEN_PERIOD_DAYS = 30  # one invoice-financing period (spec §7.4)
DEFAULT_EARLY_PAY_DAYS = 30

NOT_DEBT_KINDS = frozenset({FacilityKind.BUYER_EARLY_PAY, FacilityKind.BANK_ACCEPTANCE_BILL, FacilityKind.EQUITY})
# Purpose-bound or amortising: they cannot carry a permanent working-capital need.
EQUIPMENT_KINDS = frozenset({FacilityKind.EQUIPMENT_TERM_LOAN, FacilityKind.EQUIPMENT_LEASE})


class NoPermanentSourceError(ValueError):
    """No committed, owner-approved source can carry a permanent need."""


def pct(rate: Fraction, places: int = 4) -> str:
    """Short exact percentage for formulas: 6.4%, 0.25%, ≈10.8417% (inexact values get '≈')."""
    scaled = rate * 100 * 10**places
    q = round_half_up(scaled)
    whole, part = divmod(abs(q), 10**places)
    text = f"{whole}.{part:0{places}d}".rstrip("0").rstrip(".")
    return f"{'' if Fraction(q) == scaled else '≈'}{'-' if q < 0 else ''}{text}%"


def is_debt(f: Facility) -> bool:
    return f.kind not in NOT_DEBT_KINDS


def tier3_reasons(f: Facility) -> list[ViolationCode]:
    """Tier-3 conditions (INVARIANT 6): the router never plans a source that needs them."""
    out: list[ViolationCode] = []
    if f.kind == FacilityKind.EQUITY:
        out.append(ViolationCode.TIER3_EQUITY)
    if f.personal_guarantee:
        out.append(ViolationCode.TIER3_PERSONAL_GUARANTEE)
    if f.collateral:
        out.append(ViolationCode.TIER3_COLLATERAL)
    return out


def early_pay_rate(discount: Fraction, days_early: int) -> Fraction:
    """Annualised cost of taking a discount d for `days_early` days: d/(1−d) × 365/days."""
    if days_early <= 0:
        raise ValueError("days_early must be positive")
    return discount / (1 - discount) * DAYS_PER_YEAR / days_early


def all_in_rate(f: Facility, *, discount_bp: int | None = None, days_early: int | None = None) -> tuple[Fraction, str]:
    """(exact all-in annual rate, formula text) on the common basis."""
    match f.kind:
        case FacilityKind.INVOICE_FINANCING:
            period = f.fee_period_days or MONTH_DAYS
            rate = if_all_in_rate(f) + bp(f.upfront_fee_bp) * DAYS_PER_YEAR / period
            text = f"{pct(bp(f.rate_bp))} + {pct(bp(f.fee_bp_per_advance))} × 365/{period}"
            if f.upfront_fee_bp:
                text += f" + {pct(bp(f.upfront_fee_bp))} × 365/{period}"
            return rate, f"{text} = {pct(rate)}"
        case FacilityKind.BUYER_EARLY_PAY:
            d = bp(discount_bp if discount_bp is not None else f.rate_bp)
            days = days_early or DEFAULT_EARLY_PAY_DAYS
            rate = early_pay_rate(d, days)
            return rate, f"{pct(d)}/(1 − {pct(d)}) × 365/{days} = {pct(rate)}"
        case FacilityKind.BANK_ACCEPTANCE_BILL:
            rate = bp(f.rate_bp)
            return rate, f"bill discount rate {pct(rate)}"
        case FacilityKind.EQUITY:
            return Fraction(0), "no interest; costs ownership and control (Tier 3)"
    rate = bp(f.rate_bp)
    if not f.upfront_fee_bp:
        return rate, f"{pct(rate)} simple"
    months = f.term_months or 12
    total = rate + bp(f.upfront_fee_bp) * 12 / months
    return total, f"{pct(rate)} + {pct(bp(f.upfront_fee_bp))} × 12/{months} = {pct(total)}"


def invoice_landing_day(f: Facility, request_day: int, issue_day: int) -> int:
    """The day an advance requested on `request_day` lands: an unissued invoice is submitted on its issue day,
    then the facility's lead time (the engine's rule, `financial.trajectory._finance_invoice`)."""
    return max(request_day, issue_day) + f.lead_time_days


def action_rate(
    f: Facility,
    kind: FundingActionKind,
    *,
    amount_fen: int = 0,
    landing_day: int | None = None,
    due_day: int | None = None,
    rate_bp: int | None = None,
) -> tuple[Fraction, str]:
    """(annual cost, how it was computed) of one funding action: the one number the router tests against the
    mandate's `max_apr_bp` and the executor's admission tests (docs/FINANCIAL_SEMANTICS.md, "Rates").

    - invoice advance: every charge (interest, period fee, upfront fee) over the advance, annualised on the days
      from landing to the invoice's due day (`advance_effective_rate`); the tariff when the days are unknown;
    - early payment: d/(1-d) on the days early (landing to due);
    - bill discount: the bill's discount rate;
    - a draw and anything else: the tariff `all_in_rate`."""
    match kind:
        case FundingActionKind.FINANCE_INVOICE if (
            f.kind == FacilityKind.INVOICE_FINANCING and amount_fen > 0 and landing_day is not None
            and due_day is not None and due_day > landing_day
        ):
            days = due_day - landing_day
            rate = advance_effective_rate(f, amount_fen, days)
            return rate, (f"all charges on {fmt_yuan(amount_fen)} held {days} days (day {landing_day} to day "
                          f"{due_day}), annualised = {fmt_pct(rate)}")
        case FundingActionKind.EARLY_PAY:
            days = due_day - landing_day if landing_day is not None and due_day is not None else None
            return all_in_rate(f, discount_bp=rate_bp, days_early=days)
        case FundingActionKind.DISCOUNT_BILL if rate_bp is not None:
            return bp(rate_bp), f"bill discount rate {pct(bp(rate_bp))}"
    return all_in_rate(f)


def receipt_covered_advance(f: Facility, cap_fen: int, open_fen: int, days: int) -> int:
    """The largest advance up to `cap_fen` that the buyer's receipt of the invoice's `open_fen` can repay with its
    charges when it is held `days` days. The lender is paid from the receipt only (ADR-0010): an advance whose
    principal and charges exceed the receipt would leave the rest of the charges owed on the lot, not paid out of
    cash on the due day as the projection posts them, so the router never proposes one."""
    advance = max(0, min(cap_fen, open_fen))
    for _ in range(12):
        if advance <= 0 or days <= 0:
            return max(advance, 0)
        interest, fee, _ = finance_invoice_charges(f, advance, days)
        over = advance + interest + fee - open_fen
        if over <= 0:
            return advance
        advance -= max(1, over)
    return 0


def approval_reason(rate: Fraction, how: str, mandate: Mandate) -> str | None:
    """Why an action costing `rate` a year needs the owner (Tier 2), or None when it is within the mandate's
    `max_apr_bp` ceiling for what the agent may borrow alone."""
    cap = bp(mandate.max_apr_bp)
    if rate <= cap:
        return None
    return (f"effective annual cost {fmt_pct(rate)} is above the mandate's {fmt_pct(cap)} ceiling for what the "
            f"agent may borrow alone ({how})")


def display_rate(f: Facility, rate: Fraction) -> str:
    return "—" if f.kind == FacilityKind.EQUITY else fmt_pct(rate)


def can_carry_permanent(f: Facility) -> bool:
    """Structurally able to carry a permanent need: not early pay (only while offered, not debt),
    not held bills (a finite stock), not equity, not purpose-bound equipment finance, not a
    clean-down line, and with capacity left."""
    if f.kind in NOT_DEBT_KINDS or f.kind in EQUIPMENT_KINDS:
        return False
    if f.kind == FacilityKind.CREDIT_LINE and not line_can_carry_permanent_need(f):
        return False
    if f.limit_fen - f.drawn_fen <= 0 or f.status == FacilityStatus.REFERENCE_ONLY:
        return False
    return not tier3_reasons(f)


def permanent_sources(
    state: FinancialState, mandate: Mandate, statuses: frozenset[FacilityStatus]
) -> list[tuple[Fraction, Facility]]:
    """Owner-approved sources in `statuses` able to carry a permanent need, cheapest first."""
    out = []
    for f in state.facilities:
        if not f.owner_approved or f.status not in statuses or not can_carry_permanent(f):
            continue
        rate, _ = all_in_rate(f)
        if check_apr(Ratio.of(rate), mandate, f.name) is not None:
            continue
        out.append((rate, f))
    return sorted(out, key=lambda t: (t[0], t[1].id))


def marginal_cost(state: FinancialState, mandate: Mandate) -> tuple[Ratio, str]:
    """All-in annual rate of the cheapest COMMITTED, owner-approved source able to carry a
    permanent need, and its facility id. Golden: FAC-IF at ≈10.8417%.

    Raises NoPermanentSourceError when no such source exists."""
    found = permanent_sources(state, mandate, frozenset({FacilityStatus.COMMITTED}))
    if not found:
        raise NoPermanentSourceError("no committed, owner-approved source can carry a permanent need")
    rate, f = found[0]
    return Ratio.of(rate), f.id


def break_even_cost_share(state: FinancialState, mandate: Mandate, days_early: int) -> tuple[Fraction, int | None, int | None]:
    """(c, whole periods k, period p): what the marginal committed source charges, as a share of
    principal, to carry the money for `days_early` days. Invoice financing is billed in whole
    periods, k = ceil(days/p): c = rate × p × k/365 + period fee × k + the upfront fee ONCE (the upfront
    fee is charged when the advance is made, not again each period; F-FIN-09). Any other source accrues
    daily (c = R × days/365, k and p are None)."""
    rate, fid = marginal_cost(state, mandate)
    facility = next((f for f in state.facilities if f.id == fid), None)
    if facility is not None and facility.kind == FacilityKind.INVOICE_FINANCING:
        period = facility.fee_period_days or MONTH_DAYS
        k = max(1, -(-days_early // period))
        c = (bp(facility.rate_bp) * period * k / DAYS_PER_YEAR
             + bp(facility.fee_bp_per_advance) * k + bp(facility.upfront_fee_bp))
        return c, k, period
    return rate.value * days_early / DAYS_PER_YEAR, None, None


def break_even_discount(
    state: FinancialState, mandate: Mandate, days_early: int = BREAK_EVEN_PERIOD_DAYS
) -> tuple[Ratio, int]:
    """(d, bp floor): an early-pay discount d paid `days_early` days early is cheaper than the
    marginal source only if d/(1−d) < c, where c is that source's cost share for the tenor
    (see break_even_cost_share). d = c/(1+c). Golden at 30 days: 0.88%, 88 bp."""
    c, _, _ = break_even_cost_share(state, mandate, days_early)
    d = c / (1 + c)
    return Ratio.of(d), int(d * 10_000)
