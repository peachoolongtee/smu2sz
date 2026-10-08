"""The cash price curve route of the strategy MVP (flag `price_curve`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.1).

`GET /cash/price-curve?lang=en|zh`: what ¥10,000 arriving 30 days earlier is worth by arrival day, as bands and one
sentence. Read-only and hypothetical: nothing is written, logged as an operation or stored. Mounted through
`app/api/strategy.py`, which carries the owner check.
"""

from __future__ import annotations

import time
from fractions import Fraction
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from app.api.display import displayed
from app.api.features import require_feature
from app.api.presentation import t, when_text
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.domain.money import fmt_pct
from app.financial import EngineError
from app.funding import NoPermanentSourceError
from app.strategy.cache import CACHE_SIZE, AnswerCache, cache_key
from app.strategy.price_curve import PriceCurve, price_curve, price_sentence

router = APIRouter()

_cache: AnswerCache[PriceCurve] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _cache.clear()


def _cannot_price(exc: Exception, lang: Literal["en", "zh"]) -> HTTPException:
    """The curve's refusals in a sentence: no permanent funding source to measure against, a value above the cost of
    funds (the module's own `RuntimeError`), or an engine error."""
    if isinstance(exc, NoPermanentSourceError):
        return HTTPException(422, t(lang, "FLOW cannot price cash timing: there is no permanent funding source on the books "
                                          "to measure it against.",
                                    "FLOW 无法为资金到账时间估值：账上没有可用来比较的长期资金来源。"))
    if isinstance(exc, EngineError):
        return HTTPException(422, f"cannot project: {exc}")
    return HTTPException(422, t(lang, "FLOW cannot show the cash price curve: on some days the cash would be worth more than "
                                      "it costs to fund two billing periods, so the figures are not trusted.",
                                "FLOW 无法显示资金价格曲线：某些日子里资金的价值高于两个计费周期的融资成本，因此这些数字不可信。"))


@router.get("/cash/price-curve")
def get_price_curve(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    require_feature("price_curve")
    started = time.perf_counter()
    rt = get_runtime()
    with rt.lock:  # read the books, the mandate, the day and the commitments together; the curve is computed outside
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day

    def compute() -> PriceCurve:
        try:
            return price_curve(books, mandate, store=rt.store, day=day)
        except (NoPermanentSourceError, EngineError, RuntimeError) as exc:
            raise _cannot_price(exc, lang) from None

    curve = _cache.get_or_compute(cache_key(books.state, mandate, day, commitments), compute)
    bands = [{**b.model_dump(), "from_when": when_text(b.from_day, day, lang), "to_when": when_text(b.to_day, day, lang),
              "value_pct": fmt_pct(Fraction(b.value_bp, 10_000))} for b in curve.bands]
    return displayed({**curve.model_dump(), "bands": bands, "sentence": price_sentence(curve, today=day, lang=lang),
                      "state_version": curve.source_state_version, "day": day,
                      "computed_in_seconds": round(time.perf_counter() - started, 3)})
