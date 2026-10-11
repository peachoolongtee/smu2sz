"""The deal summary on the owner's home page (brief 03 §5.2): for each buyer, what was signed, what changed since,
what is in force now, where the money stands, what we owe them, whether what was agreed fits the contract, and the
one thing to do next.

Read only and composed from what already exists: the owner-confirmed contract record (the terms, each with its clause
quote) and the current books (the log, commitments, receivables, reconciliation, approvals, alerts). It decides and
writes nothing; every amount is a server display string (INVARIANT 13). Owner only: it discloses a buyer's terms.

Public API: `deal_summary(store, counterparty_id, day)`, `deals(store, day)`, `deal_reply(summary, lang)`.
"""

from __future__ import annotations

from typing import Any

from app.alerts import AlertKind, PromiseStatus, alerts, reconcile
from app.api.presentation import Lang, t
from app.contracts import buyer_terms, record_summary, term_display, term_view
from app.contracts.derive import BuyerContractTerms, date_display, day_of
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    ContractField,
    ContractRecord,
    DocumentKind,
    DocumentStatus,
    FinancialState,
    Obligation,
    ObligationType,
    Outcome,
    PaymentBasis,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import EngineError
from app.financial.invoices import InvoiceRef, issue_terms, recurring_receivable_id, terms_in_force
from app.operations.log import CONFIRM_DOCUMENT_KIND, REVOKE_COMMITMENT_KIND, read_entries
from app.persistence import ApprovalStatus

F = ContractField
SHOWN_TERMS = (F.PRICE, F.INVOICING, F.PAYMENT_TERMS, F.EARLY_PAYMENT, F.MILESTONE, F.RETENTION, F.LATE_INTEREST,
               F.SCHEDULED_INVOICE)
LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)
CONFIRMED_LABEL = "Read by the agent, confirmed by you"


# ---------------------------------------------------------------- small helpers


def _pct(rate_bp: int | None) -> str:
    return fmt_pct(bp(rate_bp)) if rate_bp is not None else "?"


def _obligation_text(o: Obligation) -> str:
    """One plain phrase for an obligation, from its typed fields only."""
    t = o.type
    base = fmt_yuan(o.base.amount_fen) if o.base.amount_fen is not None else None
    if t == ObligationType.IMMEDIATE_DISCOUNT:
        what = f"{base} of {o.base.receivable_id}" if base and o.base.receivable_id else (o.base.receivable_id or base
                                                                                          or "an invoice")
        by = f", paid by day {o.effective_day}" if o.effective_day is not None else ""
        return f"early settlement of {what} at {_pct(o.rate_bp)}{by}"
    if t == ObligationType.TERMS_EXTENSION:
        if o.target_terms_days is not None:
            return f"payment terms to {o.target_terms_days} days"
        return f"payment terms {o.days_delta:+d} days" if o.days_delta is not None else "a change of payment terms"
    if t == ObligationType.CONTINGENT_REBATE:
        return f"a {_pct(o.rate_bp)} rebate" + (f" on up to {base}" if base else "")
    if t == ObligationType.PRICE_ADJUSTMENT:
        return f"a price change of {_pct(o.rate_bp)}"
    if t == ObligationType.OPERATIONAL_CONCESSION:
        return "an operational change"
    if t == ObligationType.VOLUME_COMMITMENT:
        return "a volume commitment" + (f" of {base}" if base else "")
    return "a term claimed as already agreed"


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _contract(store: LedgerStore, counterparty_id: str) -> ContractRecord | None:
    """The buyer's contract the owner confirmed last (a later confirmation supersedes an earlier one)."""
    recs = [r for r in store.contract_records() if r.kind == DocumentKind.BUYER_CONTRACT
            and r.counterparty_id == counterparty_id and r.status == DocumentStatus.CONFIRMED]
    return max(recs, key=lambda r: r.decided_seq or 0) if recs else None


def _basis_unknown(days: int | None, lang: Lang) -> str:
    """The one sentence for a payment term whose days the contract does not count from anything: the check and the in-force
    row say it alike, so the card never shows a match and a difference for the same term."""
    return t(lang, f"The contract does not say what the {days} days count from; the books count from the invoice date.",
             f"合同没有写明这 {days} 天从何时起算；账面按发票日起算。")


def _terms(record: ContractRecord, field: ContractField) -> list[Any]:
    return [t for t in (record.contract.terms if record.contract else []) if t.field == field]


def _one(record: ContractRecord, field: ContractField) -> Any:
    found = _terms(record, field)
    return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------- sections


def _changes(store: LedgerStore, state: FinancialState, cp: str, record: ContractRecord,
             commitments: list[Commitment], receipts: list[Any]) -> list[dict[str, Any]]:
    events: list[tuple[int, int, dict[str, Any]]] = []
    entries, _ = read_entries(store.operations())
    seen_offers: dict[str, Any] = {}
    for v in store.verdicts():  # the latest verdict per offer of this buyer
        offer = store.get_offer(v.offer_id)
        if offer is not None and offer.counterparty_id == cp and offer.obligations:
            seen_offers[v.offer_id] = (offer, v)
    for offer, v in seen_offers.values():
        asked = [_obligation_text(o) for o in offer.obligations if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION]
        if asked:
            events.append((offer.received_day, 0, {"day": offer.received_day, "actor": "BUYER", "label": "Buyer asked",
                                                   "text": _join(asked)}))
        if v.outcome == Outcome.ACCEPT:
            reply = "Accepted as verified"
        elif v.outcome == Outcome.NEEDS_OWNER_APPROVAL:
            reply = "Sent to you for approval"
        elif v.outcome == Outcome.NO_VERDICT:
            reply = "Asked the buyer to clarify; nothing booked"
        else:
            head = {"REJECT": "Rejected", "COUNTER": "Countered", "NO_DEAL": "No deal"}.get(v.outcome.value, v.outcome.value)
            offers = [f"{c.label}: {_join([_obligation_text(o) for o in c.obligations])}" for c in v.counters]
            reply = head + (". Offered " + "; ".join(offers) if offers else "")
        events.append((offer.received_day, 1, {"day": offer.received_day, "actor": "AGENT", "label": "Agent replied",
                                               "text": reply}))
    by_offer = {c.offer_id: c for c in commitments}
    for e in entries:
        if e.result.status.value != "EXECUTED":
            continue
        payload = e.payload
        if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and payload.get("offer_id") in by_offer:
            c = by_offer[payload["offer_id"]]
            how = "booked by the agent (Tier 1)" if e.result.tier.value == "TIER_1" else "approved by you"
            events.append((e.day or 0, 2, {"day": e.day, "actor": "BUYER", "label": "Buyer accepted",
                                           "text": f"{_join([_obligation_text(o) for o in c.obligations])}; {how}"}))
        elif e.kind == REVOKE_COMMITMENT_KIND and any(payload.get("commitment_id") == c.id for c in commitments):
            events.append((e.day or 0, 2, {"day": e.day, "actor": "OWNER", "label": "You revoked",
                                           "text": f"commitment {payload['commitment_id']}"}))
        elif e.kind == CONFIRM_DOCUMENT_KIND and payload.get("document_id") == record.id:
            # the contract is the baseline: on the day it was confirmed, it comes before that day's negotiation
            events.append((e.day or 0, -1, {"day": e.day, "actor": "OWNER", "label": "You confirmed",
                                            "text": f"{record.title}, as the agent read it"}))
    for m in receipts:
        early = m.agreed_discount_fen and m.status.value == "MATCHED" and "early payment" in m.detail
        text = f"{fmt_yuan(m.received_fen)} received on {m.receivable_id}" + (" (the agreed early payment)" if early
                                                                             else "")
        events.append((m.day or 0, 3, {"day": m.day, "actor": "BANK", "label": "Bank feed", "text": text}))
    return [ev for _, _, ev in sorted(events, key=lambda x: (x[0] if x[0] is not None else 0, x[1]))]


def _in_force(state: FinancialState, cp: str, record: ContractRecord, implied: BuyerContractTerms,
              commitments: list[Commitment], lang: Lang = "en") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pay = _one(record, F.PAYMENT_TERMS)
    days = terms_in_force(state, cp)
    if days is not None:
        same = pay is not None and pay.days == days and pay.basis == PaymentBasis.INVOICE
        unknown = pay is not None and pay.basis is None  # the days count from nothing the clause names
        rows.append({"key": "payment_terms", "label": "Payment terms", "value_display": f"{days} days",
                     "vs_contract": ("NOT_COMPARABLE" if unknown else "SAME" if same else "DIFFERENT")
                     if pay is not None else "NOT_IN_CONTRACT",
                     "contract_display": term_display(pay) if pay is not None else None,
                     "vs_contract_note": _basis_unknown(pay.days, lang) if unknown and pay is not None else None})
    ri = next((r for r in state.recurring_invoices if r.counterparty_id == cp), None)
    if ri is not None:
        ref = InvoiceRef(recurring_receivable_id(cp, ri.next_issue_day), cp, ri.next_issue_day)
        face = int(issue_terms(state, ref, ri.face_fen, ri.terms_days)["face_fen"])  # type: ignore[call-overload]
        price = _one(record, F.PRICE)
        rows.append({"key": "price", "label": "Price per invoice", "value_display": fmt_yuan(face),
                     "vs_contract": ("SAME" if implied.face_fen == face else "DIFFERENT") if price is not None
                     else "NOT_IN_CONTRACT",
                     "contract_display": term_display(price) if price is not None else None})
    early = [o for c in commitments if c.status in (*LIVE, CommitmentStatus.FULFILLED) for o in c.obligations
             if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    clause = _one(record, F.EARLY_PAYMENT)
    if early or clause is not None:
        agreed = _join([_obligation_text(o) for o in early]) if early else "none agreed"
        differs = any(o.rate_bp != (clause.rate_bp if clause else None) for o in early)
        rows.append({"key": "early_payment", "label": "Early payment", "value_display": agreed,
                     "vs_contract": ("DIFFERENT" if differs else "SAME") if early else "NONE",
                     "contract_display": term_display(clause) if clause is not None else None})
    concessions = [fc for fc in state.forward_concessions if fc.counterparty_id == cp and fc.value_fen]
    rows.append({"key": "rebate", "label": "Rebates and concessions",
                 "value_display": _join([f"{fc.label} ({fmt_yuan(fc.value_fen)})" for fc in concessions])
                 if concessions else "None", "vs_contract": "NONE" if not concessions else "NOT_IN_CONTRACT",
                 "contract_display": None})
    return rows


def _invoices(store: LedgerStore, state: FinancialState, cp: str, day: int, receipts: list[Any]) -> list[dict[str, Any]]:
    from app.operations.log import parse_operation

    pending: dict[str, list[tuple[str, int]]] = {}
    for a in store.approvals(ApprovalStatus.PENDING):
        op = parse_operation(a.op_json)
        if op is not None and getattr(op, "kind", "") == "SUBMIT_INVOICE_FOR_FINANCING":
            pending.setdefault(op.receivable_id, []).append((a.id, op.advance_fen))
    rows = []
    for r in sorted((r for r in state.receivables if r.counterparty_id == cp), key=lambda r: (r.issue_day, r.id)):
        notes = []
        early_paid = sum(r.early_paid_fen.values())
        if early_paid:
            when = next((m.day for m in receipts if m.receivable_id == r.id and m.agreed_discount_fen), None)
            notes.append(f"{fmt_yuan(early_paid)} settled early" + (f" on day {when}" if when is not None else ""))
        if r.advance_fen:
            notes.append(f"financed: {fmt_yuan(r.advance_fen)} advance outstanding")
        for aid, adv in pending.get(r.id, []):
            notes.append(f"{fmt_yuan(adv)} advance waiting for your approval ({aid})")
        if r.status == "SETTLED" or r.outstanding_fen <= 0:
            status, tone, status_text = "PAID", "ok", "Paid"
        elif r.due_day < day:
            late = day - r.due_day
            status, tone, status_text = "LATE", "bad", f"{late} day{'' if late == 1 else 's'} late"
        elif pending.get(r.id):
            status, tone, status_text = "ADVANCE_WAITING", "warn", "Advance waiting for you"
        elif r.advance_fen or r.status == "FINANCED":
            status, tone, status_text = "FINANCED", "info", "Financed"
        elif r.due_day == day:
            status, tone, status_text = "DUE_TODAY", "warn", "Due today"
        else:
            status, tone, status_text = "NOT_DUE", "mute", "Not due"
        rows.append({
            "id": r.id, "label": r.id if not r.id.startswith("RI:") else f"Invoice of day {r.issue_day}",
            "issue_day": r.issue_day, "due_day": r.due_day, "amount_fen": r.face_fen, "amount_display": fmt_yuan(r.face_fen),
            "outstanding_fen": r.outstanding_fen, "outstanding_display": fmt_yuan(r.outstanding_fen),
            "status": status, "status_text": status_text, "tone": tone, "notes": notes,
        })
    return rows


def _checks(state: FinancialState, cp: str, record: ContractRecord, implied: BuyerContractTerms,
            commitments: list[Commitment], lang: Lang = "en") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def at(field: ContractField) -> str:
        t = _one(record, field)
        return f" (clause {t.clause})" if t is not None and t.clause else ""

    pay = _one(record, F.PAYMENT_TERMS)
    if pay is not None and pay.basis is not None and pay.basis != PaymentBasis.INVOICE:
        basis = {PaymentBasis.ACCEPTANCE: "acceptance", PaymentBasis.DELIVERY: "delivery",
                 PaymentBasis.MONTH_END: "the end of the invoice month"}[pay.basis]
        out.append({"status": "warn", "text": f"The contract counts the {pay.days} days from {basis}{at(F.PAYMENT_TERMS)}, "
                                              f"but the books count them from the invoice date: cash may arrive later "
                                              f"than projected."})
    elif pay is not None and pay.basis is None:
        out.append({"status": "info", "text": _basis_unknown(pay.days, lang)})
    elif pay is not None:
        out.append({"status": "ok", "text": f"The books count the payment terms from the invoice date, as the contract "
                                            f"does{at(F.PAYMENT_TERMS)}."})
    ri = next((r for r in state.recurring_invoices if r.counterparty_id == cp), None)
    if ri is not None and implied.face_fen is not None:
        same = ri.face_fen == implied.face_fen
        out.append({"status": "ok" if same else "warn",
                    "text": (f"Each invoice in the books is {fmt_yuan(ri.face_fen)}, the price in the contract"
                             f"{at(F.PRICE)}." if same else
                             f"The books invoice {fmt_yuan(ri.face_fen)}, but the contract price is "
                             f"{fmt_yuan(implied.face_fen)}{at(F.PRICE)}.")})
    if ri is not None and implied.every_days is not None:
        same = ri.every_days == implied.every_days
        out.append({"status": "ok" if same else "warn",
                    "text": (f"The books issue an invoice every {ri.every_days} days, as the contract says"
                             f"{at(F.INVOICING)}." if same else
                             f"The books issue an invoice every {ri.every_days} days; the contract says every "
                             f"{implied.every_days}{at(F.INVOICING)}.")})
    for s in implied.scheduled:
        r = next((r for r in state.receivables if r.id == s.reference), None)
        if r is None:
            continue
        base_face = r.base_face_fen if r.base_face_fen is not None else r.face_fen
        same = base_face == s.face_fen and r.issue_day == s.issue_day
        out.append({"status": "ok" if same else "warn",
                    "text": (f"{r.id} matches the contract's schedule ({fmt_yuan(base_face)}, issued day {r.issue_day})."
                             if same else f"{r.id} in the books ({fmt_yuan(base_face)}, day {r.issue_day}) differs from "
                                          f"the contract's schedule ({fmt_yuan(s.face_fen or 0)}, day {s.issue_day}).")})
    days = terms_in_force(state, cp)
    if pay is not None and days is not None and pay.days != days:
        out.append({"status": "info", "text": f"An accepted change put {days}-day terms in force against the contract's "
                                              f"{pay.days}{at(F.PAYMENT_TERMS)}."})
    early_clause = _one(record, F.EARLY_PAYMENT)
    for c in commitments:
        for o in c.obligations:
            if o.type != ObligationType.IMMEDIATE_DISCOUNT or o.rate_bp is None:
                continue
            if early_clause is None or early_clause.rate_bp is None:
                out.append({"status": "info", "text": f"The agreed {_pct(o.rate_bp)} early payment is an addition: the "
                                                      f"contract has no early-payment clause."})
            elif o.rate_bp <= early_clause.rate_bp:
                out.append({"status": "ok", "text": f"The agreed {_pct(o.rate_bp)} early payment is within the contract's "
                                                    f"{_pct(early_clause.rate_bp)}{at(F.EARLY_PAYMENT)}."})
            else:
                out.append({"status": "warn", "text": f"The agreed {_pct(o.rate_bp)} early payment is above the "
                                                      f"contract's {_pct(early_clause.rate_bp)}{at(F.EARLY_PAYMENT)}."})
    changed = [c for c in commitments if c.status in (*LIVE, CommitmentStatus.FULFILLED)
               and any(o.type in (ObligationType.TERMS_EXTENSION, ObligationType.PRICE_ADJUSTMENT) for o in c.obligations)]
    amend = _one(record, F.AMENDMENT)
    if changed and amend is not None:
        out.append({"status": "warn", "text": f"{len(changed)} accepted change(s) alter the contract's terms; the contract "
                                              f"requires amendments {amend.text}{at(F.AMENDMENT)}: get them in writing."})
    elif not changed:
        out.append({"status": "ok", "text": "No accepted change alters the contract's terms, so no amendment is needed"
                                            + (f"{at(F.AMENDMENT)}." if amend is not None else ".")})
    return out


def _stages(record: ContractRecord, invoices: list[dict[str, Any]], promised: list[Any], receipts: list[Any],
            implied: BuyerContractTerms, day: int, accepted_day: int | None) -> list[dict[str, Any]]:
    """Contract read -> terms negotiated -> early payment in -> collecting -> fulfilled. A stage is done, skipped
    (it did not apply), pending (an early payment awaited), missed (a promised one lapsed), now (collecting, while the
    contract runs or anything is open) or todo. Exactly one stage is now until the deal is fulfilled."""
    received = [p for p in promised if p.status == PromiseStatus.RECEIVED]
    awaited = [p for p in promised if p.status == PromiseStatus.AWAITED]
    lapsed = [p for p in promised if p.status == PromiseStatus.LAPSED]
    open_inv = [i for i in invoices if i["status"] != "PAID"]
    late = [i for i in open_inv if i["status"] == "LATE"]
    fulfilled = implied.end_day is not None and implied.end_day < day and not open_inv
    if received:
        arrived = next((m.day for m in receipts if m.seq == received[0].receipt_seq), received[0].promised_day)
        early_state, early_note = "done", f"day {arrived}" if arrived is not None else ""
    elif awaited:
        early_state, early_note = "pending", "awaited"
    elif lapsed:
        early_state, early_note = "missed", "missed"
    else:
        early_state, early_note = "skipped", "none agreed"
    return [
        {"key": "read", "label": "Contract read", "state": "done", "note": f"day {record.decided_day}", "tone": None},
        {"key": "negotiated", "label": "Terms negotiated", "state": "done" if accepted_day is not None else "skipped",
         "note": f"day {accepted_day}" if accepted_day is not None else "no changes", "tone": None},
        {"key": "early_payment", "label": "Early payment in", "state": early_state, "note": early_note,
         "tone": "bad" if early_state == "missed" else None},
        {"key": "collecting", "label": "Collecting", "state": "done" if fulfilled else "now",
         "note": (f"{late[0]['id']} late" if late else f"{len(open_inv)} open" if open_inv else "nothing outstanding"),
         "tone": "bad" if late else None},
        {"key": "fulfilled", "label": "Fulfilled", "state": "done" if fulfilled else "todo",
         "note": f"day {implied.end_day}" if implied.end_day is not None else "", "tone": None},
    ]


def _next_action(invoices: list[dict[str, Any]], store: LedgerStore, state: FinancialState, day: int,
                 cp: str) -> dict[str, Any]:
    from app.operations.log import parse_operation

    parts: list[str] = []
    items: list[dict[str, Any]] = []  # the same steps, typed, for other languages
    actions: list[dict[str, Any]] = []
    try:
        found = alerts(state, store.get_mandate(), store, day)
    except EngineError:
        found = []
    breach = next((a for a in found if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)
    late = [i for i in invoices if i["status"] == "LATE"]
    for i in late[:1]:
        parts.append(f"Chase the {i['outstanding_display']} on {i['id']} ({i['status_text']}).")
        items.append({"kind": "CHASE", "receivable_id": i["id"], "amount_display": i["outstanding_display"],
                      "late_days": day - i["due_day"]})
        actions.append({"key": "reconcile", "label": "Reconcile receipts", "href": "/reconciliation", "primary": False})
    by_id = {i["id"]: i for i in invoices}
    for a in store.approvals(ApprovalStatus.PENDING):
        op = parse_operation(a.op_json)
        if op is None or getattr(op, "receivable_id", None) not in by_id:
            continue
        floor_day = breach.day if breach is not None else None
        floor = f" to stay above your floor on day {floor_day}" if floor_day is not None else ""
        what = by_id[op.receivable_id]["label"]
        what = f"the {what[0].lower()}{what[1:]}" if what.startswith("Invoice of") else what
        parts.append(f"Review {a.id}: a {fmt_yuan(op.advance_fen)} advance on {what}{floor}.")
        items.append({"kind": "APPROVAL", "approval_id": a.id, "amount_display": fmt_yuan(op.advance_fen),
                      "receivable_id": op.receivable_id, "issue_day": by_id[op.receivable_id]["issue_day"],
                      "floor_day": floor_day})
        actions.insert(0, {"key": "approvals", "label": "Review approval", "href": "/approvals", "primary": True})
        break
    if not parts and any(a.kind == AlertKind.RECEIVABLE_PAST_DUE for a in found):
        parts.append("A receivable is past due.")
        items.append({"kind": "ALERT"})
        actions.append({"key": "alerts", "label": "Open alerts", "href": "/alerts", "primary": True})
    if not parts:
        return {"text": "Nothing needs you on this deal today.", "items": [], "actions": [], "tone": "ok"}
    return {"text": " ".join(parts), "items": items, "actions": actions, "tone": "bad" if late else "warn"}


# ---------------------------------------------------------------- public


def deal_summary(store: LedgerStore, counterparty_id: str, day: int) -> dict[str, Any]:
    state = store.get_state()
    cp = next((c for c in state.counterparties if c.id == counterparty_id), None)
    name = cp.name if cp else counterparty_id
    record = _contract(store, counterparty_id)
    pending_docs = [r.id for r in store.contract_records() if r.kind == DocumentKind.BUYER_CONTRACT
                    and r.counterparty_id == counterparty_id and r.status == DocumentStatus.PROPOSED]
    base: dict[str, Any] = {"counterparty_id": counterparty_id, "counterparty_name": name, "day": day,
                            "has_contract": record is not None, "pending_documents": pending_docs}
    if record is None:
        return base
    anchor = state.as_of
    implied = buyer_terms(record.contract, counterparty_id, anchor) if record.contract else None
    assert implied is not None
    commitments = [c for c in store.commitments() if c.counterparty_id == counterparty_id]
    rec = reconcile(store, day=day)
    mine = {r.id for r in state.receivables if r.counterparty_id == counterparty_id}
    receipts = [m for m in rec.receipts if m.receivable_id in mine and m.status.value != "UNMATCHED"]
    promised = [p for p in rec.promised if p.counterparty_id == counterparty_id]
    invoices = _invoices(store, state, counterparty_id, day, receipts)
    entries, _ = read_entries(store.operations())
    accepted_day = next((e.day for e in entries if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT")
                         and e.result.status.value == "EXECUTED"
                         and any(e.payload.get("offer_id") == c.offer_id for c in commitments)), None)
    signed = _one(record, F.SIGNED_DATE)
    duration = _one(record, F.DURATION)
    inv = _one(record, F.INVOICING)
    ref = _one(record, F.CONTRACT_REFERENCE)
    late = [i for i in invoices if i["status"] == "LATE"]
    waiting = sum(1 for i in invoices if i["status"] == "ADVANCE_WAITING")
    pills = ([{"label": "Payment overdue", "tone": "bad"}] if late else []) + (
        [{"label": f"{waiting} approval{'s' if waiting > 1 else ''} waiting", "tone": "warn"}] if waiting else [])
    nxt_ri = next((r for r in state.recurring_invoices if r.counterparty_id == counterparty_id), None)
    base.update({
        "label": CONFIRMED_LABEL,
        "contract": {
            "record_id": record.id, "title": record.title, "reference": ref.text if ref else None,
            "signed_display": date_display(signed.date) if signed and signed.date else None,
            "signed_day": day_of(signed.date, anchor) if signed and signed.date else None,
            "term_display": f"{duration.months} months" if duration and duration.months else None,
            "cadence_display": (f"an invoice every {inv.days} days" if inv and inv.days else "monthly invoices"
                                if inv else None),
            "end_day": implied.end_day, "confirmed_day": record.decided_day,
        },
        "pills": pills or [{"label": "On track", "tone": "ok"}],
        "stages": _stages(record, invoices, promised, receipts, implied, day, accepted_day),
        "contract_terms": [term_view(t, anchor) for f in SHOWN_TERMS for t in _terms(record, f)],
        "blanks": [b for b in record_summary_blanks(record) if b["field"] in {f.value for f in SHOWN_TERMS}],
        "changes": _changes(store, state, counterparty_id, record, commitments, receipts),
        "in_force": _in_force(state, counterparty_id, record, implied, commitments),
        "invoices": invoices,
        "next_invoice": ({"day": nxt_ri.next_issue_day, "amount_display": fmt_yuan(nxt_ri.face_fen)}
                         if nxt_ri is not None else None),
        "owed_by_us": {
            "display_only": True,
            "deliverables": [{"text": t.text, "clause": t.clause, "quote": t.span.text}
                             for t in _terms(record, F.DELIVERABLE)],
            "documents": [{"text": t.text, "clause": t.clause, "quote": t.span.text}
                          for t in _terms(record, F.REQUIRED_DOCUMENT)],
        },
        "checks": _checks(state, counterparty_id, record, implied, commitments),
        "next_action": _next_action(invoices, store, state, day, counterparty_id),
    })
    return base


def record_summary_blanks(record: ContractRecord) -> list[dict[str, Any]]:
    from app.contracts import blanks

    return blanks(record)


def deals(store: LedgerStore, day: int) -> list[dict[str, Any]]:
    """Every buyer on the registry: a full summary where a contract is confirmed, a placeholder otherwise."""
    state = store.get_state()
    out = []
    for c in state.counterparties:
        if c.role == "BUYER":
            out.append(deal_summary(store, c.id, day))
    return out


def documents_for(store: LedgerStore) -> list[dict[str, Any]]:
    state = store.get_state()
    return [record_summary(r, state) for r in store.contract_records()]


_BASIS_ZH = {"INVOICE": "发票日", "DELIVERY": "交货", "ACCEPTANCE": "验收", "MONTH_END": "开票当月月末"}
_FIELD_ZH = {"PRICE": "价格", "INVOICING": "开票", "PAYMENT_TERMS": "账期", "EARLY_PAYMENT": "提前付款",
             "MILESTONE": "阶段付款", "RETENTION": "质保金", "LATE_INTEREST": "逾期利息", "SCHEDULED_INVOICE": "约定发票"}
_STATUS_ZH = {"LATE": "已逾期", "ADVANCE_WAITING": "垫款待您批准", "FINANCED": "已融资", "DUE_TODAY": "今天到期",
              "NOT_DUE": "未到期"}


def _value_zh(t: dict[str, Any]) -> str:
    f = t["field"]
    if f == "PRICE":
        unit = {"PER_DELIVERY": "每批", "PER_UNIT": "单价", "PER_MONTH": "每月", "LUMP_SUM": "总价"}.get(t["unit"] or "", "")
        return f"{unit} {t['amount_display']}".strip()
    if f == "INVOICING":
        head = f"每 {t['days']} 天开票一次" if t["days"] else "每月开票"
        return head + (f"，首张为第 {t['day']} 天" if t["day"] is not None else "")
    if f == "PAYMENT_TERMS":
        return f"自{_BASIS_ZH.get(t['basis'] or '', '（未注明）')}起 {t['days']} 天"
    if f == "EARLY_PAYMENT":
        return f"买方可提前付款，折扣 {t['rate_display']}" + (f"，须在 {t['days']} 天内" if t["days"] is not None else "")
    if f == "SCHEDULED_INVOICE":
        return f"{t['reference'] or '发票'}：{t['amount_display'] or ''}，第 {t['day']} 天开具"
    return t["rate_display"] or t["value_display"]


def deal_reply(summary: dict[str, Any], lang: str = "en") -> str:
    """The deal summary as plain lines for the chat (SHOW_DEAL), from the summary's own strings and typed fields."""
    return _deal_reply_zh(summary) if lang == "zh" else _deal_reply_en(summary)


def _deal_reply_zh(summary: dict[str, Any]) -> str:
    name = summary["counterparty_name"]
    if not summary["has_contract"]:
        waiting = summary["pending_documents"]
        return (f"{name} 还没有经您确认的合同。" + (
            f"我已读取的 {len(waiting)} 份文件正等待您确认（{'、'.join(waiting)}）。" if waiting
            else "请上传已签署的合同，我会读取后交给您确认。"))
    c = summary["contract"]
    lines = [f"{name}：{c['title']}" + (f"，签署日 {c['signed_display']}" if c["signed_display"] else "")
             + "。由我读取，经您确认。"]
    terms = [f"{_FIELD_ZH.get(t['field'], t['label'])}：{_value_zh(t)}" + (f"（第 {t['clause']} 条）" if t["clause"] else "")
             for t in summary["contract_terms"]]
    if terms:
        lines.append("合同约定：" + "；".join(terms) + "。")
    owed = [f"{i['id']} {i['outstanding_display']}，第 {i['due_day']} 天到期，{_STATUS_ZH.get(i['status'], i['status_text'])}"
            for i in summary["invoices"] if i["status"] != "PAID"]
    lines.append("应收：" + ("；".join(owed) if owed else "无未收款项") + "。")
    warn = sum(1 for x in summary["checks"] if x["status"] == "warn")
    lines.append(f"合同核对：{warn} 项需要注意。" if warn else "合同核对：已约定的条件与合同一致。")
    steps = []
    for it in summary["next_action"]["items"]:
        if it["kind"] == "CHASE":
            steps.append(f"催收 {it['receivable_id']} 的 {it['amount_display']}（逾期 {it['late_days']} 天）")
        elif it["kind"] == "APPROVAL":
            floor = f"，以保持第 {it['floor_day']} 天现金不低于底线" if it["floor_day"] is not None else ""
            steps.append(f"审批 {it['approval_id']}：第 {it['issue_day']} 天发票的 {it['amount_display']} 垫款{floor}")
        else:
            steps.append("查看提醒")
    lines.append("下一步：" + ("；".join(steps) + "。" if steps else "今天这笔交易无需您处理。"))
    return "\n".join(lines)


def _deal_reply_en(summary: dict[str, Any]) -> str:
    name = summary["counterparty_name"]
    if not summary["has_contract"]:
        waiting = summary["pending_documents"]
        return (f"I have no confirmed contract for {name}. " + (
            f"{len(waiting)} document(s) I read for them are waiting for your confirmation ({', '.join(waiting)})."
            if waiting else "Upload the signed contract and I will read it for you to confirm."))
    c = summary["contract"]
    lines = [f"{name}: {c['title']}" + (f", signed {c['signed_display']}" if c["signed_display"] else "")
             + (f", {c['term_display']}" if c["term_display"] else "") + ". Read by me, confirmed by you."]
    terms = [f"{t['label']}: {t['value_display']}" + (f" (clause {t['clause']})" if t["clause"] else "")
             for t in summary["contract_terms"]]
    if terms:
        lines.append("The contract says: " + "; ".join(terms) + ".")
    force = [f"{r['label']} {r['value_display']}" + (" (same as the contract)" if r["vs_contract"] == "SAME"
                                                     else " (differs from the contract)" if r["vs_contract"] == "DIFFERENT"
                                                     else "") for r in summary["in_force"]]
    if force:
        lines.append("In force now: " + "; ".join(force) + ".")
    owed = [f"{i['id']} {i['outstanding_display']} due day {i['due_day']}, {i['status_text'].lower()}"
            for i in summary["invoices"] if i["status"] != "PAID"]
    lines.append("Owed to you: " + ("; ".join(owed) if owed else "nothing outstanding") + ".")
    warn = [x["text"] for x in summary["checks"] if x["status"] == "warn"]
    if warn:
        lines.append("Contract check: " + " ".join(warn))
    lines.append("Next: " + summary["next_action"]["text"])
    return "\n".join(lines)


__all__ = ["CONFIRMED_LABEL", "deal_reply", "deal_summary", "deals", "documents_for"]
