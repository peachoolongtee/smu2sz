"""The router rules added after the evaluation report (agent/evals):

- EV-06: a bullet line may be repaid on any inflow day after the gap opens, not only when the
  unfunded baseline recovers. The seeded variants R01/R03/R05/R15 now reach the brute-force optimum.
- EV-07: the display-only EXPECTED search stops after `EXPECTED_PROBE_BUDGET` candidates; the
  COMMITTED search is never capped.
- EV-11: no action below MIN_ACTION_FEN (¥1,000): a 1-fen shortfall is covered by a ¥1,000 line draw,
  not a 1-fen early payment.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import app.funding.router as router_mod
from app.domain.fixtures import golden_values
from app.domain.models import (
    BaseKind,
    Contingency,
    Duration,
    DurationKind,
    FundingActionKind,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
)
from app.financial import project
from app.funding import plan
from app.funding.search import MIN_ACTION_FEN, Search
from tests.funding import cases
from tests.funding.random_cases import random_case
from tests.funding.test_differential import LegacyRules
from tests.funding.variants import SPAN, golden, pricing_only

# (case, brute-force optimum in fen, the router's cost before EV-06). Every gap includes the existing loan's
# ¥45,000 day-30 payment (FINANCIAL_SEMANTICS §5): need = payroll + 120,000 + 45,000 + 300,000 reserve − cash.
# R01 (need 505,000): line 150,000 × 5.5% × 32/365 = 723.29 + early pay on RI:2 netting 355,000 at 0.8%: face
#   355,000 / 0.992 = 357,862.90, discount 2,862.90 -> 3,586.19. Before EV-06 the line ran to day 47:
#   150,000 × 5.5% × 47/365 = 1,062.33 + 2,862.90 = 3,925.23.
# R03 (need 515,000): line 200,000 × 6.4% × 32/365 = 1,122.19 + a bill netting 315,000 at 1.5% for 179 days:
#   face 315,000 / (1 − 1.5% × 179/365) = 317,334.36, discount 2,334.36 -> 3,456.55. Before: the whole 400,000 bill
#   (2,942.47) + an advance of 515,000 − 397,057.53 = 117,942.47 (581.63 + fee 294.86) -> 3,818.96.
# R05 (need 515,000): line 300,000 × 4.5% × 32/365 = 1,183.56 + early pay 100,000 at 1.2% (1,200.00, nets 98,800)
#   + an advance of 116,200 (116,200 × 7.8% × 30/365 = 744.95 + fee 116.20) -> 3,244.71. Before: line to day 47
#   (1,738.36) + an advance of 215,000 (1,378.36 + 215.00) -> 3,331.72.
# R15 (need 565,000): line 300,000 × 8% × 32/365 = 2,104.11 + early pay netting 265,000 at 0.8%: face 267,137.10,
#   discount 2,137.10 -> 4,241.21. Before: early pay of all 420,000 (3,360.00) + an advance of 148,360
#   (853.58 + fee 593.44) -> 4,807.02.
EV06 = [
    ("r01_early_line_repayment", 358_619, 392_523),
    ("r03_early_line_repayment", 345_655, 381_896),
    ("r05_early_line_repayment", 324_471, 333_172),
    ("r15_early_line_repayment", 424_121, 480_702),
]


def _plan_with(search_cls, *args):
    with patch.object(router_mod, "Search", search_cls):
        return plan(*args)


@pytest.mark.parametrize("name,optimum,before", EV06)
def test_line_may_be_repaid_before_the_baseline_recovers(name, optimum, before):
    # the EV-06 arithmetic, on the pricing reading (early pay and bills ranked as runnable legs, `pricing_only`):
    # since red team d F1 the router ranks a runnable plan first, which for R03/R05/R15 is a line and an advance
    s, m = getattr(cases, name)()
    p = _plan_with(pricing_only(Search), s, [], m)
    assert p.admissible and p.total_cost_fen == optimum
    line = next(a for a in p.actions if a.facility_id == "FAC-LINE")
    assert line.repay_day == 32  # RCV-A's receipt; the unfunded baseline recovers only on day 47
    t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None
    assert _plan_with(pricing_only(LegacyRules), s, [], m).total_cost_fen == before
    now = plan(s, [], m)  # today's router: the cheapest plan that can run, else the cheapest one flagged
    assert now.admissible and now.total_cost_fen >= optimum
    assert now.executable_now is not any(a.kind in (FundingActionKind.EARLY_PAY, FundingActionKind.DISCOUNT_BILL)
                                         for a in now.actions)


def test_golden_plan_is_unchanged():
    s, m = golden()
    p = plan(s, [], m)
    # line 841.64 + an advance of 405,000 − 150,000 = 255,000 (1,634.79 + fee 637.50) = 3,113.93
    assert p.total_cost_fen == golden_values()["v2_optimum_total"] == 311_393
    assert sorted((a.facility_id, a.amount_fen, a.repay_day) for a in p.actions) == [
        ("FAC-IF", 25_500_000, None), ("FAC-LINE", 15_000_000, 32)]


def _one_fen_short():
    """The evaluation's reserve boundary: a 1% early settlement of RCV-A with opening cash 1 fen short. The low is
    day 30, after the existing loan's ¥45,000 payment: 389,199.99 + 415,800 − 340,000 − 120,000 − 45,000 =
    299,999.99 (the evaluation's 344,199.99 plus that payment)."""
    s, m = golden()
    s = s.model_copy(update={"cash_fen": 38_919_999})
    ob = Obligation(id="OB-D", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=100,
                    base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=42_000_000, receivable_id="RCV-A"),
                    contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN,
                    confidence=1.0)
    return s, [ob], m


def test_a_one_fen_gap_gets_a_minimum_ticket_not_a_one_fen_early_payment():
    s, obs, m = _one_fen_short()
    old = _plan_with(pricing_only(LegacyRules), s, obs, m, "COMMITTED")  # the 1-fen early pay EV-11 removed
    assert [(a.kind, a.amount_fen) for a in old.actions] == [(FundingActionKind.EARLY_PAY, 1)]
    p = plan(s, obs, m, "COMMITTED")
    assert p.admissible and p.need_fen == 1
    assert [(a.kind, a.facility_id, a.amount_fen) for a in p.actions] == [
        (FundingActionKind.DRAW, "FAC-LINE", MIN_ACTION_FEN)]
    t = project(s, obs, p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None


@pytest.mark.parametrize("seed", range(0, 240, 3))
def test_no_action_is_below_the_minimum_ticket(seed):
    c = random_case(seed)
    p = plan(c.state, c.obligations, c.mandate, c.basis)
    assert all(a.amount_fen >= MIN_ACTION_FEN for a in p.actions)


def test_expected_search_near_the_floor_is_fast():
    """EV-07: this EXPECTED plan took 13.4 s before the cash-only probes and the budget."""
    s, obs, m = _one_fen_short()
    start = time.perf_counter()
    p = plan(s, obs, m, "EXPECTED")
    assert time.perf_counter() - start < 1.0
    assert p.admissible


class _TinyBudget(Search):
    EXPECTED_PROBE_BUDGET = 5


def test_expected_search_stops_at_its_budget_and_says_so():
    s, m = golden()
    runs: list[Search] = []

    class Recorded(_TinyBudget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            runs.append(self)

    p = _plan_with(Recorded, s, [], m, "EXPECTED")
    assert runs[0].capped
    assert "search capped" in p.label
    assert p.admissible  # the best found within the budget, still fully checked


def test_committed_search_is_never_capped():
    s, m = golden()
    runs: list[Search] = []

    class Recorded(_TinyBudget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            runs.append(self)

    p = _plan_with(Recorded, s, [], m, "COMMITTED")
    assert not runs[0].capped and len(runs[0]._probes) > _TinyBudget.EXPECTED_PROBE_BUDGET
    assert p.total_cost_fen == 311_393 and "capped" not in p.label
