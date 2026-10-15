"""The words that name a negotiation: its subject (the obligation and its scope), and its lifecycle (Slice B round two, server words batch).

    subject_text       "Foshan · 60-day terms on future invoices", "Foshan · Early settlement on the ¥420k invoice", "Foshan · Early payment, 1.5% off",
                       "Dongguan · 1% rebate next quarter", "Zhuhai · 75-day terms on the next invoice": the buyer, then the first thing it asks
                       (terms, then rebate, then discount, as the Home words the asks) in the obligation's own typed fields, and a count of the
                       rest ("and 2 more terms"). No id and no day number appears in it.
    subject_demo_text  the same with the offer's id appended, for the Demo view only (Business never shows an id, INVARIANT 13).
    lifecycle          one of `LIFECYCLE`; `status_text` is its word. The risk of the offer is the row's `severity`, a separate mark.

Two open negotiations of one customer never share a subject. When two would read alike (two early-payment offers at 1.5%), the buyer's own
words for the ask are appended in quotes; when those are alike too, an ordinal ("1 of 2"). The distinctness is taken over every deal offer on
the books, open or closed, so that a subject does not change when a sibling negotiation closes.

Nothing here is priced, projected or decided: every figure is a field of the obligation or of the books. Written for `lang` through
`t(lang, en, zh)` (INVARIANT 13).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from app.api.presentation import Lang, fmt_short, party_name, t
from app.decisions.state import DealState
from app.domain.models import BaseKind, CommitmentStatus, DurationKind, FinancialState, ObligationType
from app.strategy.words import buyer_short

log = logging.getLogger("termsledger.decisions")

LIFECYCLE = ("counter_ready", "owner_review", "awaiting_buyer", "more_information", "agreed", "declined", "lapsed", "closed")
_WORDS = {
    "counter_ready": ("Counter ready", "还价已就绪"),
    "owner_review": ("Owner review needed", "需要您审核"),
    "awaiting_buyer": ("Awaiting buyer", "等待买方回复"),
    "more_information": ("More information needed", "需要更多信息"),
    "agreed": ("Agreed", "已达成"),
    "declined": ("Declined", "已拒绝"),
    "lapsed": ("Lapsed", "已失效"),
    "closed": ("Closed", "已结束"),  # an agreed deal that is over; the queue's rows carry the tracker's own state word instead
}
_QUOTE_MAX = 48
# the order the Home words the asks in: terms first, then the rebate, then the early-payment discount
_ORDER = {ObligationType.TERMS_EXTENSION: 0, ObligationType.CONTINGENT_REBATE: 1, ObligationType.IMMEDIATE_DISCOUNT: 2}


def lifecycle_text(key: str, lang: Lang) -> str:
    return t(lang, *_WORDS[key])


def deal_lifecycle(ds: Any) -> str:
    """The lifecycle of a negotiation from the decision record's own state (`ds` is a DecisionState of the DEAL family). A reply the verdict
    counters is "counter ready", any other reply the owner's to review; a counter sent and not yet answered is "awaiting buyer"; an offer the
    buyer must clarify needs more information; an agreement in force (or kept, or missed) is agreed; a refused, ended or revoked one is declined;
    an offer the books left behind, or an agreement that ran out, is lapsed."""
    st = ds.state
    if st in (DealState.LAPSED, DealState.EXPIRED):
        return "lapsed"
    if st in (DealState.DECLINED, DealState.NO_DEAL, DealState.FAILED, DealState.REVOKED):
        return "declined"
    if st in (DealState.AGREED, DealState.FULFILLED, DealState.MISSED):
        return "agreed"
    if st == DealState.NEEDS_CLARIFICATION:
        return "more_information"
    if st == DealState.RESPONSE_READY:
        proposed = ds.commitment is not None and ds.commitment.status == CommitmentStatus.PROPOSED
        if ds.sent is not None and (ds.commitment is None or proposed):
            return "awaiting_buyer"
        verdict = ds.verdict
        if verdict is not None and (verdict.outcome.value == "COUNTER" or (verdict.outcome.value == "REJECT" and verdict.counters)):
            return "counter_ready"
    return "owner_review"


# ---------------------------------------------------------------- one ask, in words


def _rate(rate_bp: int | None) -> str | None:
    """A rate as the owner says it: "1.5%", "1%", "0.85%"."""
    if rate_bp is None:
        return None
    whole, frac = divmod(abs(rate_bp), 100)
    text = f"{whole}" if frac == 0 else f"{whole}.{frac:02d}".rstrip("0")
    return f"{'−' if rate_bp < 0 else ''}{text}%"


def _face(state: FinancialState, o: Any) -> int | None:
    """The face of the invoice an obligation names: its own base amount, else the outstanding of the receivable it names."""
    if o.base.amount_fen is not None:
        return int(o.base.amount_fen)
    rid = o.base.receivable_id
    found = next((r for r in state.receivables if r.id == rid), None) if rid else None
    return int(found.outstanding_fen) if found is not None else None


def _scope_en(o: Any) -> str:
    kind = o.base.kind
    if kind == BaseKind.FUTURE_INVOICES:
        n = o.duration.invoices if o.duration.kind == DurationKind.RECURRING_BOUNDED else None
        if n == 1:
            return "on the next invoice"
        return f"on the next {n} invoices" if n else "on future invoices"
    return ""


def _scope_zh(o: Any) -> str:
    if o.base.kind == BaseKind.FUTURE_INVOICES:
        n = o.duration.invoices if o.duration.kind == DurationKind.RECURRING_BOUNDED else None
        if n == 1:
            return "（下一张发票）"
        return f"（接下来 {n} 张发票）" if n else "（今后的发票）"
    return ""


def ask_phrase(state: FinancialState, o: Any, lang: Lang) -> str:
    """One obligation as a short phrase of the obligation and its scope, from its typed fields only."""
    kind = o.type
    rate = _rate(o.rate_bp)
    if kind == ObligationType.TERMS_EXTENSION:
        days = o.target_terms_days
        if lang == "zh":
            what = f"{days} 天账期" if days is not None else (f"账期 {o.days_delta:+d} 天" if o.days_delta is not None else "账期变更")
            return f"{what}{_scope_zh(o)}"
        what = f"{days}-day terms" if days is not None else (f"{o.days_delta:+d} days on payment terms" if o.days_delta is not None
                                                             else "A change of payment terms")
        return f"{what} {_scope_en(o)}".strip()
    if kind == ObligationType.IMMEDIATE_DISCOUNT:
        face = _face(state, o)
        if face is not None:
            return t(lang, f"Early settlement on the {fmt_short(face)} invoice", f"提前结算 {fmt_short(face)} 的发票")
        return t(lang, f"Early payment, {rate} off" if rate else "Early payment", f"提前付款，折扣 {rate}" if rate else "提前付款")
    if kind == ObligationType.CONTINGENT_REBATE:
        what = rate or (fmt_short(o.amount_fen) if o.amount_fen is not None else "")
        if o.base.kind == BaseKind.PERIOD_PURCHASES:
            return t(lang, f"{what} rebate next quarter".strip(), f"下季度 {what} 返利".strip())
        if o.base.kind == BaseKind.FUTURE_INVOICES:
            return t(lang, f"{what} rebate {_scope_en(o)}".strip(), f"{what} 返利{_scope_zh(o)}".strip())
        return t(lang, f"{what} rebate, scope to confirm".strip(), f"{what} 返利（范围待确认）".strip())
    if kind == ObligationType.PRICE_ADJUSTMENT:
        rise = (o.rate_bp or 0) >= 0
        shown = _rate(abs(o.rate_bp)) if o.rate_bp is not None else ""
        if lang == "zh":
            return f"{'提价' if rise else '降价'} {shown}{_scope_zh(o)}".strip()
        return f"{shown} price {'rise' if rise else 'cut'} {_scope_en(o)}".strip()
    if kind == ObligationType.VOLUME_COMMITMENT:
        base = fmt_short(o.base.amount_fen) if o.base.amount_fen is not None else ""
        return t(lang, f"Volume commitment of {base}" if base else "Volume commitment", f"采购量承诺 {base}".strip())
    if kind == ObligationType.OPERATIONAL_CONCESSION:
        return t(lang, "Operational change", "运营方面的调整")
    return t(lang, "Offer", "报价")


def _asks(offer: Any) -> list[Any]:
    """The obligations the buyer asked for (a claimed prior concession is not an ask), terms first."""
    return sorted((o for o in offer.obligations if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION),
                  key=lambda o: (_ORDER.get(o.type, 9), o.id))


def _headline(state: FinancialState, offer: Any, lang: Lang) -> str:
    asks = _asks(offer)
    if not asks:
        return t(lang, "Offer", "报价")
    head = ask_phrase(state, asks[0], lang)
    more = len(asks) - 1
    if more:
        head += t(lang, f" and {more} more {'term' if more == 1 else 'terms'}", f"，另有 {more} 项条款")
    return head


def _quote(offer: Any) -> str | None:
    """The first ask in the buyer's own words (its first source span), shortened at a word; None when it quotes nothing."""
    asks = _asks(offer)
    if not asks or not asks[0].spans:
        return None
    words = " ".join(asks[0].spans[0].text.split())
    if len(words) > _QUOTE_MAX:
        words = words[:_QUOTE_MAX].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return words or None


def subjects_of(state: FinancialState, offers: Iterable[Any], lang: Lang) -> dict[str, tuple[str, str]]:
    """{offer_id: (subject_text, subject_demo_text)} for the offers given: one subject each, distinct among those of one customer."""
    by_customer: dict[str, list[Any]] = defaultdict(list)
    for offer in {o.offer_id: o for o in offers}.values():
        by_customer[offer.counterparty_id].append(offer)
    out: dict[str, tuple[str, str]] = {}
    for cid, group in by_customer.items():
        who = buyer_short(party_name(state, cid)) or cid
        group.sort(key=lambda o: (o.received_day if o.received_day is not None else -1, o.offer_id))
        base = {o.offer_id: _headline(state, o, lang) for o in group}
        seen: dict[str, list[Any]] = defaultdict(list)
        for o in group:
            seen[base[o.offer_id]].append(o)
        for o in group:
            phrase = base[o.offer_id]
            alike = seen[phrase]
            if len(alike) > 1:
                quote = _quote(o)
                quoted = [_quote(x) for x in alike]
                if quote and quoted.count(quote) == 1:
                    phrase = f"{phrase} · “{quote}”"
                else:  # the same words twice, or none: the ordinal among the alike
                    phrase = f"{phrase} · " + t(lang, f"{alike.index(o) + 1} of {len(alike)}", f"第 {alike.index(o) + 1} 份，共 {len(alike)} 份")
            out[o.offer_id] = (f"{who} · {phrase}", f"{who} · {phrase} · {o.offer_id}")
    return out


def negotiation_subjects(ctx: Any, lang: Lang) -> dict[str, tuple[str, str]]:
    """The subjects of every deal offer the decision record holds (call under `rt.lock`), once per request and language."""
    cache: dict[str, dict[str, tuple[str, str]]] = ctx.subject_cache
    if lang not in cache:
        from app.api.deal_offers import (
            _submitted,  # deal_offers reads the decision record, which reads this module
        )

        offers = [ds.offer for ds, _inp in [*ctx.states().values(), *_submitted(ctx)] if ds.family == "DEAL" and ds.offer is not None]
        try:
            cache[lang] = subjects_of(ctx.state, offers, lang)
        except Exception:  # a words read: a subject that cannot be written leaves the row on its coarse words, never a 500
            log.exception("the negotiation subjects could not be written")
            cache[lang] = {}
    return cache[lang]


def subject_for(ctx: Any, offer: Any, lang: Lang) -> tuple[str | None, str | None]:
    """(subject_text, subject_demo_text) of one offer; both None when it has none."""
    found = negotiation_subjects(ctx, lang).get(offer.offer_id) if offer is not None else None
    return found if found is not None else (None, None)
