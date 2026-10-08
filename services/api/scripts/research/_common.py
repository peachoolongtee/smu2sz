"""Shared plumbing of the research spikes (wayfinder map #39, ticket #43). Never imported by the app.

The spikes are read-only: they call the engine (`evaluate`, `plan`, `project`, `alerts`, `value_concessions`) on
copies of the golden books and print what it returns. They refuse to run unless FLOW_RESEARCH_SPIKES=1.
Every money and rate figure is formatted with `fmt_yuan` / `fmt_pct`; a figure is an engine output, or a sum or a
difference of engine outputs, never a new computation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

FLAG = "FLOW_RESEARCH_SPIKES"


def require_flag() -> None:
    """Exit unless the feature flag is set. Called first, before anything of the app is imported."""
    if os.environ.get(FLAG) != "1":
        sys.stderr.write(f"research spike: refusing to run; set {FLAG}=1 to run it (read-only, never part of the app).\n")
        raise SystemExit(2)
    # the spikes run on the in-memory runtime with cached compiler output: nothing is written, nothing is called out
    os.environ.setdefault("DATABASE_URL", "memory")
    os.environ.setdefault("LLM_MODE", "cache")
    os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")


def quiet_logs() -> None:
    """The compiler logs one info line per document on stdout; keep stdout for the spike's own output."""
    import structlog

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))


def yuan_text(fen: int) -> str:
    from app.domain.money import fmt_yuan

    return fmt_yuan(fen)


def pct_text(rate_bp: int, places: int = 2) -> str:
    from app.domain.money import bp, fmt_pct

    return fmt_pct(bp(rate_bp), places)


def money(fen: int) -> dict[str, Any]:
    return {"fen": fen, "display": yuan_text(fen)}


def rate(rate_bp: int) -> dict[str, Any]:
    return {"bp": rate_bp, "display": pct_text(rate_bp)}


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """A plain fixed-width text table (the engine's strings go in as given)."""
    cells = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in cells]
    return "\n".join(out)


def dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)


class Stopwatch:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def seconds(self) -> float:
        return time.perf_counter() - self.start


def seconds_text(s: float) -> str:
    return f"{s:.2f} s"


@dataclass(frozen=True)
class Found:
    """A bisection result. `value` is the extreme value that passes (None: not even the first value passes);
    `confirmed` says the two neighbours past the boundary were also checked and fail (monotone there)."""

    value: int | None
    confirmed: bool


def last_true(values: Sequence[int], ok: Callable[[int], bool]) -> Found:
    """Largest value with ok(value), assuming ok holds up to a boundary and fails after it (binary search)."""
    if not ok(values[0]):
        return Found(None, True)
    lo, hi = 0, len(values) - 1
    if not ok(values[hi]):
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(values[mid]):
                lo = mid
            else:
                hi = mid
    else:
        lo = hi
    beyond = values[lo + 1: lo + 3]
    return Found(values[lo], all(not ok(v) for v in beyond))


def first_true(values: Sequence[int], ok: Callable[[int], bool]) -> Found:
    """Smallest value with ok(value), assuming ok fails up to a boundary and holds after it."""
    if not ok(values[-1]):
        return Found(None, True)
    lo, hi = 0, len(values) - 1
    if ok(values[lo]):
        hi = lo
    else:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(values[mid]):
                hi = mid
            else:
                lo = mid
    before = values[max(0, hi - 2): hi]
    return Found(values[hi], all(not ok(v) for v in before))
