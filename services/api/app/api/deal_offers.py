"""The Deals read's offer facts: the offer a buyer has waiting for a reply and FLOW's read of it, and what in a deal needs the owner.

Presentation only. The offer's stage is the decision record's own state (`GET /decisions`), its figures the stored verdict's, its words the
workspace's. Nothing is evaluated, projected or priced here, so the read is cheap (no trajectory, no router run)."""

from __future__ import annotations

import logging
from typing import Any

from app.api.decisions import Context
from app.api.presentation import business_action, when_text
from app.api.presentation import t as say
from app.api.workspace import _months
from app.deals import _join, _obligation_text
from app.decisions.state import DealState
from app.domain.models import ObligationType
from app.domain.money import fmt_yuan
from app.operations.log import parse_operation
from app.persistence import ApprovalStatus

# The five steps the Deals workspace shows for an offer, and where each decision state stands among them.
_STAGES = (("received", "Received", "已收到"), ("analysed", "Analysed", "已分析"), ("reply_ready", "Reply ready", "回复已就绪"),
           ("sent", "Sent", "已发送"), ("agreed", "Agreed", "已达成"))
_NOW = {DealState.RECEIVED: 0, DealState.NEEDS_CLARIFICATION: 1, DealState.RESPONSE_READY: 2, DealState.AUTHORIZATION_REQUIRED: 3}
OPEN = tuple(_NOW)
OWNER_WAITS = (DealState.RECEIVED, DealState.RESPONSE_READY, DealState.AUTHORIZATION_REQUIRED)
_COUNT_WORDS = {1: ("One reply is", "一份回复"), 2: ("Two replies are", "两份回复"), 3: ("Three replies are", "三份回复")}


def _stages(state: DealState, lang: str) -> list[dict[str, str]]:
    at = _NOW[state]
    return [{"key": key, "label": say(lang, en, zh), "state": "done" if i < at else "now" if i == at else "todo"}
            for i, (key, en, zh) in enumerate(_STAGES)]


def _read_text(ds: Any, action: str, cost: str, window: tuple[str, str], limit: str, over: bool, lang: str) -> str:
    cost_en, cost_zh = f"it would cost {cost} {window[0]}", f"成本将为{cost}（{window[1]}）"
    rel_en, rel_zh = (f"above your {limit} limit", f"高于您 {limit} 的上限") if over else (f"within your {limit} limit", f"在您 {limit} 的上限内")
    if action == "cannot":
        return say(lang, "FLOW cannot decide on this offer yet.", "FLOW 暂时无法就此报价作出判断。")
    lead = {"accept": ("You can accept it", "可以接受"), "counter": ("Don't accept as asked", "不要按对方要求接受"),
            "decline": ("Don't accept it", "不要接受"), "needs_owner": ("This needs your decision", "需要您来决定")}[action]
    return say(lang, f"{lead[0]}: {cost_en}, {rel_en}.", f"{lead[1]}：{cost_zh}，{rel_zh}。")


_SHORT = {"accept": ("Accept as asked", "按对方要求接受"), "counter": ("Counter instead of accepting as asked", "还价，不按对方要求接受"),
          "decline": ("No deal", "不成交"), "needs_owner": ("Accept, with your approval", "经您批准后接受"),
          "cannot": ("Not safe to act on", "暂不宜据此行动")}
_CLARIFY = ("Clarify before deciding", "先澄清，再决定")


def _headline_short(state: DealState, action: str, lang: str) -> str:
    """The verdict in a few words and no figure: the heading when the figures move to `headline_note`. Same branches as `_read_text`."""
    return say(lang, *(_CLARIFY if state == DealState.NEEDS_CLARIFICATION else _SHORT[action]))


def _headline_note(action: str, cost: str, window: tuple[str, str], limit: str, over: bool, replies: int, lang: str) -> str | None:
    """The figures that left the heading, in one sentence (the same display strings `_read_text` says), with the replies ready for a counter."""
    if action == "cannot":
        return None
    rel_en, rel_zh = (f"above your {limit} limit", f"高于您 {limit} 的上限") if over else (f"within your {limit} limit", f"在您 {limit} 的上限内")
    en, zh = f"As asked costs {cost} {window[0]}, {rel_en}.", f"按对方要求，成本将为{cost}（{window[1]}），{rel_zh}。"
    if action == "counter" and replies:
        w_en, w_zh = _COUNT_WORDS.get(replies, (f"{replies} replies are", f"{replies} 份回复"))
        en, zh = f"{en} {w_en} ready to send.", f"{zh}{w_zh}已可发送。"
    return say(lang, en, zh)


def _action_text(state: DealState, action: str | None, replies: int, lang: str) -> str:
    if state == DealState.RECEIVED:
        return say(lang, "FLOW has not read it yet.", "FLOW 尚未读取。")
    if state == DealState.NEEDS_CLARIFICATION:
        return say(lang, "The buyer needs to clarify first.", "需要买方先澄清。")
    if state == DealState.AUTHORIZATION_REQUIRED or action == "needs_owner":
        return say(lang, "Needs your approval.", "需要您批准。")
    if action == "accept":
        return say(lang, "FLOW can accept it within your limits.", "FLOW 可在您的授权内接受。")
    if action == "counter" and replies:
        en, zh = _COUNT_WORDS.get(replies, (f"{replies} replies are", f"{replies} 份回复"))
        return say(lang, f"{en} ready to send.", f"{zh}已可发送。")
    if action == "decline":
        return say(lang, "FLOW recommends declining.", "FLOW 建议拒绝。")
    return say(lang, "FLOW cannot decide on this yet.", "FLOW 暂时无法判断。")


def _submitted(ctx: Context) -> list[tuple[Any, Any]]:
    """Offers received but not yet evaluated: nothing is logged for them, so the decision record has no candidate. They are found through
    the session's inbound documents (an offer's id is the hash of its documents), the same cache the offer routes read, and derived
    like any decision (state RECEIVED)."""
    from app.compiler.grounding import offer_id_for
    from app.decisions.identity import deal_id
    from app.decisions.state import derive

    docs = [d for d in ctx.rt.documents.values() if d.channel in ("chat", "email", "portal", "attachment")]
    groups: dict[tuple[str, int], list[Any]] = {}
    for d in docs:
        groups.setdefault((d.sender_id, d.received_day), []).append(d)
    known = set(ctx.states())
    out: list[tuple[Any, Any]] = []
    for oid in dict.fromkeys(offer_id_for(g) for g in [*([d] for d in docs), *groups.values()]):
        if deal_id(oid) in known or ctx.offer(oid) is None:
            continue
        try:
            inp = ctx.inputs_for(deal_id(oid))
            out.append((derive(inp), inp))
        except Exception:  # an offer that cannot be derived is logged and not listed
            logging.getLogger("termsledger.decisions").exception("offer %s could not be derived for the deals read", oid)
    return out


def open_offers(ctx: Context, lang: str) -> dict[str, tuple[dict[str, Any], DealState]]:
    """The open offer of each buyer (the newest when there are several), by counterparty id, with the decision record's state."""
    found: dict[str, tuple[Any, Any]] = {}
    for ds, _inp in [*ctx.states().values(), *_submitted(ctx)]:
        if ds.family != "DEAL" or ds.offer is None or ds.state not in OPEN:
            continue
        cp = ds.offer.counterparty_id
        if cp not in found or ds.updated_seq > found[cp][0].updated_seq:
            found[cp] = (ds, ds.offer)
    return {cp: (_open_offer(ctx, ds, offer, lang), ds.state) for cp, (ds, offer) in found.items()}


def _open_offer(ctx: Context, ds: Any, offer: Any, lang: str) -> dict[str, Any]:
    state = ds.state
    verdict = ds.verdict
    cap = ctx.mandate.max_aggregate_forward_concession_fen
    months = _months(ctx.mandate.forward_concession_horizon_days)
    asked = [_obligation_text(o, lang, ctx.today, ctx.state) for o in offer.obligations
             if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION]
    action = business_action(verdict.outcome.value, len(verdict.counters)) if verdict is not None else None
    replies = len(verdict.counters) if verdict is not None and action == "counter" else 0
    window = (f"over {months} months", f"{months} 个月内")
    over = verdict is not None and verdict.forward_concession_total_fen > cap
    return {
        "offer_id": offer.offer_id,
        "verdict_id": verdict.id if verdict is not None else None,
        "received_when": when_text(offer.received_day, ctx.today, lang) if offer.received_day is not None else None,
        "asks_text": _join(asked, lang) if asked else None,
        "read_text": (_read_text(ds, action, fmt_yuan(verdict.forward_concession_total_fen), window, fmt_yuan(cap), over, lang)
                      if verdict is not None and action is not None else None),
        "headline_short": _headline_short(state, action, lang) if verdict is not None and action is not None else None,
        "headline_note": (_headline_note(action, fmt_yuan(verdict.forward_concession_total_fen), window, fmt_yuan(cap), over, replies, lang)
                          if verdict is not None and action is not None else None),
        "action_text": _action_text(state, action, replies, lang),
        "cost_display": fmt_yuan(verdict.forward_concession_total_fen) if verdict is not None else None,
        "cost_window_text": say(lang, window[0], window[1]) if verdict is not None else None,
        "limit_display": fmt_yuan(cap),
        "over_limit": bool(over),
        "replies_ready": replies,
        "stages": _stages(state, lang),
        "tone": "warn" if state in OWNER_WAITS else "info",
    }


def needs_you(ctx: Context, offer_state: DealState | None, counterparty_id: str, pending_documents: bool,
              lang: str) -> tuple[bool, str | None]:
    """Whether something in this deal waits for the owner and one short phrase for the first thing: an open offer waiting for the owner's
    reply, a document waiting for review, an approval waiting on this buyer's invoices, a late invoice to chase."""
    mine = {r.id: r for r in ctx.state.receivables if r.counterparty_id == counterparty_id}
    if offer_state in OWNER_WAITS:
        return True, say(lang, "An offer is waiting for your reply", "有一份报价等待您答复")
    if pending_documents:
        return True, say(lang, "A document is waiting for your review", "有一份文件等待您审核")
    for a in ctx.approvals:
        if a.status != ApprovalStatus.PENDING:
            continue
        op = parse_operation(a.op_json)
        if op is not None and getattr(op, "receivable_id", None) in mine:
            return True, say(lang, "An approval is waiting for you", "有一项批准等待您处理")
    if any(r.status != "SETTLED" and r.outstanding_fen > 0 and r.due_day < ctx.today for r in mine.values()):
        return True, say(lang, "An invoice is late and needs chasing", "有一张发票已逾期，需要催收")
    return False, None


def with_offers(rt: Any, rows: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    """The deals read's rows with `open_offer`, `needs_you` and `needs_you_text` added (call under `rt.lock`). The decision record is read
    once and without the alerts, which no offer stage needs."""
    from app.api.decisions import load_context

    ctx = load_context(rt, found=[])
    offers = open_offers(ctx, lang)
    for row in rows:
        cp = row["counterparty_id"]
        offer, state = offers.get(cp, (None, None))
        needs, text = needs_you(ctx, state, cp, bool(row.get("pending_documents")), lang)
        row.update({"open_offer": offer, "needs_you": needs, "needs_you_text": text})
    return rows
