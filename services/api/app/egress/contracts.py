"""Contract terms as protected values (brief 03 §6.4): a buyer's contract is that buyer's terms, a lender agreement is
that lender's, exactly like the books' own terms. Every record counts, read or confirmed: the document itself is
private whatever the owner decided about the reading.

What is protected from each record: amounts and rates, the payment days and the early-payment window days (matched next to the
owner's name, like the books' terms), the retention days and months, every date the contract states, the buyer's name as the
contract writes it, the contract reference, and the clauses' own words (each quote and each clause's text).

Who may be told: **a buyer may be told values from its own contract and never another counterparty's.** Every value is owned by
the counterparty the record is with, so a reply to that counterparty may state them (the guard's `entitled`), a reply to anyone
else may not, and the owner sees all. The supplier's own name in a contract is the sender's identity in every message and is not
protected.

`protected_for(store)` is the protected set every outbound text to a counterparty is scanned against: the books, the
mandate, the canaries and these contract values. Depends on `app.domain` only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from app.domain.models import ContractField, ContractRecord, Counterparty, FinancialState
from app.egress.protected import ProtectedSet, counterparty_aliases
from app.egress.values import Category, PrivateValue

T = Category.COUNTERPARTY_TERMS
_MIN_CLAUSE_CHARS = 12  # a shorter fragment is a common word, not the clause
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
           "December")


def date_forms(iso: str) -> tuple[str, tuple[str, ...]] | None:
    """The ISO date and the other ways a message may write it ("1 Sep 2026", "September 1, 2026", "2026年9月1日")."""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return None
    month = _MONTHS[d.month - 1]
    return iso, (f"{d.day} {month[:3]} {d.year}", f"{d.day} {month} {d.year}", f"{month} {d.day}, {d.year}",
                 f"{month[:3]} {d.day}, {d.year}", f"{d.year}/{d.month}/{d.day}", f"{d.year}/{d.month:02d}/{d.day:02d}",
                 f"{d.year}年{d.month}月{d.day}日")


def month_forms(months: int) -> tuple[str, tuple[str, ...]]:
    return f"{months} months", (f"{months}-month", f"{months} month", f"{months}个月")


def contract_private_values(records: Sequence[ContractRecord], state: FinancialState) -> list[PrivateValue]:
    known = {c.id: c for c in state.counterparties}
    out: list[PrivateValue] = []
    for r in records:
        owner = r.counterparty_id
        cp = known.get(owner) or Counterparty(id=owner, name=owner, role="BUYER")
        names, extra = counterparty_aliases(cp)
        p = f"contract.{r.id}"

        def terms(label: str, days: int, owner: str = owner, names: tuple[str, ...] = names,
                  extra: tuple[str, ...] = extra) -> None:
            if days > 0:
                out.append(PrivateValue.terms(label, days, owner=owner, aliases=(*names, *extra)))

        def words(label: str, text: str, *aliases: str, owner: str = owner, minimum: int = 3) -> None:
            if len(text.strip()) >= minimum:
                out.append(PrivateValue.text(label, text, owner=owner, aliases=aliases, category=T))

        for i, t in enumerate(r.contract.terms if r.contract else []):
            label = f"{p}.{t.field.value.lower()}.{i}"
            if t.amount_fen and t.amount_fen > 0:
                out.append(PrivateValue.money(f"{label}.amount", t.amount_fen, owner=owner, category=T))
            if t.rate_bp and t.rate_bp > 0:
                out.append(PrivateValue.rate_bp(f"{label}.rate", t.rate_bp, owner=owner, category=T))
            if t.field == ContractField.PAYMENT_TERMS and t.days and t.days > 0:
                terms(f"{label}.days", t.days)
            if t.field == ContractField.EARLY_PAYMENT and t.days:
                terms(f"{label}.window_days", t.days)
            if t.field == ContractField.RETENTION:
                terms(f"{label}.retention_days", t.days or 0)
                if t.months and t.months > 0:
                    value, aliases = month_forms(t.months)
                    words(f"{label}.retention_months", value, *aliases)
            if t.date and (forms := date_forms(t.date)) is not None:
                words(f"{label}.date", forms[0], *forms[1])
            if t.field == ContractField.CONTRACT_REFERENCE and t.text:
                words(f"{label}.text", t.text)
            elif t.field == ContractField.PARTY_BUYER and t.text:
                buyer_names, _ = counterparty_aliases(Counterparty(id=owner, name=t.text.strip(), role="BUYER"))
                words(f"{label}.party", buyer_names[0], *buyer_names[1:-1])  # the contract's name, and without its suffix
            elif t.text and t.field not in (ContractField.PARTY_SUPPLIER,):
                words(f"{label}.clause_text", t.text, minimum=_MIN_CLAUSE_CHARS)
            words(f"{label}.quote", t.span.text, minimum=_MIN_CLAUSE_CHARS)
        f = r.term_sheet.proposed_facility if r.term_sheet else None
        if r.term_sheet is not None:
            for i, cl in enumerate(r.term_sheet.clauses):
                words(f"{p}.clause.{i}.quote", cl.span.text, minimum=_MIN_CLAUSE_CHARS)
        if f is not None:
            for name, v in (("limit", f.limit_fen),):
                if v > 0:
                    out.append(PrivateValue.money(f"{p}.facility.{name}", v, owner=owner, category=Category.FACILITY))
            for name, bp in (("rate", f.rate_bp), ("fee", f.fee_bp_per_advance), ("upfront", f.upfront_fee_bp),
                             ("advance_rate", f.advance_rate_bp or 0)):
                if bp > 0:
                    out.append(PrivateValue.rate_bp(f"{p}.facility.{name}", bp, owner=owner, category=Category.FACILITY))
    return out


def protected_for(store: Any, *, extra_private: Sequence[PrivateValue] = ()) -> ProtectedSet:
    """The protected set for outbound text, built from the store's books, mandate and contract records."""
    state = store.get_state()
    records = getattr(store, "contract_records", None)
    contract_values = contract_private_values(records() if callable(records) else [], state)
    return ProtectedSet.build(state, store.get_mandate(), extra_private=[*contract_values, *extra_private])


__all__ = ["contract_private_values", "protected_for"]
