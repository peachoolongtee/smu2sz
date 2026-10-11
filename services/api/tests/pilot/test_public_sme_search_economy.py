"""The envelope and worth reads on the public-record books in week 1 (day 7), where a committed plan exists and every
figure is priced: the same sentences and figures as before map #58's ticket #78, with fewer verifier and planner runs.
The figures come from the dry pilot's week 1 (docs/pilot/dry-pilot-report-2026-10-09.md section 2); the counts are
deterministic (no wall clock), so this runs under `SKIP_PERF_BENCH=1` too."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from app.api.runtime import Runtime, set_runtime
from app.books import books_from_store
from app.strategy import collections as collections_module
from app.strategy.collections import receivables_worth
from app.strategy.envelope import envelope_answer, envelope_facts

API_DIR = Path(__file__).resolve().parents[2]
SCENARIOS = API_DIR.parents[1] / "fixtures" / "scenarios"
SCRIPT = API_DIR / "scripts" / "pilot_runtime.py"
MANDATE = SCENARIOS / "public_sme.mandate.json"


@pytest.fixture(scope="module")
def week_1(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Runtime]:
    spec = importlib.util.spec_from_file_location("pilot_runtime_search_economy", SCRIPT)
    assert spec and spec.loader
    pilot: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules["pilot_runtime_search_economy"] = pilot
    spec.loader.exec_module(pilot)
    raw = json.loads((SCENARIOS / "public_sme.json").read_text(encoding="utf-8"))
    path = tmp_path_factory.mktemp("public_sme_week_1") / "state.json"
    path.write_text(json.dumps(raw["state"]), encoding="utf-8")
    rt = pilot.build_runtime(path, MANDATE)
    rt.advance_to(7)
    set_runtime(rt)
    yield rt
    set_runtime(None)


def test_the_envelope_of_buyer_a_in_week_1_says_what_it_said_in_fewer_runs(week_1: Runtime) -> None:
    rt = week_1
    facts = envelope_facts(books_from_store(rt.store), rt.store.get_mandate(), store=rt.store, day=rt.day,
                           buyer_id="BUYER-A", zone=True, trusted_owner_key_hex=rt.owner_key_hex,
                           commitments=tuple(rt.store.commitments()))
    a = envelope_answer(facts, "en")
    assert not facts.no_plan and a.refused is None
    assert a.primary == ("You can live with: up to 100-day terms (the most FLOW checks), or early payment at up to 0.10% "
                         "on ¥5,397,202.57; a rebate up to 1.50%.")
    assert a.reason == "No payment-terms step fails inside the range FLOW checks."
    assert a.money == "Without a deal your current funding plan costs ¥5,631.28."
    assert (len(a.packages), len(a.zone)) == (6, 15)
    assert facts.evaluations <= 55, "73 distinct settings were evaluated before the searches were shortened (52 now)"


def test_the_worth_ranking_in_week_1_ranks_the_same_rows_with_fewer_planner_runs(week_1: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    rt = week_1
    calls: list[int] = []
    original = collections_module.early_pay_vs_plan

    def counted(*args: object, **kwargs: object) -> int | None:
        calls.append(1)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(collections_module, "early_pay_vs_plan", counted)
    answer = receivables_worth(books_from_store(rt.store), rt.store.get_mandate(), store=rt.store, day=rt.day,
                               trusted_owner_key_hex=rt.owner_key_hex, commitments=tuple(rt.store.commitments()))
    assert not answer.no_plan
    assert answer.top_action_second == ("Call Other buyers (aggregate) today for the ¥7,500,000.00: it saves you ¥5,631.28 "
                                        "and is the only free action.")
    assert [(r.receivable_id, r.worth_text) for r in answer.rows[:3]] == [
        ("RCV-F1", "Saves ¥5,631.28"), ("RCV-B1", "Saves ¥3,945.21 if collected"), ("RCV-D1", "Saves ¥3,352.46")]
    assert [r.net_saving_fen for r in answer.rows[3:]] == [134_356, 134_356, 106_195, 75_341, 72_352, 67_560]
    assert len(calls) <= 28, "46 early-payment comparisons were run before the rate search started from the bottom"
