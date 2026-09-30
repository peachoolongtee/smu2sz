"""Test-wide setup: never read the developer .env (no real keys or databases in tests)."""
import os

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
