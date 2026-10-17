"""Warm the strategy reads' caches for the local demo (DEMO_WARM_STRATEGY=1, which scripts/demo.mjs sets).

The Safe Deal Envelope's first read of a set of books repeats the funding search (about 17 s on the golden books with its terms and
price table, 30 s to 80 s on the busy books), and the busy books' price curve takes 8 s to 30 s: at or past the 20 s after which the
web gives up. Both answers are already cached by the books, the mandate, the day and the commitments (`app.strategy.cache`, one
computation per key while other requests for it wait), so reading them once in the background, right after the books change, makes
the owner's first visit a cache hit.

`warm_strategy_reads()` is called after a demo reset and after setup opens new books; `scripts/demo.mjs` makes the same reads once
when the API is up. It reads the price curve and BUYER-1's envelope with its table (the buyer the demo's offers come from), each only
when its feature is on; a buyer the books do not hold, or any failure, is logged and skipped. Nothing is written: both routes are
read-only. Off unless DEMO_WARM_STRATEGY=1, so the tests and a deployment never start the thread.
"""

from __future__ import annotations

import logging
import os
import threading

from fastapi import HTTPException

from app.config import get_settings

log = logging.getLogger(__name__)
WARM_BUYER = "BUYER-1"


def warming_on() -> bool:
    return os.environ.get("DEMO_WARM_STRATEGY", "").strip() == "1"


def _warm() -> None:
    from app.api.strategy_curve import get_price_curve
    from app.api.strategy_envelope import get_envelope

    features = get_settings().features
    reads = []
    if features.price_curve:
        reads.append(("price curve", lambda: get_price_curve(lang="en")))
    if features.envelope:
        reads.append((f"envelope {WARM_BUYER}", lambda: get_envelope(WARM_BUYER, zone=1, ask=None, lang="en")))
    for name, read in reads:
        try:
            read()
        except HTTPException as exc:  # no such buyer on these books, or the books cannot be projected: nothing to warm
            log.info("strategy warm-up: %s skipped (%s)", name, exc.status_code)
        except Exception:  # a warm-up never fails the reset or the setup that started it
            log.warning("strategy warm-up: %s failed", name, exc_info=True)


def warm_strategy_reads() -> threading.Thread | None:
    """Start the warm-up in a daemon thread (DEMO_WARM_STRATEGY=1 only) and return it; None when off."""
    if not warming_on():
        return None
    thread = threading.Thread(target=_warm, name="strategy-warm", daemon=True)
    thread.start()
    return thread
