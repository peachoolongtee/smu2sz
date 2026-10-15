"""Test-wide setup: never read the developer .env (no real keys or databases in tests)."""
import os

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"


import pytest


@pytest.fixture(autouse=True)
def _seeded_books_forgotten():
    """The app keeps the seeded busy books after the first replay (`app.api.seeded_books`) and restores them on later resets. A test that
    patches the executor, the planner or the seed would otherwise leave books built under its patch for the next test (or read ones
    built without it), so each test starts and ends without a snapshot: its reset replays for real, as before the snapshot existed.

    Coexists with the test-only fast path (`tests/api/busy_snapshot.py`, `fast_busy`, branch perf/busy-tests): this fixture touches only
    `app.api.seeded_books._ready` through `reset_for_tests()`; it never patches `Runtime.reset_demo` and never touches `busy_snapshot._built`,
    so the module-scoped `fast_busy` snapshot and its restores are untouched. A module that wants the app snapshot to live across its tests
    (`tests/api/test_busy_load.py`) overrides this fixture by name."""
    from app.api import seeded_books

    seeded_books.reset_for_tests()
    yield
    seeded_books.reset_for_tests()
