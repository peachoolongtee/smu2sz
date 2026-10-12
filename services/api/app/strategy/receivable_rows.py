"""The receivable rows with what each invoice nets, who governs it and what to do next (map #88, ticket #107; the owner's rules of
12 Oct, #89). Read-only: every figure is derived from the books, the commitments and the open offers' verdicts handed in, nothing
is stored, sent or booked, and every sentence is written here for `lang` through `t(lang, en, zh)` (INVARIANT 13).

Per receivable still to collect (OPEN or FINANCED with something outstanding), additive to the receivables block of Home:

    net                the net cash at collection on the due day (`app.strategy.net`) with its words
    financing_state    ARRANGED | RECEIVED | REPAID | NONE (never mixed)
    governed_by        {contract_ref, terms_days, rebate_bp, terms_text}: the confirmed contract, the terms on this invoice and the
                       rebate agreed with the buyer
    early_payment      {agreed, text}: the live agreement on THIS invoice, else "none agreed on this invoice"
    pending_counter    {decision_id, text} when an open offer's counter would apply to this invoice, else None
    collection_state   CURRENT | DUE_SOON | OVERDUE | PROMISE_MISSED, by the owner's thresholds
    collection_action  {primary, label, others[]}: VIEW_TERMS | PREPARE_REMINDER | CHASE

The thresholds are the owner's (decided 12 Oct): "due soon" is within 7 days before the due day, "Chase payment" leads from the day
after it falls due with no grace period, and a missed promise counts as overdue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from app.api.presentation import Lang, invoice_words, option_label, party_name, t, when_text
from app.books import Books
from app.decisions.identity import deal_id
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    FinancialState,
    Obligation,
    ObligationType,
    Receivable,
    Verdict,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.strategy.net import NetAtCollection, net_at_collection
from app.strategy.words import net_words, whole_yuan

DUE_SOON_DAYS = 7  # within this many days before the due day
_OPEN = ("OPEN", "FINANCED")
_LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)
_LABELS = {"VIEW_TERMS": ("View terms", "查看条款"), "PREPARE_REMINDER": ("Prepare reminder", "准备付款提醒"),
           "CHASE": ("Chase payment", "催收付款")}
_ORDER = {"CURRENT": ("VIEW_TERMS", "PREPARE_REMINDER"), "DUE_SOON": ("PREPARE_REMINDER", "VIEW_TERMS"),
          "OVERDUE": ("CHASE", "PREPARE_REMINDER", "VIEW_TERMS"), "PROMISE_MISSED": ("CHASE", "PREPARE_REMINDER", "VIEW_TERMS")}
_STATE_TEXT = {"CURRENT": ("Not due yet", "未到期"), "DUE_SOON": ("Due soon", "即将到期"), "OVERDUE": ("Overdue", "已逾期"),
               "PROMISE_MISSED": ("Promise missed", "承诺未兑现")}


class OpenOffer(NamedTuple):
    """An offer still open (no commitment yet) with its latest verdict, newest offers first."""

    offer_id: str
    buyer_id: str
    verdict: Verdict


def collection_state(due_day: int, today: int, *, promise_missed: bool = False) -> str:
    """CURRENT, DUE_SOON (the due day or up to 7 days before it), OVERDUE (from the day after the due day, no grace) or
    PROMISE_MISSED (an early payment promised and not received: it counts as overdue, whatever the due day says)."""
    if promise_missed:
        return "PROMISE_MISSED"
    if today > due_day:
        return "OVERDUE"
    return "DUE_SOON" if due_day - today <= DUE_SOON_DAYS else "CURRENT"


def collection_action(state: str, lang: Lang) -> dict[str, Any]:
    """The primary action for a collection state and the others still available, with their labels."""
    first, *rest = _ORDER[state]
    return {"primary": first, "label": t(lang, *_LABELS[first]),
            "others": [{"action": a, "label": t(lang, *_LABELS[a])} for a in rest]}


def _rebate_bp(commitments: Sequence[Commitment], buyer_id: str) -> int:
    """The rebate agreed with the buyer in live commitments, in bp (the rebates add up). Read from the commitments themselves:
    `Books.obligations` keeps a rebate only when it has an effective day (`cash_relevant`), and an agreed rebate is one whatever
    its day. A rebate already settled or lapsed no longer counts."""
    return sum(o.rate_bp or 0 for c in commitments if c.counterparty_id == buyer_id and c.status in _LIVE
               for o in c.obligations if o.type == ObligationType.CONTINGENT_REBATE
               and o.id not in c.settled_obligations and o.id not in c.lapsed_obligations)


def _governed_by(r: Receivable, ref: str | None, rebate_bp: int, lang: Lang) -> dict[str, Any]:
    terms = t(lang, f"{r.terms_days} days from the invoice date", f"自开票日起 {r.terms_days} 天")
    head = t(lang, f"Governed by agreement {ref}: " if ref else "No confirmed agreement on file; ",
             f"依据协议 {ref}：" if ref else "尚无已确认的协议；")
    rebate = (t(lang, f"; a {fmt_pct(bp(rebate_bp))} rebate is agreed with the buyer", f"；已与买方约定 {fmt_pct(bp(rebate_bp))} 的返利")
              if rebate_bp else "")
    return {"contract_ref": ref, "terms_days": r.terms_days, "rebate_bp": rebate_bp,
            "terms_text": head + t(lang, f"payment is due {terms}", f"账期为{terms}") + rebate}


def _live_discount(books: Books | None, r: Receivable) -> Obligation | None:
    if books is None:
        return None
    return next((o for o in books.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT
                 and o.base.receivable_id == r.id), None)


def _none_agreed(lang: Lang) -> dict[str, Any]:
    return {"agreed": False, "text": t(lang, "none agreed on this invoice", "这张发票没有约定提前付款")}


def _early_payment(books: Books | None, r: Receivable, today: int, lang: Lang) -> dict[str, Any]:
    o = _live_discount(books, r)
    if o is None:
        return _none_agreed(lang)
    face = min(max(0, (o.base.amount_fen or r.outstanding_fen) - r.early_paid_fen.get(o.id, 0)), r.outstanding_fen)
    if face == 0:  # the whole agreed face has been paid early: nothing is left to agree
        return _none_agreed(lang)
    rate = fmt_pct(bp(o.rate_bp or 0))
    when_en = f", {when_text(o.effective_day, today, 'en')}" if o.effective_day is not None else ""
    when_zh = f"（{when_text(o.effective_day, today, 'zh')}）" if o.effective_day is not None else ""
    return {"agreed": True, "text": t(
        lang, f"{whole_yuan(face)} of this invoice may be paid early at {rate} off{when_en}; the agreement lapses if payment comes later",
        f"这张发票的 {whole_yuan(face)} 可提前付款，折扣 {rate}{when_zh}；如果更晚才付款，该约定即告失效")}


def _pending_counter(r: Receivable, open_offers: Sequence[OpenOffer], lang: Lang) -> dict[str, Any] | None:
    """An open offer's counter that would apply to this invoice if sent and accepted: the first counter, of the newest open
    offer of the buyer, that names the invoice in an early-payment leg."""
    for offer_id, buyer_id, verdict in open_offers:
        if buyer_id != r.counterparty_id:
            continue
        for counter in verdict.counters:
            for o in counter.obligations:
                if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id == r.id:
                    face = min(o.base.amount_fen or r.outstanding_fen, r.outstanding_fen)
                    label = option_label(counter.label, lang)
                    return {"decision_id": deal_id(offer_id), "text": t(
                        lang, f"The {label} counter, if sent and accepted, would apply to {whole_yuan(face)} of it",
                        f"{label} 的还价如果发出并被接受，将适用于其中的 {whole_yuan(face)}")}
    return None


def _net_block(net: NetAtCollection, words: Mapping[str, str | None]) -> dict[str, Any]:
    return {**net.model_dump(mode="json"), **words}


def receivable_rows(state: FinancialState, today: int, lang: Lang, *, books: Books | None = None,
                    commitments: Sequence[Commitment] = (), promise_missed: frozenset[str] = frozenset(),
                    financing_repaid: frozenset[str] = frozenset(),
                    open_offers: Sequence[OpenOffer] = (),
                    contract_refs: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The rows and the summary for every receivable still to collect, due first. `books` carries the live early-payment
    agreements; `promise_missed` the receivables with a promised early payment that did not arrive; `financing_repaid` the receivables whose
    advance a receipt cleared (read from the log: the books keep no trace of it); `open_offers` the offers
    still open with their latest verdicts, newest first; `contract_refs` the agreement number of each buyer's
    confirmed contract."""
    lang = "zh" if lang == "zh" else "en"
    refs = contract_refs or {}
    owed = sorted((r for r in state.receivables if r.status in _OPEN and r.outstanding_fen > 0), key=lambda r: (r.due_day, r.id))
    rows: list[dict[str, Any]] = []
    nets: list[NetAtCollection] = []
    for r in owed:
        net = net_at_collection(state, r, max(today, r.due_day))  # an invoice already late is priced on the first day it can be paid
        if net.financing_state == "NONE" and r.id in financing_repaid:
            net = net.model_copy(update={"financing_state": "REPAID"})
        nets.append(net)
        buyer = party_name(state, r.counterparty_id)
        cstate = collection_state(r.due_day, today, promise_missed=r.id in promise_missed)
        rows.append({
            "receivable_id": r.id, "buyer_id": r.counterparty_id, "buyer_name": buyer, "invoice": invoice_words(state, r.id, lang),
            "face_fen": r.face_fen, "outstanding_fen": r.outstanding_fen, "status": r.status, "due_day": r.due_day,
            "due_when": when_text(r.due_day, today, lang), "past_due": today > r.due_day,
            "days_late": max(0, today - r.due_day),
            "net": _net_block(net, net_words(lang, net, buyer_name=buyer, today=today, due_day=r.due_day)),
            "financing_state": net.financing_state,
            "governed_by": _governed_by(r, refs.get(r.counterparty_id), _rebate_bp(commitments, r.counterparty_id), lang),
            "early_payment": _early_payment(books, r, today, lang),
            "pending_counter": _pending_counter(r, open_offers, lang),
            "collection_state": cstate, "collection_state_text": t(lang, *_STATE_TEXT[cstate]),
            "collection_action": collection_action(cstate, lang)})
    waiting = [r for r in owed if r.due_day >= today]
    first_due = min((r.due_day for r in waiting), default=None)
    coming = sum(r.outstanding_fen for r in waiting if r.due_day == first_due)
    summary = {
        "outstanding_total_fen": sum(r.outstanding_fen for r in owed),
        "outstanding_total_display": fmt_yuan(sum(r.outstanding_fen for r in owed)),
        "next_expected": ({"when_text": when_text(first_due, today, lang), "due_day": first_due, "amount_fen": coming,
                           "amount_display": fmt_yuan(coming)} if first_due is not None else None),
        "net_total_fen": sum(n.net_fen for n in nets), "net_total_display": fmt_yuan(sum(n.net_fen for n in nets)),
        "net_total_text": (t(lang, "if every invoice is paid on its due day, or today for one already late",
                             "如果每张发票都在到期日付款（已逾期的则今天付款）") if any(r.due_day < today for r in owed) else
                           t(lang, "if every invoice is paid on its due day", "如果每张发票都在到期日付款"))}
    return {"rows": rows, "summary": summary}


__all__ = ["DUE_SOON_DAYS", "OpenOffer", "collection_action", "collection_state", "receivable_rows"]
