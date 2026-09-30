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
from tests.funding.variants import SPAN, golden

# (case, brute-force optimum in fen, the router's cost before EV-06)
EV06 = [
    ("r01_early_line_repayment", 322_329, 356_233),
    ("r03_early_line_repayment", 312_307, 348_455),
    ("r05_early_line_repayment", 270_534, 299_822),
    ("r15_early_line_repayment", 387_830, 436_811),
]


def _plan_with(search_cls, *args):
    with patch.object(router_mod, "Search", search_cls):
        return plan(*args)


@pytest.mark.parametrize("name,optimum,before", EV06)
def test_line_may_be_repaid_before_the_baseline_recovers(name, optimum, before):
    s, m = getattr(cases, name)()
    p = plan(s, [], m)
    assert p.admissible and p.total_cost_fen == optimum
    line = next(a for a in p.actions if a.facility_id == "FAC-LINE")
    assert line.repay_day == 32  # RCV-A's receipt; the unfunded baseline recovers only on day 47
    t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    assert t.first_breach_day is None
    assert _plan_with(LegacyRules, s, [], m).total_cost_fen == before


def test_golden_plan_is_unchanged():
    s, m = golden()
    p = plan(s, [], m)
    assert p.total_cost_fen == golden_values()["v2_optimum_total"] == 271_294
    assert sorted((a.facility_id, a.amount_fen, a.repay_day) for a in p.actions) == [
        ("FAC-IF", 21_000_000, None), ("FAC-LINE", 15_000_000, 32)]


def _one_fen_short():
    """The evaluation's reserve boundary: a 1% early settlement of RCV-A with opening cash 1 fen short."""
    s, m = golden()
    s = s.model_copy(update={"cash_fen": 34_419_999})
    ob = Obligation(id="OB-D", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=100,
                    base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=42_000_000, receivable_id="RCV-A"),
                    contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN,
                    confidence=1.0)
    return s, [ob], m


def test_a_one_fen_gap_gets_a_minimum_ticket_not_a_one_fen_early_payment():
    s, obs, m = _one_fen_short()
    old = _plan_with(LegacyRules, s, obs, m, "COMMITTED")
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
    assert p.total_cost_fen == 271_294 and "capped" not in p.label
