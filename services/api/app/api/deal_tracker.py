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
from app.api.presentation import (
    decision_state_text,
    invoice_words,
    obligation_sentence,
    party_name,
    reconciliation_words,
    t,
    when_text,
)
from app.api.runtime import get_runtime
from app.api.selection import Selection, build_context, selection
from app.decisions import DealState, DecisionInputs, DecisionState, FundingState, WaitCode, waiting_for
from app.decisions.identity import offer_id_of
from app.decisions.state import RESERVE_ALERT, derive
from app.domain.models import CommitmentStatus, ObligationType
from app.domain.money import fmt_yuan
from app.strategy.receivable_rows import collection_action, collection_state

log = logging.getLogger("termsledger.tracker")
router = APIRouter(dependencies=[Depends(require_owner)])

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_STAGE_STATE = {"done": "done", "now": "now", "todo": "todo", "missed": "missed", "pending": "part", "skipped": "todo", "part": "part"}


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


def _stages(rt: Any, ctx: Context, buyer: str, lang: str, states: list[str], ended: bool, lapsed: bool) -> list[dict[str, Any]]:
    """The contract stages the deal row builds when a confirmed contract is on the books; else the same stages, in the same words, from the
    record's own promises (the first, contract read, is the contract's and does not apply)."""
    words = {"done": ("Done", "已完成"), "now": ("Now", "进行中"), "todo": ("Still to come", "尚未开始"),
             "missed": ("Missed", "已错过"), "part": ("Under way", "等待中")}
    rows: list[dict[str, Any]] = []
    try:
        from app.deals import deal_summary

        rows = deal_summary(rt.store, buyer, ctx.today, lang).get("stages") or []
    except Exception:  # the stages are drawn from the record instead
        log.exception("stages of the deal could not be read")
    if rows:
        mapped = [(s["key"], s["label"], _STAGE_STATE.get(str(s.get("state")), "todo")) for s in rows]
    else:
        early = ("missed" if lapsed or "missed" in states else "done" if "kept" in states[:1] or "part" in states[:1]
                 else "part" if "awaited" in states[:1] else "todo")
        collecting = "done" if ended and "late" not in states and "awaited" not in states else "now"
        mapped = [("negotiated", t(lang, "Terms negotiated", "条款已谈判"), "done"),
                  ("early_payment", t(lang, "Early payment in", "提前付款到账"), early),
                  ("collecting", t(lang, "Collecting", "催收中"), collecting),
                  ("fulfilled", t(lang, "Fulfilled", "已履行完毕"), "done" if ended and collecting == "done" else "todo")]
    return [{"key": k, "label": label, "state": st, "state_text": t(lang, *words[st])} for k, label, st in mapped]


def _booked_discounts(ctx: Context, c: Any, promised: list[Any]) -> dict[Any, int]:
    """The discount booked under the agreement, by the receipt that booked it (a receipt's own figure outranks the promise's, never both)."""
    booked: dict[Any, int] = {}
    for p in promised:
        if p.status == "RECEIVED":
            booked[p.receipt_seq if p.receipt_seq is not None else f"p:{p.obligation_id}"] = p.discount_fen
    for r in ctx.receipts:
        if getattr(r, "commitment_id", None) == c.id and r.status == "MATCHED" and r.agreed_discount_fen > 0:
            booked[r.seq] = r.agreed_discount_fen
    return booked


def _deal_receivables(ctx: Context, c: Any, promised: list[Any]) -> list[Any]:
    ids = dict.fromkeys([p.receivable_id for p in promised]
                        + [ob.base.receivable_id for ob in c.obligations if ob.base.receivable_id])
    rows = [r for r in ctx.state.receivables if r.id in ids]
    rows += [r for r in ctx.state.receivables if r.id not in ids and any(x.startswith(f"{c.id}:") for x in r.applied)]
    return rows


def _buyer_promises(ctx: Context, c: Any, promised: list[Any], receivables: list[Any], buyer: str, lang: str) -> list[dict[str, Any]]:
    agreements = {x.id: party_name(ctx.state, x.counterparty_id) for x in ctx.commitments}
    who = t(lang, "The buyer", "买方")
    out: list[dict[str, Any]] = []
    table = {"RECEIVED": ("kept", "ok", t(lang, "Kept", "已兑现")), "AWAITED": ("awaited", "neutral", t(lang, "Awaited", "等待中")),
             "LAPSED": ("missed", "bad", t(lang, "Missed", "已错过")), "SETTLED_OTHERWISE": ("part", "warn", t(lang, "Part kept", "部分兑现"))}
    for p in promised:
        state, tone, word = table.get(p.status, ("awaited", "neutral", t(lang, "Awaited", "等待中")))
        detail = reconciliation_words(ctx.state, p.detail, ctx.today, promise=True, lang=lang, agreements=agreements) or ""
        out.append({"party": "buyer", "party_text": who,
                    "title_text": t(lang, f"Pay {fmt_yuan(p.expected_fen)} early", f"提前支付 {fmt_yuan(p.expected_fen)}"),
                    "detail_text": detail, "state": state, "state_word": word, "tone": tone,
                    "evidence_href": _entry_href(p.receipt_seq) if state in ("kept", "part") else None,
                    "_seq": p.receipt_seq})
    for r in receivables:
        owed = r.face_fen - r.settled_fen
        words = invoice_words(ctx.state, r.id, lang)
        if r.status == "SETTLED" or owed <= 0:
            state, tone, word = "kept", "ok", t(lang, "Kept", "已兑现")
            detail = t(lang, f"{words[:1].upper()}{words[1:]} has been paid.", f"{words}已付清。")
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
                    "_seq": None})
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


def _funding_lines(ctx: Context, ds: DecisionState, rids: set[str], trouble_day: int | None, lang: str) -> list[dict[str, Any]]:
    """A funding decision the records link to this deal: an invoice advance on one of its invoices (QUOTED), or the cure of a reserve
    shortfall quoted after its payment was missed or late (ATTRIBUTED). The figure is the plan's stored quoted cost; no link, no line."""
    out: list[dict[str, Any]] = []
    for fid, (fds, _inp) in ctx.states().items():
        q = fds.quote
        if fds.family != "FUNDING" or q is None or fds.state in (FundingState.DECLINED, FundingState.FAILED):
            continue
        advance = any(leg.receivable_id in rids for leg in q.legs)
        cause = (not advance and trouble_day is not None and q.alert_kind == RESERVE_ALERT
                 and fds.opened_day is not None and fds.opened_day >= trouble_day)
        if not (advance or cause):
            continue
        pending = fds.state == FundingState.AUTHORIZATION_REQUIRED
        cost = q.total_cost_fen
        extra = (t(lang, " Interest on the draw itself is not in that figure.", "借款本身的利息不含在该数字中。")
                 if q.cost_note == "draw_interest_excluded" else "")
        if cause:
            certainty = "ATTRIBUTED"
            certainty_text = t(lang, "A real figure of your company's, attributed to this deal: it covers a shortfall that followed this "
                                     "buyer's missed or late payment. It is the cost FLOW quoted; the charge itself is not yet booked.",
                               "这是贵公司的真实数字，归于这笔交易：它用于弥补这位买方未付款或逾期付款之后出现的缺口。这是 FLOW 报出的成本，费用本身尚未入账。")
        else:
            certainty = "QUOTED"
            certainty_text = t(lang, "The cost FLOW quoted for funding against this deal's invoice; the charge itself is not yet booked.",
                               "FLOW 为这笔交易的发票融资所报的成本；费用本身尚未入账。")
        if cost is None:
            note = t(lang, "Not measured yet: no cost was quoted for this funding.", "尚未衡量：这笔融资没有报出成本。")
        elif pending:
            note = t(lang, f"Quoted at {fmt_yuan(cost)}; it counts only once you approve it.", f"已报价 {fmt_yuan(cost)}；您批准后才会计入。")
        else:
            note = None
        out.append({
            "key": "funding" if not out else f"funding_{len(out) + 1}",
            "label": (t(lang, "Funding to cover the shortfall this deal left", "弥补这笔交易所致缺口的融资") if cause
                      else t(lang, "Funding against this deal's invoice", "以这笔交易的发票办理的融资")),
            "expected_fen": 0, "expected_display": fmt_yuan(0),
            "actual_fen": None if (pending or cost is None) else cost,
            "actual_display": None if (pending or cost is None) else fmt_yuan(cost),
            "actual_note_text": note, "certainty": certainty, "certainty_text": certainty_text + extra,
            "tone": "neutral" if (pending or cost is None) else "bad", "evidence_href": f"/decisions/{quote(fid, safe=':')}",
            "_pending_fen": cost if pending else None,
        })
    return out


# ---------------------------------------------------------------- the whole read


def _unavailable(decision_id: str, lang: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    cost: dict[str, Any] = {"expected": None, "actual": None, "to_come": None, "difference_fen": None, "difference_display": None, "lines": [],
            "method_text": None}
    return {"decision_id": decision_id, "lang": lang, "available": False, "unavailable_text": text, "buyer_id": None, "buyer_name": None,
            "agreed_when": None, "terms_text": None, "headline_text": None, "state_word": None, "state_tone": "neutral", "state_text": None,
            "stages": [], "cost": cost, "promises": [], "promise_counts": None, "buyer": None, "next": None, "closeout_text": None,
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


def build_tracker(rt: Any, ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str, context: dict[str, Any]) -> dict[str, Any]:
    c = ds.commitment
    if ds.family != "DEAL":
        return _unavailable(ds.decision_id, lang, t(lang, "This is a funding decision, not an agreed deal, so there is nothing to track.",
                                                    "这是一项融资决定，不是已达成的交易，因此没有可跟踪的内容。"), context)
    if c is None or c.status in (CommitmentStatus.PROPOSED,):
        return _unavailable(ds.decision_id, lang, t(lang, "This deal has not been agreed yet, so there is nothing to track.",
                                                    "这笔交易尚未达成，因此没有可跟踪的内容。"), context)
    today, buyer = ctx.today, c.counterparty_id
    name = party_name(ctx.state, buyer)
    promised = [p for p in ctx.promised if getattr(p, "commitment_id", None) == c.id]
    receivables = _deal_receivables(ctx, c, promised)
    rids = {r.id for r in receivables}
    ended = ds.terminal or c.status in (CommitmentStatus.FULFILLED, CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED)

    # the cost expected at agreement, and the cost so far
    expected = _expected(ds)
    terms = _short_terms(ctx, ds, lang)
    booked = _booked_discounts(ctx, c, promised)
    booked_fen = sum(booked.values())
    lapsed = any(p.status == "LAPSED" for p in promised) or bool(c.lapsed_obligations)
    if booked:
        if expected is not None and expected > booked_fen and not ended:
            gap = expected - booked_fen
            note = t(lang, f"Not measured yet: {fmt_yuan(gap)} of the expected cost, which no record holds yet.",
                     f"尚未衡量：预期成本中有 {fmt_yuan(gap)} 目前没有任何记录。")
        elif expected is not None and expected > booked_fen:
            note = t(lang, f"Not measured: {fmt_yuan(expected - booked_fen)} of the expected cost, which no record holds.",
                     f"未能衡量：预期成本中有 {fmt_yuan(expected - booked_fen)} 没有任何记录。")
        else:
            note = None
    elif lapsed:
        note = t(lang, "The early payment did not arrive, so no discount has been given under the agreement.",
                 "提前付款没有到账，因此这份协议下没有给出任何折扣。")
    else:
        note = t(lang, "Nothing has been paid under the agreement yet.", "这份协议下目前还没有任何付款。")
    first_seq = min((k for k in booked if isinstance(k, int)), default=None)
    terms_line = {
        "key": "terms", "label": t(lang, "The terms you gave the buyer", "您给买方的条款"),
        "expected_fen": expected, "expected_display": _money(expected), "actual_fen": booked_fen, "actual_display": fmt_yuan(booked_fen),
        "actual_note_text": note, "certainty": "RECORDED",
        "certainty_text": t(lang, "Booked: the discount the bank receipts under this agreement posted. The expected figure is the one FLOW quoted when you agreed.",
                            "已入账：这份协议下银行收款所记的折扣。预期数字是您达成协议时 FLOW 报出的数字。"),
        "tone": "bad" if expected is not None and booked_fen > expected else "ok", "evidence_href": _entry_href(first_seq),
    }
    trouble = [p.promised_day for p in promised if p.status == "LAPSED" and p.promised_day is not None]
    trouble += [r.due_day for r in receivables if r.status in ("OPEN", "FINANCED") and r.face_fen - r.settled_fen > 0 and r.due_day < today]
    fund = _funding_lines(ctx, ds, rids, min(trouble) if trouble else None, lang)
    lines = [terms_line, *fund]
    actual = sum(x["actual_fen"] for x in lines if x["actual_fen"] is not None)
    pending_fen = sum(x["_pending_fen"] for x in fund if x["_pending_fen"] is not None)
    awaiting_fen = sum(p.discount_fen for p in promised if p.status == "AWAITED")
    for x in fund:
        x.pop("_pending_fen")
    diff = actual - expected if expected is not None else None
    if diff is None:
        actual_note, tone = t(lang, "The cost expected at agreement was not recorded.", "达成协议时的预期成本没有记录。"), "neutral"
    elif diff > 0:
        actual_note, tone = t(lang, f"{fmt_yuan(diff)} more than expected", f"比预期多 {fmt_yuan(diff)}"), "bad"
    elif diff < 0 and not ended and actual == 0:
        actual_note, tone = t(lang, "Nothing has been booked against the expected cost yet", "预期成本目前还没有任何入账"), "neutral"
    elif diff < 0 and not ended:
        actual_note, tone = t(lang, f"{fmt_yuan(-diff)} less than expected so far", f"目前比预期少 {fmt_yuan(-diff)}"), "ok"
    elif diff < 0:
        actual_note, tone = t(lang, f"{fmt_yuan(-diff)} less than expected", f"比预期少 {fmt_yuan(-diff)}"), "ok"
    else:
        actual_note, tone = t(lang, "As expected", "与预期一致"), "ok"
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
        "difference_fen": diff, "difference_display": _money(diff), "lines": lines,
        "method_text": t(lang, "Expected is the cost FLOW quoted when you agreed. Cost so far adds up only what the records hold: the discount "
                              "booked from bank receipts and the quoted cost of funding linked to this deal; a part no record measures is said so.",
                        "预期成本是您达成协议时 FLOW 报出的成本。至今成本只累计记录中已有的内容：银行收款所记的折扣，以及与这笔交易相关的融资报价成本；没有记录的部分会如实说明。"),
    }

    # promises
    buyer_rows = _buyer_promises(ctx, c, promised, receivables, buyer, lang)
    rows = [*buyer_rows, *_owner_promises(ctx, ds, promised, lang)]
    for r in rows:
        r.pop("_seq", None)
    kept = sum(1 for r in buyer_rows if r["state"] == "kept")
    total = len(buyer_rows)
    if total == 0:
        counts_text = t(lang, "The buyer has made no promise on this deal yet.", "买方在这笔交易中还没有作出承诺。")
    else:
        counts_text = t(lang, f"The buyer has kept {_num(kept, lang)} of {_num(total, lang)} promises on this deal.",
                        f"买方在这笔交易的 {total} 项承诺中已兑现 {kept} 项。")
    behaviour = None
    try:
        from app.books import books_from_store
        from app.strategy.payments import payment_behaviour

        pb = payment_behaviour(rt.store, books_from_store(rt.store), buyer, today, lang=lang)
        behaviour = None if pb.insufficient else pb.sentence
    except Exception:  # noqa: BLE001  feature off or too few invoices: only the deal's own count
        behaviour = None
    buyer_view = {"text": f"{counts_text} {behaviour}".strip() if behaviour else counts_text,
                  "note_text": t(lang, "FLOW will show this beside the next offer from this buyer. It does not change what FLOW may accept on your behalf.",
                                 "FLOW 会在这位买方的下一份报价旁显示这些信息。它不会改变 FLOW 可以代您接受的范围。"),
                  "href": f"/customers/{quote(buyer, safe='')}"}

    accept = next((o for o in ds.ops if o.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and o.day is not None), None)
    agreed_when = when_text(accept.day, today, lang) if accept is not None else None

    # the state
    states = [r["state"] for r in buyer_rows]
    nothing = not booked and not fund and all(s == "awaited" for s in states) and not lapsed
    if "missed" in states or lapsed:
        word, wtone = t(lang, "Promise missed", "承诺未兑现"), "bad"
    elif "late" in states:
        word, wtone = t(lang, "Payment late", "付款逾期"), "bad"
    elif "part" in states:
        word, wtone = t(lang, "Part kept", "部分兑现"), "warn"
    elif ds.state == DealState.FULFILLED:
        word, wtone = t(lang, "Completed", "已完成"), "ok"
    elif c.status in (CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED):
        word, wtone = t(lang, "Ended", "已结束"), "neutral"
    elif nothing:
        word, wtone = t(lang, "Waiting for the buyer", "等待买方"), "neutral"
    else:
        word, wtone = t(lang, "On plan", "按计划进行"), "ok"
    w = waiting_for(ds, inp)
    from app.api.decisions import waiting_view

    wait_text = waiting_view(ctx, ds, inp, lang)["text"] if w.code != WaitCode.NOTHING else ""
    state_text = f"{decision_state_text('DEAL', ds.state.value, lang)}. {wait_text}".strip() if lang != "zh" else (
        f"{decision_state_text('DEAL', ds.state.value, lang)}。{wait_text}")
    if ended:
        if diff is None:
            headline = t(lang, "This deal has closed", "这笔交易已结束")
        elif diff > 0:
            headline = t(lang, "This deal closed above the expected cost", "这笔交易结束时的成本高于预期")
        elif lapsed or "missed" in states:
            headline = t(lang, "This deal ended with the buyer's promise missed", "这笔交易结束时买方未兑现承诺")
        elif "late" in states:
            headline = t(lang, "The agreement is complete, but the buyer is late on the rest of the invoice",
                         "协议已履行完毕，但买方对发票余款已逾期")
        elif diff == 0:
            headline = t(lang, "This deal closed as expected", "这笔交易按预期结束")
        else:
            headline = t(lang, "This deal closed below the expected cost", "这笔交易结束时的成本低于预期")
        closeout = t(lang, f"This deal cost {fmt_yuan(actual)} against {_money(expected) or 'an expected cost that was not recorded'}. {counts_text}",
                     f"这笔交易的成本为 {fmt_yuan(actual)}，预期为 {_money(expected) or '未记录'}。{counts_text}")
    else:
        closeout = None
        if nothing:
            headline = t(lang, "Nothing has happened on this deal yet", "这笔交易目前还没有任何进展")
        elif diff is not None and diff > 0:
            headline = t(lang, "This deal is costing more than you agreed to", "这笔交易的成本超出了您同意的范围")
        elif wtone == "bad":
            headline = t(lang, "A promise on this deal has not been kept", "这笔交易中有一项承诺没有兑现")
        else:
            headline = t(lang, "This deal is on plan", "这笔交易按计划进行")

    # the one next step
    nxt = None
    for r in sorted(receivables, key=lambda x: x.due_day):
        owed = r.face_fen - r.settled_fen
        if r.status in ("OPEN", "FINANCED") and owed > 0:
            state = collection_state(r.due_day, today, promise_missed=lapsed and r.due_day < today)
            if state in ("OVERDUE", "PROMISE_MISSED"):
                act = collection_action(state, lang)
                nxt = {"label": act["label"],
                       "text": t(lang, f"Chase the {fmt_yuan(owed)} still owed on {invoice_words(ctx.state, r.id, lang)}, which fell due {when_text(r.due_day, today, lang)}.",
                                 f"催收{invoice_words(ctx.state, r.id, lang)}中仍未收的 {fmt_yuan(owed)}，该款已于{when_text(r.due_day, today, lang)}到期。"),
                       "href": f"/receivables?invoice={quote(r.id, safe='')}&customer={quote(buyer, safe='')}"}
                break
    if nxt is None and pending_fen:
        nxt = {"label": t(lang, "Review the funding approval", "查看融资批准事项"),
               "text": t(lang, "Funding to cover the shortfall is waiting for your approval.", "弥补缺口的融资正在等待您批准。"),
               "href": "/approvals"}

    return {
        "decision_id": ds.decision_id, "lang": lang, "available": True, "unavailable_text": None, "buyer_id": buyer, "buyer_name": name,
        "agreed_when": agreed_when, "terms_text": terms, "headline_text": headline, "state_word": word, "state_tone": wtone,
        "state_text": state_text, "stages": _stages(rt, ctx, buyer, lang, states, ended, lapsed), "cost": cost, "promises": rows,
        "promise_counts": {"buyer_kept": kept, "buyer_total": total, "text": counts_text}, "buyer": buyer_view, "next": nxt,
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


__all__ = ["build_tracker", "router"]
