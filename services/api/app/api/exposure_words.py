"""The words the Deals queue and the Receivables aside read from the exposure routes (map #88; the connected pages).

Composed from reads that already exist, never a second copy of any of them: the offer picture's own paths (the cash line each path
draws, its lowest point and the authority class the verifier gave it), the exposure block's concentration, the Customer overview's
back link and contribution function, and `net_at_collection`. Read-only context: nothing here changes a verdict, a cap or what FLOW
may do alone.

`limit_word` is null, with `limit_text` null, when the picture gives a path no authority class (a reply it cannot draw or price, e.g. Option
A once the plan has run, or an offer not yet evaluated) and for `do_nothing`, which agrees to nothing. `do_nothing` carries words only: in
the exposure block its entries in `stress.paths`, `capacity` and `band.by_path` are explicit nulls, so a lookup by its key reads null.
`share_after_text` is the buyer's share of what is owed once the path's cash from the buyer's open invoices has arrived (the day the path's own
projection receives the last of them): the concentration function on the books with the invoices received by then settled; an invoice not yet
issued is not owed. Every sentence is written for `lang` through `t(lang, en, zh)` (INVARIANT 13); no id appears in a sentence.

    deal_extras       worked out once with the cached exposure block (`app.strategy.exposure`, `deal_words=True`): `paths[*]` words and
                      `customer_context`
    path_words        per path of an offer: lowest_display, lowest_when, lowest_when_text, limit_word (WITHIN | EXCEEDED | null),
                      limit_text, share_after_text; and the `do_nothing` path the picture does not draw
    customer_back     {label, href} back to the customer's page, built from the query (never echoed unless it names this buyer)
    net_later         what the buyer's open invoices leave the owner a month later than their due days, for the 30-day stress row
"""

from __future__ import annotations

import logging
import re
from fractions import Fraction
from typing import Any
from urllib.parse import quote

from app.api.customer_overview import customer_context
from app.api.home import _lowest_ahead
from app.api.offer_picture import (
    FLOW_MAY,
    NEEDS_OWNER,
    OVER_LIMIT,
    _days_below,
    _next_invoice_day,
    cached_picture,
)
from app.api.presentation import (
    Lang,
    buyer_of_receivable,
    deal_back_label,
    fmt_short,
    party_name,
    t,
    when_text,
)
from app.books import Books
from app.decisions.identity import offer_id_of
from app.domain.models import FinancialState, LedgerEventKind, Mandate, Mode
from app.domain.money import fmt_yuan_about
from app.financial import EngineError, project
from app.strategy.concentration import concentration
from app.strategy.exposure import DO_NOTHING
from app.strategy.inputs import CustomerInputs
from app.strategy.net import net_at_collection
from app.strategy.words import buyer_short, share_text

log = logging.getLogger("termsledger.decisions")

_SAFE = re.compile(r"[A-Za-z0-9_.:\-]{1,80}")
_OPEN = ("OPEN", "FINANCED")


def _days(n: int, lang: Lang) -> str:
    return t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")


# ---------------------------------------------------------------- the words of a path


def _lowest_text(lowest_fen: int, points: list[dict[str, Any]], floor: int, lang: Lang) -> str:
    """Where the path's lowest cash stands against the minimum: "at your minimum", "above your minimum", or "below it for 15 days"
    (the picture's own count of days below, from the first day under it to the first day back at or above it)."""
    if lowest_fen == floor:
        return t(lang, "at your minimum", "恰为您的最低现金")
    if lowest_fen > floor:
        return t(lang, "above your minimum", "高于您的最低现金")
    breach = next((p["day"] for p in points if p["closing_fen"] < floor), None)
    n = _days_below(points, floor, breach) if breach is not None else None
    if n is None:
        return t(lang, "below it to the end of the forecast", "低于最低现金，直到预测期结束")
    return t(lang, f"below it for {_days(n, lang)}", f"低于最低现金 {_days(n, lang)}")


def _early_day(state: FinancialState, traj: Any, today: int, buyer: str) -> int | None:
    """The day the buyer pays an invoice early on this line (the first early receipt of theirs), else None."""
    for d in traj.days:
        if d.day >= today and any(e.kind == LedgerEventKind.EARLY_RECEIPT and buyer_of_receivable(state, e.ref) == buyer for e in d.events):
            return d.day
    return None


def _qualifier(base_next: int | None, nxt: int | None, early: int | None, today: int, lang: Lang) -> str | None:
    """How the path moves the buyer's payment: its next invoice is paid later than on the books as they stand ("for 15 days longer"),
    else it pays early ("paid 2 days after the offer")."""
    if base_next is not None and nxt is not None and nxt > base_next:
        n = nxt - base_next
        return t(lang, f"for {_days(n, lang)} longer", f"多持续 {_days(n, lang)}")
    if early is not None:
        n = early - today
        if n <= 0:
            return t(lang, "paid the day of the offer", "报价当天付款")
        return t(lang, f"paid {_days(n, lang)} after the offer", f"报价后 {_days(n, lang)}付款")
    return None


def _limit(authority: str | None, lang: Lang) -> tuple[str | None, str | None]:
    if authority == OVER_LIMIT:
        return "EXCEEDED", t(lang, "exceeded", "超出授权")
    if authority in (FLOW_MAY, NEEDS_OWNER):
        return "WITHIN", t(lang, "within", "在授权内")
    return None, None


def _received_by(state: FinancialState, traj: Any, today: int) -> dict[str, int]:
    """The day each receivable open today is received on this line (the first receipt or early receipt that names it)."""
    open_ids = {r.id for r in state.receivables if r.status in _OPEN and r.outstanding_fen > 0}
    out: dict[str, int] = {}
    for d in traj.days:
        if d.day >= today:
            for e in d.events:
                if e.kind in (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT) and e.ref in open_ids:
                    out.setdefault(e.ref, d.day)
    return out


def _share_after(books: Books, traj: Any | None, buyer: str, today: int, inputs: CustomerInputs, qualifier: str | None,
                 lang: Lang) -> str | None:
    """The buyer's share of what is owed after the path, with the path's receipt timing. With the path's projection (`traj`) the share is
    the concentration function's on the books as they stand when the path has received the buyer's open invoices (the last such receipt's
    day), with every invoice received by then settled; without one (the books as they stand) it is today's. None for a name that
    stands for many small customers."""
    state = books.state
    day = today
    if traj is not None:
        received = _received_by(state, traj, today)
        mine = [d for rid, d in received.items() if buyer_of_receivable(state, rid) == buyer]
        day = max(mine, default=today)
        settled = [r.model_copy(update={"status": "SETTLED", "settled_fen": r.face_fen}) if received.get(r.id, day + 1) <= day else r
                   for r in state.receivables]
        state = state.model_copy(update={"receivables": settled})
    c = concentration(Books(state, ()), buyer, day, inputs, lang=lang)
    if c.is_aggregate:
        return None
    share = share_text(Fraction(c.ar_buyer_fen, c.ar_total_fen) if c.ar_total_fen > 0 else Fraction(0), lang)
    return share if qualifier is None else f"{share}{t(lang, ', ', '，')}{qualifier}"


_BLANK: dict[str, Any] = {"lowest_display": None, "lowest_when": None, "lowest_when_text": None, "limit_word": None, "limit_text": None,
                          "share_after_text": None}


def path_words(rt: Any, buyer: str, offer_id: str, verdict: Any | None, books: Books, mandate: Mandate, day: int, lang: Lang,
               inputs: CustomerInputs) -> dict[str, dict[str, Any]]:
    """The words of each path of the offer, by path key, plus `do_nothing` (the books as they stand, no reply sent). The lowest cash and
    the authority class are the offer picture's own (`cached_picture`, call under `rt.lock`); the timing is read from the same projection
    of the path's obligations. A path the picture does not draw has blank words. Empty when the books cannot be projected."""
    state, floor = books.state, mandate.min_cash_fen
    today = max(day, state.as_of_day)
    try:
        base = project(state, list(books.obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    except EngineError:
        log.exception("the books could not be projected for the path words")
        return {}
    base_next = _next_invoice_day(state, base, today, buyer)
    base_points = [{"day": d.day, "closing_fen": d.closing_fen} for d in base.days if d.day >= today]
    base_low, base_low_day = _lowest_ahead(base, today)
    out: dict[str, dict[str, Any]] = {DO_NOTHING: {
        "lowest_display": fmt_short(base_low), "lowest_when": when_text(base_low_day, today, lang),
        "lowest_when_text": _lowest_text(base_low, base_points, floor, lang),
        "limit_word": None, "limit_text": None,  # it agrees to nothing: no authority class to state
        "share_after_text": _share_after(books, None, buyer, today, inputs, None, lang)}}
    if verdict is None:  # not evaluated yet: the offer as asked has no package, so it is the books as they stand
        out["asked"] = {**out[DO_NOTHING]}
        return out
    pic = cached_picture(rt, offer_id, lang)
    drawn = {p["key"]: p for p in (pic["paths"] if pic.get("available") else [])}
    packages = {"asked": list(verdict.bound_obligations), **{c.id: list(c.obligations) for c in verdict.counters}}
    for key, obligations in packages.items():
        p = drawn.get(key)
        words = dict(_BLANK)
        if p is not None and p.get("series") and p.get("lowest_fen") is not None:
            words.update(lowest_display=p["lowest_short"], lowest_when=p["lowest_when"],
                         lowest_when_text=_lowest_text(p["lowest_fen"], p["series"], floor, lang))
        words["limit_word"], words["limit_text"] = _limit(p["authority"] if p is not None else None, lang)
        try:
            traj = project(state, books.with_(obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
            q = _qualifier(base_next, _next_invoice_day(state, traj, today, buyer), _early_day(state, traj, today, buyer), today, lang)
            words["share_after_text"] = _share_after(books, traj, buyer, today, inputs, q, lang)
        except EngineError:
            words["share_after_text"] = None
        out[key] = words
    return out


def deal_extras(rt: Any, books: Books, mandate: Mandate, day: int, buyer_id: str, offer_id: str, verdict: Any | None, lang: Lang,
                inputs: CustomerInputs, base: dict[str, Any]) -> dict[str, Any]:
    """What the exposure assembly adds to its cached block for a deal (`deal_words=True`), from the books, picture and concentration it
    already holds: the block's `paths` with their words and the `do_nothing` path, and `customer_context`. `do_nothing` has no figures in
    `stress`, so its entry in `stress.paths` (and in every `stress.also` set) is an explicit null."""
    today = max(day, books.state.as_of_day)
    with rt.lock:  # the picture and the projections read together
        words = path_words(rt, buyer_id, offer_id, verdict, books, mandate, day, lang, inputs)
    stress = base["stress"]
    stress["paths"][DO_NOTHING] = None
    for extra in stress["also"]:
        extra["paths"][DO_NOTHING] = None
    return {"paths": with_path_words(base["paths"], words, lang),
            "customer_context": customer_context(books.state, inputs, buyer_id, today, base["concentration"], lang)}


def do_nothing_entry(lang: Lang) -> dict[str, Any]:
    return {"key": DO_NOTHING, "kind": DO_NOTHING, "label": t(lang, "Do nothing", "不采取行动")}


def with_path_words(paths: list[dict[str, Any]], words: dict[str, dict[str, Any]], lang: Lang) -> list[dict[str, Any]]:
    """The exposure block's paths with their words, and the `do_nothing` path last when the block does not carry one."""
    out = [{**p, **words.get(p["key"], _BLANK)} for p in paths]
    if not any(p["key"] == DO_NOTHING for p in out):
        out.append({**do_nothing_entry(lang), **words.get(DO_NOTHING, _BLANK)})
    return out


# ---------------------------------------------------------------- the back link (built from the query, never cached)


def query_buyer(state: FinancialState, customer: str | None, invoice: str | None) -> str | None:
    """The buyer a query names: `customer` when it is a buyer on the books, else the buyer the `invoice` belongs to."""
    buyer_ids = {c.id for c in state.counterparties if c.role == "BUYER"}
    owner_of = next((x.counterparty_id for x in state.receivables if x.id == invoice), None) if invoice else None
    return customer if customer in buyer_ids else owner_of if owner_of in buyer_ids else None


def _deal_of(rt: Any, buyer: str, decision: str | None) -> bool:
    """The query's `decision` is a plain key of a deal this buyer is the counterparty of (anything else is ignored, never echoed)."""
    offer_id = offer_id_of(decision) if decision and _SAFE.fullmatch(decision) else None
    offer = rt.store.get_offer(offer_id) if offer_id else None
    return offer is not None and offer.counterparty_id == buyer


def _invoice_of(state: FinancialState, buyer: str, invoice: str | None) -> bool:
    """The query's `invoice` is one of this buyer's receivables."""
    return bool(invoice) and any(x.id == invoice and x.counterparty_id == buyer for x in state.receivables)


def _customer_link(state: FinancialState, lang: Lang, buyer: str, query: list[str]) -> dict[str, str]:
    """The Customer page's link, "Back to {who}": the one set of words, carrying `query` when it has any."""
    who = buyer_short(party_name(state, buyer))
    return {"label": t(lang, f"Back to {who}", f"返回{who}"),
            "href": f"/customers/{quote(buyer, safe='')}" + (f"?{'&'.join(query)}" if query else "")}


def customer_back(rt: Any, state: FinancialState, lang: Lang, *, customer: str | None, invoice: str | None, decision: str | None,
                  path: str | None) -> dict[str, str] | None:
    """Where a Deals page opened from the customer's page goes back to: that page, carrying the deal (and the path) and the invoice the
    query named when they are this buyer's, so the customer page can find its own way back. The customer is the query's, else the
    owner of the invoice it names. None when the query carries neither, or names nothing of a buyer on the books; a part that names
    nothing of this buyer is ignored, never echoed."""
    buyer = query_buyer(state, customer, invoice)
    if buyer is None:
        return None
    query: list[str] = []
    if decision and _deal_of(rt, buyer, decision):
        query.append(f"decision={quote(decision, safe='')}")
        if path and _SAFE.fullmatch(path):
            query.append(f"path={quote(path, safe='')}")
    if invoice and _invoice_of(state, buyer, invoice):
        query.append(f"invoice={quote(invoice, safe='')}")
    return _customer_link(state, lang, buyer, query)


def origin_back(rt: Any, state: FinancialState, lang: Lang, buyer_id: str, *, customer: str | None, invoice: str | None, decision: str | None,
                path: str | None, origin: str | None = None) -> dict[str, str] | None:
    """Where the Cash page opened from a stress link goes back to. `origin` (`from` in the query: deal | invoice | customer) says which page sent
    the owner and decides when it names a target the query supports; without it the query decides: a deal of this buyer's (`decision`, with its
    `path`) back to the deal, else an invoice of this buyer's back to Receivables with it selected, else the customer when the query names this
    buyer back to the Customer page. A part that names another buyer's is ignored, never echoed; None when nothing names this buyer."""
    quoted = quote(buyer_id, safe="")
    targets: dict[str, dict[str, str]] = {}
    if decision and _deal_of(rt, buyer_id, decision):
        tail = f"&path={quote(path, safe='')}" if path and _SAFE.fullmatch(path) else ""
        who = buyer_short(party_name(state, buyer_id))
        targets["deal"] = {"label": deal_back_label(lang, who), "href": f"/deals?decision={quote(decision, safe='')}{tail}&customer={quoted}"}
    if invoice and _invoice_of(state, buyer_id, invoice):
        targets["invoice"] = {"label": t(lang, "Back to the invoice", "返回发票"), "href": f"/receivables?invoice={quote(invoice, safe='')}&customer={quoted}"}
    if customer == buyer_id:
        targets["customer"] = _customer_link(state, lang, buyer_id, [])
    if origin in targets:
        return targets[origin]
    return next((targets[k] for k in ("deal", "invoice", "customer") if k in targets), None)


# ---------------------------------------------------------------- the stress row's net a month later


def net_later(state: FinancialState, buyer_id: str, today: int, delay: int, lang: Lang) -> dict[str, Any] | None:
    """What the buyer's open invoices leave the owner if each is paid `delay` days after the day its net is priced on (its due day, or
    today for one already late): `net_at_collection`, summed. None when the buyer owes nothing."""
    owed = [r for r in state.receivables if r.counterparty_id == buyer_id and r.status in _OPEN and r.outstanding_fen > 0]
    if not owed:
        return None
    total = sum(net_at_collection(state, r, max(today, r.due_day) + delay).net_fen for r in owed)
    when = t(lang, "a month later", "一个月后") if delay == 30 else t(lang, f"{delay} days later", f"{delay} 天后")
    return {"net_later_fen": total,
            "net_later_text": t(lang, f"about {fmt_yuan_about(total)}, {when}", f"约 {fmt_yuan_about(total)}，{when}")}
