"""Bind a compiled offer to the verified state: resolve what the compiler could not.

The compiler sees documents only, so it cannot know which receivable "this one" is, what the
buyer's current terms are, what a rebate's base is, or what a delivery change costs the supplier.
`bind()` resolves those from typed state rows (receivables, recurring invoices, expected orders) and
the owner's declared operational costs, and reports every decision as a `BindNote`. It reads typed
fields only, never span or document text (INVARIANT 2): a terms change binds from the compiler's
`days_delta`, or from its `target_terms_days` minus the ledger's current terms.
An unresolved material field makes the verdict UNRESOLVED_SCOPE (INVARIANT 10). An unresolved
reference ("as usual") is informational only and books nothing.

Claimed prior concessions are never bound or booked (INVARIANT 5); the security screen handles them.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    Contingency,
    DurationKind,
    FacilityKind,
    FinancialState,
    Obligation,
    ObligationType,
    Receivable,
    RecurringInvoice,
)
from app.domain.money import fmt_pct, fmt_yuan
from app.financial.invoices import terms_in_force
from app.financial.settlement import resolve_payment_day
from app.verifier.models import BindNote

DEFAULT_EARLY_PAY_LEAD_DAYS = 2  # the engine's default when the buyer has no early-pay facility
QUARTER_DAYS = 90
REBATE_PERIOD_DAYS = 365  # the rebate period an expected order must overlap (see _expected_order_base)

# Owner-declared keys (fixture `declared_costs`). A value is an int, or a {counterparty_id: int} map. They
# cover only what the ledger cannot know: the supplier's own operational cost per event.
PER_EVENT_COST_KEYS = ("per_event_cost_fen", "shipment_cost_fen")
EVENTS_PER_YEAR_KEYS = ("events_per_year", "shipments_per_year")


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
    """Settlement DAY of an early payment requested today: today (`state.as_of_day`) + the buyer's early-pay lead
    time (mirrors the engine's default). Day 0 gives the lead time itself."""
    eps = [f for f in state.facilities if f.kind == FacilityKind.BUYER_EARLY_PAY]
    lead = next((f.lead_time_days for f in eps if f.lender_id == counterparty_id),
                eps[0].lead_time_days if eps else DEFAULT_EARLY_PAY_LEAD_DAYS)
    return state.as_of_day + lead


def _drop(unresolved: list[str], *keys: str) -> list[str]:
    return [u for u in unresolved if u not in keys]


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
        if ob.payment_timing is not None:
            day = resolve_payment_day(ob.payment_timing, self.state.as_of)
            if (day is None or ob.payment_timing.reference_day > self.state.as_of_day
                    or day < self.state.as_of_day or day >= receivable.due_day
                    or ob.effective_day is not None and ob.effective_day != day):
                self.note(ob, "payment_timing", False, True,
                          "settlement date is invalid, stale, not early, or inconsistent; clarification needed")
                return ob
            upd["effective_day"] = day
            self.note(ob, "effective_day", True, True,
                      f"stated settlement resolves from message day {ob.payment_timing.reference_day} to books day {day}; "
                      "payment remains a promise until a bank-feed receipt")
        elif ob.effective_day is None:
            upd["effective_day"] = early_pay_lead(self.state, cp)
        if ob.rate_bp is None and ob.amount_fen is None:
            self.note(ob, "rate_bp", False, True, "immediate discount without a rate or amount")
        elif ob.rate_bp is None:
            # A fixed sum ("take ¥8,000 off") is tested at its exact rate on the portion it applies to
            # (mandate.predicates.discount_rate); the sum itself stays the booked amount.
            sum_fen = ob.amount_fen or 0
            if sum_fen <= 0 or sum_fen >= amount:
                self.note(ob, "amount_fen", False, True,
                          f"a discount of {fmt_yuan(sum_fen)} on {fmt_yuan(amount)} of {receivable.id} is not a "
                          f"discount on that portion")
                return ob
            self.note(ob, "rate_bp", True, True,
                      f"fixed-sum discount {fmt_yuan(sum_fen)} on {fmt_yuan(amount)} of {receivable.id} = exact rate "
                      f"{fmt_pct(Fraction(sum_fen, amount), 4)}")
        return ob.model_copy(update=upd)

    def terms(self, ob: Obligation) -> Obligation:
        if ob.days_delta is not None:
            return ob.model_copy(update={"unresolved": _drop(ob.unresolved, "current_terms_days")})
        target = ob.target_terms_days
        if target is None:
            self.note(ob, "days_delta", False, True, "the offer states neither a terms change nor target terms")
            return ob
        rec = recurring_for(self.state, ob.counterparty_id)
        current: int | None = None
        source = ""
        if ob.base.receivable_id is not None:
            r = next((r for r in self.state.receivables if r.id == ob.base.receivable_id), None)
            if r is not None:
                current, source = r.terms_days, f"receivable {r.id}"
        elif rec is not None:
            # the terms in force for the buyer's next invoice (accepted adjustments applied), never the template's
            # base terms: a second agreement must not stack on the first (fifth red team, F2)
            current = terms_in_force(self.state, ob.counterparty_id)
            source = (f"recurring invoice to {ob.counterparty_id}" if current == rec.terms_days else
                      f"terms in force for the next invoice to {ob.counterparty_id} (base {rec.terms_days} days)")
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
        found = self._expected_order_base(ob)
        if found is not None:
            base_amount, message = found
            self.note(ob, "base.amount_fen", True, True, message)
        else:
            rec = recurring_for(self.state, ob.counterparty_id)
            if rec is None or rec.every_days <= 0:
                self.note(ob, "base.amount_fen", False, True,
                          f"rebate base is not stated, {ob.counterparty_id} has no expected order in the rebate "
                          f"period and the ledger has no recurring invoice to estimate it from")
                return ob
            n = max(1, QUARTER_DAYS // rec.every_days)
            base_amount = n * rec.face_fen
            self.note(ob, "base.amount_fen", True, True,
                      f"rebate base not stated and no expected order of {ob.counterparty_id} in the rebate period: "
                      f"conservative estimate {n} × {fmt_yuan(rec.face_fen)} = {fmt_yuan(base_amount)} "
                      f"(a quarter of the ledger's invoicing to {ob.counterparty_id})")
        return ob.model_copy(update={
            "base": ob.base.model_copy(update={"kind": BaseKind.PERIOD_PURCHASES, "amount_fen": base_amount}),
            "unresolved": _drop(ob.unresolved, "base_amount", "base"),
        })

    def _expected_order_base(self, ob: Obligation) -> tuple[int, str] | None:
        """The rebate base from the counterparty's expected orders (typed state rows, never text).

        The compiler never computes days, so it cannot place "next quarter" on the day axis: the rebate
        period is the year from the rebate's `effective_day`, or from the day after the offer. A one-off
        rebate binds to the largest single order overlapping that period; a recurring rebate to all of them.
        An order that is not firm is still counted in full (contingent concessions at maximum, INVARIANT 5).
        """
        start = ob.effective_day if ob.effective_day is not None else self.offer.received_day + 1
        end = start + REBATE_PERIOD_DAYS - 1
        orders = sorted(
            (o for o in self.state.expected_orders
             if o.counterparty_id == ob.counterparty_id and o.start_day <= end and o.end_day >= start),
            key=lambda o: (-o.amount_fen, o.start_day, o.label),
        )
        if not orders:
            return None
        chosen = orders[:1] if ob.duration.kind == DurationKind.ONE_OFF else orders
        amount = sum(o.amount_fen for o in chosen)
        described = ", ".join(
            f"{o.label} (days {o.start_day}–{o.end_day}) {fmt_yuan(o.amount_fen)}{'' if o.firm else ', not firm'}"
            for o in chosen)
        counted = "" if all(o.firm for o in chosen) else "; counted at maximum"
        return amount, f"rebate base: expected order of {ob.counterparty_id}: {described}{counted}"

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
