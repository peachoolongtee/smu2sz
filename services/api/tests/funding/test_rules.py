"""The Debt Desk's rules: committed only, time to cash, clean-down, infeasibility, expected basis."""

from __future__ import annotations

import pytest

from app.domain.models import FacilityStatus, FundingActionKind, ViolationCode
from app.domain.money import fmt_pct
from app.funding import break_even_discount, marginal_cost, menu_view, plan
from app.funding.rates import NoPermanentSourceError
from tests.funding import cases
from tests.funding.variants import golden, with_facility, without_facilities


def test_late_cheap_loan_is_rejected_when_cash_is_needed_earlier():
    s, m = cases.late_cheap_loan(payroll_day=12)
    p = plan(s, [], m)
    assert p.admissible
    assert all(a.facility_id != "FAC-GGL" for a in p.actions)
    ggl = next(r for r in menu_view(s, m, need_fen=p.need_fen, need_day=12) if r.facility_id == "FAC-GGL")
    assert ggl.reasons == [ViolationCode.LEAD_TIME_TOO_LONG] and not ggl.admissible_for_need


def test_the_same_loan_is_used_when_the_gap_opens_after_it_lands():
    s, m = cases.late_cheap_loan(payroll_day=25)
    p = plan(s, [], m)
    assert p.admissible
    assert any(a.facility_id == "FAC-GGL" for a in p.actions)


def test_permanent_need_is_never_put_on_a_clean_down_line():
    s, m = cases.permanent_need()
    p = plan(s, [], m)
    assert p.admissible
    assert [a.facility_id for a in p.actions] == ["FAC-GGL"]
    # the line is the cheapest source, but clean-down rules it out as the marginal cost of funds
    rate, fid = marginal_cost(s, m)
    assert fid == "FAC-GGL" and fmt_pct(rate.value) == "5.00%"


def test_long_gap_avoids_the_line():
    s, m = cases.long_gap()
    p = plan(s, [], m)
    assert p.admissible and all(a.facility_id != "FAC-LINE" for a in p.actions)
    assert any(r.label == "Line only" and ViolationCode.CLEAN_DOWN_BREACH in r.reasons for r in p.rejected)


def test_line_without_clean_down_can_be_the_marginal_source():
    s, m = golden()
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    s = with_facility(s, "FAC-LINE", covenants=[c for c in line.covenants if c.kind != "CLEAN_DOWN"])
    assert marginal_cost(s, m)[1] == "FAC-LINE"


def test_marginal_cost_excludes_early_pay_zero_limit_and_reference_only():
    s, m = golden()
    s = without_facilities(s, "FAC-IF", "FAC-LINE")
    with pytest.raises(NoPermanentSourceError):  # early pay, a zero-limit bill and equity cannot
        marginal_cost(s, m)


def test_break_even_follows_the_marginal_source():
    s, m = golden()
    s = with_facility(s, "FAC-IF", rate_bp=580)  # 5.8% + 0.25%/30 days
    _, floor_bp = break_even_discount(s, m)
    assert floor_bp == 72  # c = 5.8% × 30/365 + 0.25% = 0.72671%; d = c/(1+c) = 0.7215%


def test_infeasible_gap_reports_reserve_breach_and_day():
    s, m = cases.uncovered_gap()
    p = plan(s, [], m)
    assert not p.admissible and p.actions == [] and p.total_cost_fen == 0
    breach = [v for v in p.violations if v.code == ViolationCode.RESERVE_BREACH]
    assert breach and breach[0].day == 12
    assert "even with" in breach[0].message


def test_expected_basis_may_use_the_guaranteed_loan_and_says_so():
    s, m = cases.expected_only_gap()
    committed = plan(s, [], m)
    assert not committed.admissible  # INVARIANT 4: the loan counts as zero
    assert all(a.facility_id != "FAC-GGL" for a in committed.actions)
    expected = plan(s, [], m, basis="EXPECTED")
    assert expected.admissible and expected.basis == "EXPECTED"
    assert "expected" in expected.label and "never relied on" in expected.label
    ggl = [a for a in expected.actions if a.facility_id == "FAC-GGL"]
    assert ggl and ggl[0].kind == FundingActionKind.DRAW
    assert any("(expected)" in c.label for c in expected.costs if c.facility_id == "FAC-GGL")
    # the what-if never leaks into the caller's state
    assert next(f for f in s.facilities if f.id == "FAC-GGL").status == FacilityStatus.NOT_APPLIED


def test_a_plan_above_max_apr_is_admissible_but_needs_the_owner():
    s, m = golden()
    p = plan(s, [], m.model_copy(update={"max_apr_bp": 1000}))
    # only the 6.4% line is within 10%, and it cannot cover ¥360,000: the plan is still the cheapest cover, and the
    # advance leg (11.22% over its 29 days) is the one the owner must approve
    assert p.admissible and p.needs_owner_approval and "11.22%" in p.approval_reason
    by_fac = {c.facility_id: c for c in p.costs}
    assert by_fac["FAC-IF"].needs_owner_approval and not by_fac["FAC-LINE"].needs_owner_approval
    assert ViolationCode.MAX_APR_EXCEEDED not in {v.code for v in p.violations}


def test_tier3_facilities_are_never_planned():
    s, m = golden()
    s = with_facility(s, "FAC-IF", personal_guarantee=True)
    p = plan(s, [], m)
    assert all(a.facility_id != "FAC-IF" for a in p.actions)
    row = next(r for r in menu_view(s, m) if r.facility_id == "FAC-IF")
    assert ViolationCode.TIER3_PERSONAL_GUARANTEE in row.reasons


def test_not_owner_approved_is_never_planned():
    s, m = golden()
    s = with_facility(s, "FAC-IF", owner_approved=False)
    p = plan(s, [], m)
    assert all(a.facility_id != "FAC-IF" for a in p.actions)
    assert not p.admissible or p.total_cost_fen > 271_294
