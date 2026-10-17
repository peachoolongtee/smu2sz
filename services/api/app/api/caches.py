"""The books' generation and the one place that forgets what was read on books that have just been replaced.

A process holds read caches at module level. Some are keyed by the books' contents alone (the state, the mandate, the day, the
commitments in force, and whatever else the answer is pure in): a reset that brings back the same books may reuse them, and that is
what makes the strategy warm-up worth having. Others are keyed by what changes inside one set of books (the log's counts, the session's
inbound documents, the state version) and read more than their key says (the offers, the negotiations, the decision record). Inside one
set of books those keys only move forward; across a reset the counts start again, so a key from the earlier books can come back with a
different meaning (a Deals row for an offer the new books never held, then "Which negotiation?" when it is opened).

`books_replaced()` is called on every replacement of the books (`Runtime.clear_session_caches`: a demo reset or restore, a scenario swap,
Set up your books opening new books, and a new runtime). It moves the generation on, so a key built with `books_generation()` never
matches an answer read on other books (even one that a slow read puts back after the clear), clears the caches of the second kind and
abandons the strategy warm-up of the books that were replaced.

The caches and what keeps each one right across a replacement:

    cleared here and keyed by the generation       worklist, customer overview, offer picture, exposure answers and buyer blocks
    cleared here                                   exposure assembly (with spare capacity and the impact kernel), comparator,
                                                   collections worth, refusal plans (with the picture), NL sessions
    keyed by the books' contents (kept)            Safe Deal Envelope (sweep, zone, ask), price curve, the Home's late-payment test,
                                                   the early-pay faces, the what-if sandbox, borrower-file snapshots (content hash),
                                                   and in the engine the verifier's comparison, the reserve baseline and the log parse
"""

from __future__ import annotations

import itertools
import logging
import threading

log = logging.getLogger(__name__)

_lock = threading.Lock()
_counter = itertools.count(1)
_generation = next(_counter)


def books_generation() -> int:
    """The generation of the books in this process: a part of the key of every cache whose key is not pure in the books' contents."""
    return _generation


def _clear(name: str, fn: object) -> None:
    try:
        fn()  # type: ignore[operator]
    except Exception:  # one cache that cannot be cleared never stops the others
        log.exception("the %s cache could not be cleared after the books were replaced", name)


def books_replaced() -> int:
    """The books were replaced: a new generation, the caches of the second kind cleared, the warm-up of the old books abandoned."""
    global _generation
    with _lock:
        _generation = next(_counter)
        gen = _generation
    from app.api import (
        customer_overview,
        offer_picture,
        strategy_collections,
        strategy_compare,
        strategy_exposure,
        strategy_warm,
        worklist,
    )
    from app.nl import reset_sessions

    _clear("warm-up", strategy_warm.cancel)  # first: a warm-up of the replaced books stops spending the CPU the new books need
    _clear("worklist", worklist.clear_cache)
    _clear("customer overview", customer_overview.clear_cache)
    _clear("offer picture", offer_picture.clear_cache)  # with the refusal plans it shares
    _clear("exposure", strategy_exposure.clear_cache)  # with the assembly, spare capacity and the impact kernel
    _clear("comparator", strategy_compare.clear_cache)
    _clear("collections worth", strategy_collections.clear_cache)
    _clear("NL sessions", reset_sessions)
    return gen


__all__ = ["books_generation", "books_replaced"]
