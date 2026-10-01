"""The scenario runner in --inproc mode passes every scripted task and writes verifiable evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCENARIOS = ROOT / "services" / "api" / "evals" / "e2e" / "scenarios.yaml"


def test_scenarios_cover_the_required_tasks():
    scn = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    assert len(scn) >= 20
    tags = {t for s in scn for t in s.get("tags", [])}
    for need in ("scene1", "scene2", "security", "EX12", "fallback", "clarification", "correction", "out_of_scope",
                 "repay", "tier2", "replay", "extraction", "zh", "injection", "tier3"):
        assert need in tags, need
    from app.domain.fixtures import load_offers

    covered = {t for s in scn for t in s.get("tags", [])}
    for fx in load_offers():
        short = fx.split("_")[0] if not fx.startswith("SEC_") else fx
        assert short in covered or fx in covered, fx


def test_runner_inproc_passes_everything(tmp_path):
    out = tmp_path / "e2e"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_scenarios.py"), "--inproc", "--out", str(out)],
                          capture_output=True, text=True, timeout=900, cwd=ROOT, check=False)
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-4000:]
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["summary"]["failed"] == 0 and results["summary"]["pass_rate"] == 1.0
    assert (out / "summary.md").exists() and (out / "evidence.jsonl").stat().st_size > 0
    verify = ROOT / "scripts" / "verify_evidence.py"
    for f in sorted((out / "evidence").glob("*.jsonl")):
        v = subprocess.run([sys.executable, str(verify), str(f)], capture_output=True, text=True, check=False)
        assert v.returncode == 0, (f.name, v.stdout)
