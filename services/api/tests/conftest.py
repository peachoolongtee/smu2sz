"""Test-wide setup: never read the developer .env (no real keys or databases in tests)."""
import os

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
# DEMO_MODE is off by default (SEC-07); the suite runs on the demo books and credentials, so it opts in. Tests of the default unset it.
os.environ.setdefault("DEMO_MODE", "1")
