"""Shared helpers for the evaluation suites: paths, quiet logging, percentiles, the in-process API."""

from __future__ import annotations

import logging
import os
import statistics
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
FIXTURES = ROOT / "fixtures"
HELDOUT = FIXTURES / "heldout"
EVALS = API / "evals"


def heldout_path(path: str | Path | None, filename: str) -> Path:
    """The held-out file to evaluate: `path` may be None (fixtures/heldout), a directory holding
    `filename`, or the file itself. A relative path resolves against the repo root first, then the CWD."""
    if path is None:
        return HELDOUT / filename
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p if (ROOT / p).exists() else p.resolve()
    p = p / filename if p.is_dir() else p
    if not p.is_file():
        raise FileNotFoundError(f"held-out file not found: {p}")
    return p

OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "demo-owner-token")
AGENT_KEY = os.environ.get("AGENT_KEY", "demo-agent-key")


def quiet() -> None:
    """Silence the app's structured logs (they go to stdout and would bury the report)."""
    import structlog

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))


def pct(xs: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100); 0.0 on an empty list."""
    if not xs:
        return 0.0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(-(-q * len(s) // 100)) - 1))
    return round(s[k], 2)


def median(xs: list[float]) -> float:
    return round(statistics.median(xs), 2) if xs else 0.0


def ratio(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


@contextmanager
def timer() -> Iterator[list[float]]:
    out: list[float] = []
    t0 = time.perf_counter()
    try:
        yield out
    finally:
        out.append((time.perf_counter() - t0) * 1000)


@dataclass
class Metric:
    """One row of the summary table."""

    key: str
    label: str
    value: Any
    display: str
    target: str
    passed: bool | None  # None: informational, no target
    suite: str
    note: str = ""


@dataclass
class Failure:
    suite: str
    id: str
    what: str
    repro: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteResult:
    name: str
    metrics: list[Metric] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0
    error: str | None = None


class InProcApi:
    """The FastAPI app over a fresh in-memory runtime (same wiring as scripts/run_scenarios.py)."""

    def __init__(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.nl import router as nl_router
        from app.api.runtime import Runtime, set_runtime
        from app.config import get_settings
        from app.main import app as main_app
        from app.mandate.fixture import demo_owner_public_key_hex
        from app.persistence import InMemoryLedgerStore

        self.rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
        self.rt.reset()
        set_runtime(self.rt)
        app = main_app
        if not any(getattr(r, "path", None) == "/nl" for r in main_app.routes):
            app = FastAPI()
            app.include_router(main_app.router)
            app.include_router(nl_router)
        self.client = TestClient(app)

    def reset(self) -> None:
        from app.nl import reset_sessions

        self.rt.reset()
        reset_sessions()

    def post(self, path: str, body: dict | None = None, owner: bool = True) -> tuple[int, dict]:
        headers = {"X-Owner-Token": OWNER_TOKEN} if owner else {"X-Agent-Key": AGENT_KEY}
        r = self.client.post(path, json=body or {}, headers=headers)
        ctype = r.headers.get("content-type", "")
        return r.status_code, (r.json() if ctype.startswith("application/json") else {})

    def get(self, path: str) -> Any:
        r = self.client.get(path, headers={"X-Owner-Token": OWNER_TOKEN})
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


def run_suite(name: str, fn: Callable[..., SuiteResult], **kw: Any) -> SuiteResult:
    """Run one suite; an exception becomes a suite error in the report instead of aborting the run."""
    import traceback

    t0 = time.perf_counter()
    try:
        res = fn(**kw)
    except Exception as e:  # noqa: BLE001 - the report must still be written
        res = SuiteResult(name=name, error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}")
    res.seconds = round(time.perf_counter() - t0, 2)
    return res
