"""The buying side of Deals (ADR-0013, phase 8): one row per capex contract, where it stands and the one thing to do next.

Read only and composed from what already exists: the contract record (its reading and the owner's decision), the queued
and executed CommitPurchase operations, and the books' own CAPEX flows (a flow the clock has paid is no longer on the
books; the ADVANCE_CLOCK entries name it). The committed schedule is derived again from the record and the committed
timeline, by the same code that booked it, so the row never holds a second copy of the payments.

Stages: REVIEW (the reading waits for the owner), READY (confirmed; evaluate it and commit), AWAITING_APPROVAL (a commitment
is queued for the owner), COMMITTED (payments booked, some still ahead), PAID (every booked payment paid), REJECTED.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from app.api.presentation import Lang, t, when_text
from app.capex.schedule import Timeline, derive_schedule, early_schedule
from app.domain.models import ContractField, ContractRecord, DocumentKind, DocumentStatus, FlowKind
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.operations.log import read_entries
from app.persistence import ApprovalStatus

Stage = Literal["REVIEW", "READY", "AWAITING_APPROVAL", "COMMITTED", "PAID", "REJECTED"]
_TIMELINE = ("signing_day", "delivery_day", "acceptance_day", "invoice_day", "retention_release_day")


def _price(rec: ContractRecord) -> int | None:
    c = rec.contract
    return next((x.amount_fen for x in c.terms if x.field == ContractField.PRICE and x.amount_fen), None) if c else None


def _vendor_name(rec: ContractRecord, names: dict[str, str]) -> str:
    if rec.counterparty_id in names:
        return names[rec.counterparty_id]
    c = rec.contract
    party = next((x.text for x in c.terms if x.field == ContractField.PARTY_SUPPLIER and x.text), None) if c else None
    return party or rec.counterparty_id


def purchase_row(rec: ContractRecord, store: LedgerStore, today: int, lang: Lang = "en",
                 entries: list[Any] | None = None) -> dict[str, Any]:
    """The row of one capex contract. `entries` is the parsed log, when the caller already has it."""
    state = store.get_state()
    names = {c.id: c.name for c in state.counterparties}
    entries = entries if entries is not None else read_entries(store.operations())[0]
    committed = next((e for e in entries if e.kind == "COMMIT_PURCHASE" and e.result.status.value == "EXECUTED"
                      and e.payload.get("document_id") == rec.id), None)
    pending = next((a for a in store.approvals(ApprovalStatus.PENDING)
                    if a.kind == "COMMIT_PURCHASE" and json.loads(a.op_json).get("document_id") == rec.id), None)
    prefix = f"CAPEX:{rec.id}:"
    on_books = {f.id: f for f in state.flows if f.kind == FlowKind.CAPEX and f.id.startswith(prefix)}
    payments: list[dict[str, Any]] = []
    if committed is not None and rec.contract is not None:
        p = committed.payload
        timeline = Timeline(**{k: p.get(k) for k in _TIMELINE})
        derived = derive_schedule(rec.contract, timeline, anchor_iso=state.as_of, today=int(p.get("day", 0)))
        sched = derived.schedule
        if sched is not None and p.get("take_early_pay"):
            sched = early_schedule(sched)
        for x in sched.payments if sched is not None else []:
            fid = f"{prefix}{x.n}"
            paid = fid not in on_books and x.day < today
            payments.append({"n": x.n, "day": x.day, "amount_fen": x.amount_fen, "amount_display": fmt_yuan(x.amount_fen),
                             "label": x.label, "paid": paid, "when": when_text(x.day, today, lang)})
    if rec.status == DocumentStatus.REJECTED:
        stage: Stage = "REJECTED"
    elif rec.status == DocumentStatus.PROPOSED:
        stage = "REVIEW"
    elif committed is not None:
        stage = "PAID" if payments and all(x["paid"] for x in payments) else "COMMITTED"
    elif pending is not None:
        stage = "AWAITING_APPROVAL"
    else:
        stage = "READY"
    ahead = [x for x in payments if not x["paid"]]
    nxt = ahead[0] if ahead else None
    next_action = {
        "REVIEW": t(lang, "Review the agent's reading of the contract", "审核代理对合同的读取"),
        "READY": t(lang, "Choose the timeline and financing, then commit", "选择时间安排和融资方式，然后确定"),
        "AWAITING_APPROVAL": t(lang, "Approve the purchase commitment", "批准该采购承诺"),
        "COMMITTED": (t(lang, f"Next payment {nxt['amount_display']} {nxt['when']}", f"下一笔付款 {nxt['amount_display']}（{nxt['when']}）")
                      if nxt else t(lang, "Payments booked", "付款已入账")),
        "PAID": t(lang, "Every payment is paid", "所有付款已付清"),
        "REJECTED": t(lang, "You rejected the reading", "您已驳回该读取"),
    }[stage]
    price = _price(rec)
    return {
        "direction": "BUY", "document_id": rec.id, "title": rec.title, "vendor_id": rec.counterparty_id,
        "vendor_name": _vendor_name(rec, names), "vendor_registered": rec.counterparty_id in names,
        "document_status": rec.status.value, "stage": stage, "next_action": next_action,
        "price_fen": price, "price_display": fmt_yuan(price) if price is not None else None,
        "approval_id": pending.id if pending is not None else None,
        "committed_seq": committed.seq if committed is not None else None,
        "payments": payments,
        "paid_fen": sum(x["amount_fen"] for x in payments if x["paid"]),
        "to_pay_fen": sum(x["amount_fen"] for x in ahead),
        "paid_display": fmt_yuan(sum(x["amount_fen"] for x in payments if x["paid"])),
        "to_pay_display": fmt_yuan(sum(x["amount_fen"] for x in ahead)),
    }


def purchases(store: LedgerStore, today: int, lang: Lang = "en") -> list[dict[str, Any]]:
    """Every capex contract's row, newest first."""
    entries = read_entries(store.operations())[0]
    recs = [r for r in store.contract_records() if r.kind == DocumentKind.CAPEX_CONTRACT]
    return [purchase_row(r, store, today, lang, entries) for r in sorted(recs, key=lambda r: r.id, reverse=True)]


__all__ = ["purchase_row", "purchases"]
