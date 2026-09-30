"""Differential test: the fast search (cash-only probes, lazy covenants) against the frozen
reference search (`tests/funding/reference_search.py`, full `project` + covenants for every candidate).

Over seeded random states, menus, mandates, offers and bases, `plan()` must return an identical
FundingPlan (actions, cost, cost lines, rejected alternatives, violations, label, id) and, on the
COMMITTED basis, `compare()` identical rows. An exception must be the same exception.

The reference is slow on the few cases whose search is exhaustive (no admissible plan to prune
against): a case whose fast search makes more than HEAVY_PROBES probes is compared only with
ROUTER_DIFF_FULL=1 (which also checks `compare()` on every seed). By default at least 200 seeds run.
"""

from __future__ import annotations

import os
from collections import Counter
from functools import cache
from unittest.mock import patch

import pytest

import app.funding.router as router_mod
from app.funding import compare, plan
from app.funding.search import Search
from tests.funding import cases
from tests.funding.random_cases import random_case
from tests.funding.reference_search import Search as ReferenceSearch

FULL = os.environ.get("ROUTER_DIFF_FULL") == "1"
SEEDS = range(int(os.environ.get("ROUTER_DIFF_SEEDS", "240")))
COMPARE_EVERY = 1 if FULL else 4  # compare() re-runs the committed search
HEAVY_PROBES = 1500
MIN_DEFAULT_SEEDS = 200


def _outcome(fn, *args):
    try:
        return "ok", fn(*args)
    except Exception as e:  # noqa: BLE001 - the same failure is part of the contract
        return "raise", type(e).__name__, str(e)


def _with(search_cls, fn, *args):
    with patch.object(router_mod, "Search", search_cls):
        return _outcome(fn, *args)


_RUNS: list[Search] = []


class _Counted(Search):
    """The fast search, remembering its instances so a test can count their probes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _RUNS.append(self)


@cache
def _fast(seed: int) -> tuple[tuple, int]:
    """(fast plan outcome, probes it made) for a seed."""
    c = random_case(seed)
    _RUNS.clear()
    out = _with(_Counted, plan, c.state, c.obligations, c.mandate, c.basis)
    return out, sum(len(s._probes) for s in _RUNS)


def _skip_heavy(seed: int) -> None:
    probes = _fast(seed)[1]
    if probes > HEAVY_PROBES and not FULL:
        pytest.skip(f"exhaustive case ({probes} probes): run with ROUTER_DIFF_FULL=1")


@pytest.mark.parametrize("seed", SEEDS)
def test_plan_matches_reference(seed):
    _skip_heavy(seed)
    c = random_case(seed)
    assert _fast(seed)[0] == _with(ReferenceSearch, plan, c.state, c.obligations, c.mandate, c.basis)


@pytest.mark.parametrize("seed", [s for s in SEEDS if s % COMPARE_EVERY == 0])
def test_compare_matches_reference(seed):
    _skip_heavy(seed)
    c = random_case(seed)
    args = (c.state, c.obligations, c.mandate)
    assert _with(Search, compare, *args) == _with(ReferenceSearch, compare, *args)


DESIGNED = ["bill_held", "dear_line", "cheap_early_pay", "leverage_tight", "no_new_borrowing", "long_gap",
            "late_cheap_loan", "uncovered_gap", "expected_only_gap", "permanent_need"]


@pytest.mark.parametrize("name", DESIGNED)
@pytest.mark.parametrize("basis", ["COMMITTED", "EXPECTED"])
def test_designed_cases_match_reference(name, basis):
    s, m = getattr(cases, name)()
    assert _with(Search, plan, s, [], m, basis) == _with(ReferenceSearch, plan, s, [], m, basis)
    if basis == "COMMITTED":
        assert _with(Search, compare, s, [], m) == _with(ReferenceSearch, compare, s, [], m)


def test_random_cases_cover_every_outcome():
    """The random cases reach every branch that matters: no gap, an admissible plan with one, two
    and three sources, no admissible plan (best effort), and both bases."""
    kinds: Counter[str] = Counter()
    for seed in SEEDS:
        fast, probes = _fast(seed)
        kinds["compared"] += FULL or probes <= HEAVY_PROBES
        if fast[0] == "raise":
            kinds["raises"] += 1
            continue
        p = fast[1]
        kinds[p.basis] += 1
        if not p.need_fen:
            kinds["no_gap"] += 1
        elif p.admissible:
            kinds[f"plan_{len(p.actions)}"] += 1
        else:
            kinds["infeasible"] += 1
    for k in ("no_gap", "plan_1", "plan_2", "infeasible", "EXPECTED", "COMMITTED"):
        assert kinds[k] >= 5, kinds
    assert kinds["plan_3"] >= 1, kinds
    if len(SEEDS) >= MIN_DEFAULT_SEEDS:
        assert kinds["compared"] >= MIN_DEFAULT_SEEDS, kinds
