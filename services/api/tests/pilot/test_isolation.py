"""The journal stays out of the engine: no engine module imports it, and loading the engine does not load it
(docs/pilot/JOURNAL_SPEC.md section 1)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
ENGINE = ("financial", "verifier", "funding", "alerts", "operations")
NAMES = re.compile(r"app\.pilot|from app import .*\bpilot\b|\bpilot_journal\b|\bPilotJournal")


@pytest.mark.parametrize("package", ENGINE)
def test_no_engine_module_names_the_journal(package: str) -> None:
    files = sorted((APP / package).rglob("*.py"))
    assert files, package
    offenders = [str(f.relative_to(APP)) for f in files if NAMES.search(f.read_text(encoding="utf-8"))]
    assert offenders == []


def test_loading_the_engine_does_not_load_the_journal() -> None:
    code = (
        "import sys, app.financial, app.verifier, app.funding, app.alerts, app.operations;"
        "sys.exit(1 if any(m == 'app.pilot' or m.startswith('app.pilot.') or m == 'app.api.pilot' for m in sys.modules) else 0)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=APP.parent, capture_output=True, text=True, check=False,
                            # Windows needs SYSTEMROOT to start Winsock (asyncio imports it); nothing else passes through.
                            env={"PYTHONPATH": str(APP.parent), "TERMSLEDGER_NO_DOTENV": "1", "PATH": "/usr/bin:/bin",
                                 **({"SYSTEMROOT": os.environ["SYSTEMROOT"]} if "SYSTEMROOT" in os.environ else {})})
    assert result.returncode == 0, result.stderr
