"""Server-formatted views of a contract record (INVARIANT 13: the UI never formats money or rates).

`record_view` is the review screen: the document text, every term beside its quote and span, the fields left blank
and why, the flags, and for a lender agreement the agreement against the facility on the books. `record_summary` is
the row the documents card shows. Every reading is labelled "AI-generated, for reference" until the owner confirms it.
"""

from __future__ import annotations

from typing import Any

from app.contracts.derive import date_display, day_of
from app.domain.models import (
    MULTI_VALUED_CONTRACT_FIELDS,
    ContractField,
    ContractRecord,
    ContractTerm,
    DocumentKind,
    DocumentStatus,
    Facility,
    FinancialState,
    PaymentBasis,
    PriceUnit,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan

F = ContractField
AI_LABEL = "AI-generated, for reference"
AI_LABEL_ZH = "由 AI 生成，仅供参考"

FIELD_LABELS: dict[ContractField, str] = {
    F.PARTY_SUPPLIER: "Supplier", F.PARTY_BUYER: "Buyer", F.CONTRACT_REFERENCE: "Agreement number",
    F.SIGNED_DATE: "Signed", F.START_DATE: "Starts", F.END_DATE: "Ends", F.DURATION: "Term", F.PRICE: "Price",
    F.INVOICING: "Invoicing", F.SCHEDULED_INVOICE: "Scheduled invoice", F.PAYMENT_TERMS: "Payment terms",
    F.EARLY_PAYMENT: "Early payment", F.MILESTONE: "Milestone payment", F.RETENTION: "Retention",
    F.LATE_INTEREST: "Late-payment interest", F.DELIVERABLE: "Deliverable", F.REQUIRED_DOCUMENT: "Document for payment",
    F.AMENDMENT: "Amendments",
}
BASIS_TEXT = {PaymentBasis.INVOICE: "the invoice date", PaymentBasis.DELIVERY: "delivery",
              PaymentBasis.ACCEPTANCE: "acceptance", PaymentBasis.MONTH_END: "the end of the invoice month"}
UNIT_TEXT = {PriceUnit.PER_DELIVERY: "per delivery batch", PriceUnit.PER_UNIT: "per unit",
             PriceUnit.PER_MONTH: "per month", PriceUnit.LUMP_SUM: "in total"}
NOT_FOUND_REASON = "The agent found no clause for this and left it blank."


def _days(n: int, business: bool) -> str:
    return f"{n} {'business ' if business else ''}day{'' if n == 1 else 's'}"


def _date(iso: str | None, anchor: str | None) -> str:
    if iso is None:
        return ""
    return date_display(iso) + (f" (day {day_of(iso, anchor)})" if anchor else "")


def term_display(t: ContractTerm, anchor: str | None = None) -> str:
    """One plain English line for a term, from its typed fields only."""
    f = t.field
    if f == F.PRICE and t.amount_fen is not None:
        return f"{fmt_yuan(t.amount_fen)} {UNIT_TEXT.get(t.unit, '') if t.unit else ''}".strip()
    if f == F.INVOICING:
        head = f"Every {_days(t.days, False)}" if t.days else "Monthly"
        return head + (f", the first on {_date(t.date, anchor)}" if t.date else "")
    if f == F.SCHEDULED_INVOICE:
        amount = f"{fmt_yuan(t.amount_fen)} " if t.amount_fen is not None else ""
        return f"{t.reference or 'An invoice'}: {amount}issued {_date(t.date, anchor)}"
    if f == F.PAYMENT_TERMS and t.days is not None:
        return f"{_days(t.days, t.business_days)} from {BASIS_TEXT[t.basis] if t.basis else 'a date the clause does not state'}"
    if f == F.EARLY_PAYMENT and t.rate_bp is not None:
        window = f", within {_days(t.days, t.business_days)}" if t.days is not None else ""
        return f"The buyer may settle early at {fmt_pct(bp(t.rate_bp))} off{window}"
    if f == F.MILESTONE and t.rate_bp is not None:
        return f"{fmt_pct(bp(t.rate_bp))} of the price {t.text or ''}".strip()
    if f == F.RETENTION and t.rate_bp is not None:
        period = (f" for {t.months} months" if t.months else f" for {_days(t.days, False)}" if t.days
                  else f" {t.text}" if t.text else "")
        return f"{fmt_pct(bp(t.rate_bp))} retained{period}"
    if f == F.LATE_INTEREST and t.rate_bp is not None:
        return f"{fmt_pct(bp(t.rate_bp))}{' ' + t.text if t.text else ''}"
    if f in (F.SIGNED_DATE, F.START_DATE, F.END_DATE):
        return _date(t.date, anchor)
    if f == F.DURATION and t.months is not None:
        return f"{t.months} months"
    return t.text or t.value_text or ""


def term_view(t: ContractTerm, anchor: str | None) -> dict[str, Any]:
    return {
        "field": t.field.value, "label": FIELD_LABELS[t.field], "value_display": term_display(t, anchor),
        "clause": t.clause, "quote": t.span.text, "span": {"start": t.span.start, "end": t.span.end},
        "amount_fen": t.amount_fen, "amount_display": fmt_yuan(t.amount_fen) if t.amount_fen is not None else None,
        "rate_bp": t.rate_bp, "rate_display": fmt_pct(bp(t.rate_bp)) if t.rate_bp is not None else None,
        "days": t.days, "months": t.months, "date": t.date,
        "date_display": date_display(t.date) if t.date else None,
        "day": day_of(t.date, anchor) if t.date and anchor else None,
        "basis": t.basis.value if t.basis else None, "unit": t.unit.value if t.unit else None,
        "reference": t.reference, "text": t.text, "business_days": t.business_days,
    }


def blanks(record: ContractRecord) -> list[dict[str, Any]]:
    """The fields the reading left blank, each with why: a dropped term's reason, a conflict, or not found."""
    c = record.contract
    if c is None:
        return []
    out = []
    for f in [*c.not_found, *(F(a.field) for a in c.abstentions if a.reason.startswith("conflicting sources"))]:
        why = next((a.reason for a in c.abstentions if a.field == f.value and not a.field.startswith("note:")), None)
        out.append({"field": f.value, "label": FIELD_LABELS[f], "reason": why or NOT_FOUND_REASON,
                    "multi": f in MULTI_VALUED_CONTRACT_FIELDS})
    return out


def _facility_rows(agreed: Facility, books: Facility | None) -> list[dict[str, Any]]:
    def pct(v: int | None) -> str:
        return fmt_pct(bp(v)) if v else "none"

    def cov(f: Facility, kind: str) -> str:
        c = next((c for c in f.covenants if c.kind.value == kind), None)
        if c is None:
            return "none"
        if c.clean_down_days is not None:
            return f"zero for {c.clean_down_days} consecutive days a year"
        return f"{Ratio.of(bp(c.threshold_bp or 0)).text}×"

    def fee(f: Facility) -> str:
        return f"{pct(f.fee_bp_per_advance)} per {f.fee_period_days} days" if f.fee_bp_per_advance else "none"

    rows = [("Limit", fmt_yuan(agreed.limit_fen), books and fmt_yuan(books.limit_fen)),
            ("Interest rate", pct(agreed.rate_bp), books and pct(books.rate_bp)),
            ("Periodic fee", fee(agreed), books and fee(books)),
            ("Upfront fee", pct(agreed.upfront_fee_bp), books and pct(books.upfront_fee_bp)),
            ("Lead time", _days(agreed.lead_time_days, False), books and _days(books.lead_time_days, False)),
            ("Advance rate", pct(agreed.advance_rate_bp), books and pct(books.advance_rate_bp)),
            ("Minimum DSCR", cov(agreed, "DSCR_MIN"), books and cov(books, "DSCR_MIN")),
            ("Maximum leverage", cov(agreed, "LEVERAGE_MAX"), books and cov(books, "LEVERAGE_MAX")),
            ("Clean-down", cov(agreed, "CLEAN_DOWN"), books and cov(books, "CLEAN_DOWN"))]
    return [{"label": label, "agreement_display": a, "books_display": b, "same": b is not None and a == b}
            for label, a, b in rows]


def facility_summary(f: Facility) -> str:
    """"¥350,000.00 at 7.80% · 80% advance · 0.25% per 30 days · 3-day lead time"."""
    parts = [f"{fmt_yuan(f.limit_fen)} at {fmt_pct(bp(f.rate_bp))}"]
    if f.advance_rate_bp:
        parts.append(f"{fmt_pct(bp(f.advance_rate_bp))} advance")
    if f.fee_bp_per_advance:
        parts.append(f"{fmt_pct(bp(f.fee_bp_per_advance))} per {f.fee_period_days} days")
    parts.append("same-day funding" if f.lead_time_days == 0 else f"{f.lead_time_days}-day lead time")
    cd = next((c.clean_down_days for c in f.covenants if c.clean_down_days), None)
    if cd:
        parts.append(f"line at zero {cd} days a year")
    return " · ".join(parts)


def _name(state: FinancialState | None, counterparty_id: str) -> str:
    cp = next((c for c in (state.counterparties if state else []) if c.id == counterparty_id), None)
    return cp.name if cp else counterparty_id


def record_summary(record: ContractRecord, state: FinancialState | None) -> dict[str, Any]:
    if record.kind == DocumentKind.BUYER_CONTRACT and record.contract is not None:
        n_blank = len(blanks(record))
        summary = f"{len(record.contract.terms)} terms read, {n_blank} left blank"
    else:
        ts = record.term_sheet
        summary = (facility_summary(ts.proposed_facility) if ts and ts.proposed_facility
                   else "the agent could not read a facility from it")
    return {
        "id": record.id, "kind": record.kind.value, "title": record.title, "counterparty_id": record.counterparty_id,
        "counterparty_name": _name(state, record.counterparty_id), "status": record.status.value,
        "uploaded_day": record.uploaded_day, "decided_day": record.decided_day, "decided_seq": record.decided_seq,
        "linked_facility_id": record.linked_facility_id, "summary": summary, "blocked": record.blocked,
        "flags": len(record.flags), "source": record.source,
        "label": AI_LABEL if record.status != DocumentStatus.CONFIRMED else "Read by the agent, confirmed by you",
    }


def record_view(record: ContractRecord, state: FinancialState | None) -> dict[str, Any]:
    anchor = state.as_of if state is not None else None
    view = record_summary(record, state)
    view.update({
        "doc_hash": record.doc_hash,
        "document": {"doc_id": record.document.doc_id, "text": record.document.text},
        "ai_label": AI_LABEL, "ai_label_zh": AI_LABEL_ZH,
        "flags": [{"kind": f.kind, "blocking": f.blocking, "note": f.note, "quote": f.span.text,
                   "span": {"start": f.span.start, "end": f.span.end}} for f in record.flags],
        "can_confirm": record.status == DocumentStatus.PROPOSED and not record.blocked,
    })
    if record.contract is not None:
        c = record.contract
        view.update({
            "reading_status": c.status.value, "compiler": c.compiler, "prompt_version": c.prompt_version,
            "chunks": c.chunks,
            "terms": [term_view(t, anchor) for t in c.terms],
            "blanks": blanks(record),
            "notes": [{"field": a.field.removeprefix("note:"), "reason": a.reason} for a in c.abstentions
                      if a.field.startswith("note:")],
        })
    if record.term_sheet is not None:
        ts = record.term_sheet
        target = record.linked_facility_id or record.suggested_facility_id
        books = next((f for f in (state.facilities if state else []) if f.id == target), None)
        agreed = ts.proposed_facility
        view.update({
            "reading_status": ts.status.value, "compiler": ts.compiler, "prompt_version": ts.prompt_version,
            "clauses": [{"field": cl.field, "value_text": cl.value_text, "quote": cl.span.text,
                         "span": {"start": cl.span.start, "end": cl.span.end}} for cl in ts.clauses],
            "facility": None if agreed is None else {
                "kind": agreed.kind.value, "summary": facility_summary(agreed),
                "all_in_rate_display": fmt_pct(bp(ts.all_in_rate_bp)) if ts.all_in_rate_bp is not None else None,
                "repayment": agreed.repayment.value,
                "tier3": [{"field": cl.field, "quote": cl.span.text} for cl in ts.tier3_clauses],
            },
            "suggested_facility_id": record.suggested_facility_id,
            "compared_with": books.id if books is not None else None,
            "comparison": _facility_rows(agreed, books) if agreed is not None else [],
            "notes": [{"field": a.field, "reason": a.reason} for a in ts.abstentions],
        })
    return view


__all__ = ["AI_LABEL", "FIELD_LABELS", "blanks", "facility_summary", "record_summary", "record_view", "term_display",
           "term_view"]
