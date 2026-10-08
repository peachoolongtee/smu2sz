"""The collections route of the strategy MVP (flag `collections_worth`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.3).

GET /receivables/worth ranks the open receivables by what collecting each saves, net of the discount that earns it, with
the action for each. Read-only: every receipt is a hypothetical projection on a copy of the books; nothing is written,
logged as an operation or stored as a verdict.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from app.api.display import displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.financial import EngineError
from app.strategy.collections import WorthAnswer, receivables_worth, saving_text

router = APIRouter()

_CACHE_SIZE = 32
_CACHE: OrderedDict[str, WorthAnswer] = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _key(state_json: str, mandate_json: str, day: int, commitments_json: str, lang: str) -> str:
    return hashlib.sha256("|".join([state_json, mandate_json, str(day), commitments_json, lang]).encode()).hexdigest()


def _payload(answer: WorthAnswer, lang: str) -> dict[str, Any]:
    """The answer as JSON with the server-formatted strings; a saving that is zero or negative reads "no saving" (the raw
    figure stays beside it). The `impact` objects are left out: each effect already carries the figures that matter."""
    body = answer.model_dump(mode="json", exclude={"rows": {"__all__": {"effects": {"__all__": {"impact"}}}}})
    out: dict[str, Any] = displayed(body)
    for row in out["rows"]:
        if row["no_saving"]:
            row["net_saving_display"] = row["net_saving_text"]
        for effect in row["effects"]:
            if effect["no_saving"]:
                effect["saving_display"] = saving_text(effect["saving_fen"], lang)
    return out


@router.get("/receivables/worth")
def get_receivables_worth(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    require_feature("collections_worth")
    rt = get_runtime()
    with rt.lock:
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        day = rt.day
        key = _key(books.state.model_dump_json(), mandate.model_dump_json(), day,
                   "|".join(c.model_dump_json() for c in rt.store.commitments()), lang)
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
            if hit is not None:
                _CACHE.move_to_end(key)
        if hit is None:
            try:
                hit = receivables_worth(books, mandate, store=rt.store, day=day, lang=lang)
            except EngineError as exc:
                raise HTTPException(422, f"cannot project: {exc}") from None
            with _CACHE_LOCK:
                _CACHE[key] = hit
                while len(_CACHE) > _CACHE_SIZE:
                    _CACHE.popitem(last=False)
        state_version = books.state.state_version
    return {"hypothetical": True, "state_version": state_version, "day": day,
            "computed_in_seconds": hit.computed_in_seconds, **_payload(hit, lang)}
