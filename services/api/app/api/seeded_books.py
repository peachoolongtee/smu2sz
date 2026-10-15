"""The demo's seeded books, kept: a scenario with a seed file is replayed once per process, restored from a snapshot afterwards.

Replaying the busy seed (eleven offers submitted and evaluated, each evaluation running the funding planner) takes one to two
minutes, far longer than the web waits for POST /demo/reset. The books it leaves are deterministic, so `Runtime.reset_demo`
keeps what the first replay left and puts a copy of it where a replay would write: every ledger container of the in-memory
store, the runtime fields `reset_demo` sets and the answer caches the replay (and the first reads) filled.

The snapshot is used only when it is provably the same call. Its key holds everything that changes the result: the scenario, the
seed file's content, the whole fixtures tree (offers, contracts, scenario state, mandate), the settings (every feature flag,
cap and key) and the owner key. Any mismatch drops the snapshot and the real replay runs. So does anything that is not the
shipped path: a replaced seed, replay or document step, a store that is not the in-memory one, an open transaction, telemetry
in the store, or a runtime that is not the process runtime.

The SQL store always replays for real: restoring would have to write the operations log and its hash chain through the
store's own API (one append per entry, each hashing the one before) and every other table row by row, which is the replay's
work again less the planner; and a persistent store may hold what a snapshot cannot know about. The in-memory store holds
frozen records in plain containers, so a copy of them is the books.

`warm_up` builds the busy snapshot in a background thread at start-up (DEMO_MODE only), on a private runtime and store that the
routes see through `using_runtime` for that thread alone: the live runtime and its lock are never touched. It then reads the
home and the worklist in both languages once, so the answers they cache are in the snapshot too. A reset that arrives while
it runs waits for it (`lookup`, called before the runtime's lock is taken) instead of replaying twice.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from app.api import demo_seed, documents, runtime
from app.api.runtime import Runtime, get_runtime, using_runtime
from app.config import get_settings
from app.domain.fixtures import FIXTURES
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

log = logging.getLogger(__name__)

TELEMETRY = ("_llm_calls", "_evaluation_runs", "_pilot_journal")  # survive a reset; their ids are counted from them
LEDGER = tuple(n for n in InMemoryLedgerStore._CONTAINERS if n not in TELEMETRY)
RUNTIME_FIELDS = ("day", "scenario", "latest_verdict", "documents", "intake_day", "intake_count")

# The steps a snapshot stands in for, as shipped: a test or a caller that replaces one gets the real call and its own result.
_SHIPPED = (demo_seed.replay, demo_seed.scenario_seed, documents.confirm_demo_documents, runtime._confirm_demo_documents)


@dataclass
class Snapshot:
    key: str
    ledger: dict[str, Any]
    runtime: dict[str, Any]
    caches: dict[str, list[tuple[Any, Any]]]  # cache name -> its entries when the build ended, oldest first


@dataclass
class _Build:
    key: str
    done: threading.Event = field(default_factory=threading.Event)


_guard = threading.Lock()
_ready: dict[str, Snapshot] = {}  # scenario -> its snapshot
_building: dict[str, _Build] = {}  # scenario -> the warm-up now running


def reset_for_tests() -> None:
    """Forget every snapshot (a test that wants the first-call path)."""
    with _guard:
        _ready.clear()


# ---------------------------------------------------------------- the key

_fixtures_memo: tuple[tuple[Any, ...], str] | None = None


def _fixtures_digest() -> str:
    """A hash of every file under fixtures/ (path and bytes), re-read only when a file's size or mtime moved."""
    global _fixtures_memo
    files = sorted(p for p in FIXTURES.rglob("*") if p.is_file())
    stats = tuple((p.as_posix(), (st := p.stat()).st_mtime_ns, st.st_size) for p in files)
    memo = _fixtures_memo
    if memo is not None and memo[0] == stats:
        return memo[1]
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(FIXTURES).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    _fixtures_memo = (stats, h.hexdigest())
    return _fixtures_memo[1]


def key_of(scenario: str, settings: Any, owner_key_hex: str) -> str:
    """What the snapshot of `scenario` depends on besides the code: the seed file's content, the fixtures, the settings and flags (the
    runtime's own and the process's), DEMO_MODE and the owner key."""
    from app.api.auth import demo_mode

    seed = json.dumps(demo_seed.scenario_seed(scenario), sort_keys=True)
    parts = (scenario, hashlib.sha256(seed.encode()).hexdigest(), _fixtures_digest(), repr(settings), repr(get_settings()),
             repr(demo_mode()), owner_key_hex)
    return hashlib.sha256(repr(parts).encode()).hexdigest()


# ---------------------------------------------------------------- the answer caches


def _caches() -> dict[str, Any]:
    """The in-process answer caches (each keyed by a hash of the books it answers for): every module-level `AnswerCache` of the app, and
    the two ordered dicts of the same kind (`offer_picture._cache`, the verifier's comparison cache). By name, so import order is moot."""
    import importlib
    import sys

    from app.api import offer_picture
    from app.strategy.cache import AnswerCache

    evaluate = importlib.import_module("app.verifier.evaluate")  # (`app.verifier.evaluate` as an attribute is the function)
    found: dict[str, Any] = {}
    for name in sorted(sys.modules):
        if name.startswith("app.") and (mod := sys.modules[name]) is not None:
            found.update({f"{name}.{a}": v for a, v in sorted(vars(mod).items()) if isinstance(v, AnswerCache)})
    found["app.api.offer_picture._cache"] = offer_picture._cache
    found["app.verifier.evaluate._COMPARE_CACHE"] = evaluate._COMPARE_CACHE
    return found


def _entries(cache: Any) -> list[tuple[Any, Any]]:
    if hasattr(cache, "_data"):
        with cache._lock:
            return list(cache._data.items())
    return list(cache.items())


def _held() -> dict[str, list[tuple[Any, Any]]]:
    """Every entry of every answer cache, copied. Each answer is keyed by a hash of the books it was made for, so an entry that is not for
    the busy books is simply never asked for; the ones that are (the replay's, the warmed reads') are what a restore needs."""
    return {n: [(k, copy.deepcopy(v)) for k, v in _entries(c)] for n, c in _caches().items()}


# ---------------------------------------------------------------- eligibility, capture, restore


def eligible(rt: Runtime, scenario: str) -> bool:
    """True only when a snapshot would be the very call `reset_demo` makes."""
    store = rt.store
    return (not rt.private and type(store) is InMemoryLedgerStore and store._tx_depth == 0
            and all(not getattr(store, n) for n in TELEMETRY)
            and (demo_seed.replay, demo_seed.scenario_seed, documents.confirm_demo_documents, runtime._confirm_demo_documents) == _SHIPPED
            and demo_seed.scenario_seed(scenario) is not None and get_runtime() is rt)


def _capture(rt: Runtime, key: str) -> Snapshot:
    store: Any = rt.store
    with rt.lock, store._lock:
        return Snapshot(key=key, ledger={n: copy.copy(getattr(store, n)) for n in LEDGER},
                        runtime={n: copy.copy(getattr(rt, n)) for n in RUNTIME_FIELDS}, caches=_held())


def restore(rt: Runtime, snap: Snapshot) -> None:
    """Leave `rt` as `reset_demo` leaves it (call under `rt.lock`). Every container is a copy: nothing the books later do reaches the snapshot
    (the records are frozen)."""
    from app.api.strategy_exposure import clear_cache as clear_exposure_cache
    from app.nl import reset_sessions

    store: Any = rt.store
    with rt.lock, store._lock:
        for n in LEDGER:
            setattr(store, n, copy.copy(snap.ledger[n]))
        for n, v in snap.runtime.items():
            setattr(rt, n, copy.copy(v))
        reset_sessions()
        clear_exposure_cache()  # as `reset` does; the entries the replay left are put back just below
        caches = _caches()
        for n, entries in snap.caches.items():
            cache = caches.get(n)
            for k, v in entries:
                if cache is None:
                    continue
                if hasattr(cache, "put"):
                    cache.put(k, copy.deepcopy(v))
                else:
                    cache[k] = copy.deepcopy(v)
    rt.mark_fresh()


def await_warm_up(scenario: str) -> None:
    """Wait, holding nothing, for the warm-up building `scenario`'s snapshot, if one is running."""
    with _guard:
        build = _building.get(scenario)
    if build is not None:
        build.done.wait()


def lookup(rt: Runtime, scenario: str) -> tuple[Snapshot | None, str | None]:
    """The snapshot to restore for `scenario` on `rt`, or None. Call it BEFORE taking `rt.lock`: a warm-up building the same snapshot is
    waited for here, with nothing held. Also returns the key when there is none and the caller should replay and `remember`."""
    if not eligible(rt, scenario):
        return None, None
    key = key_of(scenario, rt.settings, rt.owner_key_hex)
    with _guard:
        build = _building.get(scenario)
    if build is not None and build.key == key:
        build.done.wait()
    with _guard:
        snap = _ready.get(scenario)
        if snap is not None and snap.key != key:
            del _ready[scenario]  # built under other seed, fixtures, settings or owner key: invalid
            snap = None
    return snap, key


def remember(rt: Runtime, scenario: str, key: str) -> None:
    """Keep what a real replay on `rt` just left (call under `rt.lock`, only after the seed ran without error)."""
    try:
        if eligible(rt, scenario):
            snap = _capture(rt, key)
            with _guard:
                _ready[scenario] = snap
    except Exception:
        log.warning("the seeded %s books could not be kept for later resets", scenario, exc_info=True)


# ---------------------------------------------------------------- the warm-up


def _warm_reads(lang: Literal["en", "zh"]) -> None:
    from app.api.home import read_home
    from app.api.worklist import get_worklist

    for read in (lambda: read_home(lang, None), lambda: get_worklist(lang, None)):
        try:
            read()
        except Exception:
            log.warning("a read of the busy books could not be warmed (%s)", lang, exc_info=True)


def build(scenario: str, key: str, settings: Any, owner_key_hex: str, warm_reads: bool = True) -> Snapshot:
    """Replay `scenario` for real on a private runtime and store (the routes the seed calls see it through `using_runtime`, in this thread
    only), read the home and the worklist in both languages, and keep the result. The live runtime and its lock are not used."""
    builder = Runtime(settings=settings, store=InMemoryLedgerStore(), owner_key_hex=owner_key_hex, private=True)
    with using_runtime(builder):
        builder.reset_demo(scenario)
        if warm_reads:
            _warm_reads("en")
            _warm_reads("zh")
        return _capture(builder, key)


def _run_warm_up(scenario: str, build_: _Build, settings: Any, owner_key_hex: str) -> None:
    try:
        snap = build(scenario, build_.key, settings, owner_key_hex)
        with _guard:
            _ready[scenario] = snap
        log.info("the seeded %s books are ready", scenario)
    except Exception:
        log.warning("the seeded %s books could not be built ahead; the first reset will replay them", scenario, exc_info=True)
    finally:
        with _guard:
            if _building.get(scenario) is build_:
                del _building[scenario]
        build_.done.set()


def warm_up(scenario: str = "busy") -> threading.Thread | None:
    """Start building the `scenario` snapshot in a background thread (DEMO_MODE and the in-memory store only; the SQL store replays).
    Returns at once; the thread never holds the live runtime's lock. None when there is nothing to build."""
    from app.api.auth import demo_mode

    settings = get_settings()
    if not demo_mode() or settings.database_url != "memory" or demo_seed.scenario_seed(scenario) is None:
        return None
    owner_key = demo_owner_public_key_hex()
    key = key_of(scenario, settings, owner_key)
    with _guard:
        if scenario in _building or (scenario in _ready and _ready[scenario].key == key):
            return None
        build_ = _building[scenario] = _Build(key)
    thread = threading.Thread(target=_run_warm_up, args=(scenario, build_, settings, owner_key), daemon=True,
                              name=f"seeded-books-{scenario}")
    thread.start()
    return thread
