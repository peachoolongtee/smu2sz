"""Property: `financial.project_cash` (the router's fast path) reports exactly what the full
`financial.project` reports (closing cash of every day, horizon, peak debt, posted interest, fees
and discounts) and raises exactly when `project` raises, over random states, offers and actions."""

from __future__ import annotations

from random import Random

import pytest

from app.domain.models import Mode
from app.financial import project, project_cash
from app.funding import plan
from tests.funding.random_cases import random_actions, random_case

SEEDS = range(300)


def _full(c, actions, mode):
    try:
        t = project(c.state, c.obligations, actions, mode, c.mandate.horizon_days, c.mandate.min_cash_fen)
    except Exception as e:  # noqa: BLE001 - the same failure is part of the contract
        return "raise", type(e).__name__, str(e)
    return ("ok", t.horizon_days, tuple(p.closing_fen for p in t.days),
            max(p.debt_outstanding_fen for p in t.days), t.interest_posted_fen, t.fees_posted_fen,
            t.discounts_posted_fen)


def _fast(c, actions, mode):
    try:
        p = project_cash(c.state, c.obligations, actions, mode, c.mandate.horizon_days, c.mandate.min_cash_fen)
    except Exception as e:  # noqa: BLE001
        return "raise", type(e).__name__, str(e)
    return "ok", p.horizon_days, p.closings, p.peak_debt_fen, p.interest_posted_fen, p.fees_posted_fen, \
        p.discounts_posted_fen


@pytest.mark.parametrize("seed", SEEDS)
def test_cash_path_equals_project(seed):
    c = random_case(seed)
    rng = Random(seed)
    for mode in (Mode.CONSERVATIVE, Mode.EXPECTED):
        for _ in range(4):
            actions = random_actions(rng, c.state)
            assert _fast(c, actions, mode) == _full(c, actions, mode)


@pytest.mark.parametrize("seed", range(0, 300, 5))
def test_cash_path_equals_project_on_the_router_plan(seed):
    """The router's own plans (well-formed, multi-source) are costed the same way on both paths."""
    c = random_case(seed)
    try:
        p = plan(c.state, c.obligations, c.mandate, "COMMITTED")
    except Exception:  # noqa: BLE001 - an unbindable offer: covered by the random-action test
        return
    for mode in (Mode.CONSERVATIVE, Mode.EXPECTED):
        assert _fast(c, p.actions, mode) == _full(c, p.actions, mode)


def test_random_actions_reach_both_outcomes():
    ok = raised = 0
    for seed in range(60):
        c = random_case(seed)
        rng = Random(seed)
        for _ in range(4):
            r = _full(c, random_actions(rng, c.state), Mode.CONSERVATIVE)
            ok += r[0] == "ok"
            raised += r[0] == "raise"
    assert ok >= 40 and raised >= 20, (ok, raised)
