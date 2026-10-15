"""A faster `Runtime.reset_demo("busy")` for tests: replay the busy books once per process, restore a snapshot of them afterwards.

Replaying the busy seed (eleven offers submitted and evaluated, each evaluation running the funding planner) takes one to two minutes,
and every test that opened the busy books paid it again. The books it leaves are deterministic, so the first call replays for real, on a
private runtime and store, and keeps what that left: every ledger container of the store, and the runtime fields `reset_demo` sets.
Each later call puts a copy of that snapshot where `reset_demo` would have written its books. Nothing is shared between tests: the store
holds frozen records and the containers are copied on the way in, and the runtime's dicts are deep-copied.

The fast path applies only when it is provably the same call: the scenario is busy, the seed and its replay are the ones the app ships
(not monkeypatched), the settings and the owner key match those the snapshot was built under, the store is the in-memory one outside a
transaction, its telemetry containers are empty (ids are derived from them) and the runtime is the process runtime (the seed's own
requirement). Anything else runs the real `reset_demo`. `tests/api/test_busy_snapshot.py` proves a restored runtime equals a replayed one.

Use: `pytestmark = pytest.mark.usefixtures("fast_busy")` in a module that opens the busy books.
"""

from __future__ import annotations

import copy
import hashlib
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from app.api import demo_seed, offer_picture
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.domain.fixtures import scenario_seed as _shipped_scenario_seed
from app.persistence import InMemoryLedgerStore

# What `InMemoryLedgerStore.reset()` clears and the seed rewrites; the telemetry containers and the pilot journal survive a reset.
LEDGER = ("_ops", "_nonces", "_commitments", "_states", "_mandates", "_offers", "_verdicts", "_security_events", "_approvals",
          "_evidence_exports", "_decision_facts", "_contract_records", "_customer_inputs")
TELEMETRY = ("_llm_calls", "_evaluation_runs", "_pilot_journal")
RUNTIME_FIELDS = ("day", "scenario", "latest_verdict", "documents", "intake_day", "intake_count", "fresh")

_REAL_REPLAY = demo_seed.replay
_REAL_RESET_DEMO = Runtime.reset_demo


@dataclass
class Snapshot:
    ledger: dict[str, Any]
    runtime: dict[str, Any]
    caches: list[dict[Any, Any]]  # what the replay left in each answer cache, in `answer_caches()` order


_built: dict[str, Snapshot] = {}
_building = False


def _key(rt: Runtime) -> str:
    """What the snapshot depends on besides the code: the settings (features, caps, keys) and the owner key."""
    from app.api.auth import demo_mode

    return hashlib.sha256(repr((rt.settings, get_settings(), demo_mode(), rt.owner_key_hex)).encode()).hexdigest()


def eligible(rt: Runtime) -> bool:
    store = rt.store
    return (not _building and type(store) is InMemoryLedgerStore and store._tx_depth == 0
            and all(not getattr(store, n) for n in TELEMETRY)
            and demo_seed.replay is _REAL_REPLAY and demo_seed.scenario_seed is _shipped_scenario_seed
            and get_runtime() is rt)


def answer_caches() -> list[Any]:
    """The in-process answer caches the app keeps (each keyed by a hash of the books it answers for): every `AnswerCache`, and the two
    ordered dicts of the same kind (`offer_picture._cache`, the verifier's comparison cache), in a fixed order."""
    from app.strategy.cache import AnswerCache
    import importlib

    evaluate = importlib.import_module("app.verifier.evaluate")  # (`app.verifier.evaluate` as an attribute is the function)

    found = []
    for name in sorted(sys.modules):
        if name.startswith("app.") and (mod := sys.modules[name]) is not None:
            found += [(f"{name}.{a}", v) for a, v in sorted(vars(mod).items()) if isinstance(v, AnswerCache)]
    found += [("app.api.offer_picture._cache", offer_picture._cache), ("app.verifier.evaluate._COMPARE_CACHE", evaluate._COMPARE_CACHE)]
    return [c for _, c in sorted(found, key=lambda x: x[0])]


def _data(cache: Any) -> Any:
    return cache._data if hasattr(cache, "_data") else cache


def clear_answer_caches() -> None:
    for c in answer_caches():
        _data(c).clear()


def capture(rt: Runtime) -> Snapshot:
    store: Any = rt.store
    return Snapshot(ledger={n: copy.copy(getattr(store, n)) for n in LEDGER},
                    runtime={n: copy.deepcopy(getattr(rt, n)) for n in RUNTIME_FIELDS},
                    caches=[dict(_data(c)) for c in answer_caches()])


def restore(rt: Runtime, snap: Snapshot) -> None:
    """Leave `rt` as `reset_demo("busy")` leaves it (the telemetry containers are empty, see `eligible`)."""
    from app.api.strategy_exposure import clear_cache as clear_exposure_cache
    from app.nl import reset_sessions

    store: Any = rt.store
    with rt.lock, store._lock:
        for n in LEDGER:
            setattr(store, n, copy.copy(snap.ledger[n]))
        for n, v in snap.runtime.items():
            setattr(rt, n, copy.deepcopy(v))
        reset_sessions()
        clear_exposure_cache()
        # The answer caches hold what the replay left in them (the fixtures clear two of them before a test opens the books, and the
        # replay fills them again): each answer is keyed by a hash of the books it was made for, so the same books find the same answers.
        clear_answer_caches()
        for c, held in zip(answer_caches(), snap.caches, strict=True):
            _data(c).update(copy.deepcopy(held))


def _build(like: Runtime) -> Snapshot:
    """Replay the busy seed for real on a private runtime and store, exactly as the `rt` fixtures make one."""
    global _building
    builder = Runtime(settings=like.settings, store=InMemoryLedgerStore(), owner_key_hex=like.owner_key_hex)
    builder.reset()
    previous = get_runtime_or_none()
    clear_answer_caches()  # as a test's fixtures and the reset leave them: the replay fills them
    _building = True
    set_runtime(builder)
    try:
        _REAL_RESET_DEMO(builder, "busy")
        return capture(builder)
    finally:
        _building = False
        set_runtime(previous)


def get_runtime_or_none() -> Runtime | None:
    from app.api import runtime

    return runtime._runtime


def fast_reset_demo(original: Callable[..., None]) -> Callable[..., None]:
    def reset_demo(self: Runtime, scenario: str = "golden_sme") -> None:
        if scenario != "busy" or not eligible(self):
            return original(self, scenario)
        key = _key(self)
        if key not in _built:
            _built[key] = _build(self)
        with self.lock:
            restore(self, _built[key])
    return reset_demo


@pytest.fixture
def fast_busy(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(Runtime, "reset_demo", fast_reset_demo(_REAL_RESET_DEMO))
    yield
