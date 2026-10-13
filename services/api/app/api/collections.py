"""The collection handoff for one invoice (F15): GET /receivables/{receivable_id}/chase.

An honest handoff from the books alone: who owes what on which invoice, how late it is, what was promised early, the terms
in force on the invoice and a payment request the owner can copy and send elsewhere. Nothing is sent, stored or
invented (no buyer behaviour, no calendar date), no flag gates it and it writes nothing. The figures come from the stores and
the existing `reconcile()`; the words are written here in both languages. Owner only."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import reconcile
from app.api.auth import require_owner
from app.api.presentation import live_windows, party_name, t, when_text
from app.api.receipt import collection_receipt
from app.api.receipt_facts import window_open
from app.api.runtime import get_runtime
from app.domain.models import Commitment, FinancialState, Receivable
from app.domain.money import fmt_yuan

router = APIRouter(tags=["collections"], dependencies=[Depends(require_owner)])

Lang = Literal["en", "zh"]


def _days(n: int, lang: str) -> str:
    return t(lang, f"{n} day" if n == 1 else f"{n} days", f"{n} 天")


def _zh(when: str) -> str:
    """A Chinese distance set after a character: "2 天前" takes a space before its number, "昨天" does not."""
    return f" {when}" if when[:1].isdigit() else when


def _due_clause(due_day: int, today: int, lang: str) -> str:
    """The invoice's due day as a clause: "fell due 2 days ago", "is due today", "is due in 12 days"."""
    when = when_text(due_day, today, lang)
    if due_day < today:
        return t(lang, f"fell due {when}", f"已于{_zh(when)}到期")
    if due_day == today:
        return t(lang, "is due today", "今天到期")
    return t(lang, f"is due {when}", f"将于{_zh(when)}到期")


def _deadline(n: int, lang: str) -> str:
    """A deadline `n` days ahead (n >= 0) for a window that is open now."""
    if n == 0:
        return t(lang, "by today", "今天之内")
    if n == 1:
        return t(lang, "by tomorrow", "明天之内")
    return t(lang, f"within {n} days", f"{n} 天之内")


def _left_fen(commitments: list[Commitment], promise: Any) -> int | None:
    """What an open early-payment promise still covers: the agreed face less the part already paid early."""
    c = next((x for x in commitments if x.id == promise.commitment_id), None)
    ob = next((o for o in c.obligations if o.id == promise.obligation_id), None) if c is not None else None
    agreed = ob.base.amount_fen if ob is not None else None
    if not agreed:
        return None
    paid = promise.face_fen if promise.status.value == "RECEIVED" else 0
    return max(0, agreed - paid)


def _promise_row(p: Any, today: int, lang: str) -> dict[str, Any]:
    amount, face, when = fmt_yuan(p.expected_fen), fmt_yuan(p.face_fen), when_text(p.promised_day, today, lang)
    said = t(lang, f" {when}" if when else "", f"{when}约定付" if when else "约定付")
    status = p.status.value
    if status == "AWAITED":
        text = t(lang, f"{amount} for {face} of the invoice is promised{said}", f"{said} {amount}（对应发票的 {face}），尚未到账")
    elif status == "RECEIVED":
        text = t(lang, f"{amount} for {face} of the invoice was promised{said} and has arrived", f"{said}的 {amount}（对应发票的 {face}）已收到")
    elif status == "LAPSED":
        text = t(lang, f"{amount} for {face} of the invoice was promised{said} and did not arrive", f"{said}的 {amount}（对应发票的 {face}）没有到账")
    else:
        text = t(lang, f"{amount} for {face} of the invoice was promised{said}, but the invoice was settled another way",
                 f"{said}的 {amount}（对应发票的 {face}）没有按约到账，发票已另行结清")
    return {"status": status, "amount_display": amount, "face_display": face, "promised_when": when or None, "text": text}


def _request_text(*, buyer: str, r: Receivable, today: int, outstanding: str, window: str | None, lang: str) -> str:
    face, issued, due = fmt_yuan(r.face_fen), when_text(r.issue_day, today, lang), _due_clause(r.due_day, today, lang)
    after = r.settled_fen > 0
    if lang == "zh":
        owing = f"扣除已收款项后，尚有 {outstanding} 未付" if after else f"尚有 {outstanding} 未付"
        return (f"尊敬的{buyer}：{issued}开具的 {face} 发票{due}，{owing}。请确认付款日期。"
                f"按我们约定的账期（自开票日起 {r.terms_days} 天），应在到期日付款。{window or ''}谢谢。")
    owing = f"{outstanding} remains outstanding after the payments we have received" if after else f"{outstanding} remains outstanding"
    return (f"Dear {buyer}, the {face} invoice issued {issued} {due}; {owing}. Please confirm the payment date. "
            f"Our agreed payment terms are {r.terms_days} days from the invoice date. {window + ' ' if window else ''}Thank you.")


def chase_view(state: FinancialState, rt_store: Any, receivable: Receivable, today: int, lang: str) -> dict[str, Any]:
    """The handoff for one open invoice, from the books and one reconciliation."""
    commitments = list(rt_store.commitments())
    report = reconcile(rt_store, day=today)
    live = live_windows(report, commitments, state)
    buyer = party_name(state, receivable.counterparty_id)
    outstanding = fmt_yuan(receivable.outstanding_fen)
    late = max(0, today - receivable.due_day)
    if late > 0:
        lateness = _days(late, lang)
    else:
        lateness = t(lang, "Due today", "今天到期") if receivable.due_day == today else t(lang, "Not yet due", "未到期")
    promises = [p for p in report.promised if p.receivable_id == receivable.id]
    open_windows = [p for p in promises if window_open(p, live, today)]
    window_text: str | None = None
    if open_windows:
        p = open_windows[0]
        left = _left_fen(commitments, p)
        how = _deadline((p.promised_day or today) - today, lang)
        window_text = (t(lang, f"The early-payment arrangement is still open: up to {fmt_yuan(left)} of the invoice may be settled early {how}.",
                         f"提前付款安排仍有效：发票最多 {fmt_yuan(left)} 可在{how}提前结清。") if left
                       else t(lang, f"The early-payment arrangement is still open: the invoice may be settled early {how}.",
                              f"提前付款安排仍有效：发票可在{how}提前结清。"))
    facts: list[dict[str, str]] = [
        {"id": "buyer", "label": t(lang, "Buyer", "买方"), "value": buyer},
        {"id": "invoice", "label": t(lang, "Invoice", "发票金额"), "value": fmt_yuan(receivable.face_fen)},
        {"id": "outstanding", "label": t(lang, "Outstanding", "未付余额"), "value": outstanding},
        {"id": "issued", "label": t(lang, "Issued", "开票"), "value": when_text(receivable.issue_day, today, lang)},
        {"id": "due", "label": t(lang, "Due", "到期"), "value": when_text(receivable.due_day, today, lang)},
        {"id": "late", "label": t(lang, "Late by", "逾期"), "value": lateness},
        {"id": "terms", "label": t(lang, "Agreed terms on the invoice", "发票约定账期"), "value": _days(receivable.terms_days, lang)},
    ]
    rows = [_promise_row(p, today, lang) for p in promises]
    facts += [{"id": f"promise-{i}", "label": t(lang, "Early payment promised", "约定的提前付款"), "value": row["text"]} for i, row in enumerate(rows)]
    if window_text:
        facts.append({"id": "window", "label": t(lang, "Early-payment window", "提前付款期限"), "value": window_text})
    has_thread = any(c.counterparty_id == receivable.counterparty_id for c in commitments)
    return {
        "receivable_id": receivable.id,
        "buyer_name": buyer,
        "face_display": fmt_yuan(receivable.face_fen),
        "outstanding_display": outstanding,
        "issued_when": when_text(receivable.issue_day, today, lang),
        "due_when": when_text(receivable.due_day, today, lang),
        "past_due": late > 0,
        "late_days": late,
        "terms_days": receivable.terms_days,
        "promises": rows,
        "window_open": bool(open_windows),
        "facts": facts,
        "request_text": _request_text(buyer=buyer, r=receivable, today=today, outstanding=outstanding, window=window_text, lang=lang),
        "thread_href": f"/deals?buyer={quote(receivable.counterparty_id, safe='')}" if has_thread else None,
        "receipt": collection_receipt(
            lang, buyer=buyer, outstanding=outstanding, due_clause=_due_clause(receivable.due_day, today, lang), terms_days=receivable.terms_days,
            window_text=window_text, open_promise=next((r["text"] for r in rows if r["status"] in ("AWAITED", "LAPSED")), None)),
    }


@router.get("/receivables/{receivable_id}/chase")
def get_chase(receivable_id: str, lang: Lang = "en") -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        r = next((x for x in state.receivables if x.id == receivable_id), None)
        if r is None:
            raise HTTPException(404, detail={"code": "RECEIVABLE_NOT_FOUND", "receivable_id": receivable_id})
        if r.status not in ("OPEN", "FINANCED") or r.outstanding_fen <= 0:
            raise HTTPException(422, detail={"code": "NOTHING_OUTSTANDING", "receivable_id": receivable_id,
                                             "message": "This invoice has been paid; there is nothing to chase."})
        return chase_view(state, rt.store, r, rt.day, lang)
