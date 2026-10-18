"""Test-wide setup: never read the developer .env (no real keys or databases in tests)."""
import os

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
# DEMO_MODE is off by default (SEC-07); the suite runs on the demo books and credentials, so it opts in. Tests of the default unset it.
os.environ.setdefault("DEMO_MODE", "1")


import pytest
import structlog


@pytest.fixture(autouse=True)
def _structlog_config_restored():
    """Every test starts and ends on the same structlog configuration. A script entry point a test runs (evals.common.quiet,
    scripts/research) installs a WARNING filter for the whole process; left in place, a later test's capture_logs() saw
    no info events (the router's log tests failed in a gate chunk and passed alone)."""
    saved = structlog.get_config()
    yield
    structlog.configure(**saved)
