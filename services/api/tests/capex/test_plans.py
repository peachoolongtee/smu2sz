"""ADR-0013, phase 7: long-term plan permutations on a monthly estimate, on the golden books (EBITDA ¥90,000 a month, existing
debt service ¥45,000 a month until month 34, cash ¥400,000, reserve ¥300,000)."""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from app.capex.appraisal import NPV_PRECISION
from app.capex.plans import MAX_COMBINATIONS, PlanProject, PlanRefused, PlanRequest, plan
from app.capex.schedule import Timeline
from app.contracts import read_document
from app.domain.fixtures import capex_contract_fixture_bytes
from app.domain.models import DocumentKind
from app.domain.money import post

LINE_TIMELINE = Timeline(signing_day=20, delivery_day=60, acceptance_day=80)


@pytest.fixture
def record(state):
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    return read_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM", title="GZPM", source="t", day=0,
                         facilities=state.facilities).model_copy(update={"id": "DOC-000001"})


def line(**kw):  # type: ignore[no-untyped-def]
    return PlanProject(id="line", label="Die-cutting line", document_id="DOC-000001", timeline=LINE_TIMELINE,
                       monthly_uplift_fen=2_200_000, **kw)


def robot(**kw):  # type: ignore[no-untyped-def]
    return PlanProject(id="robot", label="Packing robot", price_fen=40_000_000, monthly_uplift_fen=1_500_000,
                       uplift_start_month=4, **kw)


def test_two_projects_rank_the_admissible_permutations_by_npv(record, state, mandate):
    r = plan(PlanRequest(projects=[line(), robot(optional=True)]), state, mandate, [record])
    assert r.combinations == 4 * 4 * (4 * 4 + 1)  # 4 offsets x (cash + 3 term facilities), the robot optional
    assert r.admissible_count > 0 and len(r.best) == 5
    npvs = [b.npv_fen for b in r.best]
    assert npvs == sorted(npvs, reverse=True) and all(b.admissible and b.first_failure is None for b in r.best)
    assert [b.rank for b in r.best] == [1, 2, 3, 4, 5]
    best = r.best[0]
    assert len(best.months) == 60 and best.months[0].month == 1
    assert best.lowest_headroom_fen == min(mo.cash_fen for mo in best.months) - 30_000_000


def test_a_facility_lends_no_more_than_its_limit_across_projects(record, state, mandate):
    r = plan(PlanRequest(projects=[line(start_offsets=[0], options=["FAC-ETL"]),
                                   robot(start_offsets=[0], options=["FAC-ETL"])]), state, mandate, [record])
    assert r.admissible_count == 0 and r.best == []
    u = r.best_unconstrained
    assert u is not None and "would lend ¥1,000,000.00, above the ¥600,000.00 left on it" in (u.first_failure or "")


def test_dscr_is_tested_every_month_before_the_uplift_starts(record, state, mandate):
    # both now: month 2 carries ¥45,000 existing + ¥18,144.62 ETL + ¥9,615.66 lease service and no uplift yet
    r = plan(PlanRequest(projects=[line(start_offsets=[0], options=["FAC-ETL"]),
                                   robot(start_offsets=[0], options=["FAC-LEASE"])]), state, mandate, [record])
    u = r.best_unconstrained
    assert r.admissible_count == 0 and u is not None
    assert u.first_failure == "month 2: DSCR 1.24× is below the 1.25× minimum"
    assert Fraction(9_000_000, 4_500_000 + 1_814_462 + 961_566) < Fraction(5, 4)


def test_an_optional_project_can_be_left_out(record, state, mandate):
    r = plan(PlanRequest(projects=[line(start_offsets=[0], options=["FAC-LEASE"]),
                                   robot(start_offsets=[0], options=["CASH"], optional=True)]), state, mandate, [record])
    by = {tuple((c.project_id, c.option) for c in b.choices): b for b in r.best}
    assert (("line", "FAC-LEASE"), ("robot", "SKIP")) in by
    skipped = by[(("line", "FAC-LEASE"), ("robot", "SKIP"))]
    assert "leave Packing robot out" in skipped.text


def test_npv_is_the_sum_of_the_projects_own_npvs_rounded_once(record, state, mandate):
    alone_line = plan(PlanRequest(projects=[line(start_offsets=[0], options=["CASH"])]), state, mandate, [record])
    alone_robot = plan(PlanRequest(projects=[robot(start_offsets=[0], options=["CASH"])]), state, mandate, [record])
    both = plan(PlanRequest(projects=[line(start_offsets=[0], options=["CASH"]),
                                      robot(start_offsets=[0], options=["CASH"])]), state, mandate, [record])
    a = (alone_line.best or [alone_line.best_unconstrained])[0]
    b = (alone_robot.best or [alone_robot.best_unconstrained])[0]
    c = (both.best or [both.best_unconstrained])[0]
    assert a is not None and b is not None and c is not None
    assert abs(c.npv_fen - (a.npv_fen + b.npv_fen)) <= 1  # each rounded once; the sum rounded once


def test_a_cash_purchase_today_is_in_month_one(state, mandate):
    """A price paid today (month 0) is never dropped from the monthly tests."""
    r = plan(PlanRequest(projects=[PlanProject(id="x", price_fen=30_000_000, start_offsets=[0], options=["CASH"])]),
             state, mandate, [])
    u = r.best[0] if r.best else r.best_unconstrained
    assert u is not None
    # month 1: ¥400,000 + ¥90,000 − ¥45,000 − ¥300,000 = ¥145,000, below the reserve and lower than without the purchase
    assert u.months[0].cash_fen == 14_500_000 and not u.admissible
    assert u.first_failure is not None and u.first_failure.startswith("month 1: cash ¥145,000.00 is below")


def test_npv_of_one_cash_purchase_today_matches_the_formula(state, mandate):
    r = plan(PlanRequest(projects=[PlanProject(id="x", price_fen=10_000_000, monthly_uplift_fen=500_000,
                                               uplift_start_month=2, life_months=24, start_offsets=[0],
                                               options=["CASH"])]), state, mandate, [])
    got = (r.best or [r.best_unconstrained])[0]
    assert got is not None
    with localcontext() as ctx:
        ctx.prec = NPV_PRECISION
        rm = (1 + Decimal(1000) / Decimal(10_000)) ** (Decimal(1) / Decimal(12)) - 1
        want = -Decimal(10_000_000) + sum(Decimal(500_000) / (1 + rm) ** m for m in range(2, 25))
        assert got.npv_fen == post(Fraction(want))


def test_the_best_plans_contract_is_rechecked_day_by_day(record, state, mandate):
    r = plan(PlanRequest(projects=[line(start_offsets=[0], options=["FAC-LEASE"])]), state, mandate, [record])
    assert [c.project_id for c in r.daily_checks] == ["line"]
    assert r.daily_checks[0].plan_option_passes is True


@pytest.mark.parametrize(("projects", "code"), [
    ([PlanProject(id="a", price_fen=1), PlanProject(id="a", price_fen=1)], "DUPLICATE_PROJECT"),
    ([PlanProject(id="a")], "NO_PRICE"),
    ([PlanProject(id="a", price_fen=1, options=["FAC-NOPE"])], "UNKNOWN_OPTION"),
    ([PlanProject(id="a", price_fen=1, options=["FAC-EQUITY"])], "UNKNOWN_OPTION"),
    ([PlanProject(id="a", price_fen=1, start_offsets=[-1])], "BAD_OFFSET"),
    ([PlanProject(id="a", document_id="DOC-404", timeline=Timeline())], "NOT_A_CAPEX_CONTRACT"),
])
def test_bad_requests_are_refused_with_a_code(state, mandate, projects, code):
    with pytest.raises(PlanRefused) as exc:
        plan(PlanRequest(projects=projects), state, mandate, [])
    assert exc.value.code == code


def test_too_many_permutations_are_refused_not_sampled(state, mandate):
    many = [PlanProject(id=f"p{i}", price_fen=1_000_000, start_offsets=list(range(13)), optional=True)
            for i in range(4)]
    with pytest.raises(PlanRefused) as exc:
        plan(PlanRequest(projects=many), state, mandate, [])
    assert exc.value.code == "TOO_MANY_COMBINATIONS" and f"{MAX_COMBINATIONS:,}" in str(exc.value)


def test_no_new_borrowing_means_cash_only(state, mandate):
    with pytest.raises(PlanRefused):
        plan(PlanRequest(projects=[PlanProject(id="a", price_fen=1, options=["FAC-ETL"])]), state,
             mandate.model_copy(update={"allow_new_borrowing": False}), [])


def test_a_purchase_already_committed_comes_off_the_baseline(state, mandate):
    """Committed capex payments are capital: EBITDA does not hold them, so the plan's baseline must."""
    from app.domain.models import CashFlow, FlowKind

    req = PlanRequest(projects=[PlanProject(id="x", price_fen=1_000_000, start_offsets=[0], options=["CASH"])])
    before = plan(req, state, mandate, [])
    flow = CashFlow(id="CAPEX:DOC-000009:1", day=50, amount_fen=-18_000_000, kind=FlowKind.CAPEX, label="committed")
    after = plan(req, state.model_copy(update={"flows": [*state.flows, flow]}), mandate, [])
    b = (before.best or [before.best_unconstrained])[0]
    a = (after.best or [after.best_unconstrained])[0]
    assert a is not None and b is not None
    # day 50 is in month 2: months 1 unchanged, months 2.. lower by exactly the committed payment
    assert a.months[0].baseline_cash_fen == b.months[0].baseline_cash_fen
    assert all(x.baseline_cash_fen == y.baseline_cash_fen - 18_000_000 for x, y in zip(a.months[1:], b.months[1:], strict=True))
