"""Bind a compiled offer to the verified state: resolve what the compiler could not.

The compiler sees documents only, so it cannot know which receivable "this one" is, what the
buyer's current terms are, or what a delivery change costs the supplier. `bind()` resolves those
from typed state rows and the owner's declared values, and reports every decision as a `BindNote`.
An unresolved material field makes the verdict UNRESOLVED_SCOPE (INVARIANT 10). An unresolved
reference ("as usual") is informational only and books nothing.

Claimed prior concessions are never bound or booked (INVARIANT 5); the security screen handles them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    Contingency,
    FacilityKind,
    FinancialState,
    Obligation,
    ObligationType,
    Receivable,
    RecurringInvoice,
)
from app.domain.money import fmt_yuan
from app.verifier.models import BindNote

DEFAULT_EARLY_PAY_LEAD_DAYS = 2  # the engine's default when the buyer has no early-pay facility
QUARTER_DAYS = 90

# Owner-declared keys (fixture `declared_costs`). A value is an int, or a {counterparty_id: int} map.
PER_EVENT_COST_KEYS = ("per_event_cost_fen", "shipment_cost_fen")
EVENTS_PER_YEAR_KEYS = ("events_per_year", "shipments_per_year")
PERIOD_PURCHASES_KEYS = ("period_purchases_fen", "next_quarter_purchases_fen")

# A payment-terms length inside the obligation's own evidence span: "60 days", "30-day", "60天", "Net 60".
_DAYS = re.compile(r"(?i)(?<![\d.])(\d{1,3})\s*(?:-\s*)?(?:days?\b|天)|\bnet\s?(\d{1,3})\b")
_TARGET_KEY = re.compile(r"^target_terms_days[=:](\d{1,3})$")


def is_claimed(ob: Obligation) -> bool:
    return ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION or ob.contingency == Contingency.CLAIMED_UNEVIDENCED


def is_gain(ob: Obligation) -> bool:
    """A gain to the supplier: a shorter term or a price increase the buyer pays."""
    if ob.type == ObligationType.TERMS_EXTENSION:
        return (ob.days_delta or 0) < 0
    if ob.type == ObligationType.PRICE_ADJUSTMENT:
        return (ob.rate_bp or 0) > 0 or (ob.rate_bp is None and (ob.amount_fen or 0) > 0)
    return False


def _declared(owner_declared: Mapping[str, Any] | None, counterparty_id: str, keys: tuple[str, ...]) -> int | None:
    if not owner_declared:
        return None
    for k in keys:
        v = owner_declared.get(k)
        if isinstance(v, Mapping):
            v = v.get(counterparty_id)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    return None


def recurring_for(state: FinancialState, counterparty_id: str) -> RecurringInvoice | None:
    found = [r for r in state.recurring_invoices if r.counterparty_id == counterparty_id]
    return found[0] if len(found) == 1 else None


def open_receivables(state: FinancialState, counterparty_id: str) -> list[Receivable]:
    return [r for r in state.receivables if r.status == "OPEN" and r.counterparty_id == counterparty_id]


def early_pay_lead(state: FinancialState, counterparty_id: str) -> int:
    """Settlement day of an early payment requested today (mirrors the engine's default)."""
    eps = [f for f in state.facilities if f.kind == FacilityKind.BUYER_EARLY_PAY]
    for f in eps:
        if f.lender_id == counterparty_id:
            return f.lead_time_days
    return eps[0].lead_time_days if eps else DEFAULT_EARLY_PAY_LEAD_DAYS


def _target_terms_days(ob: Obligation) -> int | None:
    """The target payment terms a TERMS_EXTENSION names but the compiler could not turn into a delta.

    The compiler keeps the target only inside the obligation's evidence (its validated span, an exact
    substring of the source). This is the verifier's one read of span text: a single number of days,
    and nothing else. More than one distinct number, or none, is unresolved (INVARIANT 10).
    """
    for key in ob.unresolved:
        m = _TARGET_KEY.match(key)
        if m:
            return int(m.group(1))
    found: set[int] = set()
    for sp in ob.spans:
        for m in _DAYS.finditer(sp.text):
            found.add(int(m.group(1) or m.group(2)))
    return found.pop() if len(found) == 1 else None


def _drop(unresolved: list[str], *keys: str) -> list[str]:
    return [u for u in unresolved if u not in keys and not _TARGET_KEY.match(u)]


class _Binder:
    def __init__(self, offer: CompiledOffer, state: FinancialState, owner_declared: Mapping[str, Any] | None):
        self.offer = offer
        self.state = state
        self.declared = owner_declared
        self.notes: list[BindNote] = []

    def note(self, ob: Obligation | None, field: str, resolved: bool, material: bool, message: str) -> None:
        self.notes.append(BindNote(obligation_id=ob.id if ob else None, field=field, resolved=resolved,
                                   material=material, message=message))

    # ------------------------------------------------------------ per type

    def discount(self, ob: Obligation) -> Obligation:
        cp = ob.counterparty_id
        base = ob.base
        receivable: Receivable | None = None
        if base.receivable_id is not None:
            receivable = next((r for r in open_receivables(self.state, cp) if r.id == base.receivable_id), None)
            if receivable is None:
                self.note(ob, "base.receivable_id", False, True,
                          f"receivable {base.receivable_id} is not an open receivable of {cp}")
                return ob
        else:
            pool = open_receivables(self.state, cp)
            if base.amount_fen is not None:
                pool = [r for r in pool if r.face_fen == base.amount_fen]
            if len(pool) != 1:
                what = f"with face {fmt_yuan(base.amount_fen)}" if base.amount_fen is not None else ""
                self.note(ob, "base.receivable_id", False, True,
                          f"expected exactly one open receivable of {cp} {what}, found {len(pool)}".replace("  ", " "))
                return ob
            receivable = pool[0]
            how = f"face {fmt_yuan(base.amount_fen)}" if base.amount_fen is not None else "the only open receivable"
            self.note(ob, "base.receivable_id", True, True,
                      f"bound to {receivable.id} ({how}, due day {receivable.due_day})")
        amount = base.amount_fen if base.amount_fen is not None else receivable.face_fen
        if amount > receivable.face_fen:
            self.note(ob, "base.amount_fen", False, True,
                      f"{fmt_yuan(amount)} exceeds the open face of {receivable.id}")
            return ob
        upd: dict[str, Any] = {
            "base": base.model_copy(update={"kind": BaseKind.INVOICE, "receivable_id": receivable.id,
                                            "amount_fen": amount}),
            "unresolved": _drop(ob.unresolved, "receivable_id", "base_amount", "base"),
        }
        if ob.effective_day is None:
            upd["effective_day"] = early_pay_lead(self.state, cp)
        if ob.rate_bp is None and ob.amount_fen is None:
            self.note(ob, "rate_bp", False, True, "immediate discount without a rate or amount")
        return ob.model_copy(update=upd)

    def terms(self, ob: Obligation) -> Obligation:
        if ob.days_delta is not None:
            return ob.model_copy(update={"unresolved": _drop(ob.unresolved, "current_terms_days")})
        target = _target_terms_days(ob)
        if target is None:
            self.note(ob, "days_delta", False, True, "target payment terms could not be read as one number of days")
            return ob
        rec = recurring_for(self.state, ob.counterparty_id)
        current: int | None = None
        source = ""
        if ob.base.receivable_id is not None:
            r = next((r for r in self.state.receivables if r.id == ob.base.receivable_id), None)
            if r is not None:
                current, source = r.terms_days, f"receivable {r.id}"
        elif rec is not None:
            current, source = rec.terms_days, f"recurring invoice to {ob.counterparty_id}"
        if current is None:
            self.note(ob, "days_delta", False, True,
                      f"current terms of {ob.counterparty_id} are not in the ledger (no single recurring invoice)")
            return ob
        delta = target - current
        sign = "+" if delta >= 0 else "−"
        self.note(ob, "days_delta", True, True,
                  f"target {target} days − current {current} days ({source}) = {sign}{abs(delta)} days")
        if "end_date" in ob.unresolved:
            self.note(ob, "duration.end_day", False, False, "no grounded end date: treated as perpetual (conservative)")
        return ob.model_copy(update={"days_delta": delta, "unresolved": _drop(ob.unresolved, "current_terms_days")})

    def rebate(self, ob: Obligation) -> Obligation:
        if ob.amount_fen is not None or ob.base.amount_fen is not None:
            return ob.model_copy(update={"unresolved": _drop(ob.unresolved, "base_amount", "base")})
        if ob.rate_bp is None:
            self.note(ob, "rate_bp", False, True, "rebate without a rate or amount")
            return ob
        declared = _declared(self.declared, ob.counterparty_id, PERIOD_PURCHASES_KEYS)
        if declared is not None:
            self.note(ob, "base.amount_fen", True, True,
                      f"rebate base: owner-declared period purchases {fmt_yuan(declared)} (counted at maximum)")
            base_amount = declared
        else:
            rec = recurring_for(self.state, ob.counterparty_id)
            if rec is None or rec.every_days <= 0:
                self.note(ob, "base.amount_fen", False, True,
                          "rebate base is not stated, not declared by the owner and not derivable from the ledger")
                return ob
            n = max(1, QUARTER_DAYS // rec.every_days)
            base_amount = n * rec.face_fen
            self.note(ob, "base.amount_fen", True, True,
                      f"rebate base not stated or declared: conservative estimate {n} × {fmt_yuan(rec.face_fen)} "
                      f"= {fmt_yuan(base_amount)} (a quarter of the ledger's invoicing to {ob.counterparty_id})")
        return ob.model_copy(update={
            "base": ob.base.model_copy(update={"kind": BaseKind.PERIOD_PURCHASES, "amount_fen": base_amount}),
            "unresolved": _drop(ob.unresolved, "base_amount", "base"),
        })

    def operational(self, ob: Obligation) -> Obligation:
        cp = ob.counterparty_id
        amount = ob.amount_fen
        if amount is None:
            amount = _declared(self.declared, cp, PER_EVENT_COST_KEYS)
            if amount is None:
                self.note(ob, "amount_fen", False, True, "the supplier's cost per event has not been declared by the owner")
            else:
                self.note(ob, "amount_fen", True, True, f"owner-declared cost per event {fmt_yuan(amount)}")
        events = ob.base.events_per_year
        if events is None:
            events = _declared(self.declared, cp, EVENTS_PER_YEAR_KEYS)
            if events is None:
                self.note(ob, "base.events_per_year", False, True, "events per year have not been declared by the owner")
            else:
                self.note(ob, "base.events_per_year", True, True, f"owner-declared {events} events a year")
        if amount is None or events is None:
            return ob
        return ob.model_copy(update={
            "amount_fen": amount,
            "base": ob.base.model_copy(update={"kind": BaseKind.PER_EVENT, "events_per_year": events}),
            "unresolved": _drop(ob.unresolved, "per_event_cost_fen", "events_per_year"),
        })

    def price(self, ob: Obligation) -> Obligation:
        missing_base = ob.base.amount_fen is None and ob.base.receivable_id is None
        if not missing_base:
            return ob
        if ob.contingency != Contingency.FIRM and is_gain(ob):
            self.note(ob, "base", False, False, "contingent gain: counted as zero under conservative mode")
            return ob
        rec = recurring_for(self.state, ob.counterparty_id)
        if rec is None:
            if not is_gain(ob):
                self.note(ob, "base", False, True, "price change base is not stated and there is no recurring invoice")
            return ob
        self.note(ob, "base.amount_fen", True, not is_gain(ob),
                  f"price change applies to the recurring {fmt_yuan(rec.face_fen)} invoice to {ob.counterparty_id}")
        return ob.model_copy(update={
            "base": ob.base.model_copy(update={"amount_fen": rec.face_fen}),
            "unresolved": _drop(ob.unresolved, "base_amount", "base"),
        })

    # ------------------------------------------------------------ driver

    def run(self) -> list[Obligation]:
        out: list[Obligation] = []
        for ob in self.offer.obligations:
            if is_claimed(ob):
                self.note(ob, "contingency", False, False, "claimed prior concession: never bound or booked")
                continue
            match ob.type:
                case ObligationType.IMMEDIATE_DISCOUNT:
                    b = self.discount(ob)
                case ObligationType.TERMS_EXTENSION:
                    b = self.terms(ob)
                case ObligationType.CONTINGENT_REBATE:
                    b = self.rebate(ob)
                case ObligationType.OPERATIONAL_CONCESSION:
                    b = self.operational(ob)
                case ObligationType.PRICE_ADJUSTMENT:
                    b = self.price(ob)
                case _:
                    b = ob
            immaterial = b.contingency != Contingency.FIRM and is_gain(b)
            already = any(n.obligation_id == b.id and not n.resolved for n in self.notes)
            for key in [] if already else b.unresolved:
                if key == "end_date":
                    continue  # a bound that could not be grounded is treated as none (conservative)
                self.note(b, key, False, not immaterial and b.type != ObligationType.VOLUME_COMMITMENT,
                          f"unresolved: {key}")
            out.append(b)
        for a in self.offer.abstentions:
            if a.field == "unresolved_reference":
                self.note(None, "unresolved_reference", False, False,
                          "unresolved reference (e.g. \"as usual\"): the terms it points to are not in evidence; "
                          "nothing booked")
        return out


def bind(
    offer: CompiledOffer, state: FinancialState, owner_declared: Mapping[str, Any] | None = None
) -> tuple[list[Obligation], list[BindNote]]:
    """(bound bookable obligations, notes). Claimed prior concessions are left out."""
    binder = _Binder(offer, state, owner_declared)
    bound = binder.run()
    return bound, binder.notes


def material_gaps(notes: list[BindNote]) -> list[BindNote]:
    return [n for n in notes if n.material and not n.resolved]
