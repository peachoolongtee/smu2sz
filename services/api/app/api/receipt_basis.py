"""What each receipt on the cash picture rests on (map #88, ticket #116): OWED, SCHEDULED, AGREED or PENDING.

A reading of the books and the trajectory's own events; it prices, projects and decides nothing. A receipt is

    OWED       the payment of an invoice already issued, due under the terms written on it
    SCHEDULED  the payment of a recurring billing that is not invoiced yet (its receivable id is `RI:<buyer>:<issue day>`)
    AGREED     timing or amount that comes from an agreement the owner recorded (an early settlement, a discount, terms written
               on the invoice), named by the day it was made and never by an id
    PENDING    a receipt only the buyer's acceptance of a reply would move (set by the Home, from the offer picture)

An expected order is never a receipt in the CONSERVATIVE projection, so it has no basis and never appears. The words are
`app.strategy.words.basis_text`, said one way on every page. An event the books do not explain (a plan's early-payment funding,
a discounted bill) is left without a basis rather than given a wrong one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.api.presentation import buyer_of_receivable, party_name
from app.books import Books
from app.domain.models import (
    Commitment,
    FinancialState,
    LedgerEvent,
    LedgerEventKind,
    Obligation,
    ObligationType,
    OperationStatus,
    Receivable,
)
from app.financial.invoices import InvoiceRef, covers
from app.strategy import words

RECEIPT_KINDS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT, LedgerEventKind.DISCOUNT)
_AGREEMENT_KINDS = ("ACCEPT_OFFER", "RECORD_COMMITMENT")
_TRAILING_ID = re.compile(r"\(([^()]+)\)\s*$")


@dataclass(frozen=True, slots=True)
class Basis:
    """What one receipt rests on: the code, and the facts its words are written from."""

    code: str
    receivable_id: str | None = None
    commitment_id: str | None = None


def agreement_days(entries: Iterable[Any], commitments: Sequence[Commitment]) -> dict[str, int]:
    """The day each commitment was recorded: the day of the executed accept / record entry of the log that names it."""
    out: dict[str, int] = {}
    for e in entries:
        if e.kind not in _AGREEMENT_KINDS or e.result.status != OperationStatus.EXECUTED or e.day is None:
            continue
        message = e.result.message or ""
        for c in commitments:
            if c.id in message:
                out.setdefault(c.id, e.day)
    return out


class BasisReader:
    """Classifies the receipts of one read of the books and words them. Built once per request (under the runtime's lock)."""

    def __init__(self, books: Books, today: int, lang: str, agreed_on: dict[str, int] | None = None) -> None:
        self.books = books
        self.state: FinancialState = books.state
        self.today = today
        self.lang = lang
        self.agreed_on = agreed_on or {}
        self._receivables: dict[str, Receivable] = {r.id: r for r in self.state.receivables}
        self._adjustments = {a.id: a for a in self.state.invoice_adjustments}
        self._obligations: dict[str, Obligation] = {o.id: o for o in books.obligations}

    # ------------------------------------------------------------ which basis

    def _owner(self, o: Obligation) -> str | None:
        return self.books.owner_of(o)

    def _early_pay(self, receivable_id: str | None) -> Obligation | None:
        if receivable_id is None:
            return None
        return next((o for o in self.books.obligations
                     if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id == receivable_id), None)

    def _terms_agreement(self, receivable_id: str) -> tuple[bool, str | None]:
        """(whether an agreement's terms or price are written on this invoice, or will be on a recurring one not issued yet, and
        which commitment: None when the books do not say)."""
        r = self._receivables.get(receivable_id)
        if r is not None:
            if not r.applied:
                return False, None
            first = self._adjustments.get(r.applied[0])
            return True, (first.commitment_id or None) if first is not None else None
        buyer = buyer_of_receivable(self.state, receivable_id)
        parts = receivable_id.split(":")
        if buyer is None or parts[0] != "RI" or len(parts) != 3 or not parts[2].isdigit():
            return False, None
        ref = InvoiceRef(receivable_id, buyer, int(parts[2]))
        hit = next((a for a in self.state.invoice_adjustments if not a.contingent_gain and covers(a, ref)), None)
        return (True, hit.commitment_id or None) if hit is not None else (False, None)

    def of(self, e: LedgerEvent) -> Basis | None:
        """The basis of one trajectory event, or None when it is not a receipt or the books do not explain it."""
        if e.kind not in RECEIPT_KINDS:
            return None
        if e.kind == LedgerEventKind.DISCOUNT:
            ob = self._obligations.get(e.ref or "")
            return Basis(words.AGREED, ob.base.receivable_id, self._owner(ob)) if ob is not None else None
        rid = e.ref
        if e.kind == LedgerEventKind.EARLY_RECEIPT:
            named = _TRAILING_ID.search(e.label)
            ob = self._obligations.get(named.group(1)) if named else None
            ob = ob or self._early_pay(rid)
            return Basis(words.AGREED, rid, self._owner(ob)) if ob is not None else None
        if rid is None:
            return None
        return self.of_receivable(rid)

    def of_receivable(self, rid: str) -> Basis | None:
        """The basis of the payment of one receivable, issued or recurring: what the Receivables rows say too."""
        early = self._early_pay(rid)
        if early is not None:  # the rest of an invoice part of which is paid early under an agreement
            return Basis(words.AGREED, rid, self._owner(early))
        written, commitment_id = self._terms_agreement(rid)
        if written:
            return Basis(words.AGREED, rid, commitment_id)
        if rid in self._receivables:
            return Basis(words.OWED, rid)
        if rid.startswith("RI:"):
            return Basis(words.SCHEDULED, rid)
        return None

    # ------------------------------------------------------------ its words

    def text(self, b: Basis) -> str:
        r = self._receivables.get(b.receivable_id or "")
        buyer = buyer_of_receivable(self.state, b.receivable_id)
        return words.basis_text(
            self.lang, b.code, today=self.today, issue_day=r.issue_day if r is not None else None,
            due_day=r.issue_day + r.terms_days if r is not None else None,
            agreement_day=self.agreed_on.get(b.commitment_id) if b.commitment_id else None,
            buyer_name=party_name(self.state, buyer) if buyer else "")

    def fields(self, e: LedgerEvent) -> dict[str, str]:
        """`basis` and `basis_text` for an event, or nothing."""
        b = self.of(e)
        return {"basis": b.code, "basis_text": self.text(b)} if b is not None else {}


def annotate(rows: list[dict[str, Any]] | None, traj: Any, reader: BasisReader) -> None:
    """Put `basis` and `basis_text` on the receipt events of a series drawn by `_series` from `traj` (its events in the trajectory's own
    order, so each is read from the raw posting and no id is parsed from the words)."""
    if not rows:
        return
    by_day = {d.day: d for d in traj.days}
    for row in rows:
        day = by_day.get(row["day"])
        if day is None or len(day.events) != len(row["events"]):
            continue
        for shown, raw in zip(row["events"], day.events, strict=True):
            shown.update(reader.fields(raw))


def scheduled_billing(state: FinancialState) -> tuple[int, int] | None:
    """(the total, the day it is invoiced) of the earliest recurring billing not yet invoiced, or None. The face is the one the
    clock will write on the invoice (`issue_terms`); a billing the books do not run (every 0 days) is not scheduled."""
    from app.financial.invoices import issue_terms, recurring_receivable_id

    soonest: dict[int, int] = {}
    for ri in state.recurring_invoices:
        if ri.every_days <= 0:
            continue
        day = ri.next_issue_day
        face = issue_terms(state, InvoiceRef(recurring_receivable_id(ri.counterparty_id, day), ri.counterparty_id, day),
                           ri.face_fen, ri.terms_days)["face_fen"]
        soonest[day] = soonest.get(day, 0) + (face if isinstance(face, int) else ri.face_fen)
    if not soonest:
        return None
    first = min(soonest)
    return soonest[first], first
