"""Warm the strategy reads' caches for the local demo (DEMO_WARM_STRATEGY=1, which scripts/demo.mjs sets).

The Safe Deal Envelope's first read of a set of books repeats the funding search (about 17 s on the golden books with its terms and
price table, 30 s to 80 s on the busy books), and the busy books' price curve takes 8 s to 30 s: at or past the 20 s after which the
web gives up. Both answers are cached by the books, the mandate, the day and the commitments (`app.strategy.cache`), so computing them
once in the background, right after the books change, makes the owner's first visit a cache hit.

A warm-up never blocks the owner (the 110 s reset stall of 17 Oct):

- it computes in a process of its own (`app.api.strategy_warm_worker`, below normal priority), never in a thread of the API process:
  a funding search in a thread held the interpreter lock for seconds at a time, and every owner read that waited on SQLite or on the
  network had to win it back, so a Home read of a tenth of a second took several seconds while a warm-up ran, and longer behind two;
- it reads the books once, under the runtime lock, for as long as a snapshot takes, and computes on that snapshot with no lock held;
- it holds no entry of the cache while it computes: an owner's read of the same answer computes it at once rather than waiting for the
  warm-up's, and the warm-up's answer, when it comes, is put under the same key the route reads;
- a replacement of the books (`app.api.caches.books_replaced`: a reset, a restore, a swap, setup opening new books) stops the process
  of the old books, and an answer that arrives after a replacement is dropped. Only one warm-up runs at a time.

`warm_strategy_reads()` is called after a demo reset or restore and after setup opens new books; `scripts/demo.mjs` makes the same
reads once when the API is up. It warms the price curve and BUYER-1's envelope with its table (the buyer the demo's offers come
from), each only when its feature is on and its answer is not cached already; a buyer the books do not hold is skipped. Nothing is
written: both reads are read-only. Off unless DEMO_WARM_STRATEGY=1, so the tests and a deployment never start the process.
"""

from __future__ import annotations

import logging
import os
import pickle
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.strategy.cache import AnswerCache

log = logging.getLogger(__name__)
WARM_BUYER = "BUYER-1"
API_ROOT = Path(__file__).resolve().parents[2]  # services/api: where `python -m app.api.strategy_warm_worker` resolves
WORKER = [sys.executable, "-m", "app.api.strategy_warm_worker"]  # tests replace it with a slow stand-in to show a cancel
TIMEOUT_S = 900  # a warm-up still running after this is stopped: the owner's own read computes the answer when it is asked for

_lock = threading.Lock()
_current: subprocess.Popen[bytes] | None = None
_cancels = 0  # how many times the warm-ups were cancelled: a warm-up started before the last cancel keeps nothing


def warming_on() -> bool:
    """The local demo only: DEMO_WARM_STRATEGY=1 and DEMO_MODE on (WARM-1: a deployment that set the flag by mistake starts nothing)."""
    from app.api.auth import demo_mode

    return os.environ.get("DEMO_WARM_STRATEGY", "").strip() == "1" and demo_mode()


# WARM-1: the worker computes from the pickled job alone; it gets the few variables a Python process needs to start, never the API's
# credentials or provider keys.
_WORKER_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL",
               "VIRTUAL_ENV", "PYTHONPATH")


def _worker_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _WORKER_ENV or k.startswith("FEATURE_")}
    return {**env, "TERMSLEDGER_NO_DOTENV": "1", "PYTHONUTF8": "1", "DATABASE_URL": "memory", "LLM_MODE": "cache"}


def _job() -> dict[str, Any] | None:
    """The snapshot to warm (read under the runtime lock, no computation) and the reads it still needs; None when nothing is missing."""
    from app.api import strategy_curve, strategy_envelope
    from app.api.runtime import get_runtime
    from app.books import books_from_store

    features = get_settings().features
    rt = get_runtime()
    with rt.lock:
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day
    reads: list[tuple[str, str, str | None]] = []
    if features.price_curve:
        key = strategy_curve.curve_key(books.state, mandate, day, commitments)
        if key not in strategy_curve._cache:
            reads.append(("curve", key, None))
    if features.envelope:
        if any(c.id == WARM_BUYER for c in books.state.counterparties):
            key = strategy_envelope.envelope_key(books.state, mandate, day, commitments, WARM_BUYER)
            if key not in strategy_envelope._cache:
                reads.append(("envelope", key, WARM_BUYER))
            if key not in strategy_envelope._zone_cache:
                reads.append(("zone", key, WARM_BUYER))
        else:
            log.info("strategy warm-up: envelope %s skipped (no such buyer on these books)", WARM_BUYER)
    if not reads:
        return None
    return {"books": books, "mandate": mandate, "day": day, "commitments": commitments, "owner_key_hex": rt.owner_key_hex, "reads": reads}


def _put(kind: str, key: str, value: Any) -> None:
    from app.api import strategy_curve, strategy_envelope

    caches: dict[str, AnswerCache[Any]] = {"curve": strategy_curve._cache, "envelope": strategy_envelope._cache,
                                           "zone": strategy_envelope._zone_cache}
    caches[kind].put(key, value)


def _start(cancels: int) -> subprocess.Popen[bytes] | None:
    """The worker process, unless a cancel came after this warm-up began (then nothing is started)."""
    global _current
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    env = _worker_env()  # the worker reads no configuration and no database (WARM-1)
    with _lock:
        if cancels != _cancels:
            return None
        if _current is not None and _current.poll() is None:  # one warm-up at a time: the newer books win
            _current.kill()
        _current = subprocess.Popen(WORKER, cwd=API_ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    creationflags=flags)
        return _current


def _run(job: dict[str, Any], cancels: int) -> None:
    global _current
    try:
        proc = _start(cancels)
        if proc is None:
            log.info("strategy warm-up: abandoned before it started (the books were replaced)")
            return
        try:
            out, _ = proc.communicate(pickle.dumps(job, protocol=pickle.HIGHEST_PROTOCOL), timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            log.warning("strategy warm-up: stopped after %s s", TIMEOUT_S)
            return
        finally:
            with _lock:
                if _current is proc:
                    _current = None
        if proc.returncode != 0:
            log.warning("strategy warm-up: the worker stopped with exit code %s", proc.returncode)
            return
        results = pickle.loads(out)  # this process's own worker, over its own pipe (never a request's data)
        with _lock:  # the cancel check and the writes together, so a reset cannot land between them
            if cancels != _cancels:
                log.info("strategy warm-up: abandoned (the books were replaced while it ran)")
                return
            for kind, key, value in results:
                if value is not None:
                    _put(kind, key, value)
    except Exception:  # a warm-up never fails the reset or the setup that started it
        log.warning("strategy warm-up failed", exc_info=True)


def cancel() -> None:
    """The books were replaced (`app.api.caches.books_replaced`): stop the warm-up of the old books and keep nothing it computes."""
    global _cancels, _current
    with _lock:
        _cancels += 1
        if _current is not None and _current.poll() is None:
            _current.kill()
            log.info("strategy warm-up: stopped (the books were replaced)")
        _current = None


def running() -> bool:
    """A warm-up's worker process is computing."""
    with _lock:
        return _current is not None and _current.poll() is None


def warm_strategy_reads() -> threading.Thread | None:
    """Start the warm-up (DEMO_WARM_STRATEGY=1 only) and return the thread that waits for its worker; None when off."""
    if not warming_on():
        return None
    with _lock:
        cancels = _cancels
    try:
        job = _job()
    except Exception:  # the books cannot be read just now: the owner's own read computes the answers
        log.warning("strategy warm-up: the books could not be read", exc_info=True)
        job = None
    thread = threading.Thread(target=_run if job is not None else (lambda *_: None), args=(job, cancels), name="strategy-warm",
                              daemon=True)
    thread.start()
    return thread


__all__ = ["cancel", "running", "warm_strategy_reads", "warming_on"]
