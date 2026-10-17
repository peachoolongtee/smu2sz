"""The strategy warm-up's own process (`python -m app.api.strategy_warm_worker`; started by `app.api.strategy_warm`, never by hand).

It reads one job from stdin: a pickled snapshot of the books (the books, the mandate, the day, the commitments in force, the owner's key)
and the reads to make (the price curve; BUYER-1's envelope sweep and its table), each with the key the route caches it under. It
computes each read with the route's own function (`compute_curve`, `sweep_facts`, `zone_facts`) and writes the pickled results to
stdout: (kind, key, value) for a read that answered, (kind, key, None) for one the route would have refused. Nothing is opened or
written: no store, no database, no network. Running in a process of its own, at a lower priority, the long funding searches never take
the API process's interpreter lock from the owner's reads.

The job comes from the API process that started this one, over a pipe: it is that process's own data, never a request's.
"""

from __future__ import annotations

import logging
import os
import pickle
import sys
from typing import Any

log = logging.getLogger("termsledger.strategy_warm")


def _lower_priority() -> None:
    """Below the API process (POSIX: a nicer process; on Windows the parent starts this one below normal priority)."""
    if hasattr(os, "nice"):
        try:
            os.nice(10)
        except OSError:
            pass


def run(job: dict[str, Any]) -> list[tuple[str, str, Any]]:
    from fastapi import HTTPException

    from app.api.strategy_curve import CommitmentsSnapshot, compute_curve
    from app.api.strategy_envelope import sweep_facts, zone_facts

    books, mandate, day = job["books"], job["mandate"], job["day"]
    commitments, owner_key = tuple(job["commitments"]), job["owner_key_hex"]
    out: list[tuple[str, str, Any]] = []
    for kind, key, buyer_id in job["reads"]:
        try:
            if kind == "curve":
                value: Any = compute_curve(books, mandate, CommitmentsSnapshot(commitments), day)
            elif kind == "envelope":
                value = sweep_facts(books, mandate, day, buyer_id, owner_key, commitments)
            elif kind == "zone":
                value = zone_facts(books, mandate, day, buyer_id, owner_key, commitments)
            else:
                continue
        except HTTPException as exc:  # the route's own refusal: nothing to warm
            log.info("strategy warm-up: %s skipped (%s)", kind, exc.status_code)
            value = None
        except ValueError:  # the table off the levers' grids: the route answers it without caching it
            log.info("strategy warm-up: %s is outside the levers' ranges", kind)
            value = None
        out.append((kind, key, value))
    return out


def main() -> int:
    _lower_priority()
    result_pipe = sys.stdout.buffer
    sys.stdout = sys.stderr  # whatever an import prints goes to the log, never into the results
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    job = pickle.loads(sys.stdin.buffer.read())  # the parent API process's own snapshot, over its own pipe
    results = run(job)
    result_pipe.write(pickle.dumps(results, protocol=pickle.HIGHEST_PROTOCOL))
    result_pipe.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
