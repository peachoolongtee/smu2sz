"""Wave 6 of map #47: the quick backtest (the golden scenario and the differential against the oracle) exits 0 with no
failure. The full run over the 49 e2e scenarios is `scripts/strategy_backtest.py` and its committed report."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "strategy_backtest.py"
# the script sets these in os.environ when it is imported; monkeypatch puts them back afterwards
_ENV = ("TERMSLEDGER_NO_DOTENV", "DATABASE_URL", "LLM_MODE", "PYTHONUTF8", "FEATURE_ENVELOPE", "FEATURE_PRICE_CURVE",
        "FEATURE_COLLECTIONS_WORTH")


@pytest.fixture
def backtest(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    for key in _ENV:
        monkeypatch.setenv(key, "x")  # records the original (or its absence) so the teardown restores it
    spec = importlib.util.spec_from_file_location("strategy_backtest", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "strategy_backtest", mod)
    monkeypatch.setitem(sys.modules, "run_scenarios", ModuleType("run_scenarios"))  # replaced by the script's own load
    spec.loader.exec_module(mod)
    return mod


def test_the_quick_backtest_passes(backtest: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    started = time.perf_counter()
    report = tmp_path / "report.md"
    code = backtest.main(["--quick", "--json", "--out", str(report)])
    elapsed = time.perf_counter() - started
    result = json.loads(capsys.readouterr().out)
    sections = {s["name"]: s for s in result["sections"]}
    assert code == 0 and result["failures_total"] == 0, [f for s in result["sections"] for f in s["failures"]]
    assert sections["collections"]["counts"]["turns"] >= 3 and sections["collections"]["counts"]["rows_checked"] >= 1
    assert sections["curve"]["counts"]["band_end_checks"] >= 2
    day34 = {k: v for k, v in sections["differential"]["counts"]["by_kind"].items() if k.startswith("day 34")}
    assert day34["day 34: effects (saving)"] == 6 and day34["day 34: sweep points (C1 less C0)"] == 120
    assert day34["day 34: ceilings (largest rate)"] == 4 and day34["day 34: net value at the ceiling"] == 3
    assert day34["day 34: curve points"] == 91
    assert len(sections["differential"]["counts"]["expected_differences"]) == 1  # day 0's plan's-need face, not a failure
    assert sections["envelope"]["status"] == "skipped"
    assert report.read_text(encoding="utf-8").startswith("# Strategy backtest")
    assert elapsed < 60
