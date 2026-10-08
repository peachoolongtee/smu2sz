"""The cash price curve route of the strategy MVP (flag `price_curve`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.1).

`GET /cash/price-curve?lang=en|zh`: what ¥10,000 arriving 30 days earlier is worth by arrival day, as bands and one
sentence. Read-only and hypothetical: nothing is written, logged as an operation or stored. Mounted through
`app/api/strategy.py`, which carries the owner check.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from fractions import Fraction
from typing import Any, Literal

from fastapi import APIRouter

from app.api.display import displayed
from app.api.features import require_feature
from app.api.presentation import when_text
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.domain.money import fmt_pct
from app.strategy.price_curve import PriceCurve, price_curve, price_sentence

router = APIRouter()

CACHE_SIZE = 32


class _Lru:
    def __init__(self, size: int) -> None:
        self.size = size
        self.data: OrderedDict[str, PriceCurve] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> PriceCurve | None:
        with self.lock:
            hit = self.data.get(key)
            if hit is not None:
                self.data.move_to_end(key)
            return hit

    def put(self, key: str, value: PriceCurve) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.data.clear()


_cache = _Lru(CACHE_SIZE)


@router.get("/cash/price-curve")
def get_price_curve(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    require_feature("price_curve")
    started = time.perf_counter()
    rt = get_runtime()
    with rt.lock:
        state, mandate, day = rt.store.get_state(), rt.store.get_mandate(), rt.day
        commitments = rt.store.commitments()
        held = "|".join(c.model_dump_json() for c in commitments)
        key = hashlib.sha256(f"{state.model_dump_json()}|{mandate.model_dump_json()}|{day}|{held}".encode()).hexdigest()
        curve = _cache.get(key)
        if curve is None:
            curve = price_curve(books_from_store(rt.store), mandate, store=rt.store, day=day)
            _cache.put(key, curve)
    bands = [{**b.model_dump(), "from_when": when_text(b.from_day, day, lang), "to_when": when_text(b.to_day, day, lang),
              "value_pct": fmt_pct(Fraction(b.value_bp, 10_000))} for b in curve.bands]
    return displayed({**curve.model_dump(), "bands": bands, "sentence": price_sentence(curve, today=day, lang=lang),
                      "state_version": curve.source_state_version, "day": day,
                      "computed_in_seconds": round(time.perf_counter() - started, 3)})
