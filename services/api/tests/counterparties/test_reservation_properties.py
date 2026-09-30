"""The buyer never accepts below its reservation and always accepts at or above it.

The oracle below re-derives the buyer's surplus independently (Decimal half-up per component)
from the profile's declared parameters, so the kernel is checked against a second computation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.counterparties import BuyerDecision, BuyerKernel
from app.counterparties.profiles import BuyerProfile, get_profile
from app.domain.models import Obligation
from tests.counterparties.builders import (
    OPTION_A_FACE_FEN,
    discount,
    option_a,
    price_adjustment,
    rebate,
    terms,
)

kernel = BuyerKernel()
PROFILES = ["BUYER-1", "BUYER-1-HARDLINE", "BUYER-2"]


def _half_up(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def oracle_acceptable(p: BuyerProfile, disc: tuple[int, int] | None, delta: int | None,
                      reb: tuple[int, int] | None, price: int | None) -> bool:
    surplus = 0
    if disc is not None:
        rate, face = disc
        d = _half_up(Decimal(face) * rate / 10_000)
        days = (p.invoice_due_day - p.early_settlement_day) if p.invoice_due_day is not None else 0
        cost = _half_up(Decimal(face - d) * p.funding_cost_bp / 10_000 * days / 365)
        surplus += d - cost
    if delta is not None:
        surplus += delta * p.payment_day_value_fen * p.invoices_per_year
    if reb is not None:
        rate, base = reb
        surplus += _half_up(Decimal(base) * rate / 10_000)
    if price is not None:
        surplus -= _half_up(Decimal(42_000_000) * price / 10_000) * p.invoices_per_year
    if p.requires_early_pay and disc is None:
        return False
    if disc is not None and disc[0] < p.min_early_pay_discount_bp:
        return False
    if p.insists_on_terms_extension and p.current_terms_days + (delta or 0) < p.min_terms_days:
        return False
    if p.min_rebate_bp and (reb is None or reb[0] < p.min_rebate_bp):
        return False
    return surplus >= p.min_surplus_fen


@settings(max_examples=200, deadline=None)
@given(rate=st.integers(min_value=0, max_value=400), round_no=st.integers(min_value=1, max_value=3))
def test_accommodating_buyer_accepts_option_a_exactly_at_or_above_its_minimum(rate: int, round_no: int) -> None:
    r = kernel.respond("BUYER-1", option_a(rate), round_no)
    reservation = get_profile("BUYER-1").min_early_pay_discount_bp
    assert (r.decision is BuyerDecision.ACCEPT) == (rate >= reservation)


@settings(max_examples=200, deadline=None)
@given(rate=st.integers(min_value=0, max_value=400), delta=st.integers(min_value=0, max_value=30))
def test_hardline_needs_both_its_discount_and_its_terms(rate: int, delta: int) -> None:
    p = get_profile("BUYER-1-HARDLINE")
    r = kernel.respond("BUYER-1-HARDLINE", [discount(rate, 42_000_000), terms(delta)], 1)
    expected = oracle_acceptable(p, (rate, 42_000_000), delta, None, None)
    assert (r.decision is BuyerDecision.ACCEPT) == expected
    if rate < p.min_early_pay_discount_bp or 45 + delta < p.min_terms_days:
        assert r.decision is not BuyerDecision.ACCEPT


@settings(max_examples=150, deadline=None)
@given(rate=st.integers(min_value=0, max_value=300))
def test_buyer2_accepts_a_rebate_exactly_at_or_above_its_minimum(rate: int) -> None:
    r = kernel.respond("BUYER-2", [rebate(rate, 25_000_000, cp="BUYER-2")], 1)
    assert (r.decision is BuyerDecision.ACCEPT) == (rate >= get_profile("BUYER-2").min_rebate_bp)


@settings(max_examples=400, deadline=None)
@given(
    profile_id=st.sampled_from(PROFILES),
    disc=st.none() | st.tuples(st.integers(0, 300), st.sampled_from([OPTION_A_FACE_FEN, 42_000_000, 10_000_000])),
    delta=st.none() | st.integers(-15, 30),
    reb=st.none() | st.tuples(st.integers(0, 300), st.sampled_from([25_000_000, 40_000_000])),
    price=st.none() | st.integers(0, 100),
    round_no=st.integers(1, 3),
)
def test_accepts_iff_the_package_meets_the_reservation(
    profile_id: str,
    disc: tuple[int, int] | None,
    delta: int | None,
    reb: tuple[int, int] | None,
    price: int | None,
    round_no: int,
) -> None:
    package: list[Obligation] = []
    if disc is not None:
        package.append(discount(disc[0], disc[1]))
    if delta is not None:
        package.append(terms(delta))
    if reb is not None:
        package.append(rebate(reb[0], reb[1]))
    if price is not None:
        package.append(price_adjustment(price))
    if not package:
        return
    r = kernel.respond(profile_id, package, round_no)
    expected = oracle_acceptable(get_profile(profile_id), disc, delta, reb, price)
    assert (r.decision is BuyerDecision.ACCEPT) == expected
    # past the bound nothing is ever accepted
    assert kernel.respond(profile_id, package, 4).decision is BuyerDecision.REJECT
