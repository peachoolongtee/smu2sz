"""One answer cache for the strategy routes (docs/STRATEGY_MVP_BRIEF.md section 4).

A thread-safe LRU keyed by a sha256 string, with single-flight: when a key is being computed, a second request for it
waits for the first and takes its answer instead of computing again. A failed computation is not cached; the requests
that were waiting for it get the same error. `cache_key` is the one key builder: the books, the mandate, the day and
the commitments in force, plus whatever else the answer depends on.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence

from app.domain.models import Commitment, FinancialState, Mandate

CACHE_SIZE = 32


def cache_key(state: FinancialState, mandate: Mandate, day: int, commitments: Sequence[Commitment], *extra: object) -> str:
    """The key of an answer that is pure in (state, mandate, day, commitments) and the `extra` parts (a buyer, a
    language, a flag): sha256 over the parts, each length-prefixed so that no two part lists share a digest."""
    h = hashlib.sha256()
    parts = [state.model_dump_json(), mandate.model_dump_json(), str(day), "|".join(c.model_dump_json() for c in commitments),
             *(str(x) for x in extra)]
    for part in parts:
        data = part.encode()
        h.update(str(len(data)).encode() + b":" + data)
    return h.hexdigest()


class _Flight:
    """One computation in progress: the requests for the same key wait on `done` and read the outcome."""

    __slots__ = ("done", "error", "value")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.value: object = None
        self.error: BaseException | None = None


class AnswerCache[T]:
    def __init__(self, size: int = CACHE_SIZE) -> None:
        self.size = size
        self._data: OrderedDict[str, T] = OrderedDict()
        self._flights: dict[str, _Flight] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._data

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def get(self, key: str) -> T | None:
        """The cached answer (and the key becomes the most recent), or None."""
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.size:
                self._data.popitem(last=False)

    def get_or_compute(self, key: str, compute: Callable[[], T]) -> T:
        """The answer for `key`: from the cache, from the request already computing it, or from `compute()` (run on this
        thread, outside any lock of the cache)."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            flight = self._flights.get(key)
            owner = flight is None
            if flight is None:
                flight = self._flights[key] = _Flight()
        if not owner:
            flight.done.wait()
            if flight.error is not None:
                raise flight.error
            value: T = flight.value  # type: ignore[assignment]
            return value
        try:
            result = compute()
        except BaseException as exc:
            flight.error = exc
            self._finish(key, flight, None)
            raise
        flight.value = result
        self._finish(key, flight, result)
        return result

    def _finish(self, key: str, flight: _Flight, result: T | None) -> None:
        with self._lock:
            if flight.error is None:
                self._data[key] = result  # type: ignore[assignment]
                self._data.move_to_end(key)
                while len(self._data) > self.size:
                    self._data.popitem(last=False)
            self._flights.pop(key, None)
        flight.done.set()


__all__ = ["CACHE_SIZE", "AnswerCache", "cache_key"]
