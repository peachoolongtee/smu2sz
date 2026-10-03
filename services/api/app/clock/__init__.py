"""The clock (ADR-0006 §2): the only way simulated time moves.

`advance(store, to_day, actor)` closes every day before `to_day` in one store transaction:
scheduled flows dated on those days are posted to cash, the existing debts' scheduled payments due on those days
are paid (`app.financial.debts`, the schedule the projection posts), recurring invoices issued on those days
become real receivables (with the accepted adjustments in scope written on them, ADR-0009), finite
adjustments whose invoices are all issued are consumed (an ACTIVE commitment left with nothing live becomes
FULFILLED once every invoice carrying its terms is SETTLED), commitments past their expiry are marked EXPIRED, `as_of_day` moves and
one ADVANCE_CLOCK entry goes on the hash-chained log. It never records a receipt: receipts come
only from the bank feed, which is what makes a missing one detectable.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from typing import Any

from app.commitments import CommitmentError, transition
from app.commitments.lifecycle import PRE_ACTIVE
from app.domain.models import (
    Actor,
    CashFlow,
    CommitmentStatus,
    Contingency,
    DebtPosition,
    Facility,
    FinancialState,
    FundingLot,
    ObligationType,
    OperationResult,
    OperationStatus,
    Receivable,
    Tier,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial.debts import debt_payments, first_payment_day
from app.financial.invoices import InvoiceRef, consumed, issue_terms, only_adjusting, recurring_receivable_id
from app.financial.lots import contractual_payments, ensure_lots, landing_cash
from app.persistence import canonical_json, is_retryable

ADVANCE_CLOCK_KIND = "ADVANCE_CLOCK"
_CAS_ATTEMPTS = 8  # a unit of work that lost a compare-and-swap runs again, at most this many times in all


@dataclass(frozen=True, slots=True)
class ClockAdvance:
    from_day: int
    to_day: int
    posted_flow_ids: list[str] = field(default_factory=list)
    posted_net_fen: int = 0
    skipped_unconfirmed_inflow_ids: list[str] = field(default_factory=list)
    issued_receivable_ids: list[str] = field(default_factory=list)
    expired_commitment_ids: list[str] = field(default_factory=list)
    added_flow_ids: list[str] = field(default_factory=list)
    result: OperationResult | None = None
    consumed_adjustment_ids: list[str] = field(default_factory=list)
    fulfilled_commitment_ids: list[str] = field(default_factory=list)
    settled_lot_ids: list[str] = field(default_factory=list)  # ADR-0010: funding whose cash landed
    posted_debt_payments: list[dict[str, Any]] = field(default_factory=list)  # instalments and maturities paid
    lots_net_fen: int = 0  # cash those moved: landings less payments
    posted_debt_service: list[dict[str, Any]] = field(default_factory=list)  # existing debts' scheduled payments
    debt_service_fen: int = 0  # the cash they took (positive)
    lapsed_commitment_ids: list[str] = field(default_factory=list)  # early-pay commitments ended (EXPIRED) on lapse

    @property
    def moved(self) -> bool:
        return self.to_day > self.from_day


def close_days(state: FinancialState, to_day: int) -> tuple[FinancialState, ClockAdvance]:
    """Pure: the state with every day before `to_day` closed, and what closing them did."""
    today = state.as_of_day
    if to_day <= today:
        return state, ClockAdvance(today, today)
    state = ensure_lots(state)  # ADR-0010: a balance no lot explains is dated today
    posted, skipped, kept, net = [], [], [], 0
    for fl in state.flows:
        if fl.day >= to_day or fl.day < today:
            kept.append(fl)  # still ahead (or already behind the books; the engine ignores it)
        elif fl.amount_fen > 0 and not fl.confirmed:
            skipped.append(fl.id)  # an unconfirmed inflow is never assumed to have arrived
        else:
            posted.append(fl.id)
            net += fl.amount_fen
    receivables, issued, recurring = list(state.receivables), [], []
    have = {r.id for r in receivables}
    for ri in state.recurring_invoices:
        d = ri.next_issue_day
        while ri.every_days > 0 and d < to_day:
            rid = recurring_receivable_id(ri.counterparty_id, d)
            if rid not in have:
                # ADR-0009: the accepted adjustments in scope are written onto the invoice as it is issued
                terms = issue_terms(state, InvoiceRef(rid, ri.counterparty_id, d), ri.face_fen, ri.terms_days)
                receivables.append(Receivable(id=rid, counterparty_id=ri.counterparty_id, issue_day=d,
                                              confirmed=True, **terms))  # type: ignore[arg-type]
                issued.append(rid)
            d += ri.every_days
        recurring.append(ri.model_copy(update={"next_issue_day": d}))
    # ADR-0009 §7: a finite adjustment whose every invoice is now issued is consumed
    ids = {r.id for r in receivables}
    done = [a for a in state.invoice_adjustments if consumed(a, ids, to_day)]
    left = [a for a in state.invoice_adjustments if a not in done]
    lots, facilities, settled, payments, bank = _close_lots(state, to_day)
    debts, serviced, service = _close_debts(state.debts, today, to_day)
    new = state.model_copy(update={"cash_fen": state.cash_fen + net + bank - service, "flows": kept,
                                   "receivables": receivables, "recurring_invoices": recurring, "as_of_day": to_day,
                                   "invoice_adjustments": left, "state_version": state.state_version + 1,
                                   "lots": lots, "facilities": facilities, "debts": debts})
    return new, ClockAdvance(today, to_day, posted, net, skipped, issued,
                             consumed_adjustment_ids=[a.id for a in done], settled_lot_ids=settled,
                             posted_debt_payments=payments, lots_net_fen=bank, posted_debt_service=serviced,
                             debt_service_fen=service)


def _close_debts(debts: list[DebtPosition], today: int,
                 to_day: int) -> tuple[list[DebtPosition], list[dict[str, Any]], int]:
    """The existing debts' scheduled payments on the days being closed (`debt_payments`, the projection's schedule):
    cash out, principal down, the next payment day moved past the closed days. Returns (debts, payments, cash paid)."""
    out: list[DebtPosition] = []
    paid: list[dict[str, Any]] = []
    cash = 0
    for dbt in debts:
        pays = debt_payments(dbt, today, to_day)
        if not pays and dbt.next_payment_day >= to_day:
            out.append(dbt)
            continue
        for p in pays:
            cash += p.amount
            paid.append({"debt_id": dbt.id, "day": p.day, "principal_fen": p.principal, "interest_fen": p.interest})
        principal = pays[-1].remaining if pays else dbt.principal_fen
        out.append(dbt.model_copy(update={"principal_fen": principal,
                                          "next_payment_day": first_payment_day(dbt, to_day)}))
    return out, paid, cash


def _close_lots(state: FinancialState, to_day: int) -> tuple[list[FundingLot], list[Facility], list[str],
                                                              list[dict[str, Any]], int]:
    """ADR-0010 §2, §4: the simulated bank on the days being closed. A lot whose arrival day is closed lands (its
    cash, net of the upfront fee); the contractual payments falling on closed days (amortising instalments, a bullet
    term loan's maturity) are paid, reducing the lot and the facility's drawn balance. A credit line is never repaid
    here (its repayment is discretionary) and an invoice advance is repaid when its receipt is recorded.
    Returns (lots, facilities, settled lot ids, posted payments, net cash)."""
    fac = {f.id: f for f in state.facilities}
    drawn = {f.id: f.drawn_fen for f in state.facilities}
    lots: list[FundingLot] = []
    settled: list[str] = []
    payments: list[dict[str, Any]] = []
    cash = 0
    for lot in state.lots:
        f = fac.get(lot.facility_id)
        if f is None:
            lots.append(lot)
            continue
        if not lot.settled and lot.arrival_day < to_day:
            cash += landing_cash(f, lot)
            lot = lot.model_copy(update={"settled": True})
            settled.append(lot.id)
        if lot.settled:
            remaining = lot.remaining_fen
            for p in contractual_payments(lot, f):
                if p.day >= to_day:
                    break
                cash -= p.principal + p.interest
                remaining -= p.principal
                drawn[f.id] -= p.principal
                payments.append({"lot_id": lot.id, "facility_id": f.id, "day": p.day, "principal_fen": p.principal,
                                 "interest_fen": p.interest})
            lot = lot.model_copy(update={"remaining_fen": remaining})
        if lot.remaining_fen > 0:
            lots.append(lot)
    facilities = [f.model_copy(update={"drawn_fen": drawn[f.id]}) if drawn[f.id] != f.drawn_fen else f
                  for f in state.facilities]
    return lots, facilities, settled, payments, cash


def _fulfil(store: LedgerStore, state: FinancialState, consumed_ids: Sequence[str],
            to_day: int) -> tuple[FinancialState, list[str]]:
    """ADR-0009 §7 (amended 3 Oct, red team F7): an ACTIVE commitment with no adjustment left and nothing else live
    becomes FULFILLED, and its forward concession leaves the state, once every invoice in its scope is SETTLED (the
    concession has then been paid away). Until then it still counts against the caps, so an agreement split into
    one-invoice agreements over time cannot release its cap room as each invoice is issued.

    The scope of a consumed adjustment is read from the invoices themselves: every receivable whose `applied` holds
    `<commitment id>:...` carries it, so no extra record is kept. A commitment none of whose invoices carries it (only
    contingent gains, never written) is fulfilled when its adjustments are consumed, as before."""
    left = {a.commitment_id for a in state.invoice_adjustments}
    fulfilled: list[str] = []
    for c in store.commitments():
        # an early payment already received on time (red team d, F5) no longer keeps the commitment live
        rest = c.model_copy(update={"obligations": [o for o in c.obligations if o.id not in c.settled_obligations]})
        if c.status != CommitmentStatus.ACTIVE or c.id in left or not only_adjusting(rest):
            continue
        written = [r for r in state.receivables if any(i.startswith(f"{c.id}:") for i in r.applied)]
        if not written and not any(i.startswith(f"{c.id}:") for i in consumed_ids):
            continue
        if any(r.status != "SETTLED" for r in written):
            continue  # a concession is still ahead on an invoice not yet paid
        try:
            store.put_commitment(transition(c, CommitmentStatus.FULFILLED, to_day))
        except CommitmentError:
            continue
        fulfilled.append(c.id)
    if fulfilled:
        state = state.model_copy(update={"forward_concessions": [
            fc for fc in state.forward_concessions if fc.commitment_id not in fulfilled]})
    return state, fulfilled


def _end_lapsed(store: LedgerStore, state: FinancialState, to_day: int) -> tuple[FinancialState, list[str]]:
    """Red team d, F3: a live commitment whose only obligations are early payments, every one of them either paid
    on time (`settled_obligations`) or lapsed on the books just closed (its day passed unpaid, or the invoice was
    settled otherwise), is over: it moves to EXPIRED with the lapsed obligation ids recorded on it, so the owner sees
    it ended and `current_books` keeps reporting what did not arrive. Its forward concession leaves the state, as on
    revocation. A commitment with any other obligation stays as it is (the owner may revoke it)."""
    from app.books import current_books  # the books module projects with the engine; imported where it is used

    commitments = store.commitments()
    lapsed: dict[str, list[str]] = {}
    for lp in current_books(state, commitments).lapsed:
        lapsed.setdefault(lp.commitment_id, []).append(lp.obligation.id)
    ended: list[str] = []
    for c in commitments:
        if c.status not in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE) or c.id not in lapsed:
            continue
        booked = [o for o in c.obligations
                  if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION and o.contingency != Contingency.CLAIMED_UNEVIDENCED]
        if not booked or any(o.type != ObligationType.IMMEDIATE_DISCOUNT or not o.base.receivable_id for o in booked):
            continue
        if any(o.id not in lapsed[c.id] and o.id not in c.settled_obligations for o in booked):
            continue
        try:
            done = transition(c, CommitmentStatus.EXPIRED, to_day)
        except CommitmentError:
            continue
        store.put_commitment(done.model_copy(update={"lapsed_obligations": list(lapsed[c.id])}))
        ended.append(c.id)
    if ended:
        state = state.model_copy(update={"forward_concessions": [
            fc for fc in state.forward_concessions if fc.commitment_id not in ended]})
    return state, ended


def apply_events(state: FinancialState, to_day: int, events: Sequence[dict[str, Any]]) -> tuple[FinancialState, list[str]]:
    """Pure: scheduled flows the outside world added on the days being closed (ADD_FLOW events dated in
    [as_of_day, to_day)). A flow already on the books, or dated before its own event, is ignored."""
    have = {f.id for f in state.flows}
    added: list[CashFlow] = []
    for ev in events:
        if ev.get("type") != "ADD_FLOW" or not (state.as_of_day <= int(ev["day"]) < to_day):
            continue
        fl = CashFlow.model_validate_json(json.dumps(ev["flow"]))
        if fl.id in have or fl.day < int(ev["day"]):
            continue
        have.add(fl.id)
        added.append(fl)
    if not added:
        return state, []
    return state.model_copy(update={"flows": [*state.flows, *added]}), [f.id for f in added]


def advance(store: LedgerStore, to_day: int, actor: Actor = Actor.SYSTEM,
            events: Sequence[dict[str, Any]] = ()) -> ClockAdvance:
    """Move the books to `to_day`. A day already reached is a no-op (nothing logged). `events` are the
    scenario's dated outside-world events (new scheduled flows); they are applied before the days close.

    One unit of work, run through the same retry as an executor unit (`Executor._atomically`): the new books are
    written compare-and-swap on the version they were computed from, so a writer that committed first makes this
    unit keep nothing (`ConcurrentWriteConflict`) and it runs again on the books as they now are. A conflict that
    survives `_CAS_ATTEMPTS` runs is raised to the caller."""
    for attempt in range(_CAS_ATTEMPTS):
        try:
            return _advance_once(store, to_day, actor, events)
        except Exception as exc:
            if attempt == _CAS_ATTEMPTS - 1 or not is_retryable(exc):
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def _advance_once(store: LedgerStore, to_day: int, actor: Actor, events: Sequence[dict[str, Any]]) -> ClockAdvance:
    tx = getattr(store, "transaction", None)
    with tx() if callable(tx) else nullcontext():
        state = store.get_state()
        read_version = state.state_version
        if to_day <= state.as_of_day:
            return ClockAdvance(state.as_of_day, state.as_of_day)
        state, added = apply_events(state, to_day, events)
        new, adv = close_days(state, to_day)
        adv = replace(adv, added_flow_ids=added)
        expired = []
        for c in store.commitments():
            if c.status in PRE_ACTIVE and to_day > c.expires_day:
                try:
                    store.put_commitment(transition(c, CommitmentStatus.EXPIRED, to_day))
                    expired.append(c.id)
                except CommitmentError:
                    continue
        new, fulfilled = _fulfil(store, new, adv.consumed_adjustment_ids, to_day)
        new, lapsed = _end_lapsed(store, new, to_day)
        store.put_state(new, expected_version=read_version)
        op_id = f"clock-{adv.from_day}-{adv.to_day}"
        payload = {"kind": ADVANCE_CLOCK_KIND, "op_id": op_id, "from_day": adv.from_day, "to_day": adv.to_day,
                   "requested_by": actor.value, "day": adv.to_day, "posted_flow_ids": adv.posted_flow_ids,
                   "posted_net_fen": adv.posted_net_fen, "issued_receivable_ids": adv.issued_receivable_ids,
                   "expired_commitment_ids": expired, "added_flow_ids": adv.added_flow_ids}
        if adv.consumed_adjustment_ids or fulfilled:
            payload |= {"consumed_adjustment_ids": adv.consumed_adjustment_ids, "fulfilled_commitment_ids": fulfilled}
        if lapsed:  # red team d, F3: early-pay commitments ended because their early payments lapsed
            payload |= {"lapsed_commitment_ids": lapsed}
        if adv.settled_lot_ids:  # ADR-0010: like the ADR-0009 additions, only when there is something to say
            payload |= {"settled_lot_ids": adv.settled_lot_ids}
        if adv.posted_debt_payments:
            payload |= {"posted_debt_payments": adv.posted_debt_payments}
        if adv.settled_lot_ids or adv.posted_debt_payments:
            payload |= {"lots_net_fen": adv.lots_net_fen}
        if adv.posted_debt_service:  # the existing debts' scheduled payments, only when there are some
            payload |= {"posted_debt_service": adv.posted_debt_service, "debt_service_fen": adv.debt_service_fen}
        msg = (f"Clock moved from day {adv.from_day} to day {adv.to_day}: {len(adv.posted_flow_ids)} scheduled "
               f"flow(s) posted (net {fmt_yuan(adv.posted_net_fen)}), {len(adv.issued_receivable_ids)} invoice(s) "
               f"issued, {len(expired)} commitment(s) expired"
               + (f", {len(adv.added_flow_ids)} new scheduled flow(s) recorded" if adv.added_flow_ids else "")
               + (f", {len(fulfilled)} commitment(s) fulfilled (every invoice carrying the accepted terms is settled)"
                  if fulfilled else "")
               + (f", {len(lapsed)} early-payment commitment(s) ended: the promised payment did not arrive "
                  f"({', '.join(lapsed)}, now EXPIRED)" if lapsed else "")
               + (f", {len(adv.settled_lot_ids)} funding request(s) landed" if adv.settled_lot_ids else "")
               + (f", {len(adv.posted_debt_payments)} loan payment(s) posted" if adv.posted_debt_payments else "")
               + (f" (funding net {fmt_yuan(adv.lots_net_fen)})"
                  if adv.settled_lot_ids or adv.posted_debt_payments else "")
               + (f", {len(adv.posted_debt_service)} existing-debt payment(s) posted "
                  f"({fmt_yuan(-adv.debt_service_fen)})" if adv.posted_debt_service else ""))
        result = OperationResult(op_id=op_id, kind=ADVANCE_CLOCK_KIND, status=OperationStatus.EXECUTED,
                                 tier=Tier.TIER_1, effective_day=adv.to_day, message=msg)
        rec = store.append_operation(op_id, ADVANCE_CLOCK_KIND, op_id, canonical_json(payload), canonical_json(result))
        result = result.model_copy(update={"seq": rec.seq, "entry_hash": rec.entry_hash, "prev_hash": rec.prev_hash})
        return replace(adv, expired_commitment_ids=expired, result=result, fulfilled_commitment_ids=fulfilled,
                       lapsed_commitment_ids=lapsed)


__all__ = ["ADVANCE_CLOCK_KIND", "ClockAdvance", "advance", "apply_events", "close_days"]
