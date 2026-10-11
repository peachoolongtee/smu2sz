"""The decision record stays out of the engine: no engine module imports it, loading the engine does not load it, and the
record itself reads only `app.domain` and `app.persistence.records` (ADR-0011: it computes no money and grants no authority)."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
ENGINE = ("financial", "verifier", "funding", "alerts", "operations", "clock", "books")
NAMES = re.compile(r"app\.decisions|from app import .*\bdecisions\b|\bDecisionFact|\bdecision_facts\b")


@pytest.mark.parametrize("package", ENGINE)
def test_no_engine_module_names_the_decision_record(package: str) -> None:
    files = sorted((APP / package).rglob("*.py"))
    assert files, package
    offenders = [str(f.relative_to(APP)) for f in files if NAMES.search(f.read_text(encoding="utf-8"))]
    assert offenders == []


def test_loading_the_engine_does_not_load_the_decision_record() -> None:
    code = (
        "import sys, app.financial, app.verifier, app.funding, app.alerts, app.operations, app.clock, app.books;"
        "sys.exit(1 if any(m == 'app.decisions' or m.startswith('app.decisions.') for m in sys.modules) else 0)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=APP.parent, capture_output=True, text=True, check=False,
                            # Windows needs SYSTEMROOT to start Winsock (asyncio imports it); nothing else passes through.
                            env={"PYTHONPATH": str(APP.parent), "TERMSLEDGER_NO_DOTENV": "1", "PATH": "/usr/bin:/bin",
                                 **({"SYSTEMROOT": os.environ["SYSTEMROOT"]} if "SYSTEMROOT" in os.environ else {})})
    assert result.returncode == 0, result.stderr


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def test_the_record_imports_only_the_domain_and_the_stored_record_types() -> None:
    allowed = re.compile(r"^(app\.domain(\.|$)|app\.persistence\.records$|app\.decisions(\.|$))")
    files = sorted((APP / "decisions").glob("*.py"))
    assert {f.name for f in files} >= {"__init__.py", "facts.py", "identity.py", "state.py"}
    for f in files:
        bad = [m for m in _imports(f) if m.startswith("app.") and not allowed.match(m)]
        assert bad == [], f"{f.name} imports {bad}"


def test_the_record_does_no_io_and_reads_no_clock() -> None:
    banned = re.compile(r"\b(open\(|requests|httpx|sqlalchemy|datetime|time\.time|os\.environ|random)\b")
    for f in sorted((APP / "decisions").glob("*.py")):
        assert banned.search(f.read_text(encoding="utf-8")) is None, f.name
