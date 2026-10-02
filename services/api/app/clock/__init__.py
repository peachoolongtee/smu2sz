"""The clock (ADR-0006 §2): the only way simulated time moves.

`advance(store, to_day, actor)` closes every day before `to_day` in one store transaction:
scheduled flows dated on those days are posted to cash, recurring invoices issued on those days
become real receivables (with the accepted adjustments in scope written on them, ADR-0009), finite
adjustments whose invoices are all issued are consumed (an ACTIVE commitment left with nothing live becomes
FULFILLED), commitments past their expiry are marked EXPIRED, `as_of_day` moves and
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
    FinancialState,
    OperationResult,
    OperationStatus,
    Receivable,
    Tier,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial.invoices import InvoiceRef, consumed, issue_terms, only_adjusting, recurring_receivable_id
from app.persistence import canonical_json

ADVANCE_CLOCK_KIND = "ADVANCE_CLOCK"


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

    @property
    def moved(self) -> bool:
        return self.to_day > self.from_day


def close_days(state: FinancialState, to_day: int) -> tuple[FinancialState, ClockAdvance]:
    """Pure: the state with every day before `to_day` closed, and what closing them did."""
    today = state.as_of_day
    if to_day <= today:
        return state, ClockAdvance(today, today)
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
    new = state.model_copy(update={"cash_fen": state.cash_fen + net, "flows": kept, "receivables": receivables,
                                   "recurring_invoices": recurring, "as_of_day": to_day,
                                   "invoice_adjustments": left, "state_version": state.state_version + 1})
    return new, ClockAdvance(today, to_day, posted, net, skipped, issued,
                             consumed_adjustment_ids=[a.id for a in done])


def _fulfil(store: LedgerStore, state: FinancialState, consumed_ids: Sequence[str],
            to_day: int) -> tuple[FinancialState, list[str]]:
    """ADR-0009 §7: an ACTIVE commitment with no adjustment left and nothing else live becomes FULFILLED, and its
    forward concession leaves the state (it is in the invoices now)."""
    left = {a.commitment_id for a in state.invoice_adjustments}
    fulfilled: list[str] = []
    for c in store.commitments():
        if c.status != CommitmentStatus.ACTIVE or c.id in left or not only_adjusting(c):
            continue
        if not any(i.startswith(f"{c.id}:") for i in consumed_ids):
            continue
        try:
            store.put_commitment(transition(c, CommitmentStatus.FULFILLED, to_day))
        except CommitmentError:
            continue
        fulfilled.append(c.id)
    if fulfilled:
        state = state.model_copy(update={"forward_concessions": [
            fc for fc in state.forward_concessions if fc.commitment_id not in fulfilled]})
    return state, fulfilled


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
    scenario's dated outside-world events (new scheduled flows); they are applied before the days close."""
    tx = getattr(store, "transaction", None)
    with tx() if callable(tx) else nullcontext():
        state = store.get_state()
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
        store.put_state(new)
        op_id = f"clock-{adv.from_day}-{adv.to_day}"
        payload = {"kind": ADVANCE_CLOCK_KIND, "op_id": op_id, "from_day": adv.from_day, "to_day": adv.to_day,
                   "requested_by": actor.value, "day": adv.to_day, "posted_flow_ids": adv.posted_flow_ids,
                   "posted_net_fen": adv.posted_net_fen, "issued_receivable_ids": adv.issued_receivable_ids,
                   "expired_commitment_ids": expired, "added_flow_ids": adv.added_flow_ids}
        if adv.consumed_adjustment_ids or fulfilled:
            payload |= {"consumed_adjustment_ids": adv.consumed_adjustment_ids, "fulfilled_commitment_ids": fulfilled}
        msg = (f"Clock moved from day {adv.from_day} to day {adv.to_day}: {len(adv.posted_flow_ids)} scheduled "
               f"flow(s) posted (net {fmt_yuan(adv.posted_net_fen)}), {len(adv.issued_receivable_ids)} invoice(s) "
               f"issued, {len(expired)} commitment(s) expired"
               + (f", {len(adv.added_flow_ids)} new scheduled flow(s) recorded" if adv.added_flow_ids else "")
               + (f", {len(fulfilled)} commitment(s) fulfilled (accepted terms now on every invoice in scope)"
                  if fulfilled else ""))
        result = OperationResult(op_id=op_id, kind=ADVANCE_CLOCK_KIND, status=OperationStatus.EXECUTED,
                                 tier=Tier.TIER_1, effective_day=adv.to_day, message=msg)
        rec = store.append_operation(op_id, ADVANCE_CLOCK_KIND, op_id, canonical_json(payload), canonical_json(result))
        result = result.model_copy(update={"seq": rec.seq, "entry_hash": rec.entry_hash, "prev_hash": rec.prev_hash})
        return ClockAdvance(adv.from_day, adv.to_day, adv.posted_flow_ids, adv.posted_net_fen,
                            adv.skipped_unconfirmed_inflow_ids, adv.issued_receivable_ids, expired,
                            adv.added_flow_ids, result, adv.consumed_adjustment_ids, fulfilled)


__all__ = ["ADVANCE_CLOCK_KIND", "ClockAdvance", "advance", "apply_events", "close_days"]
