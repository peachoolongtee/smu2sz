"""Two-process harness for the concurrency certification (docs/research/concurrency-certification-2026-10-03.md).

Two long-lived worker PROCESSES (spawned, so each has its own interpreter, executor lock and engine) run
operations against one database. A shared `multiprocessing.Barrier` puts both in flight together:

- `call`: both workers wait at the barrier, then call the executor at once (they then contend for the
  database: `BEGIN IMMEDIATE` on SQLite queues the second behind the first);
- `first-write`: inside the unit of work, after every read, each worker waits at the barrier before its first
  write. Both have read the same books (same state version, same log head) before either writes: the worst
  interleaving, the one a process-local lock cannot prevent. Only an engine whose reads take no write lock
  allows it (SQLite in `deferred` mode, PostgreSQL READ COMMITTED); the store's compare-and-swap must hold.

No sleeps: barriers and events only, every wait bounded by `TIMEOUT`.

Each scenario's committed actions are replayed SERIALLY, in log order, on a fresh in-memory store seeded the
same way. The concurrent books must equal the serial ones exactly: same log entry hashes, same state, same
commitments and approvals. That is "the books equal one serial order", checked byte for byte.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TIMEOUT = 60.0  # seconds; every barrier, event and queue wait is bounded by it
CTX = mp.get_context("spawn")
PG_ENV = "TERMSLEDGER_TEST_DATABASE_URL"
PG_MARKER = "termsledger_concurrency_marker"
DAY = 0

# The store methods that write. A `first-write` rendezvous happens before the first of them in a unit of work.
WRITES = frozenset({
    "put_state", "append_operation", "put_commitment", "mark_nonce_used", "add_approval",
    "add_security_event", "decide_approval", "put_offer", "put_verdict", "put_mandate",
})


@dataclass(frozen=True)
class Engine:
    """One database configuration under test."""

    name: str
    url: str
    sqlite_begin: str  # "immediate" | "deferred" (ignored by PostgreSQL)
    rendezvous: str  # "call" | "first-write"

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")


# ================================================================ store proxies (used inside the workers)


class _Proxy:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class Attempts(_Proxy):
    """Counts the units of work opened: a worker whose compare-and-swap lost opens one more."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.units = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.units += 1
        with self._inner.transaction():
            yield


class Rendezvous(_Proxy):
    """Waits at the shared barrier before the first write of the first unit of work, then never again."""

    def __init__(self, inner: Any, barrier: Any) -> None:
        super().__init__(inner)
        self._barrier = barrier
        self._armed = True

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if name not in WRITES or not callable(attr):
            return attr

        def write(*args: Any, **kwargs: Any) -> Any:
            if self._armed:
                self._armed = False
                self._barrier.wait(TIMEOUT)
            return attr(*args, **kwargs)

        return write


class FailingAppend(_Proxy):
    """The next `append_operation` raises, after the unit has written its state, commitment, nonce and approval."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.fail = True

    def append_operation(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail:
            self.fail = False
            raise ConnectionError("injected: the log append failed after the state write")
        return self._inner.append_operation(*args, **kwargs)


class HangInAppend(_Proxy):
    """Signals `inside` when the unit reaches its log append (everything else written, nothing committed), then
    blocks until the parent kills the process (bounded)."""

    def __init__(self, inner: Any, inside: Any, release: Any) -> None:
        super().__init__(inner)
        self._inside, self._release = inside, release

    def append_operation(self, *args: Any, **kwargs: Any) -> Any:
        self._inside.set()
        self._release.wait(TIMEOUT)
        raise TimeoutError("the parent did not kill this process")


# ================================================================ seeding (parent, and the serial replay)


def open_store(engine: Engine, *, create: bool = False) -> Any:
    from app.persistence import SqlLedgerStore

    return SqlLedgerStore(engine.url, create_tables=create, sqlite_begin=engine.sqlite_begin)


def plain_executor(store: Any, day: int = DAY) -> Any:
    from app.mandate import demo_owner_public_key_hex
    from app.operations import Executor

    return Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=lambda: day)


def runtime_executor(store: Any, day: int = DAY) -> Any:
    """The executor as the API wires it (admission and re-verification hooks)."""
    from app.api.runtime import Runtime
    from app.config import get_settings
    from app.mandate import demo_owner_public_key_hex

    return Runtime(settings=get_settings(), store=store, owner_key_hex=demo_owner_public_key_hex(), day=day).executor


def seed_books(store: Any, *, if_lead_days: int | None = None) -> None:
    """The golden SME books and the owner-signed demo mandate. `if_lead_days` sets FAC-IF's lead time."""
    from app.domain.fixtures import load_scenario
    from app.mandate import load_signed_mandate

    state, _ = load_scenario()
    if if_lead_days is not None:
        state = state.model_copy(update={"facilities": [
            f.model_copy(update={"lead_time_days": if_lead_days}) if f.id == "FAC-IF" else f for f in state.facilities]})
    store.put_state(state)
    store.put_mandate(load_signed_mandate())


# ================================================================ actions


def perform(ex: Any, action: tuple[Any, ...]) -> dict[str, Any]:
    """Run one action and describe its outcome (picklable). An exception is an outcome too."""
    from app.domain.models import Actor

    kind = action[0]
    try:
        if kind == "execute":
            r = ex.execute(action[1])
        elif kind == "revoke":
            r = ex.revoke_commitment(action[1], Actor.OWNER)
        elif kind == "decide":
            r = ex.decide(action[1], action[2], Actor.OWNER)
        else:
            raise ValueError(f"unknown action {kind}")
    except Exception as exc:  # noqa: BLE001  reported to the parent, which asserts on it
        return {"action": action, "error": type(exc).__name__, "message": str(exc)}
    return {"action": action, "status": r.status.value, "seq": r.seq, "message": r.message,
            "codes": [v.code.value for v in r.violations], "approval_id": r.approval_id}


# ================================================================ worker-side tasks


def task_run(*, barrier: Any, engine: Engine, actions: list[tuple[Any, ...]], fail_append: bool = False,
             wiring: str = "plain", rendezvous: bool = True) -> dict[str, Any]:
    store = open_store(engine)
    try:
        s: Any = FailingAppend(store) if fail_append else store
        counted = Attempts(s)
        s = counted
        if rendezvous and engine.rendezvous == "first-write":
            s = Rendezvous(s, barrier)
        ex = (runtime_executor if wiring == "runtime" else plain_executor)(s)
        if rendezvous and engine.rendezvous == "call":
            barrier.wait(TIMEOUT)
        outcomes = [perform(ex, a) for a in actions]
        return {"outcomes": outcomes, "units": counted.units, "pid": os.getpid()}
    finally:
        store.dispose()


def task_put_state_cas(*, barrier: Any, engine: Engine, cash_delta: int) -> dict[str, Any]:
    """Invariant 7 at the store: read the books, meet the other writer, then compare-and-swap a new version."""
    from app.persistence import StateVersionConflict

    store = open_store(engine)
    try:
        read = store.get_state()
        barrier.wait(TIMEOUT)  # both writers have read the same state_version
        new = read.model_copy(update={"cash_fen": read.cash_fen + cash_delta, "state_version": read.state_version + 1})
        try:
            store.put_state(new, expected_version=read.state_version)
        except StateVersionConflict as exc:
            return {"read": read.state_version, "written": False, "error": type(exc).__name__, "pid": os.getpid()}
        return {"read": read.state_version, "written": True, "pid": os.getpid()}
    finally:
        store.dispose()


def task_hydrate_and_decide(*, barrier: Any, engine: Engine, approval_id: str) -> dict[str, Any]:
    """Invariant 6: a fresh process hydrates the runtime from the database (`get_runtime`), then decides."""
    from dataclasses import replace

    from app.api import runtime as rt_mod

    os.environ["DATABASE_URL"] = engine.url
    os.environ["DEMO_MODE"] = "1"
    rt_mod.set_runtime(None)
    rt = rt_mod.get_runtime()
    try:
        hydrated = {"day": rt.day, "pending": [a.id for a in rt.store.approvals("PENDING")]}
    finally:
        rt.store.dispose()  # type: ignore[attr-defined]
        rt_mod.set_runtime(None)
    store = open_store(engine)
    try:
        counted = Attempts(store)
        s: Any = Rendezvous(counted, barrier) if engine.rendezvous == "first-write" else counted
        ex = replace(rt, store=s).executor  # the hydrated runtime's wiring, on this worker's connection
        if engine.rendezvous == "call":
            barrier.wait(TIMEOUT)
        out = perform(ex, ("decide", approval_id, True))
        return {"hydrated": hydrated, "outcomes": [out], "units": counted.units, "pid": os.getpid()}
    finally:
        store.dispose()


def process_queue_then_hang(engine: Engine, accept_op: Any, inside: Any, release: Any, out: Any) -> None:
    """Invariant 6, the process that dies: queue a Tier-2 acceptance (committed), then start the owner's
    decision and hang inside its unit of work, after every write but the log entry, until killed."""
    os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
    store = open_store(engine)
    queued = perform(runtime_executor(store), ("execute", accept_op))
    out.put(queued)
    perform(runtime_executor(HangInAppend(store, inside, release)), ("decide", queued["approval_id"], True))


def _worker_loop(barrier: Any, inbox: Any, outbox: Any) -> None:
    os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
    while True:
        item = inbox.get()
        if item is None:
            return
        name, kwargs = item
        try:
            outbox.put(("ok", globals()[name](barrier=barrier, **kwargs)))
        except BaseException:  # noqa: BLE001  the parent fails the test with this traceback
            outbox.put(("err", traceback.format_exc()))


# ================================================================ parent side


class WorkerPair:
    """Two worker processes sharing one barrier. Reused across tests (spawning is slow on Windows)."""

    def __init__(self) -> None:
        self.barrier = CTX.Barrier(2)
        self.inboxes = [CTX.Queue(), CTX.Queue()]
        self.outboxes = [CTX.Queue(), CTX.Queue()]
        self.procs = [CTX.Process(target=_worker_loop, args=(self.barrier, i, o), daemon=True)
                      for i, o in zip(self.inboxes, self.outboxes, strict=True)]
        for p in self.procs:
            p.start()

    def _collect(self, i: int) -> Any:
        try:
            kind, value = self.outboxes[i].get(timeout=4 * TIMEOUT)
        except queue.Empty as exc:
            raise AssertionError(f"worker {i} did not answer within {4 * TIMEOUT}s") from exc
        if kind == "err":
            raise AssertionError(f"worker {i} failed:\n{value}")
        return value

    def both(self, a: tuple[str, dict[str, Any]], b: tuple[str, dict[str, Any]]) -> tuple[Any, Any]:
        """Run `a` in worker 0 and `b` in worker 1 at the same time."""
        self.barrier.reset()
        self.inboxes[0].put(a)
        self.inboxes[1].put(b)
        return self._collect(0), self._collect(1)

    def one(self, task: tuple[str, dict[str, Any]], worker: int = 0) -> Any:
        self.inboxes[worker].put(task)
        return self._collect(worker)

    def close(self) -> None:
        for q in self.inboxes:
            q.put(None)
        for p in self.procs:
            p.join(TIMEOUT)
            if p.is_alive():
                p.kill()


def run(engine: Engine, actions: list[tuple[Any, ...]], **kw: Any) -> tuple[str, dict[str, Any]]:
    return ("task_run", {"engine": engine, "actions": actions, **kw})


# ---------------------------------------------------------------- PostgreSQL guard


class RefusedDatabase(RuntimeError):
    """The PostgreSQL database named for the tests holds something the tests did not create."""


def claim_postgres(url: str) -> None:
    """Make `url` a clean test database, or refuse. Allowed: an EMPTY database (no tables; the marker table is
    created), or one this suite created before (it holds the marker table). Anything else is never touched."""
    from sqlalchemy import create_engine, inspect, text

    from app.persistence import tables as t

    eng = create_engine(url)
    try:
        with eng.begin() as conn:
            names = set(inspect(conn).get_table_names())
            if names and PG_MARKER not in names:
                raise RefusedDatabase(
                    f"{PG_ENV} names a database that already holds tables ({len(names)}) the concurrency tests did "
                    "not create; refusing to touch it. Point it at an empty database.")
            if not names:
                conn.execute(text(f"CREATE TABLE {PG_MARKER} (created_by TEXT NOT NULL)"))
                conn.execute(text(f"INSERT INTO {PG_MARKER} VALUES ('tests/concurrency')"))
            t.metadata.drop_all(conn)
    finally:
        eng.dispose()


# ---------------------------------------------------------------- serial replay and the accounting


@dataclass
class Journal:
    """Every committed action of a scenario, with the log seq its result landed on."""

    entries: list[tuple[int, tuple[Any, ...]]] = field(default_factory=list)

    def add(self, *outcomes: dict[str, Any]) -> None:
        for o in outcomes:
            if o.get("seq") is not None:
                self.entries.append((int(o["seq"]), o["action"]))

    def in_log_order(self) -> list[tuple[Any, ...]]:
        return [a for _seq, a in sorted(self.entries, key=lambda e: e[0])]


class _Counting(_Proxy):
    """Records, for every log entry the replay appends, whether its unit of work wrote the state."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.wrote_state = False
        self.by_seq: dict[int, bool] = {}

    def put_state(self, state: Any, **kwargs: Any) -> None:
        self.wrote_state = True
        self._inner.put_state(state, **kwargs)

    def append_operation(self, *args: Any, **kwargs: Any) -> Any:
        rec = self._inner.append_operation(*args, **kwargs)
        self.by_seq[rec.seq] = self.wrote_state
        self.wrote_state = False
        return rec


def replay(seed: Callable[[Any], None], journal: Journal, *, wiring: str = "plain") -> _Counting:
    from app.persistence import InMemoryLedgerStore

    store = _Counting(InMemoryLedgerStore())
    seed(store)
    store.by_seq.clear()
    store.wrote_state = False  # the seed's own state is not a logged change
    ex = (runtime_executor if wiring == "runtime" else plain_executor)(store)
    for action in journal.in_log_order():
        perform(ex, action)
    return store


def assert_serial_and_accounted(sql: Any, serial: _Counting, *, seed_states: int) -> None:
    """Invariant 8 and the serial-order proof, after every scenario.

    - the chain verifies and its seqs are 1..n;
    - the concurrent log is byte-identical to the serial replay's (same entry hashes in the same order), and so
      are the state, the commitments and the approvals;
    - every state change is explained by exactly one log entry: the state versions written after seeding are
      consecutive, one per log entry whose unit wrote the state, and each such entry is EXECUTED."""
    from app.operations.log import parse_entry

    ops = sql.operations()
    assert sql.verify_chain() is True
    assert [e.seq for e in ops] == list(range(1, len(ops) + 1))
    replayed = serial.operations()
    assert [e.entry_hash for e in ops] == [e.entry_hash for e in replayed], "the books are not one serial order"
    assert sql.get_state() == serial.get_state()
    assert sorted(sql.commitments(), key=lambda c: c.id) == sorted(serial.commitments(), key=lambda c: c.id)
    assert sql.approvals() == serial.approvals()

    history = sql.state_history()[seed_states - 1:]
    versions = [s.state_version for s in history]
    assert versions == list(range(versions[0], versions[0] + len(versions))), f"state versions {versions}"
    writers = [seq for seq, wrote in serial.by_seq.items() if wrote]
    assert len(history) - 1 == len(writers), "a state change without its log entry (or the reverse)"
    for seq in writers:
        entry = parse_entry(ops[seq - 1])
        assert entry.result.status.value == "EXECUTED" or entry.kind == "ADVANCE_CLOCK", (seq, entry.kind)


def engine_for(name: str, tmp: Path) -> Engine:
    """`sqlite-immediate`: the shipped SQLite configuration (writers queue on `BEGIN IMMEDIATE`).
    `sqlite-deferred`: reads take no lock, so both writers read the same books; only the compare-and-swap holds.
    `postgres`: the URL in TERMSLEDGER_TEST_DATABASE_URL (READ COMMITTED), forced into the same interleaving."""
    if name == "postgres":
        return Engine(name, os.environ[PG_ENV], "immediate", "first-write")
    url = f"sqlite:///{(tmp / 'books.db').as_posix()}"
    if name == "sqlite-immediate":
        return Engine(name, url, "immediate", "call")
    return Engine(name, url, "deferred", "first-write")
