"""ADR-0013, phase 5: the buy side's financial health on the golden books, every figure checked by hand.

Golden books (fixtures/scenarios/golden_sme.json): cash ¥400,000, reserve ¥300,000, EBITDA ¥90,000 a month, one existing
debt (D-EQUIP, ¥1,500,000 at ¥45,000 a month), payroll ¥340,000 on day 12, a supplier payment ¥120,000 on day 20, a bill
¥100,000 on day 47."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.capex.evaluate import term_service
from app.domain.fixtures import load_scenario
from app.domain.models import CashFlow, FlowKind
from app.health import HealthInputs, financial_health, largest_principal
from app.mandate import load_signed_mandate


@pytest.fixture
def books():
    state, _ = load_scenario("golden_sme")
    return state, load_signed_mandate()


def test_cash_reads_the_first_breach_ahead_and_whether_a_committed_plan_cures_it(books):
    state, mandate = books
    c = financial_health(state, mandate).cash
    assert (c.cash_fen, c.reserve_fen, c.headroom_fen) == (40_000_000, 30_000_000, 10_000_000)
    assert (c.first_breach_day, c.first_breach_cash_fen) == (12, 6_000_000)  # ¥400,000 − ¥340,000 payroll
    assert c.status == "SHORT" and c.plan_admissible is True and c.plan_cost_fen is not None
    assert c.lowest_headroom_fen == c.lowest_fen - 30_000_000


def test_the_90_day_coverage_is_the_projections_own_cash_in_and_out(books):
    state, mandate = books
    cov = financial_health(state, mandate).coverage
    # out: payroll 340,000 + supplier 120,000 + bill 100,000 + debt service 45,000 on days 30 and 60
    assert (cov.window_days, cov.out_fen, cov.operating_in_fen, cov.funding_in_fen) == (90, 65_000_000, 126_000_000, 0)
    assert cov.ratio is not None and cov.ratio.value == Fraction(40_000_000 + 126_000_000, 65_000_000)
    assert cov.capex_out_fen == 0


def test_a_committed_capex_payment_is_in_the_coverage_and_the_12_month_figure(books):
    state, mandate = books
    flow = CashFlow(id="CAPEX:DOC-000001:1", day=20, amount_fen=-18_000_000, kind=FlowKind.CAPEX, label="deposit")
    h = financial_health(state.model_copy(update={"flows": [*state.flows, flow]}), mandate)
    assert h.coverage.capex_out_fen == 18_000_000 and h.coverage.out_fen == 83_000_000
    assert h.liquidity.capex_due_12m_fen == 18_000_000


def test_the_current_and_quick_ratios_need_every_owner_entry(books):
    state, mandate = books
    li = financial_health(state, mandate, inputs=HealthInputs(inventory_fen=30_000_000)).liquidity
    assert not li.available and li.current_ratio is None
    assert li.needs == ["other_current_assets_fen", "trade_payables_fen", "other_current_liabilities_fen"]
    assert li.debt_due_12m_fen == 54_000_000  # D-EQUIP: twelve ¥45,000 payments in the next 365 days, all principal


def test_the_current_and_quick_ratios_on_the_owners_entries(books):
    state, mandate = books
    li = financial_health(state, mandate, inputs=HealthInputs(
        inventory_fen=30_000_000, other_current_assets_fen=0, trade_payables_fen=25_000_000,
        other_current_liabilities_fen=5_000_000)).liquidity
    assert li.available and li.evidence == "OWNER_ESTIMATE"
    receivables = sum(r.outstanding_fen for r in state.receivables if r.status in ("OPEN", "FINANCED"))
    assert li.current_assets_fen == 40_000_000 + receivables + 30_000_000
    assert li.current_liabilities_fen == 25_000_000 + 5_000_000 + 54_000_000
    assert li.current_ratio is not None and li.current_ratio.value == Fraction(li.current_assets_fen, 84_000_000)
    assert li.quick_ratio is not None and li.quick_ratio.value == Fraction(40_000_000 + receivables, 84_000_000)


def test_covenant_room_on_the_worst_projected_month(books):
    state, mandate = books
    r = financial_health(state, mandate).covenants
    assert r is not None
    assert r.worst_dscr is not None and r.worst_dscr.value == 2  # ¥90,000 / ¥45,000
    assert r.dscr_room_monthly_fen == 2_700_000  # ¥90,000 / 1.25 − ¥45,000
    assert r.worst_debt_fen == 145_500_000 and r.leverage_room_fen == 124_500_000  # 12 × ¥90,000 × 2.5 − ¥1,455,000
    assert r.dscr_ok and r.leverage_ok


def test_capacity_per_term_facility_names_what_binds(books):
    state, mandate = books
    h = financial_health(state, mandate)
    cap = {c.facility_id: c for c in h.capacity}
    assert set(cap) == {"FAC-GGL", "FAC-ETL", "FAC-LEASE"}  # owner-approved term facilities only
    etl = cap["FAC-ETL"]
    assert (etl.capacity_fen, etl.binding, etl.monthly_payment_fen, etl.counts_now) == (60_000_000, "LIMIT", 1_814_462,
                                                                                        False)
    ggl = cap["FAC-GGL"]
    f = next(x for x in state.facilities if x.id == "FAC-GGL")
    assert ggl.binding == "DSCR"
    assert max(term_service(f, ggl.capacity_fen, 12)) <= 2_700_000 < max(term_service(f, ggl.capacity_fen + 1, 12))
    assert "counts as zero until it is committed" in ggl.text


def test_a_tighter_leverage_limit_binds_the_capacity(books):
    state, mandate = books
    tight = mandate.model_copy(update={"max_leverage_bp": 14_000})  # room = 12 × ¥90,000 × 1.4 − ¥1,455,000 = ¥57,000
    h = financial_health(state, tight)
    assert h.covenants is not None and h.covenants.leverage_room_fen == 5_700_000
    etl = next(c for c in h.capacity if c.facility_id == "FAC-ETL")
    assert (etl.capacity_fen, etl.binding) == (5_700_000, "LEVERAGE")


def test_no_ebitda_means_no_ratio_reading_and_no_capacity(books):
    state, mandate = books
    h = financial_health(state.model_copy(update={"monthly_ebitda_fen": 0}), mandate)
    assert h.covenants is None and all(c.capacity_fen == 0 and c.binding == "NONE" for c in h.capacity)


def test_health_writes_nothing(books):
    state, mandate = books
    before = state.model_dump_json()
    financial_health(state, mandate, inputs=HealthInputs(inventory_fen=1, other_current_assets_fen=1,
                                                         trade_payables_fen=1, other_current_liabilities_fen=1))
    assert state.model_dump_json() == before


@pytest.mark.parametrize(("threshold", "upper", "expected"), [(0, 10, 0), (1, 10, 1), (7, 10, 7), (10, 10, 10),
                                                               (50, 10, 10), (5, 0, 0)])
def test_largest_principal_is_an_exact_bisection(threshold, upper, expected):
    assert largest_principal(lambda p: p <= threshold, upper) == expected
