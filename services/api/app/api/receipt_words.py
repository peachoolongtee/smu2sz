"""The owner's words for a payment they record themself (POST /operations, RECEIVE_PAYMENT requested by the OWNER).

Presentation only: the executor has already booked the receipt (or refused it) when these words are written, and nothing here
changes the books. Every figure is read from the books just before and just after the receipt, under the same lock, so the
sentences say what the executor did: what reached the owner's cash, what went to the lender first on a financed invoice, what is
still open on the invoice, and how the reconciliation reads the receipt (INVARIANT 13: the web prints these sentences as they
are). English and Chinese.
"""

from __future__ import annotations

from typing import Any

from app.alerts import reconcile
from app.api.presentation import (
    business_text,
    executed_words,
    facility_name,
    invoice_words,
    party_name,
    reconciliation_words,
    t,
    when_text,
)
from app.domain.models import FinancialState
from app.domain.money import fmt_yuan


def _receivable(state: FinancialState, receivable_id: str) -> Any:
    return next((r for r in state.receivables if r.id == receivable_id), None)


def _lot(state: FinancialState, receivable_id: str) -> Any:
    return next((x for x in state.lots if x.receivable_id == receivable_id and x.remaining_fen > 0), None)


def _stop(text: str, lang: str) -> str:
    text = text.rstrip()
    end = "。" if lang == "zh" else "."
    return text if text.endswith((".", "。", "!", "?")) else text + end


def _lender_lines(before: FinancialState, after: FinancialState, rid: str, amount: int, today: int, lang: str) -> list[str]:
    """What the receipt did to the financing on the invoice, read from the advance lot before and after."""
    lot = _lot(before, rid)
    if lot is None:
        return []
    fac = facility_name(before, lot.facility_id)
    left = _lot(after, rid)
    if not lot.settled:  # the advance had not landed: the receipt is the owner's (ADR-0010)
        if left is None:
            return [t(lang, f"The advance of {fmt_yuan(lot.remaining_fen)} you asked {fac} for on this invoice had not landed yet, "
                            f"so it was cancelled with no charges and the room on {fac} is free again.",
                     f"您就此发票向{fac}申请的 {fmt_yuan(lot.remaining_fen)} 预付款尚未到账，已取消且不收取任何费用，{fac}的额度已释放。")]
        return [t(lang, f"The advance of {fmt_yuan(lot.remaining_fen)} you asked {fac} for on this invoice has not landed yet; "
                        f"it still lands {when_text(lot.arrival_day, today, lang)}. This payment is yours.",
                 f"您就此发票向{fac}申请的 {fmt_yuan(lot.remaining_fen)} 预付款尚未到账，仍将于{when_text(lot.arrival_day, today, lang)}到账。此笔付款归您所有。")]
    kept = after.cash_fen - before.cash_fen
    to_lender = amount - kept
    lines: list[str] = []
    if to_lender > 0 and kept > 0:
        lines.append(t(lang, f"{fmt_yuan(to_lender)} went to {fac} first, to repay the advance on this invoice; {fmt_yuan(kept)} reached your cash.",
                       f"其中 {fmt_yuan(to_lender)} 先用于偿还{fac}就此发票的预付款；{fmt_yuan(kept)} 进入您的现金。"))
    elif to_lender > 0:
        lines.append(t(lang, f"All {fmt_yuan(to_lender)} went to {fac} first, against the advance on this invoice; none of it reached your cash.",
                       f"全部 {fmt_yuan(to_lender)} 先用于偿还{fac}就此发票的预付款，未进入您的现金。"))
    if left is not None:
        r_after = _receivable(after, rid)
        settled = r_after is not None and r_after.status == "SETTLED"
        lines.append(t(lang, f"{fmt_yuan(left.remaining_fen)} of the advance is still owed to {fac}"
                             + ("; the invoice is paid, so you repay it to the lender directly." if settled else "; the invoice stays financed."),
                       f"仍欠{fac} {fmt_yuan(left.remaining_fen)} 预付款"
                       + ("；发票已付清，此款需由您直接偿还贷款方。" if settled else "；该发票仍处于融资状态。")))
    elif to_lender > 0:
        lines.append(t(lang, f"The advance from {fac} on this invoice is repaid in full.", f"{fac}就此发票的预付款已全部还清。"))
    return lines


def _residual_line(before: FinancialState, after: FinancialState, rid: str, today: int, lang: str) -> str | None:
    r = _receivable(after, rid)
    if r is None:
        return None
    invoice = invoice_words(before, rid, lang)
    if r.status == "SETTLED" or r.outstanding_fen <= 0:
        return t(lang, f"{invoice[:1].upper() + invoice[1:]} is paid in full.", f"{invoice}已全部付清。")
    return t(lang, f"{fmt_yuan(r.outstanding_fen)} is still open on {invoice}, due {when_text(r.due_day, today, lang)}.",
             f"{invoice}仍有 {fmt_yuan(r.outstanding_fen)} 未付，{_due_zh(r.due_day, today)}。")


def _due_zh(due_day: int, today: int) -> str:
    """"32 天后到期" / "今天到期" / "3 天前已到期" (the Chinese order of the due clause)."""
    when = when_text(due_day, today, "zh")
    return f"{when}已到期" if due_day < today else f"{when}到期"


def _reconciliation_line(rt: Any, after: FinancialState, op_id: str, today: int, lang: str) -> str | None:
    """How the reconciliation reads this receipt: the sentence the Reconciliation page shows for it, as a full sentence (the web puts its own
    "Reconciliation" label before it)."""
    try:
        report = reconcile(rt.store, day=today)
    except Exception:  # noqa: BLE001  the receipt is booked either way; the line is only left out
        return None
    row = next((x for x in report.receipts if x.op_id == op_id), None)
    if row is None:
        return None
    agreements = {c.id: party_name(after, c.counterparty_id) for c in rt.store.commitments()}
    said = reconciliation_words(after, row.detail, today, promise=False, lang=lang, agreements=agreements)
    if not said:
        return None
    return _stop(said[:1].upper() + said[1:] if lang != "zh" else said, lang)


def receipt_words(rt: Any, before: FinancialState, after: FinancialState, *, payload: dict[str, Any], result: dict[str, Any],
                  today: int, lang: str) -> dict[str, Any]:
    """{status, tone, headline_text, lines, reconciliation_text}: the answer the owner reads beside the form."""
    status = str(result.get("status") or "")
    rid = str(payload.get("receivable_id") or "")
    amount = int(payload.get("amount_fen") or 0)
    agreements = {c.id: party_name(before, c.counterparty_id) for c in rt.store.commitments()}
    words = executed_words(after if status == "EXECUTED" else before, payload=payload, result=result, today=today, lang=lang,
                           agreements=agreements)
    out: dict[str, Any] = {"status": status, "tone": "neutral", "headline_text": None, "lines": [], "reconciliation_text": None}
    if status == "EXECUTED":
        buyer = party_name(before, next((r.counterparty_id for r in before.receivables if r.id == rid), None))
        out["tone"] = "ok"
        out["headline_text"] = _stop(t(lang, f"Recorded: {fmt_yuan(amount)} received from {buyer}", f"已记录：收到{buyer}的 {fmt_yuan(amount)}")
                                     if buyer else t(lang, f"Recorded: {fmt_yuan(amount)} received", f"已记录：收到 {fmt_yuan(amount)}"), lang)
        lines = _lender_lines(before, after, rid, amount, today, lang)
        residual = _residual_line(before, after, rid, today, lang)
        if residual:
            lines.append(residual)
        lines.append(t(lang, f"Your cash is now {fmt_yuan(after.cash_fen)}.", f"您的现金现为 {fmt_yuan(after.cash_fen)}。"))
        out["lines"] = lines
        out["reconciliation_text"] = _reconciliation_line(rt, after, str(result.get("op_id") or payload.get("op_id") or ""), today, lang)
        return out
    if status == "DUPLICATE":
        out["tone"] = "info"
        out["headline_text"] = t(lang, "This payment was already recorded; nothing changed.", "此笔付款此前已记录，未作任何更改。")
        return out
    if status == "PENDING_APPROVAL":
        out["tone"] = "warn"
        out["headline_text"] = words.get("event_text") or t(lang, "Waiting for your approval.", "等待您批准。")
        return out
    # REFUSED: the executor's reason in the owner's words; nothing was booked.
    out["tone"] = "bad"
    out["headline_text"] = t(lang, "Nothing was recorded.", "未记录任何内容。")
    r = _receivable(before, rid)
    if r is not None and r.status in ("OPEN", "FINANCED") and 0 < r.outstanding_fen < amount:
        invoice = invoice_words(before, rid, lang)
        out["lines"] = [t(lang, f"{fmt_yuan(amount)} is more than the {fmt_yuan(r.outstanding_fen)} still open on {invoice}; "
                                f"enter at most {fmt_yuan(r.outstanding_fen)}.",
                          f"{fmt_yuan(amount)} 超过{invoice}尚未付清的 {fmt_yuan(r.outstanding_fen)}；请输入不超过 {fmt_yuan(r.outstanding_fen)} 的金额。")]
        return out
    if r is not None and (r.status not in ("OPEN", "FINANCED") or r.outstanding_fen <= 0):
        invoice = invoice_words(before, rid, lang)
        out["lines"] = [t(lang, f"{invoice[:1].upper() + invoice[1:]} is already paid in full.", f"{invoice}已全部付清。")]
        return out
    reason = str(result.get("message") or "").removeprefix("Refused: ").strip()
    why = business_text(before, reason, today, lang, agreements) if reason else None
    if why:
        out["lines"] = [_stop(why[:1].upper() + why[1:] if lang != "zh" else why, lang)]
    return out
