"""What a confirmed contract implies for the books, in the books' own units, so the two can be compared.

Read only: these values are compared with the stored books (the golden equality test, the contract check on the deal
card) and never written into them (brief 03 §3: the language model never sets the starting state). Calendar dates
become day numbers only against the books' own anchor (`FinancialState.as_of`, day 0; ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.models import (
    CompiledContract,
    ContractField,
    ContractTerm,
    PaymentBasis,
    PriceUnit,
    RecurringInvoice,
)

F = ContractField


def day_of(iso: str, anchor_iso: str) -> int:
    """The absolute day number of a calendar date, day 0 being the books' `as_of` date."""
    return (date.fromisoformat(iso) - date.fromisoformat(anchor_iso)).days


def date_display(iso: str, lang: str = "en") -> str:
    d = date.fromisoformat(iso)
    return f"{d.year}年{d.month}月{d.day}日" if lang == "zh" else f"{d.day} {d.strftime('%b')} {d.year}"


@dataclass(frozen=True)
class ScheduledInvoice:
    reference: str | None
    issue_day: int
    face_fen: int | None
    clause: str | None


@dataclass(frozen=True)
class BuyerContractTerms:
    """The terms of one confirmed buyer contract that the books also hold, converted to day numbers."""

    counterparty_id: str
    face_fen: int | None  # the price of one invoiced delivery (PER_DELIVERY), else None
    unit: PriceUnit | None
    every_days: int | None
    first_issue_day: int | None
    terms_days: int | None  # only when counted from the invoice date, as the books count them
    terms_basis: PaymentBasis | None
    terms_business_days: bool
    early_pay_rate_bp: int | None
    early_pay_window_days: int | None
    scheduled: tuple[ScheduledInvoice, ...]
    start_day: int | None
    end_day: int | None

    def next_issue_day(self, today: int) -> int | None:
        """The first scheduled regular invoice day on or after `today`."""
        if self.first_issue_day is None or not self.every_days:
            return None
        if self.first_issue_day >= today:
            return self.first_issue_day
        k = -(-(today - self.first_issue_day) // self.every_days)  # ceiling division
        return self.first_issue_day + k * self.every_days

    def recurring(self, today: int) -> RecurringInvoice | None:
        """The recurring invoice the contract describes, as the books would hold it on `today`."""
        nxt = self.next_issue_day(today)
        if self.face_fen is None or self.every_days is None or nxt is None or self.terms_days is None:
            return None
        return RecurringInvoice(counterparty_id=self.counterparty_id, face_fen=self.face_fen,
                                every_days=self.every_days, next_issue_day=nxt, terms_days=self.terms_days)

    def scheduled_invoice(self, reference: str) -> ScheduledInvoice | None:
        return next((s for s in self.scheduled if s.reference == reference), None)


def _one(terms: list[ContractTerm], field: ContractField) -> ContractTerm | None:
    found = [t for t in terms if t.field == field]
    return found[0] if len(found) == 1 else None


def buyer_terms(contract: CompiledContract, counterparty_id: str, anchor_iso: str) -> BuyerContractTerms:
    t = contract.terms
    price, inv, pay = _one(t, F.PRICE), _one(t, F.INVOICING), _one(t, F.PAYMENT_TERMS)
    early, start, end = _one(t, F.EARLY_PAYMENT), _one(t, F.START_DATE), _one(t, F.END_DATE)
    face = price.amount_fen if price is not None and price.unit == PriceUnit.PER_DELIVERY else None
    scheduled = tuple(
        ScheduledInvoice(reference=s.reference, issue_day=day_of(s.date, anchor_iso), face_fen=s.amount_fen,
                         clause=s.clause)
        for s in t if s.field == F.SCHEDULED_INVOICE and s.date is not None)
    return BuyerContractTerms(
        counterparty_id=counterparty_id,
        face_fen=face,
        unit=price.unit if price is not None else None,
        every_days=inv.days if inv is not None else None,
        first_issue_day=day_of(inv.date, anchor_iso) if inv is not None and inv.date else None,
        terms_days=pay.days if pay is not None and pay.basis == PaymentBasis.INVOICE else None,
        terms_basis=pay.basis if pay is not None else None,
        terms_business_days=bool(pay and pay.business_days),
        early_pay_rate_bp=early.rate_bp if early is not None else None,
        early_pay_window_days=early.days if early is not None else None,
        scheduled=scheduled,
        start_day=day_of(start.date, anchor_iso) if start is not None and start.date else None,
        end_day=day_of(end.date, anchor_iso) if end is not None and end.date else None,
    )


__all__ = ["BuyerContractTerms", "ScheduledInvoice", "buyer_terms", "date_display", "day_of"]
