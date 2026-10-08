"""Contract terms as protected values (brief 03 §6.4): a buyer's contract is that buyer's terms, a lender agreement is
that lender's, exactly like the books' own terms. Every record counts, read or confirmed: the document itself is
private whatever the owner decided about the reading.

`protected_for(store)` is the protected set every outbound text to a counterparty is scanned against: the books, the
mandate, the canaries and these contract values. Depends on `app.domain` only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.models import ContractField, ContractRecord, Counterparty, FinancialState
from app.egress.protected import ProtectedSet, counterparty_aliases
from app.egress.values import Category, PrivateValue

T = Category.COUNTERPARTY_TERMS


def contract_private_values(records: Sequence[ContractRecord], state: FinancialState) -> list[PrivateValue]:
    known = {c.id: c for c in state.counterparties}
    out: list[PrivateValue] = []
    for r in records:
        owner = r.counterparty_id
        cp = known.get(owner) or Counterparty(id=owner, name=owner, role="BUYER")
        names, extra = counterparty_aliases(cp)
        p = f"contract.{r.id}"
        for i, t in enumerate(r.contract.terms if r.contract else []):
            label = f"{p}.{t.field.value.lower()}.{i}"
            if t.amount_fen and t.amount_fen > 0:
                out.append(PrivateValue.money(f"{label}.amount", t.amount_fen, owner=owner, category=T))
            if t.rate_bp and t.rate_bp > 0:
                out.append(PrivateValue.rate_bp(f"{label}.rate", t.rate_bp, owner=owner, category=T))
            if t.field == ContractField.PAYMENT_TERMS and t.days and t.days > 0:
                out.append(PrivateValue.terms(f"{label}.days", t.days, owner=owner, aliases=(*names, *extra)))
            if t.field == ContractField.CONTRACT_REFERENCE and t.text and len(t.text.strip()) >= 3:
                out.append(PrivateValue.text(f"{label}.text", t.text, owner=owner, category=T))
        f = r.term_sheet.proposed_facility if r.term_sheet else None
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
