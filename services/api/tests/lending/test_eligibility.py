"""ADR-0013, phase 6: indicative loan eligibility against the synthetic catalogue, on the golden books (EBITDA ¥90,000 a month,
worst projected debt service ¥45,000 a month, worst month-end debt ¥1,455,000, every open receivable owed by BUYER-1)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.capex.evaluate import term_service
from app.domain.fixtures import load_scenario
from app.domain.models import CovenantKind, FacilityStatus
from app.lending import EligibilityInputs, concentration, eligibility, facility_of, load_catalogue, product
from app.mandate import load_signed_mandate


@pytest.fixture
def books():
    state, _ = load_scenario("golden_sme")
    return state, load_signed_mandate()


def _row(e, pid):  # type: ignore[no-untyped-def]
    return next(r for r in e.products if r.product.id == pid)


def test_the_catalogue_is_labelled_synthetic_and_loads():
    ids = [p.id for p in load_catalogue()]
    assert ids == ["PRD-BANK1-TERM-60", "PRD-BANK2-GGL-36", "PRD-LESSOR1-LEASE-60", "PRD-LENDERNB-SECURED-84"]
    from app.domain.fixtures import FIXTURES

    assert "not a real lender's offer" in (FIXTURES / "lending" / "catalogue.json").read_text(encoding="utf-8")


def test_the_largest_eligible_amount_is_exact_on_the_lenders_ratios(books):
    state, mandate = books
    r = _row(eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48)), "PRD-BANK1-TERM-60")
    p, f = r.product, facility_of(r.product)
    cap = r.max_eligible_fen
    assert r.status == "ELIGIBLE_UP_TO" and cap is not None and p.min_amount_fen <= cap < p.max_amount_fen

    def ok(a: int) -> bool:
        dscr = Fraction(9_000_000, 4_500_000 + max(term_service(f, a, p.term_months)))
        lev = Fraction(145_500_000 + a, 12 * 9_000_000)
        return dscr >= Fraction(13, 10) and lev <= 3

    assert ok(cap) and not ok(cap + 1)  # the bisection's answer is the exact boundary
    assert r.monthly_payment_fen == max(term_service(f, cap, 60))


def test_months_trading_is_unknown_until_the_owner_says_and_never_assumed(books):
    state, mandate = books
    r = _row(eligibility(state, mandate), "PRD-BANK1-TERM-60")
    assert r.status == "UNKNOWN" and r.max_eligible_fen is not None
    months = next(c for c in r.criteria if c.name == "Months trading")
    assert months.passes is None and "not given" in months.observed
    short = _row(eligibility(state, mandate, inputs=EligibilityInputs(months_trading=6)), "PRD-BANK1-TERM-60")
    assert short.status == "NOT_ELIGIBLE"


def test_buyer_concentration_fails_the_guaranteed_loan(books):
    state, mandate = books
    conc, top = concentration(state)
    assert conc is not None and conc.value == 1 and top == "BUYER-1"
    r = _row(eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48)), "PRD-BANK2-GGL-36")
    assert r.status == "NOT_ELIGIBLE" and "largest buyer's share of receivables" in r.text


def test_a_product_needing_tier_3_steps_says_so_and_ranks_after_the_others(books):
    state, mandate = books
    e = eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48))
    secured = _row(e, "PRD-LENDERNB-SECURED-84")
    assert set(secured.tier3) == {"TIER3_PERSONAL_GUARANTEE", "TIER3_COLLATERAL"} and "Tier-3" in secured.text
    eligible = [r.product.id for r in e.products if r.status in ("ELIGIBLE", "ELIGIBLE_UP_TO")]
    assert eligible[-1] == "PRD-LENDERNB-SECURED-84"  # cheapest, yet after every product that needs no Tier-3 step


def test_the_owners_own_limits_are_shown_beside_the_lenders(books):
    state, mandate = books
    r = _row(eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48)), "PRD-BANK1-TERM-60")
    assert r.own_limits_max_fen == 124_500_000 and r.own_limits_binding == "LEVERAGE"  # 12 × ¥90,000 × 2.5 − ¥1,455,000
    assert r.max_eligible_fen is not None and r.own_limits_max_fen < r.max_eligible_fen
    assert "Your own limits allow ¥1,245,000.00" in r.text


def test_a_requested_amount_is_tested_too(books):
    state, mandate = books
    e = eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48, amount_fen=60_000_000))
    assert _row(e, "PRD-BANK1-TERM-60").requested_passes is True
    assert _row(e, "PRD-LENDERNB-SECURED-84").requested_passes is False  # below its ¥1,000,000 minimum
    unknown = eligibility(state, mandate, inputs=EligibilityInputs(amount_fen=60_000_000))
    assert _row(unknown, "PRD-BANK1-TERM-60").requested_passes is None  # the ratios fit; months trading not given


def test_the_menu_facility_carries_the_lenders_covenants_and_counts_as_zero(books):
    p = product("PRD-BANK1-TERM-60")
    assert p is not None
    f = facility_of(p, 50_000_000)
    assert (f.id, f.status, f.owner_approved, f.limit_fen, f.term_months) == (
        "FAC-BANK1-TERM-60", FacilityStatus.NOT_APPLIED, False, 50_000_000, 60)
    assert {(c.kind, c.threshold_bp) for c in f.covenants} == {(CovenantKind.DSCR_MIN, 13000),
                                                             (CovenantKind.LEVERAGE_MAX, 30000)}


def test_no_ebitda_means_not_eligible(books):
    state, mandate = books
    e = eligibility(state.model_copy(update={"monthly_ebitda_fen": 0}), mandate)
    assert all(r.status == "NOT_ELIGIBLE" and r.max_eligible_fen is None for r in e.products)


def test_eligibility_writes_nothing(books):
    state, mandate = books
    before = state.model_dump_json()
    eligibility(state, mandate, inputs=EligibilityInputs(months_trading=48, amount_fen=1))
    assert state.model_dump_json() == before
