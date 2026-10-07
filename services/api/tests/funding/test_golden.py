"""The router on the golden fixture, exact against fixtures/golden/golden_values.json."""

from __future__ import annotations

import time

import pytest

from app.domain.fixtures import golden_values
from app.domain.models import FacilityStatus, FundingActionKind, Mode, ViolationCode
from app.domain.money import fmt_pct
from app.domain.ports import FundingRouter
from app.financial import project
from app.funding import (
    ComparisonResult,
    Router,
    break_even_discount,
    compare,
    extension_cost_bases,
    marginal_cost,
    menu_view,
    plan,
)
from tests.funding.variants import golden, terms_extension


@pytest.fixture(scope="module")
def g():
    return golden_values()


@pytest.fixture(scope="module")
def sm():
    return golden()


@pytest.fixture(scope="module")
def baseline_plan(sm):
    s, m = sm
    return plan(s, [], m)


@pytest.fixture(scope="module")
def rows(sm):
    s, m = sm
    return {r.key: r for r in compare(s, [], m)}


def test_plan_is_line_plus_invoice_financing(baseline_plan, g):
    p = baseline_plan
    assert p.admissible and p.basis == "COMMITTED"
    assert p.need_fen == g["funding_need_before_day_32"]
    got = sorted((a.kind, a.facility_id, a.amount_fen, a.receivable_id) for a in p.actions)
    assert got == sorted([
        (FundingActionKind.DRAW, "FAC-LINE", 15_000_000, None),
        (FundingActionKind.FINANCE_INVOICE, "FAC-IF", g["plan_advance"], "RCV-A"),  # 405,000 − 150,000
    ])
    line = next(a for a in p.actions if a.facility_id == "FAC-LINE")
    assert line.day == 0 and line.repay_day == 32
    assert p.total_cost_fen == g["v2_optimum_total"]
    assert sum(c.fen for c in p.costs) == p.total_cost_fen


def test_plan_cost_lines_and_formulas(baseline_plan, g):
    costs = {c.facility_id: c for c in baseline_plan.costs}
    assert costs["FAC-LINE"].fen == g["line_interest_150k_32d"]
    assert costs["FAC-LINE"].formula == "150,000.00 × 6.4% × 32/365 = 841.64"
    # 255,000 × 7.8% × 30/365 = 1,634.79 + fee 255,000 × 0.25% = 637.50 -> 2,272.29; + line 841.64 = 3,113.93
    assert costs["FAC-IF"].fen == g["if_cost_plan_advance"]
    assert "1 × 30-day period" in costs["FAC-IF"].formula and "total ¥2,272.29" in costs["FAC-IF"].formula
    assert baseline_plan.label.endswith("¥3,113.93")


def test_plan_reports_marginal_cost_and_rejections(baseline_plan):
    p = baseline_plan
    assert p.marginal_facility_id == "FAC-IF"
    assert p.marginal_cost_annual is not None and fmt_pct(p.marginal_cost_annual.value) == "10.84%"
    rejected = {r.label: r for r in p.rejected}
    assert set(rejected) == {
        "Discount the whole invoice at 1.2%",
        "Line + early payment on part of the invoice at 1.2%",
        "Line + guaranteed loan",
        "Line only",
    }
    assert rejected["Line only"].reasons == [ViolationCode.RESERVE_BREACH]
    assert "day 12" in rejected["Line only"].note
    assert rejected["Line + guaranteed loan"].reasons == [
        ViolationCode.UNCOMMITTED_FACILITY, ViolationCode.LEAD_TIME_TOO_LONG]
    assert rejected["Discount the whole invoice at 1.2%"].reasons == []


def test_plan_trajectory_holds_the_floor(sm, baseline_plan):
    s, m = sm
    t = project(s, [], baseline_plan.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None
    # 400,000 + 150,000 + 255,000 − 340,000 − 120,000 = 345,000 after the supplier payment; the existing loan's
    # ¥45,000 on day 30 takes it exactly to the floor
    assert t.days[20].closing_fen == m.min_cash_fen + 4_500_000
    assert t.days[30].closing_fen == m.min_cash_fen


def test_plan_runs_under_one_second(sm):
    s, m = sm
    start = time.perf_counter()
    plan(s, [], m)
    assert time.perf_counter() - start < 1.0


def test_plan_is_deterministic(sm, baseline_plan):
    s, m = sm
    again = plan(s, [], m)
    assert again == baseline_plan


def test_compare_rows(rows, g):
    assert list(rows) == ["full_discount", "line_partial_early_pay", "router_optimum",
                          "line_guaranteed_loan", "line_only"]
    full = rows["full_discount"]
    assert full.result == ComparisonResult.ADMISSIBLE and full.cost_fen == g["full_discount_1_2pct"]
    assert full.cost_display == "¥5,040.00"
    v1 = rows["line_partial_early_pay"]
    assert v1.result == ComparisonResult.ADMISSIBLE and v1.cost_fen == g["v1_optimum_total"]
    ep = next(a for a in v1.actions if a.kind == FundingActionKind.EARLY_PAY)
    assert ep.amount_fen == g["v1_partial_face"]
    # face 255,000 / (1 − 1.2%) = 258,097.17, discount 3,097.17
    assert v1.cost_display == "¥841.64 + ¥3,097.17 = ¥3,938.81"
    opt = rows["router_optimum"]
    assert opt.result == ComparisonResult.SELECTED and opt.cost_fen == g["v2_optimum_total"]
    assert opt.cost_display == "¥841.64 + ¥2,272.29 = ¥3,113.93"
    line_only = rows["line_only"]
    assert line_only.result == ComparisonResult.NOT_ADMISSIBLE
    assert line_only.reasons == [ViolationCode.RESERVE_BREACH] and line_only.breach_day == 12
    # what the line alone leaves uncovered (display only): ¥90,000 short on day 12, ¥255,000 at the deepest, day 30
    assert line_only.shortfall_fen == 25_500_000 and line_only.worst_day == 30
    assert rows["line_guaranteed_loan"].shortfall_fen is None and rows["router_optimum"].shortfall_fen is None
    ggl = rows["line_guaranteed_loan"]
    assert ggl.result == ComparisonResult.NOT_ADMISSIBLE
    assert ggl.reasons == [ViolationCode.UNCOMMITTED_FACILITY, ViolationCode.LEAD_TIME_TOO_LONG]
    assert ggl.cost_fen is None and ggl.cost_display == "—"


def test_marginal_cost_is_invoice_financing(sm):
    s, m = sm
    rate, fid = marginal_cost(s, m)
    assert fid == "FAC-IF"
    assert fmt_pct(rate.value) == "10.84%"
    assert fmt_pct(rate.value, 4) == golden_values()["if_all_in_rate_display"]


def test_break_even_discount(sm, g):
    s, m = sm
    d, floor_bp = break_even_discount(s, m)
    assert floor_bp == g["break_even_discount_bp"] == 88
    assert fmt_pct(d.value) == g["break_even_discount_display"]
    c = d.value / (1 - d.value)  # d/(1−d) recovers the 30-day cost share
    assert round(c * 1_000_000) == g["if_30d_cost_share_bp_x100"]


def test_extension_cost_bases(sm, g):
    s, m = sm
    notional, committed, expected = extension_cost_bases(s, terms_extension(15), m)
    assert notional.value_fen == g["extension_notional_line_12m"]
    assert notional.per_invoice_fen == g["extension_notional_line_per_invoice"]
    assert "not usable" in notional.basis
    assert committed.value_fen == g["extension_committed_12m"]
    assert committed.per_invoice_fen == g["extension_committed_per_invoice"]
    assert "committed marginal source" in committed.basis
    assert expected.value_fen == g["extension_expected_12m"]
    assert "expected plan" in expected.basis and "21-day" in expected.basis


def test_extension_cost_bases_rejects_other_obligations(sm):
    s, m = sm
    ob = terms_extension().model_copy(update={"type": "PRICE_ADJUSTMENT"})
    with pytest.raises(ValueError):
        extension_cost_bases(s, ob, m)


def test_menu_view_same_basis(sm):
    s, m = sm
    rows = {r.facility_id: r for r in menu_view(s, m, need_fen=36_000_000, need_day=12)}
    assert rows["FAC-LINE"].all_in_display == "6.40%" and rows["FAC-LINE"].short_term_only
    assert rows["FAC-LINE"].admissible_for_need and rows["FAC-LINE"].time_to_cash_days == 0
    assert rows["FAC-IF"].all_in_display == "10.84%" and rows["FAC-IF"].admissible_for_need
    assert rows["FAC-EARLYPAY"].all_in_display == "14.78%" and not rows["FAC-EARLYPAY"].is_debt
    assert rows["FAC-GGL"].reasons == [ViolationCode.UNCOMMITTED_FACILITY, ViolationCode.LEAD_TIME_TOO_LONG]
    assert rows["FAC-GGL"].available_fen == 0 and rows["FAC-GGL"].expected_only
    assert rows["FAC-LEASE"].reasons == [ViolationCode.UNCOMMITTED_FACILITY]
    assert ViolationCode.TIER3_EQUITY in rows["FAC-EQUITY"].reasons
    assert not rows["FAC-BILL"].admissible_for_need  # no bills held
    for fid, row in rows.items():
        if row.status != FacilityStatus.COMMITTED:
            assert row.available_fen == 0, fid


def test_menu_flags_max_apr(sm):
    s, m = sm
    tight = m.model_copy(update={"max_apr_bp": 1000})
    rows = {r.facility_id: r for r in menu_view(s, tight)}
    assert ViolationCode.MAX_APR_EXCEEDED in rows["FAC-IF"].reasons
    assert ViolationCode.MAX_APR_EXCEEDED in rows["FAC-EARLYPAY"].reasons
    assert ViolationCode.MAX_APR_EXCEEDED not in rows["FAC-LINE"].reasons


def test_router_satisfies_port(sm, g):
    s, m = sm
    r: FundingRouter = Router()
    assert r.plan(s, [], m).total_cost_fen == g["v2_optimum_total"]
    assert r.marginal_cost(s, m)[1] == "FAC-IF"


def test_expected_basis_on_golden_is_labelled_expected(sm, g):
    s, m = sm
    p = plan(s, [], m, basis="EXPECTED")
    assert p.basis == "EXPECTED" and "expected" in p.label
    # the guaranteed loan lands on day 21, after payroll: the expected plan cannot use it here either
    assert p.total_cost_fen == g["v2_optimum_total"]


def test_no_gap_gives_empty_plan(sm):
    s, m = sm
    rich = s.model_copy(update={"cash_fen": 100_000_000})
    p = plan(rich, [], m)
    assert p.admissible and p.actions == [] and p.total_cost_fen == 0 and p.need_fen == 0
    rows = compare(rich, [], m)
    assert len(rows) == 1 and rows[0].result == ComparisonResult.SELECTED and rows[0].cost_fen == 0


def test_bad_basis_raises(sm):
    s, m = sm
    with pytest.raises(ValueError):
        plan(s, [], m, basis="HOPEFUL")
