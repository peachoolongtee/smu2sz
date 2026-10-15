"""The deal tracker (`GET /decisions/{id}/tracker`): one agreed deal, what was expected at agreement against what has happened.

A read model over the durable decision record (`app.api.decisions`): it lays side by side facts the record already derives. The cost
expected at agreement is the figure the decision record shows for the accepted reply. The cost so far is built only from booked facts
(the discount a receipt or a received promise posted) and, when the records link one to this deal, the stored quoted cost of a funding
decision. Nothing is priced here: every figure is read from a record or is an integer sum or difference of such figures in fen, and a
part no record measures is said in words to be not measured yet. A GET changes nothing. Owner only, under `rt.lock`.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.decisions import Context, load_context
from app.api.lifecycle import lifecycle_stages
from app.api.presentation import (
    invoice_words,
    obligation_sentence,
    party_name,
    reconciliation_words,
    t,
    when_text,
)
from app.api.runtime import get_runtime
from app.api.selection import Selection, build_context, selection
from app.decisions import DealState, DecisionInputs, DecisionState, FundingState
from app.decisions.identity import offer_id_of
from app.decisions.state import RESERVE_ALERT, derive
from app.domain.models import CommitmentStatus, ObligationType, OperationStatus
from app.domain.money import fmt_yuan
from app.financial.trajectory import early_pay_discount
from app.strategy.receivable_rows import collection_action, collection_state

log = logging.getLogger("termsledger.tracker")

# The owner's current choice: funding the records relate to a deal is counted in its cost only when it followed this buyer's late payment
# (and only in one tracker). Set False and no related funding is counted; it is still shown, with `cost.related_fen`.
COUNT_RELATED_FUNDING = True
router = APIRouter(dependencies=[Depends(require_owner)])

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _num(n: int, lang: str) -> str:
    return _WORDS[n] if lang != "zh" and 0 <= n < len(_WORDS) else str(n)


def _money(fen: int | None) -> str | None:
    return fmt_yuan(fen) if fen is not None else None


def _entry_href(seq: int | None) -> str | None:
    return f"/trust?view=evidence&entry={seq}&from=tracker" if seq is not None else None


# ---------------------------------------------------------------- the pieces


def _expected(ds: DecisionState) -> int | None:
    """The cost expected at agreement, as the decision record shows it: the sent counter's stored supplier cost, else (the offer accepted
    as asked) the verdict's forward cost."""
    s = ds.sent
    if s is not None and s.counter_economics is not None:
        return s.counter_economics.supplier_cost_fen
    if s is not None and s.accepted_counter_id is not None:
        return None  # a counter was accepted and its economics were not recorded
    if ds.verdict is not None:
        return ds.verdict.forward_concession_total_fen
    return ds.commitment.forward_value_fen if ds.commitment is not None else None


def _pct(bp: int | None) -> str:
    return f"{(bp or 0) / 100:g}%"


def _short_terms(ctx: Context, ds: DecisionState, lang: str) -> str:
    c = ds.commitment
    assert c is not None
    parts = []
    for ob in c.obligations:
        try:
            if ob.type == ObligationType.IMMEDIATE_DISCOUNT and ob.rate_bp is not None and ob.base.amount_fen:
                parts.append(t(lang, f"{_pct(ob.rate_bp)} off up to {fmt_yuan(ob.base.amount_fen)} if paid early",
                               f"提前付款可减 {_pct(ob.rate_bp)}，最高 {fmt_yuan(ob.base.amount_fen)}"))
            else:
                parts.append(obligation_sentence(ctx.state, ob, ctx.today, lang))
        except (ValueError, KeyError, AttributeError):
            continue
    return "; ".join(parts) if lang != "zh" else "；".join(parts)


def _owner_title(ob: Any, lang: str) -> str:
    kind = ob.type
    if kind == ObligationType.IMMEDIATE_DISCOUNT:
        return t(lang, f"Allow {_pct(ob.rate_bp)} off if paid early", f"提前付款可减 {_pct(ob.rate_bp)}")
    if kind == ObligationType.TERMS_EXTENSION and ob.days_delta:
        return (t(lang, f"Allow {ob.days_delta} more days to pay", f"多给 {ob.days_delta} 天付款期") if ob.days_delta > 0
                else t(lang, f"Shorten the payment period by {-ob.days_delta} days", f"付款期缩短 {-ob.days_delta} 天"))
    if kind == ObligationType.PRICE_ADJUSTMENT:
        return t(lang, f"Change the price by {_pct(ob.rate_bp)}", f"价格调整 {_pct(ob.rate_bp)}")
    if kind == ObligationType.CONTINGENT_REBATE:
        return t(lang, f"Give a rebate of {_pct(ob.rate_bp)}", f"给予 {_pct(ob.rate_bp)} 的返利")
    return t(lang, "A further promise to the buyer", "对买方的另一项承诺")


def _executed_seqs(ctx: Context) -> set[int]:
    """The log positions of the operations that ran. A refused, queued or duplicate entry is not a payment."""
    return {e.seq for e in ctx.entries if e.result.status == OperationStatus.EXECUTED}


def _receipts(ctx: Context) -> list[Any]:
    """The reconciliation's receipts that an executed operation booked: the only receipts any figure, day or lateness here comes from."""
    ran = _executed_seqs(ctx)
    return [r for r in ctx.receipts if r.seq in ran]


def _receipt_days(ctx: Context) -> dict[str, int]:
    """The latest day an executed receipt was booked against each invoice."""
    out: dict[str, int] = {}
    for r in _receipts(ctx):
        if r.day is not None:
            out[r.receivable_id] = max(out.get(r.receivable_id, r.day), r.day)
    return out


def _discount_by_receipt(ctx: Context) -> dict[int, int]:
    """The discount each executed receipt that honoured a promise really gave, from the invoice's own record: what the invoice has settled
    less the cash its executed receipts brought, never below 0 and never above the promise's posted discount. An invoice paid at face
    settled exactly its cash, so it gave none; a receipt's `agreed_discount_fen` and a promise's face are reference figures and are not read."""
    cash: dict[str, int] = {}
    for x in _receipts(ctx):
        cash[x.receivable_id] = cash.get(x.receivable_id, 0) + x.received_fen
    left = {r.id: max(0, r.settled_fen - cash.get(r.id, 0)) for r in ctx.state.receivables}
    out: dict[int, int] = {}
    ran = {x.seq for x in _receipts(ctx)}
    for p in sorted((q for q in ctx.promised if q.status == "RECEIVED" and q.receipt_seq in ran), key=lambda q: q.receipt_seq):
        given = min(p.discount_fen, left.get(p.receivable_id, 0))
        out[p.receipt_seq] = given
        left[p.receivable_id] = left.get(p.receivable_id, 0) - given
    return out


def _booked_discounts(ctx: Context, promised: list[Any]) -> dict[Any, int]:
    """The discount booked under the agreement, by the receipt that gave it: only what the cash shows (see `_discount_by_receipt`)."""
    given = _discount_by_receipt(ctx)
    return {p.receipt_seq: given[p.receipt_seq] for p in promised
            if p.status == "RECEIVED" and p.receipt_seq in given and given[p.receipt_seq] > 0}


def _deal_receivables(ctx: Context, c: Any, promised: list[Any]) -> list[Any]:
    ids = dict.fromkeys([p.receivable_id for p in promised]
                        + [ob.base.receivable_id for ob in c.obligations if ob.base.receivable_id])
    rows = [r for r in ctx.state.receivables if r.id in ids]
    rows += [r for r in ctx.state.receivables if r.id not in ids and any(x.startswith(f"{c.id}:") for x in r.applied)]
    return rows


def _early_zh(ctx: Context, p: Any) -> str:
    when = when_text(p.promised_day, ctx.today, "zh") if p.promised_day is not None else ""
    inv = invoice_words(ctx.state, p.receivable_id, "zh")
    amount = fmt_yuan(p.expected_fen)
    return {"AWAITED": f"约定于{when}到账的 {amount} 提前付款尚未到账。",
            "RECEIVED": f"已收到约定的 {amount} 提前付款。",
            "LAPSED": f"约定于{when}到账的 {amount} 提前付款没有到账；{inv}将回到原来的到期日。",
            "SETTLED_OTHERWISE": f"{inv}已结清，但并非按约定的 {amount} 提前付款。"}.get(p.status, "")


def _buyer_promises(ctx: Context, promised: list[Any], receivables: list[Any], buyer: str, lang: str) -> list[dict[str, Any]]:
    agreements = {x.id: party_name(ctx.state, x.counterparty_id) for x in ctx.commitments}
    who = t(lang, "The buyer", "买方")
    out: list[dict[str, Any]] = []
    table = {"RECEIVED": ("kept", "ok", t(lang, "Kept", "已兑现"), "paid_early"),
             "AWAITED": ("awaited", "neutral", t(lang, "Awaited", "等待中"), "awaited"),
             "LAPSED": ("missed", "bad", t(lang, "Missed", "已错过"), "missed"),
             "SETTLED_OTHERWISE": ("part", "warn", t(lang, "Part kept", "部分兑现"), "part")}
    paid_on = _receipt_days(ctx)
    day_of = {r.seq: r.day for r in _receipts(ctx) if r.day is not None}
    by_id = {r.id: r for r in receivables}

    def days_late(n: int) -> str:
        return t(lang, f"{n} {'day' if n == 1 else 'days'} late", f"逾期 {n} 天")

    for p in promised:
        state, tone, word, kind = table.get(p.status, ("awaited", "neutral", t(lang, "Awaited", "等待中"), "awaited"))
        detail = (_early_zh(ctx, p) if lang == "zh" else
                  reconciliation_words(ctx.state, p.detail, ctx.today, promise=True, lang=lang, agreements=agreements)) or ""
        arrived = day_of.get(p.receipt_seq) if p.receipt_seq is not None else None
        rec = by_id.get(p.receivable_id)
        if state == "kept" and arrived is not None and p.promised_day is not None and arrived > p.promised_day:
            late = arrived - p.promised_day  # a promise met after its day is not kept
            state, tone, word, kind = "paid_late", "warn", t(lang, "Paid late", "逾期支付"), "paid_late"
            detail = t(lang, f"The early payment of {fmt_yuan(p.expected_fen)} was due {when_text(p.promised_day, ctx.today, lang)} and "
                             f"arrived {when_text(arrived, ctx.today, lang)}, {days_late(late)}.",
                       f"{fmt_yuan(p.expected_fen)} 的提前付款应于{when_text(p.promised_day, ctx.today, lang)}到账，"
                       f"实际于{when_text(arrived, ctx.today, lang)}到账，{days_late(late)}。")
        elif (p.status != "RECEIVED" and rec is not None and p.promised_day is not None and rec.face_fen - rec.settled_fen <= 0
              and paid_on.get(rec.id, p.promised_day + 1) <= p.promised_day):
            # the buyer paid everything on or before the promised day, only without the discount: the promise was kept
            state, tone, word, kind = "kept", "ok", t(lang, "Paid in full, without the discount", "已全额付清（未享受折扣）"), "full"
            detail = t(lang, f"The buyer paid {invoice_words(ctx.state, rec.id, lang)} in full on or before the day promised, without taking the discount.",
                       f"买方在约定日期当天或之前已付清{invoice_words(ctx.state, rec.id, lang)}的全款，但没有享受折扣。")
        out.append({"party": "buyer", "party_text": who,
                    "title_text": t(lang, f"Pay {fmt_yuan(p.expected_fen)} early", f"提前支付 {fmt_yuan(p.expected_fen)}"),
                    "detail_text": detail, "state": state, "state_word": word, "tone": tone,
                    "evidence_href": _entry_href(p.receipt_seq) if state in ("kept", "part", "paid_late") and p.receipt_seq is not None else None,
                    "_kind": kind})
    for r in receivables:
        owed = r.face_fen - r.settled_fen
        words = invoice_words(ctx.state, r.id, lang)
        kind = "invoice"
        if r.status == "SETTLED" or owed <= 0:
            state, tone, word = "kept", "ok", t(lang, "Kept", "已兑现")
            detail = t(lang, f"{words[:1].upper()}{words[1:]} has been paid.", f"{words}已付清。")
            paid = paid_on.get(r.id)
            if paid is not None and paid > r.due_day:
                state, tone, word = "paid_late", "warn", t(lang, "Paid late", "逾期支付")
                detail = t(lang, f"{words[:1].upper()}{words[1:]} was due {when_text(r.due_day, ctx.today, lang)} and was paid "
                                 f"{when_text(paid, ctx.today, lang)}, {days_late(paid - r.due_day)}.",
                           f"{words}应于{when_text(r.due_day, ctx.today, lang)}付清，实际于{when_text(paid, ctx.today, lang)}付清，"
                           f"{days_late(paid - r.due_day)}。")
        elif r.status not in ("OPEN", "FINANCED"):
            state, tone, word = "failed", "bad", t(lang, "Failed", "已失败")
            detail = t(lang, f"{fmt_yuan(owed)} on {words} can no longer be collected: the invoice failed.",
                       f"{words}的 {fmt_yuan(owed)} 已无法收回：这张发票已失败。")
        else:
            state = "late" if r.due_day < ctx.today else "awaited"
            tone, word = ("bad", t(lang, "Late", "已逾期")) if state == "late" else ("neutral", t(lang, "Awaited", "等待中"))
            when = when_text(r.due_day, ctx.today, lang)
            detail = (t(lang, f"{fmt_yuan(owed)} on {words} was due {when} and is still unpaid.",
                        f"{words}应付 {fmt_yuan(owed)}，已于{when}到期，仍未付款。") if state == "late"
                      else t(lang, f"{fmt_yuan(owed)} on {words} falls due {when}.", f"{words}应付 {fmt_yuan(owed)}，将于{when}到期。"))
        out.append({"party": "buyer", "party_text": who, "title_text": t(lang, "Pay the invoice by its due date", "按期支付发票款项"),
                    "detail_text": detail, "state": state, "state_word": word, "tone": tone,
                    "evidence_href": f"/receivables?invoice={quote(r.id, safe='')}&customer={quote(buyer, safe='')}",
                    "_kind": kind})
    return out


def _owner_promises(ctx: Context, ds: DecisionState, promised: list[Any], lang: str) -> list[dict[str, Any]]:
    c = ds.commitment
    assert c is not None
    who = t(lang, "You", "您")
    accept = next((o for o in ds.ops if o.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT")), None)
    out = []
    for ob in c.obligations:
        taken = next((p for p in promised if p.obligation_id == ob.id and p.status in ("RECEIVED", "SETTLED_OTHERWISE")), None)
        if taken is not None or c.status == CommitmentStatus.FULFILLED:
            state, tone, word = "kept", "ok", t(lang, "Kept", "已履行")
            seq = taken.receipt_seq if taken is not None else None
        elif c.status in (CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED) or ob.id in c.lapsed_obligations:
            state, tone, word, seq = "ended", "neutral", t(lang, "Ended", "已结束"), None
        else:
            state, tone, word, seq = "in_force", "neutral", t(lang, "In force", "有效"), None
        try:
            detail = obligation_sentence(ctx.state, ob, ctx.today, lang)
        except (ValueError, KeyError, AttributeError):
            detail = ""
        out.append({"party": "you", "party_text": who, "title_text": _owner_title(ob, lang), "detail_text": detail, "state": state,
                    "state_word": word, "tone": tone, "evidence_href": _entry_href(seq if seq is not None else (accept.seq if accept else None))})
    return out


def _late_at(ctx: Context, receivables: list[Any], day: int, seq: int | None) -> bool:
    """Whether one of these invoices was late when a cure was quoted: past its due day on `day` and still owed after the executed receipts that
    came EARLIER IN THE LOG than the quote (`seq`), never by day alone. A lapsed early promise before the due day is not lateness."""
    ran = _receipts(ctx)
    given = _discount_by_receipt(ctx)
    for r in receivables:
        if seq is None:
            owed = r.face_fen - r.settled_fen
        else:
            # what the earlier executed receipts settled: the cash, and the discount that cash shows for a promise it honoured
            owed = r.face_fen - sum(x.received_fen + given.get(x.seq, 0)
                                    for x in ran if x.receivable_id == r.id and x.seq < seq)
        if r.due_day < day and owed > 0:
            return True
    return False


def _quoted_day(ctx: Context, fid: str, fds: DecisionState) -> int | None:
    row = next((r for r in ctx.facts if r.decision_id == fid and r.fact == "QUOTED"), None)
    if row is not None:
        return int(row.day)
    return fds.quote.alert_day if fds.quote is not None and fds.quote.alert_day is not None else fds.opened_day


def _funding_lines(ctx: Context, ds: DecisionState, rids: set[str], lang: str) -> list[dict[str, Any]]:
    """Every funding decision after the agreement that the records relate to this deal becomes a line, with its `relation`:
    `after_late_payment` (on the day it was quoted this buyer was the only buyer with a late invoice, and this deal the only late deal of that
    buyer) or `secured_on_invoice` (an advance on one of this deal's invoices). Its figure is the plan's stored quoted cost. The records do
    not show how much of it this deal caused, so the line says so. A line is COUNTED in the deal's cost only under `COUNT_RELATED_FUNDING`,
    only for `after_late_payment`, and in at most one tracker: when two deals could claim it, neither counts it."""
    c = ds.commitment
    assert c is not None
    buyer = c.counterparty_id
    agreed = next((o.day for o in ds.ops if o.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and o.day is not None), None)

    def mine(commitment: Any, day: int, seq: int | None) -> bool:
        promised = [p for p in ctx.promised if p.commitment_id == commitment.id]
        return _late_at(ctx, _deal_receivables(ctx, commitment, promised), day, seq)

    out: list[dict[str, Any]] = []
    for fid, (fds, _inp) in ctx.states().items():
        q = fds.quote
        if fds.family != "FUNDING" or q is None or fds.state in (FundingState.DECLINED, FundingState.FAILED):
            continue
        qday = _quoted_day(ctx, fid, fds)
        # where the cure sits in the log: its FIRST entry (queued or pending approval), never the later entry that ran it
        first = [e.seq for _pos, e in ctx.index.runs.get(fid, ())]
        qseq = min(first) if first else min((o.seq for o in fds.ops), default=None)
        if agreed is not None and qday is not None and qday < agreed:
            continue
        secured = any(leg.receivable_id in rids for leg in q.legs)
        late_cause = unique = False
        why = ""
        if q.alert_kind == RESERVE_ALERT and qday is not None:
            late_buyers = {x.counterparty_id for x in ctx.state.receivables if _late_at(ctx, [x], qday, qseq)}
            late_cause = buyer in late_buyers and mine(c, qday, qseq)
            if late_cause:
                others = [x for x in ctx.commitments if x.counterparty_id == buyer and x.id != c.id
                          and x.status != CommitmentStatus.PROPOSED and mine(x, qday, qseq)]
                if late_buyers != {buyer}:
                    why = "buyers"
                elif others:
                    why = "deals"
                unique = not why
        if not (late_cause or secured):
            continue
        relation = "after_late_payment" if late_cause else "secured_on_invoice"
        pending = fds.state == FundingState.AUTHORIZATION_REQUIRED
        cost = q.total_cost_fen
        extra = (t(lang, " Interest on the draw itself is not in that figure.", "借款本身的利息不含在该数字中。")
                 if q.cost_note == "draw_interest_excluded" else "")
        if relation == "after_late_payment":
            certainty = "ATTRIBUTED"
            certainty_text = t(lang, "FLOW arranged this funding after this buyer's payment was late. The records do not show how much of it this "
                                     "deal caused. It is the cost FLOW quoted; the charge itself is not yet booked.",
                               "FLOW 是在这位买方付款逾期之后安排的这笔融资。记录并没有显示其中有多少是这笔交易造成的。"
                               "这是 FLOW 报出的成本，费用本身尚未入账。")
        else:
            certainty = "QUOTED"
            certainty_text = t(lang, "This funding is secured on one of this deal's invoices. The records do not show how much of it this deal "
                                     "caused. It is the cost FLOW quoted; the charge itself is not yet booked.",
                               "这笔融资以这笔交易的一张发票作担保。记录并没有显示其中有多少是这笔交易造成的。"
                               "这是 FLOW 报出的成本，费用本身尚未入账。")
        eligible = COUNT_RELATED_FUNDING and relation == "after_late_payment" and unique
        if not eligible:
            if relation == "secured_on_invoice":
                note = t(lang, "This funding is secured on this deal's invoice. It is shown with the deal but not counted in its cost.",
                         "这笔融资以这笔交易的发票作担保。它与这笔交易一并显示，但不计入其成本。")
            elif why == "buyers":
                note = t(lang, "This funding followed late payments from several buyers, so it is not counted in this deal's cost.",
                         "这笔融资是在多位买方逾期付款之后安排的，因此不计入这笔交易的成本。")
            elif why == "deals":
                note = t(lang, "This funding followed late payments on several of this buyer's deals, so it is not counted in this deal's cost.",
                         "这笔融资是在这位买方多笔交易逾期付款之后安排的，因此不计入这笔交易的成本。")
            else:
                note = t(lang, "FLOW is set not to count related funding in a deal's cost, so this is shown but not counted.",
                         "FLOW 目前设置为不把相关融资计入交易成本，因此这笔融资仅显示，不计入。")
        elif cost is None:
            note = t(lang, "Not measured yet: no cost was quoted for this funding.", "尚未衡量：这笔融资没有报出成本。")
        elif pending:
            note = t(lang, f"Quoted at {fmt_yuan(cost)}; it counts only once you approve it.", f"已报价 {fmt_yuan(cost)}；您批准后才会计入。")
        else:
            note = None
        shown = eligible and not pending and cost is not None
        out.append({
            "key": "funding" if not out else f"funding_{len(out) + 1}",
            "label": (t(lang, "Funding after this buyer's late payment", "这位买方逾期付款之后的融资") if relation == "after_late_payment"
                      else t(lang, "Funding secured on this deal's invoice", "以这笔交易的发票作担保的融资")),
            "expected_fen": 0, "expected_display": fmt_yuan(0),
            "actual_fen": cost if shown else None, "actual_display": fmt_yuan(cost) if shown and cost is not None else None,
            "actual_note_text": note, "certainty": certainty, "certainty_text": certainty_text + extra,
            "tone": "bad" if shown else "neutral", "evidence_href": f"/decisions/{quote(fid, safe=':')}",
            "relation": relation, "counted": shown, "related_fen": cost, "related_display": _money(cost),
            "figure_fen": cost, "figure_display": _money(cost), "counted_note_text": None if eligible else note,
            "_pending": pending, "_pending_fen": cost if (pending and eligible) else None, "_waits": pending and eligible,
        })
    return out


def _planned_funding(ds: DecisionState, lang: str) -> tuple[dict[str, Any] | None, int | None]:
    """The funding FLOW planned for the rest of the gap when the deal was agreed (the sent counter's stored gap plan): its stored cost, and
    whether its operations ran. Returns the line and the planned (expected) component."""
    s = ds.sent
    gp = s.gap_plan if s is not None else None
    if s is None or gp is None or gp.total_cost_fen is None:
        return None, None
    ran = bool(s.funding_op_ids) and all(any(o.op_id == i and o.status == OperationStatus.EXECUTED for o in ds.ops) for i in s.funding_op_ids)
    cost = gp.total_cost_fen  # the cost stored for the plan that actually ran
    line = {
        "key": "planned_funding", "label": t(lang, "Funding planned when you agreed", "达成协议时计划的融资"),
        "expected_fen": cost, "expected_display": fmt_yuan(cost),
        "actual_fen": cost if ran else None, "actual_display": fmt_yuan(cost) if ran else None,
        "actual_note_text": None if ran else t(lang, "The funding planned when you agreed was not run.", "达成协议时计划的融资没有执行。"),
        "certainty": "QUOTED",
        "certainty_text": t(lang, "The cost FLOW planned for funding the rest of the gap when you agreed; the charge itself is not yet booked.",
                            "达成协议时 FLOW 为弥补其余缺口计划的融资成本；费用本身尚未入账。"),
        "tone": "neutral", "evidence_href": None, "relation": None, "counted": ran,
        "figure_fen": cost, "figure_display": fmt_yuan(cost), "counted_note_text": None,
    }
    return line, cost


def _state_text(ctx: Context, kinds: list[str], receivables: list[Any], funding_done: bool, funding_pending: bool, lang: str) -> str:
    """What has happened so far, in one or two sentences, from the promises' and the invoices' own state. Never a bare status word."""
    today = ctx.today
    first = ""
    for kind in ("missed", "paid_late", "part", "full", "paid_early", "awaited"):
        if kind in kinds:
            first = {"missed": t(lang, "The buyer's early payment did not arrive.", "买方承诺的提前付款没有到账。"),
                     "paid_late": t(lang, "The buyer paid the early part it promised, but after the day it promised.", "买方支付了承诺提前支付的部分，但晚于承诺的日期。"),
                     "part": t(lang, "The buyer settled the early part, but not as agreed.", "买方结清了提前支付的部分，但并非按约定的方式。"),
                     "full": t(lang, "The buyer paid the whole invoice in time, without taking the discount.", "买方按时付清了整张发票，但没有享受折扣。"),
                     "paid_early": t(lang, "The buyer paid the early part it promised.", "买方已支付它承诺提前支付的部分。"),
                     "awaited": t(lang, "The buyer's early payment is still awaited.", "买方承诺的提前付款仍在等待中。")}[kind]
            break
    paid_early = bool({"paid_early", "paid_late"} & set(kinds))
    unpaid = [r for r in receivables if r.status in ("OPEN", "FINANCED") and r.face_fen - r.settled_fen > 0]
    failed = [r for r in receivables if r.status not in ("OPEN", "FINANCED", "SETTLED") and r.face_fen - r.settled_fen > 0]
    late = [r for r in unpaid if r.due_day < today]
    who = t(lang, "The rest of the invoice" if paid_early else "The invoice", "发票余款" if paid_early else "发票")
    if failed:
        second = t(lang, "An invoice on this deal can no longer be collected.", "这笔交易的一张发票已无法收回。")
    elif not unpaid:
        second = t(lang, "Every invoice on this deal has been paid.", "这笔交易的所有发票都已付清。") if receivables else ""
    elif late:
        days = max(today - r.due_day for r in late)
        if len(late) > 1:
            second = t(lang, f"{len(late)} invoices on this deal are late, the longest by {days} {'day' if days == 1 else 'days'}",
                       f"这笔交易有 {len(late)} 张发票已逾期，最长已逾期 {days} 天")
        else:
            second = t(lang, f"{who} is {days} {'day' if days == 1 else 'days'} late", f"{who}已逾期 {days} 天")
        if funding_pending:
            second += t(lang, ", and funding arranged after it is waiting for your approval.", "，在此之后为您安排的融资正在等待您批准。")
        elif funding_done:
            second += t(lang, ", and you arranged funding after it.", "，您在此之后安排了融资。")
        else:
            second += t(lang, ".", "。")
    else:
        due = min(r.due_day for r in unpaid)
        second = t(lang, f"{who} falls due {when_text(due, today, lang)}.", f"{who}将于{when_text(due, today, lang)}到期。")
        if funding_pending:
            second += t(lang, " Funding is waiting for your approval.", "融资正在等待您批准。")
    text = f"{first} {second}".strip() if lang != "zh" else f"{first}{second}"
    return text or t(lang, "The agreement is in force; nothing has been paid under it yet.", "协议已生效；目前还没有任何付款。")


# ---------------------------------------------------------------- the whole read


def _unavailable(decision_id: str, lang: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    cost: dict[str, Any] = {"expected": None, "actual": None, "to_come": None, "unmeasured_fen": None, "unmeasured_display": None,
                            "related_fen": None, "related_display": None, "difference_fen": None, "difference_display": None, "lines": [],
                            "method_text": None}
    return {"decision_id": decision_id, "lang": lang, "available": False, "unavailable_text": text, "buyer_id": None, "buyer_name": None,
            "agreed_when": None, "agreed_text": None, "terms_text": None, "headline_text": None, "state_word": None, "state_key": None, "ended": False, "state_tone": "neutral", "state_text": None,
            "stages": [], "lifecycle_stages": [], "cost": cost, "promises": [], "promise_counts": None, "buyer": None, "next": None, "closeout_text": None,
            "links": {"record_href": f"/decisions/{quote(decision_id, safe=':')}",
                      "activity_href": f"/activity?decision={quote(decision_id, safe=':')}"},
            "context": context}


def _find(ctx: Context, decision_id: str) -> tuple[DecisionState, DecisionInputs]:
    found = ctx.states().get(decision_id)
    if found is not None:
        return found
    offer_id = offer_id_of(decision_id)
    if offer_id is None or ctx.offer(offer_id) is None:
        raise HTTPException(404, {"code": "DECISION_NOT_FOUND", "decision_id": decision_id})
    inp = ctx.inputs_for(decision_id)
    return derive(inp), inp


def _not_agreed_text(state: str, lang: str) -> str:
    """Why there is nothing to track, in the words of the state the decision is in."""
    words = {
        "NO_DEAL": ("No deal was agreed on this offer, so there is nothing to track.", "这份报价没有达成任何协议，因此没有可跟踪的内容。"),
        "LAPSED": ("This offer lapsed before it was agreed, so there is nothing to track.", "这份报价在达成协议之前已失效，因此没有可跟踪的内容。"),
        "DECLINED": ("You declined this deal, so nothing was agreed and there is nothing to track.", "您已拒绝这笔交易，没有达成协议，因此没有可跟踪的内容。"),
        "FAILED": ("This deal could not be agreed, so there is nothing to track.", "这笔交易未能达成，因此没有可跟踪的内容。"),
    }
    en, zh = words.get(state, ("This deal has not been agreed yet, so there is nothing to track.", "这笔交易尚未达成，因此没有可跟踪的内容。"))
    return t(lang, en, zh)


def build_tracker(rt: Any, ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str, context: dict[str, Any]) -> dict[str, Any]:
    c = ds.commitment
    if ds.family != "DEAL":
        return _unavailable(ds.decision_id, lang, t(lang, "This is a funding decision, not an agreed deal, so there is nothing to track.",
                                                    "这是一项融资决定，不是已达成的交易，因此没有可跟踪的内容。"), context)
    if c is None or c.status in (CommitmentStatus.PROPOSED,):
        # nothing to track yet, but the strip of the deal's life so far is the same function's (the offer's stages)
        return {**_unavailable(ds.decision_id, lang, _not_agreed_text(ds.state.value, lang), context),
                "lifecycle_stages": lifecycle_stages(rt, ctx, ds, inp, lang)}
    today, buyer = ctx.today, c.counterparty_id
    name = party_name(ctx.state, buyer)
    promised = [p for p in ctx.promised if getattr(p, "commitment_id", None) == c.id]
    receivables = _deal_receivables(ctx, c, promised)
    rids = {r.id for r in receivables}

    # the promises
    buyer_rows = _buyer_promises(ctx, promised, receivables, buyer, lang)
    kinds = [r.pop("_kind") for r in buyer_rows]
    early_kinds = kinds[:len(promised)]
    states = [r["state"] for r in buyer_rows]
    rows = [*buyer_rows, *_owner_promises(ctx, ds, promised, lang)]
    kept = sum(1 for r in buyer_rows if r["state"] == "kept")  # met on or before its day
    paid_late = sum(1 for r in buyer_rows if r["state"] == "paid_late")
    total = len(buyer_rows)
    lapsed = "missed" in states

    # later funding, and whether the deal has ended
    fund = _funding_lines(ctx, ds, rids, lang)
    funding_pending = any(x["_pending"] for x in fund)
    reopens = any(x["_waits"] for x in fund)  # a cure that is not this deal's to count never reopens it
    funding_done = any(not x["_pending"] for x in fund)
    blocked = [r for r in receivables if r.status != "SETTLED" and r.face_fen - r.settled_fen > 0]
    # ENDED, the one flag the headline, the tone, the close-out and the stages read: every invoice of the deal is settled (an invoice that
    # failed is not), no cure waits for the owner, and either the deal has invoices that are all paid (whatever the commitment's status) or
    # its agreement is over with no early payment awaited. Anything else is LIVE.
    over_agreement = c.status in (CommitmentStatus.FULFILLED, CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED)
    ended = (not blocked and not reopens
             and ((bool(receivables)) or (over_agreement and "awaited" not in early_kinds)))

    # the cost expected at agreement, in the two components the accepted reply stores, and the cost so far
    expected = _expected(ds)
    terms = _short_terms(ctx, ds, lang)
    planned_line, planned_run = _planned_funding(ds, lang)
    discounts = sum(p.discount_fen for p in promised)
    # Both expected components come from the accepted reply's stored quote-time economics: its supplier cost is the concession (the posted
    # discount) plus the funding quoted for the rest of the gap, so the quoted funding is the supplier cost less the posted discount. The
    # plan that ran may have cost something else; that shows on the planned line's actual. When the figures cannot be split, one line.
    # No record stores the discount as an amount, so it is the engine's own posted discount (`early_pay_discount`, the figure the
    # reconciliation posts) on the commitment's stored obligations at their full agreed base: fixed at acceptance, whatever has been paid since.
    agreed = [ob for ob in c.obligations if ob.type == ObligationType.IMMEDIATE_DISCOUNT and ob.base.amount_fen]
    agreed_discount = sum(early_pay_discount(ob, ob.base.amount_fen or 0) for ob in agreed)
    split = (planned_line is not None and expected is not None and len(agreed) == len(c.obligations) > 0
             and 0 < agreed_discount <= expected)
    concession_expected = agreed_discount if split else expected
    planned_expected = (expected - agreed_discount) if split and expected is not None else 0
    if planned_line is not None:
        planned_line["expected_fen"], planned_line["expected_display"] = planned_expected, fmt_yuan(planned_expected)
        if planned_line["actual_fen"] is not None and planned_run != planned_expected and split:
            planned_line["actual_note_text"] = t(lang, f"The plan that ran cost {fmt_yuan(planned_run or 0)} against {fmt_yuan(planned_expected)} quoted.",
                                                 f"实际执行的计划成本为 {fmt_yuan(planned_run or 0)}，报价为 {fmt_yuan(planned_expected)}。")
    booked = _booked_discounts(ctx, promised)
    booked_fen = sum(booked.values())
    planned_actual = planned_line["actual_fen"] if planned_line is not None and planned_line["actual_fen"] is not None else 0
    # what no record holds: the part of the expected concession that no promise's posted discount covers
    # nothing is unmeasured when the stored supplier cost splits into its two stored components; only a whole, unsplit figure can be
    unmeasured = (0 if split else max(0, concession_expected - discounts)) if concession_expected is not None else None
    revoked = c.status == CommitmentStatus.REVOKED
    first_seq = min((k for k in booked if isinstance(k, int)), default=None)
    if not booked:
        note = (t(lang, "The agreement was withdrawn before the discount was given.", "协议在给出折扣之前已被撤回。") if revoked
                else t(lang, "The early payment did not arrive, so no discount has been given under the agreement.",
                       "提前付款没有到账，因此这份协议下没有给出任何折扣。") if lapsed
                else t(lang, "Nothing has been paid under the agreement yet.", "这份协议下目前还没有任何付款。"))
    elif unmeasured:
        note = (t(lang, f"Not measured: {fmt_yuan(unmeasured)} of the expected cost, which no record holds.",
                  f"未能衡量：预期成本中有 {fmt_yuan(unmeasured)} 没有任何记录。") if ended
                else t(lang, f"Not measured yet: {fmt_yuan(unmeasured)} of the expected cost, which no record holds yet.",
                       f"尚未衡量：预期成本中有 {fmt_yuan(unmeasured)} 目前没有任何记录。"))
    else:
        note = None
    if any(ob.type in (ObligationType.CONTINGENT_REBATE, ObligationType.PRICE_ADJUSTMENT) for ob in c.obligations):
        more = t(lang, "A rebate or price change in the agreement is not measured yet.", "协议中的返利或价格调整尚未衡量。")
        note = f"{note} {more}" if note else more
    if planned_line is not None and not split and expected is not None:
        more = t(lang, "The expected cost could not be split into the concession and the planned funding, so it is shown whole here.",
                 "预期成本无法拆分为让步和计划融资两部分，因此在此整体显示。")
        note = f"{note} {more}" if note else more
    terms_line = {
        "key": "terms", "label": t(lang, "The terms you gave the buyer", "您给买方的条款"),
        "expected_fen": concession_expected, "expected_display": _money(concession_expected),
        "actual_fen": booked_fen, "actual_display": fmt_yuan(booked_fen),
        "actual_note_text": note, "certainty": "RECORDED",
        "certainty_text": t(lang, "Booked: the discount the bank receipts under this agreement gave, the face they settled less the cash received. "
                                  "The expected figure is the one FLOW quoted when you agreed.",
                            "已入账：这份协议下银行收款实际给出的折扣，即所结清的面额减去收到的现金。预期数字是您达成协议时 FLOW 报出的数字。"),
        "tone": ("bad" if concession_expected is not None and booked_fen > concession_expected
                 else "ok" if ended and not unmeasured and concession_expected is not None else "neutral"),
        "evidence_href": _entry_href(first_seq), "relation": None, "counted": True,
        "figure_fen": booked_fen, "figure_display": fmt_yuan(booked_fen), "counted_note_text": None,
    }
    lines = [terms_line, *([planned_line] if planned_line is not None else []), *fund]
    actual = sum(x["actual_fen"] for x in lines if x["actual_fen"] is not None)
    # the cost ON TOP of the agreed terms: what the counted later funding lines add. Unsigned; it is not "actual minus expected".
    on_top = sum(x["actual_fen"] for x in fund if x["actual_fen"] is not None)
    related = sum(x["related_fen"] for x in fund if x["related_fen"] is not None)
    pending_fen = sum(x["_pending_fen"] for x in fund if x["_pending_fen"] is not None)
    awaiting_fen = sum(p.discount_fen for p in promised if p.status == "AWAITED")
    for x in fund:
        x.pop("_pending_fen")
        x.pop("_pending")
        x.pop("_waits")
    base = booked_fen + planned_actual
    over = expected is not None and base > expected
    parts: list[str] = []
    if planned_actual:
        parts.append(t(lang, f"Includes {fmt_yuan(planned_actual)} of funding planned when you agreed.",
                       f"其中包含达成协议时计划的 {fmt_yuan(planned_actual)} 融资成本。"))
    if on_top:
        parts.append(t(lang, f"Includes {fmt_yuan(on_top)} of funding on top of the terms you agreed.",
                       f"其中包含 {fmt_yuan(on_top)} 在您同意的条款之外的融资成本。"))
    not_counted = sum(x["related_fen"] for x in fund if x["counted_note_text"] and x["related_fen"] is not None)
    if not_counted:
        parts.append(t(lang, f"{fmt_yuan(not_counted)} of funding related to this deal is shown but not counted.",
                       f"与这笔交易相关的 {fmt_yuan(not_counted)} 融资仅显示，不计入。"))
    if over and expected is not None:
        parts.append(t(lang, f"The booked cost is {fmt_yuan(base - expected)} above the expected cost.",
                       f"已入账的成本比预期高 {fmt_yuan(base - expected)}。"))
    if not booked:
        parts.append(note or "")
    if unmeasured and booked:
        parts.append(t(lang, f"{fmt_yuan(unmeasured)} of the expected cost is not measured yet.",
                       f"预期成本中有 {fmt_yuan(unmeasured)} 尚未衡量。"))
    if expected is None:
        parts.append(t(lang, "The cost expected at agreement was not recorded.", "达成协议时的预期成本没有记录。"))
    parts = [x for x in parts if x]
    actual_note = " ".join(parts) if lang != "zh" else "".join(parts)
    if on_top or over:
        tone = "bad"
    elif ended and not unmeasured and expected is not None:
        tone = "ok"
    else:
        tone = "neutral"
    to_come_fen = pending_fen + (awaiting_fen if not ended else 0)
    if to_come_fen:
        to_come_note = (t(lang, "Still to come: the quoted funding once you approve it, and the discount if the buyer pays early as promised.",
                          "尚待发生：您批准后的融资报价成本，以及买方按承诺提前付款时的折扣。") if pending_fen and awaiting_fen
                        else t(lang, "Still to come once you approve the quoted funding.", "您批准报价的融资后才会发生。") if pending_fen
                        else t(lang, "Still to come if the buyer pays early as promised: the discount posted for that payment.",
                               "买方按承诺提前付款时才会发生：该笔付款所记的折扣。"))
    elif ended:
        to_come_note = t(lang, "Nothing further is due under this agreement.", "这份协议下没有后续款项。")
    else:
        to_come_note = t(lang, "No record holds a further cost yet; anything that appears will be shown here.",
                         "目前没有记录显示还有后续成本；一旦出现会在此显示。")
    cost = {
        "expected": {"amount_fen": expected, "amount_display": _money(expected), "basis_text": terms, "certainty": "QUOTED"},
        "actual": {"amount_fen": actual, "amount_display": fmt_yuan(actual), "note_text": actual_note, "tone": tone},
        "to_come": {"amount_fen": to_come_fen or None, "amount_display": _money(to_come_fen or None), "note_text": to_come_note},
        "unmeasured_fen": unmeasured, "unmeasured_display": _money(unmeasured),
        "related_fen": related, "related_display": fmt_yuan(related),
        "difference_fen": on_top, "difference_display": fmt_yuan(on_top), "lines": lines,
        "method_text": t(lang, "Expected is the cost FLOW quoted when you agreed, in two parts: the concession you gave and the funding planned "
                              "for the rest of the gap. Cost so far adds up only what the records hold; a part no record holds is shown apart as "
                              "not measured. The difference is the funding counted on top of the terms you agreed; funding related to this deal "
                              "is shown beside it, counted or not.",
                        "预期成本是您达成协议时 FLOW 报出的成本，分为两部分：您给出的让步，以及为弥补其余缺口计划的融资。至今成本只累计记录中已有的内容；"
                        "没有记录的部分会单独标明为未衡量。差额是在您同意的条款之外计入的融资；与这笔交易相关的融资无论是否计入，都会在旁边显示。"),
    }

    to_come = sum(1 for x in states if x == "awaited")  # a promise not yet due or settled is neither kept nor missed
    due = total - to_come
    if total == 0:
        counts_text = t(lang, "The buyer has made no promise on this deal yet.", "买方在这笔交易中还没有作出承诺。")
    elif due == 0:
        counts_text = t(lang, ("The buyer has made one promise on this deal; it is not due yet." if total == 1
                               else f"The buyer has made {_num(total, lang)} promises on this deal; none is due yet."),
                        f"买方在这笔交易中作出了 {total} 项承诺，目前都还未到期。")
    elif to_come:
        late = (f"; {_num(paid_late, lang)} {'was' if paid_late == 1 else 'were'} paid late" if paid_late else "")
        counts_text = t(lang, f"The buyer has kept {_num(kept, lang)} of {_num(due, lang)} {'promise' if due == 1 else 'promises'} due so far{late}; "
                              f"{_num(to_come, lang)} more {'is' if to_come == 1 else 'are'} still to come.",
                        f"买方已到期的 {due} 项承诺中已兑现 {kept} 项" + (f"；有 {paid_late} 项逾期后才付款" if paid_late else "")
                        + f"；另有 {to_come} 项尚未到期。")
    else:
        counts_text = t(lang, f"The buyer has kept {_num(kept, lang)} of {_num(total, lang)} promises on this deal"
                              + (f"; {_num(paid_late, lang)} {'was' if paid_late == 1 else 'were'} paid late." if paid_late else "."),
                        f"买方在这笔交易的 {total} 项承诺中已兑现 {kept} 项" + (f"；有 {paid_late} 项逾期后才付款。" if paid_late else "。"))
    behaviour = None
    try:
        from app.books import books_from_store
        from app.strategy.payments import payment_behaviour

        pb = payment_behaviour(rt.store, books_from_store(rt.store), buyer, today, lang=lang)
        behaviour = None if pb.insufficient else pb.sentence
    except Exception:  # noqa: BLE001  feature off or too few invoices: no behaviour sentence
        behaviour = None
    buyer_view = {"text": behaviour,
                  "note_text": t(lang, "FLOW will show this beside the next offer from this buyer. It does not change what FLOW may accept on your behalf.",
                                 "FLOW 会在这位买方的下一份报价旁显示这些信息。它不会改变 FLOW 可以代您接受的范围。"),
                  "href": f"/customers/{quote(buyer, safe='')}"}

    accept = next((o for o in ds.ops if o.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and o.day is not None), None)
    agreed_when = when_text(accept.day, today, lang) if accept is not None else None
    agreed_text = t(lang, f"Agreed {agreed_when}", f"{agreed_when}达成协议") if agreed_when else None

    # the state
    nothing = not booked and not fund and all(s == "awaited" for s in states) and not lapsed
    if "missed" in states:
        word, wtone, key = t(lang, "Promise missed", "承诺未兑现"), "bad", "missed"
    elif "failed" in states:
        word, wtone, key = t(lang, "Payment failed", "付款失败"), "bad", "failed"
    elif "late" in states:
        word, wtone, key = t(lang, "Payment late", "付款逾期"), "bad", "late"
    elif "part" in states:
        word, wtone, key = t(lang, "Part kept", "部分兑现"), "warn", "part"
    elif "paid_late" in states:
        word, wtone, key = t(lang, "Paid late", "逾期支付"), "warn", "paid_late"
    elif ended and ds.state == DealState.FULFILLED:
        word, wtone, key = t(lang, "Completed", "已完成"), "ok", "completed"
    elif ended:
        word, wtone, key = t(lang, "Ended", "已结束"), "neutral", "ended"
    elif nothing:
        word, wtone, key = t(lang, "Waiting for the buyer", "等待买方"), "neutral", "waiting"
    else:
        word, wtone, key = t(lang, "On plan", "按计划进行"), "ok", "on_plan"
    state_text = _state_text(ctx, kinds, receivables, funding_done, funding_pending, lang)
    if ended:
        if expected is None:
            headline = t(lang, "This deal has closed", "这笔交易已结束")
        elif on_top > 0 or over:
            headline = t(lang, "This deal closed with extra cost on top of the terms you agreed", "这笔交易结束时，在您同意的条款之外还有额外成本")
        elif lapsed:
            headline = t(lang, "This deal ended with the buyer's promise missed", "这笔交易结束时买方未兑现承诺")
        elif unmeasured:
            headline = t(lang, "This deal has closed; part of its expected cost was never measured", "这笔交易已结束；预期成本中有一部分始终未能衡量")
        elif base == expected:
            headline = t(lang, "This deal closed as expected", "这笔交易按预期结束")
        else:
            headline = t(lang, "This deal closed below the expected cost", "这笔交易结束时的成本低于预期")
        sentence = f"This deal cost {fmt_yuan(actual)}" + (f" against {fmt_yuan(expected)} expected" if expected is not None else "")
        sentence_zh = f"这笔交易的成本为 {fmt_yuan(actual)}" + (f"，预期为 {fmt_yuan(expected)}" if expected is not None else "")
        if on_top:
            sentence += f", including {fmt_yuan(on_top)} of funding on top"
            sentence_zh += f"，其中包含 {fmt_yuan(on_top)} 的额外融资成本"
        sentence += (f"; {fmt_yuan(unmeasured)} of the expected cost was never measured" if unmeasured else "") + "."
        sentence_zh += (f"；预期成本中有 {fmt_yuan(unmeasured)} 始终未能衡量" if unmeasured else "") + "。"
        if revoked and not booked:
            sentence += " The agreement was withdrawn before the discount was given."
            sentence_zh += "协议在给出折扣之前已被撤回。"
        if expected is None:
            sentence += " The cost expected at agreement was not recorded."
            sentence_zh += "达成协议时的预期成本没有记录。"
        if due:
            sentence += f" The buyer kept {kept} of {due} promises" + (f"; {paid_late} {'was' if paid_late == 1 else 'were'} paid late." if paid_late else ".")
            sentence_zh += f"买方在 {due} 项承诺中兑现了 {kept} 项" + (f"；有 {paid_late} 项逾期后才付款。" if paid_late else "。")
        closeout = t(lang, sentence, sentence_zh)
    else:
        closeout = None
        if nothing and planned_actual:
            headline = t(lang, "The planned funding has run; the buyer's payment is still awaited", "计划的融资已执行；买方的付款仍在等待中")
        elif nothing:
            headline = t(lang, "Nothing has happened on this deal yet", "这笔交易目前还没有任何进展")
        elif on_top > 0 or over:
            headline = t(lang, "This deal is costing more than you agreed to", "这笔交易的成本超出了您同意的范围")
        elif "failed" in states:
            headline = t(lang, "An invoice on this deal failed", "这笔交易的一张发票已失败")
        elif lapsed:
            headline = t(lang, "A promise on this deal was missed", "这笔交易中有一项承诺没有兑现")
        elif "late" in states:
            headline = t(lang, "The buyer is late on this deal", "买方在这笔交易上已逾期")
        else:
            headline = t(lang, "This deal is on the agreed terms so far", "到目前为止，这笔交易按约定的条款进行")

    # the one next step
    nxt = None
    if funding_pending:  # cash safety first: the approval of the cure comes before chasing the payment
        nxt = {"label": t(lang, "Review the funding approval", "查看融资批准事项"),
               "text": t(lang, "Funding to cover the shortfall is waiting for your approval.", "弥补缺口的融资正在等待您批准。"),
               "href": "/approvals"}
    for r in sorted(receivables, key=lambda x: x.due_day):
        owed = r.face_fen - r.settled_fen
        if nxt is None and r.status in ("OPEN", "FINANCED") and owed > 0:
            state = collection_state(r.due_day, today, promise_missed=lapsed and r.due_day < today)
            if state in ("OVERDUE", "PROMISE_MISSED"):
                act = collection_action(state, lang)
                nxt = {"label": act["label"],
                       "text": t(lang, f"Chase the {fmt_yuan(owed)} still owed on {invoice_words(ctx.state, r.id, lang)}, which fell due {when_text(r.due_day, today, lang)}.",
                                 f"催收{invoice_words(ctx.state, r.id, lang)}中仍未收的 {fmt_yuan(owed)}，该款已于{when_text(r.due_day, today, lang)}到期。"),
                       "href": f"/receivables?invoice={quote(r.id, safe='')}&customer={quote(buyer, safe='')}"}
                break

    stages = lifecycle_stages(rt, ctx, ds, inp, lang, early_kinds=early_kinds, ended=ended, agreed_when=agreed_when)  # the one function the workspace read calls too
    return {
        "decision_id": ds.decision_id, "lang": lang, "available": True, "unavailable_text": None, "buyer_id": buyer, "buyer_name": name,
        "agreed_when": agreed_when, "agreed_text": agreed_text, "terms_text": terms, "headline_text": headline, "state_word": word, "state_key": key, "ended": ended, "state_tone": wtone,
        "state_text": state_text, "stages": stages, "lifecycle_stages": stages, "cost": cost, "promises": rows,
        "promise_counts": {"buyer_kept": kept, "buyer_total": total, "buyer_paid_late": paid_late, "buyer_due": due, "buyer_to_come": to_come,
                           "text": counts_text}, "buyer": buyer_view, "next": nxt,
        "closeout_text": closeout,
        "links": {"record_href": f"/decisions/{quote(ds.decision_id, safe=':')}",
                  "activity_href": f"/activity?decision={quote(ds.decision_id, safe=':')}"},
        "context": context,
    }


@router.get("/decisions/{decision_id}/tracker")
def get_tracker(decision_id: str, lang: str = "en", *, sel: Annotated[Selection, Depends(selection)]) -> dict[str, Any]:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        ctx = load_context(rt)
        ds, inp = _find(ctx, decision_id)
        subject = ds.offer if ds.offer is not None else ds.commitment
        context = build_context(rt, lang, sel, page="decision", buyer=subject.counterparty_id if subject is not None else None,
                                deal=decision_id)
        try:
            return build_tracker(rt, ctx, ds, inp, lang, context)
        except HTTPException:
            raise
        except Exception:
            log.exception("the tracker of %s could not be drawn", decision_id)
            return _unavailable(decision_id, lang, t(lang, "FLOW could not draw the tracker for this deal just now.",
                                                     "FLOW 暂时无法绘制这笔交易的跟踪页面。"), context)


__all__ = ["COUNT_RELATED_FUNDING", "build_tracker", "router"]
