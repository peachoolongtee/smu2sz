"""CAPEX-2 (a): what the owner is approving when a CommitPurchase waits on the Approvals queue, in the server's words.

The row of `GET /approvals/queue` for a COMMIT_PURCHASE gains, beside the usual fields:

    schedule_title   "What you are committing to"
    schedule_rows    [{label, value_text}]  the vendor, the document, each payment (amount and when), the early-payment choice
                     and the total, in that order; [] when the schedule cannot be shown
    schedule_note    null, or why the rows are empty / what differs ("The schedule has changed since this was requested ...")

The schedule is derived again here by code from the stored contract and the operation's own timeline (the way the executor
derives it); nothing is read from the requester's words. Written for `lang` through `t(lang, en, zh)` (INVARIANT 13): the browser
builds no sentence.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.api.presentation import Lang, party_name, t, when_text
from app.capex.schedule import Timeline, derive_schedule, early_schedule
from app.domain.models import ContractField, DocumentKind
from app.domain.money import BP_DENOM, fmt_pct, fmt_yuan

_KIND = {"MILESTONE": ("payment", "付款"), "PAYMENT_TERMS": ("payment", "付款"), "RETENTION": ("retention", "质保金")}


def _empty(title: str, note: str) -> dict[str, Any]:
    return {"schedule_title": title, "schedule_rows": [], "schedule_note": note}


def purchase_schedule_view(store: Any, state: Any, op: dict[str, Any], today: int, lang: Lang) -> dict[str, Any]:
    title = t(lang, "What you are committing to", "您将承诺的内容")
    rec = store.get_contract_record(str(op.get("document_id") or ""))
    if rec is None or rec.kind != DocumentKind.CAPEX_CONTRACT or rec.contract is None:
        return _empty(title, t(lang, "The contract this refers to cannot be found, so its payments cannot be shown.",
                               "找不到这项请求所指的合同，因此无法显示其付款。"))
    timeline = Timeline(**{k: op.get(k) for k in ("signing_day", "delivery_day", "acceptance_day", "invoice_day",
                                                  "retention_release_day")})
    derived = derive_schedule(rec.contract, timeline, anchor_iso=state.as_of, today=max(today, state.as_of_day))
    if not derived.derivable or derived.schedule is None:
        return _empty(title, t(lang, "No payment schedule follows from this contract on this timeline today, so approving it "
                                     "would be refused.",
                               "按今天的情况，这份合同在该时间安排下无法得出付款计划，批准将被拒绝。"))
    take = bool(op.get("take_early_pay"))
    option = derived.schedule.early_pay
    schedule = early_schedule(derived.schedule) if take else derived.schedule
    if schedule is None:
        return _empty(title, t(lang, "The contract offers no early-payment discount, so approving it would be refused.",
                               "合同没有提供提前付款折扣，批准将被拒绝。"))
    note = None
    if schedule.schedule_hash != op.get("schedule_hash"):
        note = t(lang, "The payments below are what the contract gives today. They differ from the schedule that was requested, "
                       "so approving it would be refused.",
                 "以下是合同今天得出的付款，与所请求的付款计划不一致，批准将被拒绝。")
    vendor = party_name(state, rec.counterparty_id)
    name = next((x.text for x in rec.contract.terms if x.field == ContractField.PARTY_SUPPLIER and x.text), None)
    if vendor == rec.counterparty_id and name:
        vendor = name
    rows = [(t(lang, "Vendor", "供应商"), vendor), (t(lang, "Contract", "合同"), rec.title)]
    for p in schedule.payments:
        word = t(lang, *_KIND.get(p.kind, ("payment", "付款")))
        rows.append((t(lang, f"Payment {p.n}", f"第 {p.n} 笔付款"),
                     t(lang, f"{fmt_yuan(p.amount_fen)}, {when_text(p.day, today, lang)} ({word})",
                       f"{fmt_yuan(p.amount_fen)}，{when_text(p.day, today, lang)}（{word}）")))
    if take and option is not None:
        choice = t(lang, f"Taken: {fmt_pct_bp(option.rate_bp)} off the delivery payment, {fmt_yuan(option.discount_fen)} saved, "
                         f"paid by {when_text(option.pay_by_day, today, lang)}",
                   f"选择提前付款：交货款减免 {fmt_pct_bp(option.rate_bp)}，节省 {fmt_yuan(option.discount_fen)}，"
                   f"{when_text(option.pay_by_day, today, lang)}前付清")
    elif option is not None:
        choice = t(lang, "Not taken: every payment is made on its day", "未选择提前付款：每笔款项在到期日支付")
    else:
        choice = t(lang, "None offered by the contract", "合同未提供")
    rows.append((t(lang, "Early payment", "提前付款"), choice))
    rows.append((t(lang, "Total you will pay", "您将支付的总额"), fmt_yuan(schedule.price_fen)))
    return {"schedule_title": title, "schedule_note": note,
            "schedule_rows": [{"label": k, "value_text": v} for k, v in rows if v]}


def fmt_pct_bp(bp: int) -> str:
    return fmt_pct(Fraction(bp, BP_DENOM))
