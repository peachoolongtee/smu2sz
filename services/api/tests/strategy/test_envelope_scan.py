"""The envelope's monotonicity guard (ticket #98, P5; brief E.2).

Online: `top_first` no longer takes a passing top on trust; one middle probe and the neighbour below the top must pass too,
or the lever is scanned whole and reported unconfirmed. Offline: the weekly exhaustive scan
(`scripts/envelope_monotone_scan.py`) compares every terms x price cell with the online answers and fails loudly on any
disagreement. The scan itself costs 273 evaluations per buyer, so it is run by the pilot's weekly job, not here: these tests
pin its comparison on synthetic scans, and its exit code.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.strategy.envelope import AskFacts, EnvelopeFacts, Maximum, Probe, Setting, ZoneRow, last_true

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "envelope_monotone_scan.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("envelope_monotone_scan", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # its dataclasses look their module up while it loads
    spec.loader.exec_module(mod)
    return mod


scan_mod = _script()


# ---------------------------------------------------------------- the online middle probe


def test_a_lever_that_passes_at_both_ends_and_fails_between_is_scanned_not_trusted():
    values = list(range(30, 95, 5))
    asked: list[int] = []

    def ok(v: int) -> bool:
        asked.append(v)
        return v in (30, 35, 90)

    found = last_true(values, ok, gallop=True, top_first=True)
    assert found.value == 90 and found.scanned and not found.confirmed  # reported, never taken as a confirmed maximum


def test_a_monotone_lever_with_no_wall_costs_four_evaluations_and_is_confirmed():
    values = list(range(30, 95, 5))
    asked: list[int] = []

    def ok(v: int) -> bool:
        asked.append(v)
        return True

    found = last_true(values, ok, gallop=True, top_first=True)
    assert (found.value, found.confirmed, found.scanned) == (90, True, False)
    assert sorted(set(asked)) == [30, 60, 85, 90]


def test_an_island_just_below_the_top_is_caught_by_the_neighbour():
    values = list(range(30, 95, 5))
    found = last_true(values, lambda v: v != 85, top_first=True)
    assert found.scanned and not found.confirmed


# ---------------------------------------------------------------- the weekly scan's comparison


def _probe(s: Setting) -> Probe:
    return Probe(setting=s, outcome="ACCEPT", tier="TIER_1", passes=True, liquidity_only=True, codes=(), binding=(),
                 forward_total_fen=0, reserve_day=None, reserve_curable=None, cure_cost_fen=None, cure_needs_owner=False,
                 cure_cannot_run_today=False, counters=(), counter_costs_fen=(), plan_cost_fen=None, recheck=None)


TERMS = (45, 50, 55, 60)
PRICES = (0, 5, 10, 15, 20, 25, 30)
WALL = {45: 0, 50: 10, 55: 25}  # the smallest approved price per term; 60 days: none


def _grid(walls: dict[int, int] = WALL) -> dict[tuple[int, int], Any]:
    return {(t, p): scan_mod.Cell(t in walls and p >= walls[t], t in walls and p >= walls[t], t <= 55)
            for t in TERMS for p in PRICES}


def _facts(zone_55: int | None = 25, terms_with_price: int = 55) -> EnvelopeFacts:
    zone = tuple(ZoneRow(t, WALL.get(t) if t != 55 else zone_55, True, None, None, _probe(Setting(t))) for t in TERMS)
    maxima = (Maximum("a", "terms_alone", "days", 45, True, False, None, None, None),
              Maximum("b", "terms_budget_ignored", "days", 55, True, False, None, None, None),
              Maximum("c", "terms_with_price", "days", terms_with_price, True, False, None, None, None))
    return EnvelopeFacts("BUYER-1", "Foshan", 0, 1, False, None, 45, 42_000_000, True, maxima, zone, (), {}, None, None, False,
                         0, 0.0)


def _scan(grid: dict[tuple[int, int], Any], **kw: Any) -> Any:
    return scan_mod.Scan("BUYER-1", 45, TERMS, PRICES, grid, **kw)


def test_the_scan_agrees_with_an_envelope_that_read_the_same_books():
    assert scan_mod.disagreements(_facts(), _scan(_grid())) == []


def test_a_zone_price_the_scan_does_not_find_is_a_disagreement():
    out = scan_mod.disagreements(_facts(zone_55=20), _scan(_grid()))
    assert out == ["BUYER-1: zone, smallest approved price at 55 days: online 20, exhaustive scan 25"]


def test_a_longest_term_the_scan_does_not_find_is_a_disagreement():
    out = scan_mod.disagreements(_facts(terms_with_price=50), _scan(_grid()))
    assert out == ["BUYER-1: terms with a price rise, longest approved: online 50, exhaustive scan 55"]


def test_a_column_that_passes_fails_and_passes_again_is_not_monotone():
    grid = _grid()
    grid[(50, 20)] = scan_mod.Cell(False, False, True)  # 50 days: passes from 0.10%, fails at 0.20%, passes again
    out = scan_mod.disagreements(_facts(), _scan(grid))
    assert "BUYER-1: not monotone in the price at 50 days: ..PP.PP" in out


def test_a_row_that_fails_and_passes_again_is_not_monotone():
    grid = _grid()
    grid[(60, 30)] = scan_mod.Cell(True, True, False)  # 60 days passes at 0.30% though 55 days... and the zone says none
    out = scan_mod.disagreements(_facts(), _scan(grid))
    assert any(line.startswith("BUYER-1: zone, smallest approved price at 60 days") for line in out)
    assert any("not monotone in the terms" in line for line in out) is False  # 55 passes at 0.30% too: the row is monotone
    grid[(55, 30)] = scan_mod.Cell(False, False, True)
    out = scan_mod.disagreements(_facts(), _scan(grid))
    assert "BUYER-1: not monotone in the terms at a 30 bp price rise: PP.P" in out


def _ask(face: int | None) -> AskFacts:
    early = _probe(Setting(60, price=40, discount=5, face=face)) if face is not None else None
    return AskFacts(60, 45, 42_000_000, None, 45, None, _probe(Setting(60, price=30)), early, True, 27, 1.0)


def test_the_face_column_must_agree_with_the_asks_smallest_face():
    faces = {f: f >= 24_020_000 for f in range(1_000_000, 42_000_001, 1_000_000)}
    checks = {24_020_000: True, 24_010_000: False}
    assert scan_mod.disagreements(_facts(), _scan(_grid(), faces=faces, face_checks=checks), _ask(24_020_000)) == []
    faces[30_000_000] = False  # a face above the boundary that fails: the column is not what the ask assumed
    out = scan_mod.disagreements(_facts(), _scan(_grid(), faces=faces, face_checks=checks), _ask(24_020_000))
    assert out == ["BUYER-1: the face column disagrees with the ask's smallest face 24020000 at [30000000]"]
    out = scan_mod.disagreements(_facts(), _scan(_grid(), faces={}, face_checks={24_020_000: True, 24_010_000: True}),
                                 _ask(24_020_000))
    assert out and "is not a boundary" in out[0]


def test_the_script_fails_loudly_on_a_disagreement(monkeypatch, capsys):
    monkeypatch.setattr(scan_mod, "_books", lambda args: (None, None, "key"))
    monkeypatch.setattr(scan_mod, "run", lambda *a, **k: {"day": 0, "buyers": {"BUYER-1": {"cells": 28}},
                                                         "disagreements": ["BUYER-1: zone at 55 days: online 20, scan 25"]})
    assert scan_mod.main(["--buyer", "BUYER-1"]) == 1
    err = capsys.readouterr().err
    assert "DISAGREEMENT BUYER-1: zone at 55 days" in err and "scan FAILED: 1 disagreement(s)" in err


def test_the_script_exits_zero_when_the_scan_agrees(monkeypatch, capsys):
    monkeypatch.setattr(scan_mod, "_books", lambda args: (None, None, "key"))
    monkeypatch.setattr(scan_mod, "run", lambda *a, **k: {"day": 0, "buyers": {}, "disagreements": []})
    assert scan_mod.main(["--buyer", "BUYER-1"]) == 0
    assert "agree" in capsys.readouterr().out


def test_state_and_mandate_go_together():
    with pytest.raises(SystemExit):
        scan_mod.main(["--state", "x.json"])
