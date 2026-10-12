"""GET /offers/{offer_id}/picture: an offer's cash picture, one line for the offer as asked and one for each reply FLOW has ready.

A presentation read, computed on request and cached per state version. It reads the stored verdict (the obligations it bound and its
counters) and the books, and projects them with the engine's own projector and router; nothing is evaluated, stored, logged or decided,
so it never changes the verdict, the books or the log."""

from __future__ import annotations

import re
import threading
from bisect import bisect_right
from collections import Counter, OrderedDict
from functools import reduce
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.decisions import latest_verdict_for
from app.api.home import _distance, _lowest_ahead, _series
from app.api.presentation import (
    business_action,
    business_text,
    buyer_of_receivable,
    first_breach_ahead,
    fmt_short,
    option_label,
    party_name,
    series_axis,
)
from app.api.presentation import t as say
from app.api.runtime import get_runtime
from app.api.workspace import _months, _posted_discount
from app.books import current_books
from app.domain.models import Actor, LedgerEventKind, Mode, ObligationType, Outcome, RecordCommitment, Tier
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.financial import EngineError, project
from app.funding import plan
from app.mandate import tier_for
from app.operations import lengthens_terms
from app.operations.executor import only_early_pay

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


# ---------------------------------------------------------------- the paths: one entry per line on the chart, with its column's words

_TERM_ROWS = (("payment_terms", "Payment terms", "账期"), ("early_payment", "Early payment", "提前付款"),
              ("rebate_or_price", "Rebate or price", "返利或价格"))


def _terms_in_force(state: Any, buyer: str | None) -> int | None:
    """The payment terms the books write on this buyer's next invoice (the recurring invoice's own terms), or None when unknown."""
    ri = next((x for x in state.recurring_invoices if x.counterparty_id == buyer), None)
    return ri.terms_days if ri is not None else None


def _pct(rate_bp: int | None) -> str:
    return fmt_pct(bp(abs(rate_bp))) if rate_bp is not None else "?"


def _term_rows(state: Any, obligations: list[Any], buyer: str | None, lang: str) -> dict[str, tuple[str, str]]:
    """The three rows of a path from its obligations, each as (what the column says, the same said after "instead of"). A term the
    path does not carry is "None"; payment terms it leaves alone are the terms in force."""
    in_force = _terms_in_force(state, buyer)
    none = say(lang, "None", "无")
    ext = next((o for o in obligations if o.type == ObligationType.TERMS_EXTENSION), None)
    days: int | None = None
    if ext is not None:
        days = ext.target_terms_days if ext.target_terms_days is not None else (
            in_force + ext.days_delta if in_force is not None and ext.days_delta is not None else None)
    elif in_force is not None:
        days = in_force
    if days is not None:
        terms = (say(lang, f"{days} days", f"{days} 天"), say(lang, str(days), f"{days} 天"))
    else:
        unchanged = say(lang, "Unchanged", "不变")
        terms = (unchanged, unchanged)
    early = [o for o in obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    if early:
        parts = []
        for o in early:
            face = o.base.amount_fen
            parts.append(say(lang, f"{_pct(o.rate_bp)} off {fmt_yuan(face)}" if face is not None else f"{_pct(o.rate_bp)} off",
                             f"{fmt_yuan(face)} 减免 {_pct(o.rate_bp)}" if face is not None else f"减免 {_pct(o.rate_bp)}"))
        text = say(lang, ", ", "、").join(parts)
        early_row = (text, text)
    else:
        early_row = (none, say(lang, "none", "无"))
    other = []
    for o in obligations:
        if o.type == ObligationType.CONTINGENT_REBATE:
            what = _pct(o.rate_bp) if o.rate_bp is not None else (fmt_yuan(o.amount_fen) if o.amount_fen is not None else "")
            other.append((say(lang, f"{what} rebate".strip(), f"{what} 返利".strip()),
                          say(lang, f"a {what} rebate" if what else "a rebate", f"{what} 返利".strip())))
        elif o.type == ObligationType.PRICE_ADJUSTMENT:
            rise = (o.rate_bp or 0) >= 0
            what = _pct(o.rate_bp) if o.rate_bp is not None else ""
            word = say(lang, "price rise" if rise else "price cut", "提价" if rise else "降价")
            text = f"{what} {word}".strip() if lang != "zh" else f"{word} {what}".strip()
            other.append((text, say(lang, f"a {text}", text)))
    if other:
        join = say(lang, ", ", "、")
        other_row = (join.join(v for v, _ in other), join.join(i for _, i in other))
    else:
        other_row = (none, say(lang, "none", "无"))
    return {"payment_terms": terms, "early_payment": early_row, "rebate_or_price": other_row}


def _terms_view(rows: dict[str, tuple[str, str]], asked_rows: dict[str, tuple[str, str]] | None, lang: str) -> list[dict[str, Any]]:
    out = []
    for key, en, zh in _TERM_ROWS:
        value, instead = rows[key][0], None
        if asked_rows is not None and value != asked_rows[key][0]:
            instead = say(lang, f"instead of {asked_rows[key][1]}", f"而非 {asked_rows[key][1]}")
        out.append({"key": key, "label": say(lang, en, zh), "value_text": value, "instead_of_text": instead})
    return out


def _next_invoice_day(state: Any, traj: Any, today: int, buyer: str | None) -> int | None:
    """The day the buyer's next not-yet-issued invoice is paid on this path: the first receipt of a recurring invoice of theirs."""
    for d in traj.days:
        if d.day < today:
            continue
        for e in d.events:
            if e.kind == LedgerEventKind.RECEIPT and e.ref and e.ref.startswith("RI:") and buyer_of_receivable(state, e.ref) == buyer:
                return d.day
    return None


def _days_below(series: list[dict[str, Any]], floor: int, breach_day: int) -> int | None:
    """How many days the line stays below the minimum from its first breach until the first day it is back at or above it; None when it
    is not back within the forecast."""
    back = next((p["day"] for p in series if p["day"] > breach_day and p["closing_fen"] >= floor), None)
    return None if back is None else back - breach_day


def _tag(lang: str, kind: str | None) -> tuple[str | None, str | None]:
    return {"over": (say(lang, "Over your limit", "超出您的授权"), "bad"),
            "recommended": (say(lang, "FLOW recommends", "FLOW 推荐"), "info"),
            "approval": (say(lang, "Needs your approval", "需要您批准"), "warn")}.get(kind or "", (None, None))


def _decides(lang: str, sendable: bool, needs_owner: bool, terms_change: bool) -> str:
    if not sendable:
        return say(lang, "Cannot be accepted within your signed limits.", "在您已签署的授权内无法接受。")
    if needs_owner and terms_change:
        return say(lang, "It changes your terms, so you approve it first.", "它会改变您的条款，需要您先批准。")
    if needs_owner:
        return say(lang, "It is above what FLOW may agree alone, so you approve it first.", "它超出 FLOW 可自行同意的范围，需要您先批准。")
    return say(lang, "FLOW can send it. Your approval is not needed.", "FLOW 可以发送。无需您批准。")


def _cost_note_reply(c: Any, months: int, lang: str) -> str:
    cost, forward = c.supplier_cost_fen, c.forward_value_fen
    if cost > 0 and forward <= 0:
        return say(lang, "once; nothing ongoing", "一次性；之后无持续成本")
    if cost > 0:
        return say(lang, f"once, plus {fmt_yuan(forward)} over {months} months", f"一次性，另加 {months} 个月内 {fmt_yuan(forward)}")
    if forward > 0:
        return say(lang, f"over {months} months", f"{months} 个月内")
    kinds = {o.type for o in c.obligations}
    gain = any(o.type == ObligationType.PRICE_ADJUSTMENT and (o.rate_bp or 0) > 0 for o in c.obligations)
    if gain and ObligationType.TERMS_EXTENSION in kinds:
        return say(lang, "the price rise pays for the longer terms", "提价抵补了延长账期的成本")
    return say(lang, "nothing to pay", "无需付出成本")


def _path_entry(*, key: str, kind: str, label: str, recommended: bool, sendable: bool, needs_owner: bool, tag: str | None,
                cost_display: str, cost_note: str, terms: list[dict[str, Any]], decides: str, reply_text: str | None,
                series: list[dict[str, Any]] | None, low: dict[str, Any], breach_when: str | None, band: str | None,
                lang: str) -> dict[str, Any]:
    tag_text, tag_tone = _tag(lang, tag)
    return {"key": key, "kind": kind, "label": label, "recommended": recommended, "sendable": sendable, "needs_owner": needs_owner,
            "tag_text": tag_text, "tag_tone": tag_tone, "cost_display": cost_display, "cost_note": cost_note, "terms": terms,
            "decides_text": decides, "reply_text": reply_text, "series": series, **low, "first_breach_when": breach_when,
            "band_text": band}


def _paths(rt: Any, offer: Any, verdict: Any, books: Any, mandate: Any, today: int, lang: str, asked: Any, asked_view: dict[str, Any],
           breach: tuple[int, int] | None, replies: list[dict[str, Any]], trajs: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per line on the chart: the offer as asked, then each reply in the verdict's order, with every word its column says.
    Each figure and word is the verdict's, the workspace's or the executor's own (see the comment on each)."""
    state, floor, buyer = books.state, mandate.min_cash_fen, offer.counterparty_id
    months = _months(mandate.forward_concession_horizon_days)
    action = business_action(verdict.outcome.value, len(verdict.counters))
    chosen = verdict.counters[0].id if action == "counter" and verdict.counters else None  # the workspace's priced response
    bound = list(verdict.bound_obligations)
    asked_rows = _term_rows(state, bound, buyer, lang)
    asked_next = _next_invoice_day(state, asked, today, buyer)

    # the offer as asked: the workspace's forward total with the immediate discount (as the projection posted it) beside it
    once = sum(d for o in bound if o.type == ObligationType.IMMEDIATE_DISCOUNT if (d := _posted_discount(asked, o.id)) is not None)
    forward = verdict.forward_concession_total_fen
    if forward > 0:
        cost_fen = forward
        note = (say(lang, f"over {months} months, plus {fmt_yuan(once)} once", f"{months} 个月内，另加一次性 {fmt_yuan(once)}")
                if once else say(lang, f"over {months} months", f"{months} 个月内"))
    elif once:
        cost_fen, note = once, say(lang, "once; nothing ongoing", "一次性；之后无持续成本")
    else:
        cost_fen, note = 0, say(lang, "nothing to pay", "无需付出成本")
    accepts = verdict.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
    asked_needs_owner = accepts and verdict.required_tier != Tier.TIER_1
    asked_recommended = action == "accept"
    tag = "over" if not accepts else "recommended" if asked_recommended else "approval" if asked_needs_owner else None
    band = None
    if breach is not None:
        n = _days_below(asked_view["series"], floor, breach[0])
        band = (say(lang, f"Below your minimum for {n} {'day' if n == 1 else 'days'}", f"低于您的最低现金储备 {n} 天") if n is not None
                else say(lang, "Below your minimum to the end of the forecast", "到预测期结束前一直低于您的最低现金储备"))
    paths = [_path_entry(
        key="asked", kind="asked", label=say(lang, "As they asked", "按对方要求"), recommended=asked_recommended, sendable=accepts,
        needs_owner=asked_needs_owner, tag=tag, cost_display=fmt_yuan(cost_fen), cost_note=note,
        terms=_terms_view(asked_rows, None, lang), decides=_decides(lang, accepts, asked_needs_owner, lengthens_terms(bound)),
        reply_text=None, series=asked_view["series"], low={k: asked_view[k] for k in ("lowest_fen", "lowest_short", "lowest_when")},
        breach_when=asked_view["first_breach_when"], band=band, lang=lang)]

    by_id = {r["counter_id"]: r for r in replies}
    for c in verdict.counters:
        r = by_id[c.id]
        obligations = list(c.obligations)
        # the tier the executor gives the agreement this reply records once the buyer accepts it: Tier 1 only for early payment on a named
        # invoice with nothing else changed and a value within the single-commitment threshold
        op = RecordCommitment(op_id="picture", idempotency_key="picture", mandate_version=mandate.version, requested_by=Actor.AGENT,
                              day=today, commitment_id="picture", nonce="picture")
        terms_change = lengthens_terms(obligations)
        needs_owner = tier_for(op, mandate, state, accepts_terms_change=terms_change, commitment_value_fen=c.forward_value_fen,
                               accepts_beyond_early_pay=not only_early_pay(obligations)) != Tier.TIER_1
        traj = trajs.get(c.id)
        band = None
        if traj is not None:
            nxt = _next_invoice_day(state, traj, today, buyer)
            if asked_next is not None and nxt is not None and nxt < asked_next:
                n = asked_next - nxt
                band = say(lang, f"The next invoice is paid {n} {'day' if n == 1 else 'days'} sooner than as asked",
                           f"下一张发票比按对方要求早 {n} 天收款")
            elif r["lowest_fen"] is not None and r["lowest_fen"] >= floor:
                band = say(lang, "Stays at or above your minimum", "现金始终不低于您的最低现金储备")
        reply_breach = first_breach_ahead(traj, today, floor) if traj is not None else None
        recommended = c.id == chosen
        paths.append(_path_entry(
            key=c.id, kind="reply", label=r["label"], recommended=recommended, sendable=traj is not None, needs_owner=needs_owner,
            tag="recommended" if recommended else ("approval" if needs_owner else None), cost_display=fmt_yuan(c.supplier_cost_fen),
            cost_note=_cost_note_reply(c, months, lang), terms=_terms_view(_term_rows(state, obligations, buyer, lang), asked_rows, lang),
            decides=_decides(lang, traj is not None, needs_owner, terms_change), reply_text=business_text(state, c.text, rt.day, lang),
            series=r["series"], low={k: r[k] for k in ("lowest_fen", "lowest_short", "lowest_when")},
            breach_when=_distance(reply_breach[0], today, lang) if reply_breach else None, band=band, lang=lang))
    return paths


# ---------------------------------------------------------------- the moments: the days where looking is worth it, with every path's cash

_MAX_MOMENTS = 6
_ARRIVALS = ("RECEIPT", "EARLY_RECEIPT", "ADVANCE", "DRAW")  # the events that bring cash in


def _chip(n: int, lang: str) -> str:
    """A day as the chip says it: "Today", "Tomorrow", "In 47 days"."""
    if n == 0:
        return say(lang, "Today", "今天")
    if n == 1:
        return say(lang, "Tomorrow", "明天")
    return say(lang, f"In {n} days", f"{n} 天后")


def _names(lang: str, items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return say(lang, ", ".join(items[:-1]) + " and " + items[-1], "、".join(items))


def _moment_text(lang: str, events: dict[str, list[str]], below: list[str], names: dict[str, str], everyone: bool) -> str:
    """What happens on one day, from the paths' own events: what every path has said once, then what each path adds, then which paths are
    below the minimum."""
    keys = list(events)
    sep = say(lang, "; ", "；")
    common: list[str] = []
    if len(keys) > 1:
        shared = reduce(lambda a, b: a & b, (Counter(events[k]) for k in keys))
        common = list(shared.elements())
        for e in common:
            for k in keys:
                events[k].remove(e)
    parts: list[str] = []
    if common:
        parts.append(say(lang, f"On every path: {sep.join(common)}.", f"每条路径都有：{sep.join(common)}。"))
    for k in keys:
        if events[k]:
            parts.append(say(lang, f"{names[k]}: {sep.join(events[k])}.", f"{names[k]}：{sep.join(events[k])}。"))
    if below:
        if everyone and len(below) > 1:
            parts.append(say(lang, "On every path, cash is below your minimum.", "每条路径的现金都低于您的最低现金储备。"))
        else:
            who = _names(lang, [names[k] for k in below])
            parts.append(say(lang, f"{who}, cash is below your minimum.", f"{who}的现金低于您的最低现金储备。"))
    if not parts:
        return (say(lang, "No cash moves on any path.", "各路径都没有现金变动。") if len(keys) > 1
                else say(lang, "No cash moves.", "当天没有现金变动。"))
    return " ".join(parts)


def _moments(paths: list[dict[str, Any]], today: int, floor: int, horizon_days: int, lang: str) -> list[dict[str, Any]]:
    """At most six days, ascending, where looking is worth it, each with every path's cash that day; exactly one is decisive. A day is
    chosen in this order until six are held: today; the first day any path is below the minimum (or, when none is, the day the paths differ
    most); the asked path's lowest day; the first day after today cash arrives on any path; the recommended reply's lowest day; the first
    day after the asked path's breach on which it is back at or above the minimum; then the days the paths differ most."""
    live = [p for p in paths if p["series"]]
    if not live:
        return []
    last = today + min(90, horizon_days)  # the picture never shows past 90 days
    rows = {p["key"]: {r["day"]: r for r in p["series"] if r["day"] <= last} for p in live}
    days = sorted({d for r in rows.values() for d in r})
    if not days:
        return []
    order = {p["key"]: sorted(rows[p["key"]]) for p in live}

    def closing(key: str, day: int) -> int:
        have = order[key]
        i = bisect_right(have, day) - 1
        return rows[key][have[max(i, 0)]]["closing_fen"]

    def spread(day: int) -> int:
        values = [closing(p["key"], day) for p in live]
        return max(values) - min(values)

    def lowest_day(p: dict[str, Any]) -> int:
        return min(((r["closing_fen"], d) for d, r in rows[p["key"]].items()))[1]

    event_days = sorted({d for r in rows.values() for d, row in r.items() if row["events"]} | {days[0]})
    below_days = [d for d in days if any(closing(p["key"], d) < floor for p in live)]
    asked = next((p for p in live if p["key"] == "asked"), live[0])
    differs = sorted(event_days, key=lambda d: (-spread(d), d))
    decisive = below_days[0] if below_days else (differs[0] if spread(differs[0]) else lowest_day(asked))

    wanted: list[int | None] = [days[0], decisive, lowest_day(asked)]
    wanted.append(next((d for d in event_days if d > today and any(
        e["kind"] in _ARRIVALS and e["amount_fen"] > 0 for p in live for e in rows[p["key"]].get(d, {"events": []})["events"])), None))
    recommended = next((p for p in live if p["recommended"] and p["kind"] == "reply"), None)
    wanted.append(lowest_day(recommended) if recommended is not None else None)
    asked_breach = next((d for d in sorted(rows[asked["key"]]) if rows[asked["key"]][d]["closing_fen"] < floor), None)
    wanted.append(next((d for d in sorted(rows[asked["key"]])
                        if asked_breach is not None and d > asked_breach and rows[asked["key"]][d]["closing_fen"] >= floor), None))
    wanted.extend(differs)
    chosen: list[int] = []
    for d in wanted:
        if d is not None and d not in chosen and len(chosen) < _MAX_MOMENTS:
            chosen.append(d)
    names = {p["key"]: (say(lang, "As asked", "按对方要求") if p["kind"] == "asked" else p["label"]) for p in live}

    out = []
    for d in sorted(chosen):
        values = []
        for p in live:
            c = closing(p["key"], d)
            values.append({"key": p["key"], "closing_fen": c, "closing_display": fmt_yuan(c), "below_floor": c < floor,
                           "note": say(lang, "Below your minimum", "低于您的最低现金储备") if c < floor else None})
        discount = say(lang, "Early-payment discount", "提前付款折扣")  # the row's own label is a whole sentence about one invoice
        events = {p["key"]: [f"{discount if e['kind'] == 'DISCOUNT' else e['label_short']} {e['amount_short']}"
                             for e in rows[p["key"]].get(d, {"events": []})["events"]] for p in live}
        below = [v["key"] for v in values if v["below_floor"]]
        out.append({"day": d, "label": _chip(d - today, lang), "title": _chip(d - today, lang), "decisive": d == decisive,
                    "text": _moment_text(lang, events, below, names, len(below) == len(live)), "values": values})
    return out


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
    try:
        asked = project(books.state, books.with_(verdict.bound_obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    except EngineError:
        # the days the offer named have passed, or its invoice has changed since: there is nothing to draw on today's books
        return {"offer_id": offer_id, "verdict_id": verdict.id, "lang": lang, "day": today, "available": False,
                "unavailable_text": say(lang, "This offer can no longer be drawn on today's books: the days it named have passed or the "
                                              "invoice has changed since.",
                                        "此报价已无法按今天的账目绘制：它所说的日期已过，或发票自那时起已有变动。"),
                "asked": None, "replies": [], "paths": [], "moments": [], "axis": None, "picture_days": None,
                "floor_fen": floor, "floor_short": fmt_short(floor), "horizon_days": mandate.horizon_days}
    breach = first_breach_ahead(asked, today, floor)
    replies = []
    trajs: dict[str, Any] = {}
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
        trajs[c.id] = traj
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
    asked_view = {"label": say(lang, "As asked", "按对方要求"), "series": asked_series,
                  **_lowest(books.state, asked, today, lang),
                  "first_breach_day": breach[0] if breach else None,
                  "first_breach_when": _distance(breach[0], today, lang) if breach else None}
    paths = _paths(rt, offer, verdict, books, mandate, today, lang, asked, asked_view, breach, replies, trajs)
    moments = _moments(paths, today, floor, mandate.horizon_days, lang)
    # the window the picture shows: past the last stop by four days, a month at least, three months at most, never past the horizon
    picture_days = min(max((moments[-1]["day"] - today if moments else 0) + 4, 30), 90, mandate.horizon_days)
    return {
        "offer_id": offer_id, "verdict_id": verdict.id, "lang": lang, "day": today,
        "available": True, "unavailable_text": None,
        "asked": asked_view,
        "replies": replies,
        "paths": paths,
        "moments": moments,
        "picture_days": picture_days,
        "axis": series_axis([asked_series, *(r["series"] for r in replies)], floor, picture_days),
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
