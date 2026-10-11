"""GET /offers/{offer_id}/picture: an offer's cash picture, one line for the offer as asked and one for each reply FLOW has ready.

A presentation read, computed on request and cached per state version. It reads the stored verdict (the obligations it bound and its
counters) and the books, and projects them with the engine's own projector and router; nothing is evaluated, stored, logged or decided,
so it never changes the verdict, the books or the log."""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.decisions import latest_verdict_for
from app.api.home import _distance, _lowest_ahead, _series
from app.api.presentation import (
    buyer_of_receivable,
    first_breach_ahead,
    fmt_short,
    option_label,
    party_name,
    series_axis,
)
from app.api.presentation import t as say
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import Mode
from app.financial import EngineError, project
from app.funding import plan

router = APIRouter(tags=["offers"], dependencies=[Depends(require_owner)])

_CACHE_SIZE = 32
_cache: OrderedDict[tuple, dict[str, Any]] = OrderedDict()
_lock = threading.Lock()
_ID = re.compile(r"\s*[(（](?:OFF|RCV|COM|FAC|BUYER|CTR|VER|DOC|APR)-[^)）]*[)）]")
_RECEIVABLE = re.compile(r"(RCV-[\w-]+|RI:[\w:-]+)")


def _business_events(state: Any, points: list[dict[str, Any]], raw_labels: dict[tuple[int, int], str], lang: str) -> None:
    """Event labels the owner can read: an early settlement says whose payment it is, and no id stays in a label."""
    for p in points:
        for i, e in enumerate(p["events"]):
            raw = raw_labels.get((p["day"], i), "")
            if e["kind"] == "EARLY_RECEIPT":
                m = _RECEIVABLE.search(raw)
                who = party_name(state, buyer_of_receivable(state, m.group(1))) if m else ""
                e["label_short"] = say(lang, f"Early payment from {who}" if who else "Early payment",
                                       f"来自{who}的提前付款" if who else "提前付款")
                e["label"] = e["label_short"]
            else:
                e["label"] = _ID.sub("", e["label"])
                e["label_short"] = _ID.sub("", e["label_short"])


def _line(state: Any, traj: Any, today: int, lang: str) -> list[dict[str, Any]]:
    points = _series(state, traj, lang, from_day=today)
    raw = {(d.day, i): ev.label for d in traj.days if d.day >= today for i, ev in enumerate(d.events)}
    _business_events(state, points, raw, lang)
    return points


def _lowest(state: Any, traj: Any, today: int, lang: str) -> dict[str, Any]:
    low, day = _lowest_ahead(traj, today)
    return {"lowest_fen": low, "lowest_short": fmt_short(low), "lowest_when": _distance(day, today, lang)}


def build(rt: Any, offer_id: str, lang: str) -> dict[str, Any]:
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
    verdict = latest_verdict_for(rt, offer_id)
    if verdict is None:
        raise HTTPException(404, {"code": "NO_VERDICT_YET", "offer_id": offer_id,
                                  "message": "evaluate the offer first; there is nothing to draw yet"})
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    held = [c for c in rt.store.commitments() if c.offer_id != offer_id]  # the offer as asked, not as it was later booked
    books = current_books(state, held)
    today = max(rt.day, state.as_of_day)
    floor = mandate.min_cash_fen
    asked = project(books.state, books.with_(verdict.bound_obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    breach = first_breach_ahead(asked, today, floor)
    replies = []
    for c in verdict.counters:
        label = option_label(c.label, lang)
        try:
            with_counter = books.with_(c.obligations)
            funding = plan(books.state, with_counter, mandate)
            actions = list(funding.actions) if funding.admissible else []
            traj = project(books.state, with_counter, actions, Mode.CONSERVATIVE, mandate.horizon_days, floor)
        except EngineError:
            replies.append({"counter_id": c.id, "label": label, "series": None, "lowest_fen": None, "lowest_short": None,
                            "lowest_when": None, "note": say(lang, "Cash cannot be projected for this reply.", "无法为此回复预测现金。")})
            continue
        if actions:
            note = say(lang, "If the buyer accepts, with the funding FLOW would run within your limits.",
                       "若买方接受，并含 FLOW 在您的授权内会办理的融资。")
        elif funding.need_fen == 0:
            note = say(lang, "If the buyer accepts. No funding is needed.", "若买方接受。无需融资。")
        else:
            note = say(lang, "If the buyer accepts. Funding within your limits does not cover the whole gap.",
                       "若买方接受。您授权内的融资无法覆盖全部缺口。")
        replies.append({"counter_id": c.id, "label": label, "series": _line(books.state, traj, today, lang),
                        **_lowest(books.state, traj, today, lang), "note": note})
    asked_series = _line(books.state, asked, today, lang)
    return {
        "offer_id": offer_id, "verdict_id": verdict.id, "lang": lang, "day": today,
        "asked": {"label": say(lang, "As asked", "按对方要求"), "series": asked_series,
                  **_lowest(books.state, asked, today, lang),
                  "first_breach_day": breach[0] if breach else None,
                  "first_breach_when": _distance(breach[0], today, lang) if breach else None},
        "replies": replies,
        "axis": series_axis([asked_series, *(r["series"] for r in replies)], floor),
        "floor_fen": floor, "floor_short": fmt_short(floor), "horizon_days": mandate.horizon_days,
    }


@router.get("/offers/{offer_id}/picture")
def get_picture(offer_id: str, lang: str = "en") -> dict[str, Any]:
    """The cash picture of an offer: `asked` (the offer as it stands, no new funding) and one line per reply. Display only."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        state = rt.store.get_state()
        verdict = latest_verdict_for(rt, offer_id)
        key = (state.state_version, rt.day, offer_id, verdict.id if verdict else None, rt.store.get_mandate().version, lang,
               tuple(c.id + c.status.value for c in rt.store.commitments()))
        with _lock:
            hit = _cache.get(key)
            if hit is not None:
                _cache.move_to_end(key)
                return hit
        out = build(rt, offer_id, lang)
        with _lock:
            _cache[key] = out
            while len(_cache) > _CACHE_SIZE:
                _cache.popitem(last=False)
        return out
