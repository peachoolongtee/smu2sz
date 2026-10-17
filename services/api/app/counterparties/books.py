"""A simulated buyer fitted to the books in use.

The fixture profiles (fixtures/counterparties/buyers.yaml) were written for the golden demo's buyers: BUYER-1 is Foshan Home Retail Co.
with invoice RCV-A of ¥420,000.00, BUYER-2 is Dongguan Office Supplies Ltd. Books the owner opened through setup reuse the ids BUYER-1,
BUYER-2, ... for their own customers, whose invoices are RCV-1-1 and so on. Without fitting, the simulated buyer's counter on those books
named the golden demo's invoice ("early settlement of invoice RCV-A (¥420,000.00) on day 2"), an invoice the owner never had.

`fitted_profile` keeps the fixture profile unchanged on the books it was written for (the same buyer name and, when it has one, its
invoice in the books): the golden demo's replies, transcripts and hashes stay as they were. On any other books it keeps the buyer's
behaviour (every rate gate, step and round, all in basis points) and moves what is about the golden invoice onto the books:

- the invoice: the one the supplier's counters settle early, else the buyer's open invoice falling due first (none: no early settlement);
- its words: the invoice by amount and the date it was sent, the settlement by its calendar date, as the message to the buyer names an
  invoice ("the ¥300,000.00 invoice dated 29 Sep 2026"); FLOW's ids mean nothing to the buyer and never reach the owner's text;
- the buyer's money thresholds (value of a payment day, the surplus it needs, the benefits it declared) in proportion to the size of
  the business with the owner (the invoice, else a quarter's purchases), and next quarter's purchases from the books' contract.

Hidden state is untouched by this: the fitted profile is still a `BuyerProfile`, which refuses to serialise (INVARIANTS 7).
Depends on `app.domain` only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from fractions import Fraction

from app.counterparties.profiles import BuyerProfile
from app.domain.models import CounterProposal, FinancialState, ObligationType, Receivable
from app.domain.money import fmt_yuan, post

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_QUARTER_DAYS = 91


def _dates(state: FinancialState, day: int) -> tuple[str, str]:
    """A simulated day as the owner's calendar ("29 Sep 2026", "2026年9月29日"), as `presentation._calendar` writes it."""
    d = date.fromisoformat(state.as_of) + timedelta(days=day)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}", f"{d.year}年{d.month}月{d.day}日"


def written_for(profile: BuyerProfile, state: FinancialState) -> bool:
    """True on the books the fixture profile was written for: the buyer of that id carries the profile's name and, when the profile
    names an invoice, the books hold it for that buyer."""
    party = next((c for c in state.counterparties if c.id == profile.counterparty_id), None)
    if party is None or party.name != profile.name:
        return False
    if profile.receivable_id is None:
        return True
    return any(r.id == profile.receivable_id and r.counterparty_id == profile.counterparty_id for r in state.receivables)


def _open(r: Receivable, buyer: str, today: int) -> bool:
    return r.counterparty_id == buyer and r.status == "OPEN" and r.outstanding_fen > 0 and r.due_day > today


def _invoice(state: FinancialState, buyer: str, today: int, counters: Sequence[CounterProposal]) -> Receivable | None:
    """The invoice the buyer would settle early: the one the supplier's counters name, else its open invoice falling due first."""
    held = {r.id: r for r in state.receivables if _open(r, buyer, today)}
    for c in counters:
        for o in c.obligations:
            if o.type is ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id in held:
                return held[o.base.receivable_id]
    return min(held.values(), key=lambda r: (r.due_day, r.id), default=None)


def _quarter_purchases(state: FinancialState, buyer: str) -> int:
    """A quarter of the buyer's purchases from the books: its repeating invoices over 91 days, else the invoices it has open."""
    contracts = [ri for ri in state.recurring_invoices if ri.counterparty_id == buyer and ri.every_days > 0]
    if contracts:
        return sum(post(Fraction(ri.face_fen * _QUARTER_DAYS, ri.every_days)) for ri in contracts)
    return sum(r.face_fen for r in state.receivables if r.counterparty_id == buyer and r.status in ("OPEN", "FINANCED"))


def fitted_profile(
    profile: BuyerProfile, state: FinancialState, today: int, counters: Sequence[CounterProposal] = ()
) -> BuyerProfile:
    """The fixture profile on the books it was written for; on any other books, the same buyer fitted to them (module docstring)."""
    if written_for(profile, state):
        return profile
    buyer = profile.counterparty_id
    invoice = _invoice(state, buyer, today, counters) if profile.receivable_id is not None else None
    purchases = _quarter_purchases(state, buyer)
    if invoice is not None and profile.invoice_face_fen:
        k = Fraction(invoice.outstanding_fen, profile.invoice_face_fen)
    elif purchases and profile.next_quarter_purchases_fen:
        k = Fraction(purchases, profile.next_quarter_purchases_fen)
    else:
        k = Fraction(1)
    update: dict[str, object] = {
        "payment_day_value_fen": post(profile.payment_day_value_fen * k),
        "min_surplus_fen": post(profile.min_surplus_fen * k),
        "declared_benefits": [b.model_copy(update={"value_fen": post(b.value_fen * k)}) for b in profile.declared_benefits],
        "next_quarter_purchases_fen": purchases or post(profile.next_quarter_purchases_fen * k),
        "early_settlement_day": max(today, 0) + profile.early_settlement_day,
    }
    if invoice is None:
        update |= {"receivable_id": None, "invoice_face_fen": 0, "invoice_due_day": None, "invoice_words": None, "settle_words": None}
    else:
        sent_en, sent_zh = _dates(state, invoice.issue_day)
        settle_en, settle_zh = _dates(state, max(today, 0) + profile.early_settlement_day)
        face, owed = fmt_yuan(invoice.face_fen), fmt_yuan(invoice.outstanding_fen)
        if invoice.settled_fen:
            words = {"en": f"the {owed} still owed on the {face} invoice dated {sent_en}", "zh": f"{sent_zh}开具的 {face} 发票尚欠的 {owed}"}
        else:
            words = {"en": f"the {face} invoice dated {sent_en}", "zh": f"{sent_zh}开具的 {face} 发票"}
        update |= {"receivable_id": invoice.id, "invoice_face_fen": invoice.outstanding_fen, "invoice_due_day": invoice.due_day,
                   "invoice_words": words, "settle_words": {"en": settle_en, "zh": settle_zh}}
    return profile.model_copy(update=update)
