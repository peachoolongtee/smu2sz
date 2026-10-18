"""Test-wide setup: never read the developer .env (no real keys or databases in tests)."""
import os

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
# DEMO_MODE is off by default (SEC-07); the suite runs on the demo books and credentials, so it opts in. Tests of the default unset it.
os.environ.setdefault("DEMO_MODE", "1")


import pytest
import structlog


@pytest.fixture(autouse=True)
def _structlog_config_restored():
    """Every test starts and ends on structlog's defaults, the configuration the app runs with (it never configures structlog
    itself). Script entry points a test runs (evals.common.quiet, run_certification in scripts/certify_language_boundary.py,
    judge_eval, run_scenarios) install a WARNING filter for the whole process, sometimes from a module-scoped fixture that runs
    before this one; left in place, a later test's capture_logs() saw no info events (the router's log tests failed after
    tests/certification and passed alone)."""
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()
