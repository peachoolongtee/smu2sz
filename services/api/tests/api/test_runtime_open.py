"""Opening the books once (`get_runtime`): simultaneous first calls open one runtime and share it; an opening that fails hands its error
to the calls that waited for it and the next call opens again; code inside the opening that asks for the runtime fails at once
instead of waiting for itself. Each test holds the opening until every caller is waiting on it, so the race is not left to timing."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, Self

import pytest

from app.api import runtime

CALLERS = 6


class CountingLock:
    """The opening lock, counting the calls that have reached it: a call reads the openings count before it waits here."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._count = threading.Lock()
        self.arrived = 0

    def __enter__(self) -> Self:
        with self._count:
            self.arrived += 1
        self._lock.acquire()
        return self

    def __exit__(self, *exc: object) -> bool:
        self._lock.release()
        return False


def wait_until(ready: Callable[[], bool], seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while not ready():
        assert time.monotonic() < end, "the callers never all reached the opening"
        time.sleep(0.005)


def together(call: Callable[[], Any], n: int = CALLERS) -> tuple[list[Any], list[BaseException | None]]:
    results: list[Any] = [None] * n
    errors: list[BaseException | None] = [None] * n

    def run(i: int) -> None:
        try:
            results[i] = call()
        except BaseException as e:  # noqa: BLE001 - the test inspects what each caller got
            errors[i] = e

    threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a caller is still waiting: the opening hung"
    return results, errors


@pytest.fixture
def lock(monkeypatch: pytest.MonkeyPatch) -> Iterator[CountingLock]:
    monkeypatch.setenv("DATABASE_URL", "memory")
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("LLM_MODE", "cache")
    counting = CountingLock()
    monkeypatch.setattr(runtime, "_opening", counting)
    monkeypatch.setattr(runtime, "_runtime", None)
    monkeypatch.setattr(runtime, "_failure", None)
    yield counting
    runtime._runtime, runtime._failure = None, None  # not set_runtime: a failed test may have left the opening lock held


def test_simultaneous_first_calls_open_one_runtime_and_share_it(lock: CountingLock, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[int] = []
    real = runtime._open_runtime

    def held_open() -> runtime.Runtime:
        wait_until(lambda: lock.arrived >= CALLERS)  # every caller has found no runtime and is waiting on this opening
        opened.append(1)
        return real()

    monkeypatch.setattr(runtime, "_open_runtime", held_open)
    results, errors = together(runtime.get_runtime)
    assert errors == [None] * CALLERS
    assert len(opened) == 1
    assert {id(r) for r in results} == {id(runtime.get_runtime())}


def test_a_failed_opening_fails_its_waiters_once_and_the_next_call_opens_again(
        lock: CountingLock, monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []
    real = runtime._open_runtime

    def flaky_open() -> runtime.Runtime:
        attempts.append(1)
        if len(attempts) == 1:
            wait_until(lambda: lock.arrived >= CALLERS)
            raise ConnectionError("the database is unreachable")
        return real()

    monkeypatch.setattr(runtime, "_open_runtime", flaky_open)
    results, errors = together(runtime.get_runtime)
    assert len(attempts) == 1, "each waiting caller tried the opening again"
    assert results == [None] * CALLERS
    assert sum(isinstance(e, ConnectionError) for e in errors) == 1  # the caller that opened gets the error itself
    shared = [e for e in errors if not isinstance(e, ConnectionError)]
    assert len(shared) == CALLERS - 1
    assert all(isinstance(e, runtime.StartupError) and isinstance(e.__cause__, ConnectionError) for e in shared)
    assert runtime.get_runtime() is runtime.get_runtime() and len(attempts) == 2


def test_asking_for_the_runtime_while_opening_it_fails_at_once(lock: CountingLock, monkeypatch: pytest.MonkeyPatch) -> None:
    real_confirm = runtime._confirm_demo_documents

    def asks_for_the_runtime(rt: runtime.Runtime, scenario: str) -> None:
        runtime.get_runtime()

    monkeypatch.setattr(runtime, "_confirm_demo_documents", asks_for_the_runtime)
    _, errors = together(runtime.get_runtime, n=1)
    assert isinstance(errors[0], runtime.StartupError) and "while this thread was opening the books" in str(errors[0])
    monkeypatch.setattr(runtime, "_confirm_demo_documents", real_confirm)
    assert runtime.get_runtime() is not None  # nothing was left half open: the next call opens normally


def test_an_injected_runtime_is_used_as_it_is(lock: CountingLock) -> None:
    rt = runtime.Runtime(settings=runtime.get_settings(), store=runtime.InMemoryLedgerStore(), owner_key_hex="0" * 64)
    runtime.set_runtime(rt)
    assert runtime.get_runtime() is rt
    runtime.set_runtime(None)
    assert runtime._runtime is None
