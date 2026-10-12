"""GET /offers/{offer_id}/picture: an offer's cash picture, one line for the offer as asked and one for each reply FLOW has ready.

A presentation read, computed on request and cached per state version. It reads the stored verdict (the obligations it bound and its
counters) and the books, and projects them with the engine's own projector and router; nothing is evaluated, stored, logged or decided,
so it never changes the verdict, the books or the log."""

from __future__ import annotations

import re
import threading
from bisect import bisect_right
from collections import Counter, OrderedDict
from functools import reduce
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.decisions import latest_verdict_for
from app.api.home import _distance, _lowest_ahead, _series
from app.api.presentation import (
    business_action,
    business_text,
    buyer_of_receivable,
    counter_economics,
    first_breach_ahead,
    fmt_short,
    option_label,
    party_name,
    series_axis,
    when_text,
    whole,
)
from app.api.presentation import t as say
from app.api.runtime import get_runtime
from app.api.workspace import _months, _posted_discount
from app.books import current_books
from app.domain.models import (
    Actor,
    FundingActionKind,
    LedgerEventKind,
    Mode,
    ObligationType,
    Outcome,
    RecordCommitment,
    Tier,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.financial import EngineError, project
from app.funding import plan
from app.mandate import tier_for
from app.operations import lengthens_terms
from app.operations.executor import only_early_pay
from app.verifier import counter_recheck
from app.verifier.evaluate import CAP_CODES
from app.verifier.screen import SECURITY_CODES

router = APIRouter(tags=["offers"], dependencies=[Depends(require_owner)])

_CACHE_SIZE = 32
_cache: OrderedDict[tuple, dict[str, Any]] = OrderedDict()
_lock = threading.Lock()
_ID = re.compile(r"\s*[(（](?:OFF|RCV|COM|FAC|BUYER|CTR|VER|DOC|APR)-[^)）]*[)）]")
_RECEIVABLE = re.compile(r"(RCV-[\w-]+|RI:[\w:-]+)")


def _business_events(state: Any, points: list[dict[str, Any]], raw_labels: dict[tuple[int, int], str], lang: str) -> None:
    """Event labels the owner can read: an early settlement says whose payment it is, and no id stays in a label."""
    for p in points:
        for i, e in enumerate(p["events"]):
            raw = raw_labels.get((p["day"], i), "")
            if e["kind"] == "EARLY_RECEIPT":
                m = _RECEIVABLE.search(raw)
                who = party_name(state, buyer_of_receivable(state, m.group(1))) if m else ""
                e["label_short"] = say(lang, f"Early payment from {who}" if who else "Early payment",
                                       f"来自{who}的提前付款" if who else "提前付款")
                e["label"] = e["label_short"]
            else:
                e["label"] = _ID.sub("", e["label"])
                e["label_short"] = _ID.sub("", e["label_short"])


def _line(state: Any, traj: Any, today: int, lang: str) -> list[dict[str, Any]]:
    points = _series(state, traj, lang, from_day=today)
    raw = {(d.day, i): ev.label for d in traj.days if d.day >= today for i, ev in enumerate(d.events)}
    _business_events(state, points, raw, lang)
    return points


def _lowest(state: Any, traj: Any, today: int, lang: str) -> dict[str, Any]:
    low, day = _lowest_ahead(traj, today)
    return {"lowest_fen": low, "lowest_short": fmt_short(low), "lowest_when": _distance(day, today, lang)}


# ---------------------------------------------------------------- the paths: one entry per line on the chart, with its column's words

_TERM_ROWS = (("payment_terms", "Payment terms", "账期"), ("early_payment", "Early payment", "提前付款"),
              ("rebate_or_price", "Rebate or price", "返利或价格"))


def _terms_in_force(state: Any, buyer: str | None) -> int | None:
    """The payment terms the books write on this buyer's next invoice (the recurring invoice's own terms), or None when unknown."""
    ri = next((x for x in state.recurring_invoices if x.counterparty_id == buyer), None)
    return ri.terms_days if ri is not None else None


def _payment_days(state: Any, obligations: list[Any], buyer: str | None) -> int | None:
    """The payment terms of a path in days: its terms extension's target (or the terms in force plus its delta), else the terms in force."""
    in_force = _terms_in_force(state, buyer)
    ext = next((o for o in obligations if o.type == ObligationType.TERMS_EXTENSION), None)
    if ext is None:
        return in_force
    if ext.target_terms_days is not None:
        return int(ext.target_terms_days)
    return in_force + ext.days_delta if in_force is not None and ext.days_delta is not None else None


def _pct(rate_bp: int | None, *, absolute: bool = False) -> str:
    """A rate as a percentage, with its sign; `absolute` where the words around it (a price cut) already carry the sign."""
    if rate_bp is None:
        return "?"
    return fmt_pct(bp(abs(rate_bp) if absolute else rate_bp))


def _rebate_what(o: Any) -> str:
    """A rebate as the terms rows say it: its rate, else its amount."""
    return _pct(o.rate_bp) if o.rate_bp is not None else (fmt_yuan(o.amount_fen) if o.amount_fen is not None else "")


def _term_rows(state: Any, obligations: list[Any], buyer: str | None, lang: str) -> dict[str, tuple[str, str]]:
    """The three rows of a path from its obligations, each as (what the column says, the same said after "instead of"). A term the
    path does not carry is "None"; payment terms it leaves alone are the terms in force."""
    none = say(lang, "None", "无")
    days = _payment_days(state, obligations, buyer)
    if days is not None:
        terms = (say(lang, f"{days} days", f"{days} 天"), say(lang, str(days), f"{days} 天"))
    else:
        unchanged = say(lang, "Unchanged", "不变")
        terms = (unchanged, unchanged)
    early = [o for o in obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    if early:
        parts = []
        for o in early:
            face = o.base.amount_fen
            parts.append(say(lang, f"{_pct(o.rate_bp)} off {fmt_yuan(face)}" if face is not None else f"{_pct(o.rate_bp)} off",
                             f"{fmt_yuan(face)} 减免 {_pct(o.rate_bp)}" if face is not None else f"减免 {_pct(o.rate_bp)}"))
        text = say(lang, ", ", "、").join(parts)
        early_row = (text, text)
    else:
        early_row = (none, say(lang, "none", "无"))
    other = []
    for o in obligations:
        if o.type == ObligationType.CONTINGENT_REBATE:
            what = _rebate_what(o)
            other.append((say(lang, f"{what} rebate".strip(), f"{what} 返利".strip()),
                          say(lang, f"a {what} rebate" if what else "a rebate", f"{what} 返利".strip())))
        elif o.type == ObligationType.PRICE_ADJUSTMENT:
            rise = (o.rate_bp or 0) >= 0
            what = _pct(o.rate_bp, absolute=True) if o.rate_bp is not None else ""
            word = say(lang, "price rise" if rise else "price cut", "提价" if rise else "降价")
            text = f"{what} {word}".strip() if lang != "zh" else f"{word} {what}".strip()
            other.append((text, say(lang, f"a {text}", text)))
    if other:
        join = say(lang, ", ", "、")
        other_row = (join.join(v for v, _ in other), join.join(i for _, i in other))
    else:
        other_row = (none, say(lang, "none", "无"))
    return {"payment_terms": terms, "early_payment": early_row, "rebate_or_price": other_row}


def _terms_view(rows: dict[str, tuple[str, str]], asked_rows: dict[str, tuple[str, str]] | None, lang: str) -> list[dict[str, Any]]:
    out = []
    for key, en, zh in _TERM_ROWS:
        value, instead = rows[key][0], None
        if asked_rows is not None and value != asked_rows[key][0]:
            instead = say(lang, f"instead of {asked_rows[key][1]}", f"而非 {asked_rows[key][1]}")
        out.append({"key": key, "label": say(lang, en, zh), "value_text": value, "instead_of_text": instead})
    return out


def _next_invoice_day(state: Any, traj: Any, today: int, buyer: str | None) -> int | None:
    """The day the buyer's next not-yet-issued invoice is paid on this path: the first receipt of a recurring invoice of theirs."""
    for d in traj.days:
        if d.day < today:
            continue
        for e in d.events:
            if e.kind == LedgerEventKind.RECEIPT and e.ref and e.ref.startswith("RI:") and buyer_of_receivable(state, e.ref) == buyer:
                return d.day
    return None


def _days_below(series: list[dict[str, Any]], floor: int, breach_day: int) -> int | None:
    """How many days the line stays below the minimum from its first breach until the first day it is back at or above it; None when it
    is not back within the forecast."""
    back = next((p["day"] for p in series if p["day"] > breach_day and p["closing_fen"] >= floor), None)
    return None if back is None else back - breach_day


def _tag(lang: str, kind: str | None) -> tuple[str | None, str | None]:
    return {"over": (say(lang, "Over your limit", "超出您的授权"), "bad"),
            "recommended": (say(lang, "FLOW recommends", "FLOW 推荐"), "info"),
            "approval": (say(lang, "Needs your approval", "需要您批准"), "warn")}.get(kind or "", (None, None))


# who decides: three classes, from the verifier's own verdict and the funding plan's flag (never from the route's own rule)
FLOW_MAY, NEEDS_OWNER, OVER_LIMIT = "flow_may", "needs_owner", "over_limit"


def _authority_text(lang: str, authority: str) -> str:
    return {FLOW_MAY: say(lang, "FLOW can send it", "FLOW 可以直接发送"),
            NEEDS_OWNER: say(lang, "Needs your approval", "需要您批准"),
            OVER_LIMIT: say(lang, "Over a limit you signed: only a new mandate changes that",
                            "超出您签署的上限：只有签署新的授权才能改变")}[authority]


def _asked_authority(lang: str, verdict: Any) -> tuple[str | None, str]:
    """(authority, its words) for the offer as asked. A cap violation is over a limit you signed; an acceptance is the verdict's tier
    OR-ed with the funding plan's flag; a counter instead of an acceptance says so; the other outcomes are not a question of authority."""
    codes = {v.code for v in verdict.violations}
    owner = verdict.required_tier != Tier.TIER_1 or bool(verdict.plan is not None and verdict.plan.needs_owner_approval)
    if codes & CAP_CODES:
        return OVER_LIMIT, _authority_text(lang, OVER_LIMIT)
    if verdict.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
        authority = NEEDS_OWNER if owner or verdict.outcome == Outcome.NEEDS_OWNER_APPROVAL else FLOW_MAY
        return authority, _authority_text(lang, authority)
    if verdict.outcome == Outcome.NO_VERDICT:
        return None, say(lang, "FLOW needs one more fact before it can price this", "FLOW 还需要再确认一个事实才能为此定价")
    if verdict.outcome == Outcome.NO_DEAL:
        return None, say(lang, "There is no deal to send: it ended without an agreement", "没有可发送的交易：它未达成协议就结束了")
    if codes & SECURITY_CODES:
        return None, say(lang, "FLOW will not act on this: the message failed its security checks", "FLOW 不会处理此消息：它未通过安全检查")
    if verdict.outcome == Outcome.COUNTER or verdict.counters:  # the offer as asked is not sent; the replies carry the authority
        return None, say(lang, "FLOW counters instead", "FLOW 改为还价")
    return None, say(lang, "FLOW cannot accept this as asked", "FLOW 无法按对方的要求接受")


def _reply_authority(lang: str, verdict: Any | None, owner: bool) -> tuple[str | None, str]:
    """(authority, its words) for a reply, from the verifier's own re-check of the counter as an agreement (`verdict`), `owner` being
    that tier OR-ed with the executor's tier and the funding plan's flag."""
    if verdict is None or verdict.outcome == Outcome.NO_VERDICT:  # the re-check gave no verdict (or could not be run)
        if verdict is not None and {v.code for v in verdict.violations} & CAP_CODES:
            return OVER_LIMIT, _authority_text(lang, OVER_LIMIT)
        return None, say(lang, "FLOW needs one more fact before it can price this", "FLOW 还需要再确认一个事实才能为此定价")
    if {v.code for v in verdict.violations} & CAP_CODES:
        return OVER_LIMIT, _authority_text(lang, OVER_LIMIT)
    if verdict.outcome not in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
        return None, say(lang, "FLOW cannot send this reply as it stands", "FLOW 目前无法发送此回复")
    authority = NEEDS_OWNER if owner else FLOW_MAY
    return authority, _authority_text(lang, authority)


def _decides(lang: str, authority: str | None, authority_text: str, sendable: bool, needs_owner: bool, terms_change: bool) -> str:
    """The sentence the page of `dev` reads, kept as it was where it was true; a case it never covered says the authority's words."""
    if authority == OVER_LIMIT:
        return say(lang, "Cannot be accepted within your signed limits.", "在您已签署的授权内无法接受。")
    if authority is None or not sendable:
        return authority_text
    if needs_owner and terms_change:
        return say(lang, "It changes your terms, so you approve it first.", "它会改变您的条款，需要您先批准。")
    if needs_owner:
        return say(lang, "It is above what FLOW may agree alone, so you approve it first.", "它超出 FLOW 可自行同意的范围，需要您先批准。")
    return say(lang, "FLOW can send it. Your approval is not needed.", "FLOW 可以发送。无需您批准。")


# ---------------------------------------------------------------- the evidence behind who decides

def _owner_rule(terms_change: bool, early_pay_only: bool, tier: Tier, in_plan: bool) -> str:
    """Which rule sent a reply to the owner, in the order the mandate applies them (`tier_for`: a terms change, then anything beyond an
    early payment on a named invoice, then a value above the single-commitment threshold), then the funding plan's flag, else the
    verifier's own re-check. The same facts `owner` is made of; nothing is decided here."""
    if terms_change:
        return "terms"
    if not early_pay_only:
        return "beyond_early_pay"
    if tier != Tier.TIER_1:
        return "value"
    return "plan" if in_plan else "recheck"


def _rule_text(lang: str, rule: str, mandate: Any) -> str:
    return {
        "terms": say(lang, "Your mandate lets FLOW send a counter on its own only when the terms stay as they are.",
                     "您的授权只允许 FLOW 在条款保持不变时自行发送还价。"),
        "beyond_early_pay": say(lang, "Your mandate lets FLOW agree on its own only to an early-payment discount on a named invoice, with nothing else changed.",
                                "您的授权只允许 FLOW 自行同意针对指定发票的提前付款折扣，且不改变其他任何条款。"),
        "value": say(lang, f"Your mandate lets FLOW agree on its own only to a commitment of up to {fmt_yuan(mandate.tier2_single_commitment_fen)}.",
                     f"您的授权只允许 FLOW 自行同意不超过 {fmt_yuan(mandate.tier2_single_commitment_fen)} 的承诺。"),
        "plan": say(lang, "The funding plan this reply needs requires your approval because of its cost.",
                    "此回复所需的融资方案因其成本需要您批准。"),
        "recheck": say(lang, "The verifier's own check of this reply asks for your approval.", "验证器对此回复的复核要求您批准。"),
    }[rule]


def _signed_pct(rate_bp: int | None) -> str:
    return "?" if rate_bp is None else (f"+{_pct(rate_bp)}" if rate_bp >= 0 else f"−{_pct(rate_bp, absolute=True)}")


def _changes_text(lang: str, state: Any, obligations: list[Any], buyer: str | None) -> str:
    """Each term the reply changes against the terms in force, before → after, from the fields the terms column reads: the payment days
    (`_payment_days`), the early-payment and rebate words (`_term_rows`), the price adjustment's own rate."""
    now, after = _term_rows(state, [], buyer, lang), _term_rows(state, obligations, buyer, lang)
    out: list[str] = []
    before_days, after_days = _payment_days(state, [], buyer), _payment_days(state, obligations, buyer)
    if after_days is not None and after_days != before_days:
        out.append(say(lang, f"Payment terms {before_days} → {after_days} days." if before_days is not None else f"Payment terms {after_days} days.",
                       f"账期 {before_days} → {after_days} 天。" if before_days is not None else f"账期 {after_days} 天。"))
    if after["early_payment"][0] != now["early_payment"][0]:
        out.append(say(lang, f"Early payment {now['early_payment'][1]} → {after['early_payment'][0]}.",
                       f"提前付款 {now['early_payment'][1]} → {after['early_payment'][0]}。"))
    for o in obligations:
        if o.type == ObligationType.CONTINGENT_REBATE:
            out.append(say(lang, f"Rebate none → {_rebate_what(o)}.", f"返利 无 → {_rebate_what(o)}。"))
        elif o.type == ObligationType.PRICE_ADJUSTMENT:
            out.append(say(lang, f"Price on future invoices {_signed_pct(o.rate_bp)}.", f"今后发票的价格 {_signed_pct(o.rate_bp)}。"))
    return say(lang, " ", "").join(out)


def _stays_text(lang: str, state: Any, obligations: list[Any], buyer: str | None, mandate: Any) -> str:
    """What a reply FLOW may send leaves as it is, and the limit what it does offer sits within."""
    days = _payment_days(state, obligations, buyer)
    stays = [say(lang, f"Terms stay at {days} days" if days is not None else "Terms stay as they are",
                 f"账期保持 {days} 天" if days is not None else "账期保持不变")]
    if not any(o.type in (ObligationType.CONTINGENT_REBATE, ObligationType.PRICE_ADJUSTMENT) for o in obligations):
        stays.append(say(lang, "no rebate", "无返利"))
    text = say(lang, ", ", "，").join(stays) + say(lang, ".", "。")
    cap = mandate.max_immediate_discount_bp
    for o in obligations:
        if o.type == ObligationType.IMMEDIATE_DISCOUNT:
            limit = say(lang, f"the {_pct(cap)} limit you signed" if cap is not None else "the limit you signed",
                        f"您签署的 {_pct(cap)} 上限" if cap is not None else "您签署的上限")
            text += say(lang, f" The early-settlement offer at {_pct(o.rate_bp)} is within {limit}.",
                        f"{_pct(o.rate_bp)} 的提前结算方案在{limit}之内。")
    return text


def _authority_reason(lang: str, authority: str | None, owner_rule: str | None, state: Any, obligations: list[Any], buyer: str | None,
                      mandate: Any) -> str | None:
    """The evidence behind `decides_text` for a reply: what it changes and the mandate rule it crosses (it needs the owner), or what it
    leaves alone and the limit it sits within (FLOW may send it); nothing for any other path."""
    if authority == NEEDS_OWNER and owner_rule is not None:
        return f"{_changes_text(lang, state, obligations, buyer)}{say(lang, ' ', '')}{_rule_text(lang, owner_rule, mandate)}".strip()
    if authority == FLOW_MAY:
        return _stays_text(lang, state, obligations, buyer, mandate)
    return None


def _cost_note_reply(c: Any, months: int, lang: str) -> str:
    cost, forward = c.supplier_cost_fen, c.forward_value_fen
    if cost > 0 and forward <= 0:
        return say(lang, "once; nothing ongoing", "一次性；之后无持续成本")
    if cost > 0:
        return say(lang, f"once, plus {fmt_yuan(forward)} over {months} months", f"一次性，另加 {months} 个月内 {fmt_yuan(forward)}")
    if forward > 0:
        return say(lang, f"over {months} months", f"{months} 个月内")
    kinds = {o.type for o in c.obligations}
    gain = any(o.type == ObligationType.PRICE_ADJUSTMENT and (o.rate_bp or 0) > 0 for o in c.obligations)
    if gain and ObligationType.TERMS_EXTENSION in kinds:
        return say(lang, "the price rise pays for the longer terms", "提价抵补了延长账期的成本")
    return say(lang, "nothing to pay", "无需付出成本")


def _cost_basis(once: int, forward: int, months: int, net: bool, lang: str) -> tuple[str | None, str]:
    """(the one total, its basis) from the two kernel parts. A total exists only when exactly one part does (then it is that part);
    when both do there is no total: the two parts stand side by side, never added. `net`: the cost nets a funding cost against an offset."""
    if once > 0 and forward > 0:
        return None, say(lang, "two parts: once, and over 12 months".replace("12", str(months)), f"两部分：一次性，以及 {months} 个月内")
    if once > 0:
        return fmt_yuan(once), say(lang, "once, nothing ongoing", "一次性，之后无持续成本")
    if forward > 0:
        return fmt_yuan(forward), say(lang, f"over {months} months", f"{months} 个月内")
    if net:
        return fmt_yuan(0), say(lang, f"net over {months} months", f"{months} 个月内的净额")
    return fmt_yuan(0), say(lang, "nothing to pay", "无需付出成本")


def _reply_cost(c: Any, state: Any, mandate: Any, months: int, lang: str, plan_cost_fen: int = 0) -> dict[str, Any]:
    """One reply's cost on the common basis: the 12-month figure when the verifier gives one, else the one-off, with the basis said and
    the two kernel parts beside it (never added here). A reply whose net is the funding cost less a price offset carries both
    components, from the `dev` page's own `counter_economics`."""
    once, forward = c.supplier_cost_fen, c.forward_value_fen
    try:
        eco = counter_economics(list(c.obligations), state, mandate)
    except EngineError:
        eco = None
    components: list[dict[str, str]] = []
    if eco is not None and eco["is_net"]:
        kinds = {o.type for o in c.obligations}
        price = next((o for o in c.obligations if o.type == ObligationType.PRICE_ADJUSTMENT), None)
        longer = ObligationType.TERMS_EXTENSION in kinds
        components = [
            {"label": say(lang, "Funding cost of the longer terms" if longer else "Funding cost",
                          "延长账期的融资成本" if longer else "融资成本"), "display": eco["funding_cost_display"]},
            {"label": (say(lang, f"Offset by the {_pct(price.rate_bp, absolute=True)} price rise",
                           f"{_pct(price.rate_bp, absolute=True)} 提价的抵补")
                       if price is not None and price.rate_bp is not None and price.rate_bp > 0
                       else say(lang, "Offset by the price adjustment", "价格调整的抵补")), "display": eco["offset_display"]}]
        if plan_cost_fen > 0:  # the router's plan that funds the shortfall on these terms: beside the net, which the verifier does not add it to
            components.append({"label": say(lang, "Funding plan for the shortfall (not in the net)", "补足缺口的融资方案（不计入净额）"),
                               "display": fmt_yuan(plan_cost_fen)})
    total, basis = _cost_basis(once, forward, months, bool(components), lang)
    return {"cost_total_display": total, "cost_basis_text": basis,
            "cost_once_display": fmt_yuan(once) if once > 0 else None,
            "cost_forward_display": fmt_yuan(forward) if forward > 0 else None, "cost_components": components}


def _below_band(series: list[dict[str, Any]], floor: int, breach_day: int, lang: str) -> str:
    n = _days_below(series, floor, breach_day)
    return (say(lang, f"Below your minimum for {n} {'day' if n == 1 else 'days'}", f"低于您的最低现金储备 {n} 天") if n is not None
            else say(lang, "Below your minimum to the end of the forecast", "到预测期结束前一直低于您的最低现金储备"))


def _recommended_reason(lang: str, needs_owner: bool) -> str:
    """Why this reply is the recommended one, by the rule `_paths` applies (the first reply FLOW could send, in the verdict's order: one
    FLOW may send alone, else the first that needs the owner). Nothing about cost: cost is not what picks it."""
    if needs_owner:
        return say(lang, "Recommended because it is the first counter within your mandate; it needs your approval.",
                   "推荐原因：它是您授权范围内的第一个还价；需要您批准。")
    return say(lang, "Recommended because FLOW can send it within your mandate without your approval.",
               "推荐原因：FLOW 可以在您的授权范围内直接发送，无需您批准。")


_LANDING_KINDS = {FundingActionKind.DRAW: ("credit-line draw", "信用额度提款"), FundingActionKind.FINANCE_INVOICE: ("invoice financing", "发票融资")}


def _plan_legs(actions: list[Any], today: int, lang: str) -> str:
    """A funding plan's legs that bring cash in, in the Home's words ("¥150k credit-line draw today, ¥255k invoice financing in 3 days"):
    each leg's own amount and landing day (the router's `lands_day`, else the day it is requested), the short money form, no figure made here."""
    parts = []
    for a in actions:
        if a.kind not in _LANDING_KINDS:
            continue
        what = say(lang, *_LANDING_KINDS[a.kind])
        when = when_text(a.lands_day if a.lands_day is not None else a.day, today, lang)
        parts.append(say(lang, f"{fmt_short(a.amount_fen)} {what} {when}", f"{what} {fmt_short(a.amount_fen)}（{when}）"))
    return say(lang, ", ", "、").join(parts)


def _scenario_assumption(lang: str, kind: str, legs: str | None, *, funded: bool, projected: bool = True) -> str:
    """What a path's line assumes, the sentence a chart states beside it: the offer as asked takes no new funding; a reply is drawn as if
    the buyer accepts it and with the funding plan the router found for it (its legs), or without one when none is admissible."""
    if kind == "asked":
        return say(lang, "Assumes the buyer accepts this offer and FLOW takes no new funding.", "假设买方接受此报价，且 FLOW 不新增融资。")
    if not projected:
        return say(lang, "Assumes the buyer accepts this reply; FLOW cannot draw its cash on today's books.",
                   "假设买方接受此回复；FLOW 无法按今天的账目绘制其现金。")
    if legs:
        return say(lang, f"Assumes the buyer accepts this reply and FLOW's funding plan runs ({legs}); without the plan, cash falls lower.",
                   f"假设买方接受此回复，且 FLOW 的融资方案得以执行（{legs}）；没有该方案，现金会更低。")
    if funded:
        return say(lang, "Assumes the buyer accepts this reply; no funding plan is available within your mandate.",
                   "假设买方接受此回复；您的授权范围内没有可用的融资方案。")
    return say(lang, "Assumes the buyer accepts this reply; no new funding is needed.", "假设买方接受此回复；无需新增融资。")


def _path_entry(*, key: str, kind: str, label: str, recommended: bool, sendable: bool, needs_owner: bool, tag: str | None,
                cost_display: str, cost_note: str, cost: dict[str, Any], terms: list[dict[str, Any]], decides: str,
                authority: str | None, authority_text: str, assumption: str | None, reply_text: str | None,
                series: list[dict[str, Any]] | None, low: dict[str, Any], breach_when: str | None, band: str | None,
                lang: str, reason: str | None = None, recommended_reason: str | None = None,
                scenario_assumption: str | None = None) -> dict[str, Any]:
    tag_text, tag_tone = _tag(lang, tag)
    return {"key": key, "kind": kind, "label": label, "recommended": recommended, "sendable": sendable, "needs_owner": needs_owner,
            "tag_text": tag_text, "tag_tone": tag_tone, "cost_display": cost_display, "cost_note": cost_note, **cost, "terms": terms,
            "decides_text": decides, "authority_reason_text": reason, "recommended_reason_text": recommended_reason,
            "scenario_assumption_text": scenario_assumption, "authority": authority, "authority_text": authority_text, "assumption_text": assumption,
            "reply_text": reply_text, "series": series, **low, "first_breach_when": breach_when, "band_text": band}


def _paths(rt: Any, offer: Any, verdict: Any, books: Any, mandate: Any, today: int, lang: str, asked: Any, asked_view: dict[str, Any],
           breach: tuple[int, int] | None, replies: list[dict[str, Any]], trajs: dict[str, Any], flagged: set[str],
           rechecked: dict[str, Any], plan_costs: dict[str, int], assumed: dict[str, str]) -> list[dict[str, Any]]:
    """One entry per line on the chart: the offer as asked, then each reply in the verdict's order, with every word its column says.
    Each figure and word is the verdict's, the workspace's or the executor's own (see the comment on each). `flagged` holds the ids of
    the replies whose funding plan needs the owner's approval; `rechecked` the verifier's verdict on each reply as an agreement."""
    state, floor, buyer = books.state, mandate.min_cash_fen, offer.counterparty_id
    months = _months(mandate.forward_concession_horizon_days)
    action = business_action(verdict.outcome.value, len(verdict.counters))
    bound = list(verdict.bound_obligations)
    asked_rows = _term_rows(state, bound, buyer, lang)
    asked_next = _next_invoice_day(state, asked, today, buyer)

    # the offer as asked: the workspace's forward total with the immediate discount (as the projection posted it) beside it
    once = sum(d for o in bound if o.type == ObligationType.IMMEDIATE_DISCOUNT if (d := _posted_discount(asked, o.id)) is not None)
    forward = verdict.forward_concession_total_fen
    if forward > 0:
        cost_fen = forward
        note = (say(lang, f"over {months} months, plus {fmt_yuan(once)} once", f"{months} 个月内，另加一次性 {fmt_yuan(once)}")
                if once else say(lang, f"over {months} months", f"{months} 个月内"))
    elif once:
        cost_fen, note = once, say(lang, "once; nothing ongoing", "一次性；之后无持续成本")
    else:
        cost_fen, note = 0, say(lang, "nothing to pay", "无需付出成本")
    asked_total, asked_basis = _cost_basis(once, forward, months, False, lang)
    authority, authority_text = _asked_authority(lang, verdict)
    accepts = verdict.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
    asked_needs_owner = accepts and authority == NEEDS_OWNER
    asked_recommended = action == "accept"
    tag = ("over" if authority == OVER_LIMIT else "recommended" if asked_recommended else "approval" if asked_needs_owner else None)
    band = _below_band(asked_view["series"], floor, breach[0], lang) if breach is not None else None
    paths = [_path_entry(
        key="asked", kind="asked", label=say(lang, "As they asked", "按对方要求"), recommended=asked_recommended, sendable=accepts,
        needs_owner=asked_needs_owner, tag=tag, cost_display=fmt_yuan(cost_fen), cost_note=note,
        cost={"cost_total_display": asked_total, "cost_basis_text": asked_basis, "cost_once_display": fmt_yuan(once) if once > 0 else None,
              "cost_forward_display": fmt_yuan(forward) if forward > 0 else None, "cost_components": []},
        terms=_terms_view(asked_rows, None, lang), decides=_decides(lang, authority, authority_text, accepts, asked_needs_owner,
                                                                     lengthens_terms(bound)),
        authority=authority, authority_text=authority_text, assumption=None, reply_text=None, series=asked_view["series"],
        low={k: asked_view[k] for k in ("lowest_fen", "lowest_short", "lowest_when")},
        breach_when=asked_view["first_breach_when"], band=band, lang=lang,
        scenario_assumption=_scenario_assumption(lang, "asked", None, funded=False))]

    by_id = {r["counter_id"]: r for r in replies}
    who: dict[str, tuple[str | None, str, bool, str]] = {}  # per reply: (authority, its words, whether the owner decides, the rule that says so)
    for c in verdict.counters:
        obligations = list(c.obligations)
        # who decides: the verifier's own re-check of the counter as an agreement (its tier, the past-due and autonomy rules), OR-ed with
        # the tier the executor gives the agreement (Tier 1 only for early payment on a named invoice with nothing else changed and a
        # value within the single-commitment threshold) and with the funding plan's flag
        op = RecordCommitment(op_id="picture", idempotency_key="picture", mandate_version=mandate.version, requested_by=Actor.AGENT,
                              day=today, commitment_id="picture", nonce="picture")
        terms_change = lengthens_terms(obligations)
        check = rechecked.get(c.id)
        tier = tier_for(op, mandate, state, accepts_terms_change=terms_change, commitment_value_fen=c.forward_value_fen,
                        accepts_beyond_early_pay=not only_early_pay(obligations))
        owner = (tier != Tier.TIER_1
                 or c.id in flagged
                 or (check is not None and (check.required_tier != Tier.TIER_1 or check.outcome == Outcome.NEEDS_OWNER_APPROVAL)))
        if c.id in trajs:
            r_authority, r_text = _reply_authority(lang, check, owner)
        else:
            r_authority, r_text = None, say(lang, "FLOW cannot draw this reply on today's books", "FLOW 无法按今天的账目绘制此回复")
        who[c.id] = (r_authority, r_text, owner, _owner_rule(terms_change, only_early_pay(obligations), tier, c.id in flagged))
    # the workspace's priced response is the first reply FLOW could send: one that is over a limit, unpriced or not drawn is never it
    chosen = next((c.id for c in verdict.counters if who[c.id][0] in (FLOW_MAY, NEEDS_OWNER)), None) if action == "counter" else None
    for c in verdict.counters:
        r = by_id[c.id]
        obligations = list(c.obligations)
        traj = trajs.get(c.id)
        terms_change = lengthens_terms(obligations)
        r_authority, r_text, owner, owner_rule = who[c.id]
        sendable = r_authority in (FLOW_MAY, NEEDS_OWNER)
        needs_owner = sendable and owner
        band = None
        reply_breach = first_breach_ahead(traj, today, floor) if traj is not None else None
        if traj is not None:
            nxt = _next_invoice_day(state, traj, today, buyer)
            if reply_breach is not None:  # it still dips below the minimum: say what it does against it, not how soon the invoice is paid
                band = _below_band(r["series"], floor, reply_breach[0], lang)
            elif asked_next is not None and nxt is not None and nxt < asked_next:
                n = asked_next - nxt
                band = say(lang, f"The next invoice is paid {n} {'day' if n == 1 else 'days'} sooner than as asked",
                           f"下一张发票比按对方要求早 {n} 天收款")
            elif r["lowest_fen"] is not None and r["lowest_fen"] >= floor:
                band = say(lang, "Stays at or above your minimum", "现金始终不低于您的最低现金储备")
        recommended = c.id == chosen
        paths.append(_path_entry(
            key=c.id, kind="reply", label=r["label"], recommended=recommended, sendable=sendable, needs_owner=needs_owner,
            tag=("recommended" if recommended else "approval" if needs_owner else "over" if r_authority == OVER_LIMIT else None), cost_display=fmt_yuan(c.supplier_cost_fen),
            cost_note=_cost_note_reply(c, months, lang), cost=_reply_cost(c, state, mandate, months, lang, plan_costs.get(c.id, 0)),
            terms=_terms_view(_term_rows(state, obligations, buyer, lang), asked_rows, lang),
            decides=_decides(lang, r_authority, r_text, sendable, needs_owner, terms_change), authority=r_authority,
            authority_text=r_text, assumption=say(lang, "If the buyer accepts this reply", "如果买方接受此回复"),
            reply_text=business_text(state, c.text, rt.day, lang),
            series=r["series"], low={k: r[k] for k in ("lowest_fen", "lowest_short", "lowest_when")},
            breach_when=_distance(reply_breach[0], today, lang) if reply_breach else None, band=band, lang=lang,
            reason=_authority_reason(lang, r_authority, owner_rule if needs_owner else None, state, obligations, buyer, mandate),
            recommended_reason=_recommended_reason(lang, needs_owner) if recommended else None,
            scenario_assumption=assumed[c.id]))
    return paths


def _signed_whole(fen: int) -> str:
    """A difference with its sign in the KPIs' money form: "+¥422,012.23", "−¥1,000", "¥0" (the signed form of `home_hybrid._signed`, at
    the precision of the two figures it sits between)."""
    return "¥0" if fen == 0 else (f"+{whole(fen)}" if fen > 0 else whole(fen))


def _same_day_comparison(paths: list[dict[str, Any]], lang: str) -> None:
    """The inspector's strip for each day, on every point of every path's series: the offer as asked beside the recommended reply and what
    separates them, from the two series the read already carries (the same objects the chart draws). `comparison` is null where there is no
    recommended reply (the offer as asked, or nothing sendable, is recommended) or where either path has no point that day."""
    asked = next((p for p in paths if p["kind"] == "asked"), None)
    reply = next((p for p in paths if p["kind"] == "reply" and p["recommended"]), None)
    a_by_day = {pt["day"]: pt for pt in (asked or {}).get("series") or []}
    r_by_day = {pt["day"]: pt for pt in (reply or {}).get("series") or []}
    label = say(lang, "Same day", "同一天")
    for p in paths:
        for pt in p["series"] or []:
            a, r = a_by_day.get(pt["day"]), r_by_day.get(pt["day"])
            pt["comparison"] = (None if a is None or r is None else
                                {"label": label, "asked_display": a["closing_display"], "recommended_display": r["closing_display"],
                                 "difference_display": _signed_whole(r["closing_fen"] - a["closing_fen"])})


# ---------------------------------------------------------------- the moments: the days where looking is worth it, with every path's cash

_MAX_MOMENTS = 6
_ARRIVALS = ("RECEIPT", "EARLY_RECEIPT", "ADVANCE", "DRAW")  # the events that bring cash in


def _chip(n: int, lang: str) -> str:
    """A day as the chip says it: "Today", "Tomorrow", "In 47 days"."""
    if n == 0:
        return say(lang, "Today", "今天")
    if n == 1:
        return say(lang, "Tomorrow", "明天")
    return say(lang, f"In {n} days", f"{n} 天后")


def _names(lang: str, items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return say(lang, ", ".join(items[:-1]) + " and " + items[-1], "、".join(items))


def _moment_text(lang: str, events: dict[str, list[str]], below: list[str], names: dict[str, str], everyone: bool) -> str:
    """What happens on one day, from the paths' own events: what every path has said once, then what each path adds, then which paths are
    below the minimum."""
    keys = list(events)
    sep = say(lang, "; ", "；")
    common: list[str] = []
    if len(keys) > 1:
        shared = reduce(lambda a, b: a & b, (Counter(events[k]) for k in keys))
        common = list(shared.elements())
        for e in common:
            for k in keys:
                events[k].remove(e)
    parts: list[str] = []
    if common:
        parts.append(say(lang, f"On every path: {sep.join(common)}.", f"每条路径都有：{sep.join(common)}。"))
    for k in keys:
        if events[k]:
            parts.append(say(lang, f"{names[k]}: {sep.join(events[k])}.", f"{names[k]}：{sep.join(events[k])}。"))
    if below:
        if everyone and len(below) > 1:
            parts.append(say(lang, "On every path, cash is below your minimum.", "每条路径的现金都低于您的最低现金储备。"))
        else:
            who = _names(lang, [names[k] for k in below])
            parts.append(say(lang, f"{who}, cash is below your minimum.", f"{who}的现金低于您的最低现金储备。"))
    if not parts:
        return (say(lang, "No cash moves on any path.", "各路径都没有现金变动。") if len(keys) > 1
                else say(lang, "No cash moves.", "当天没有现金变动。"))
    return " ".join(parts)


_KINDS = ("today", "paths_part", "reserve_cross", "invoice_due", "lowest", "end")  # which word a day wears when it is several moments


def _word(kind: str, n: int, crossing: str, lang: str, lowest_of: list[str] | None = None) -> str:
    """The chip word of a moment. `lowest_of` names the paths whose lowest point it is, when more than one moment lists a lowest point."""
    if kind == "today":
        return say(lang, "Today", "今天")
    if kind == "invoice_due":
        return say(lang, "Invoice due", "发票到期")
    if kind == "paths_part":
        return say(lang, "Paths part", "路径分叉")
    if kind == "lowest":
        if lowest_of:
            who = _names(lang, lowest_of)
            return say(lang, f"Lowest, {who}", f"最低点，{who}")
        return say(lang, "Lowest point", "最低点")
    if kind == "reserve_cross":
        if crossing == "both":  # one path goes below the reserve on the day another comes back above it
            return say(lang, "Paths cross the reserve", "路径穿过储备")
        return say(lang, "Below the reserve", "低于储备") if crossing == "down" else say(lang, "Back above the reserve", "回到储备之上")
    return say(lang, f"Day {n}", f"第 {n} 天")


def _who_decides(lang: str, live: list[dict[str, Any]], names: dict[str, str]) -> str:
    """The parting moment's last sentence: who decides for each reply."""
    parts = []
    for p in live:
        if p["kind"] == "reply" and p["authority_text"]:
            text = p["authority_text"]
            if lang != "zh" and not text.startswith("FLOW"):
                text = text[0].lower() + text[1:]
            parts.append(f"{names[p['key']]}: {text}" if lang != "zh" else f"{names[p['key']]}：{text}")
    if not parts:
        return ""
    return (f"由谁决定：{'；'.join(parts)}。" if lang == "zh" else f"Who decides: {'; '.join(parts)}.")


def _signed_short(fen: int) -> str:
    """A difference between two lines as the short formatter says it, with its sign ("+¥90k", "−¥10k", "¥0")."""
    return "¥0" if fen == 0 else (f"+{fmt_short(fen)}" if fen > 0 else fmt_short(fen))


def _moments(paths: list[dict[str, Any]], today: int, floor: int, horizon_days: int, invoice_day: int | None,
             lang: str) -> tuple[list[dict[str, Any]], int]:
    """The whole list the cursor visits, with the picture's window in days. A moment is a day where something changes between the paths:
    today; the invoice falling due; the first day any two paths' cash differs; each path's lowest point; every day a path crosses the
    reserve in either direction; and the end of the picture window. At most six, ascending, each with every path's cash that day.
    The cap keeps, in this order: today, the day the paths part, the offer as asked's lowest point, the first reserve crossing, the
    end of the window, then the rest by day. Exactly one is decisive: the first day any path is below the minimum, else the day the
    paths part, else the offer as asked's lowest point (always one of the first four kept)."""
    live = [p for p in paths if p["series"]]
    if not live:
        return [], min(30, horizon_days)
    last = today + min(90, horizon_days)  # the picture never shows past 90 days
    rows = {p["key"]: {r["day"]: r for r in p["series"] if r["day"] <= last} for p in live}
    days = sorted({d for r in rows.values() for d in r})
    if not days:
        return [], min(30, horizon_days)
    order = {p["key"]: sorted(rows[p["key"]]) for p in live}

    def closing(key: str, day: int) -> int:
        have = order[key]
        i = bisect_right(have, day) - 1
        return rows[key][have[max(i, 0)]]["closing_fen"]

    def spread(day: int) -> int:
        values = [closing(p["key"], day) for p in live]
        return max(values) - min(values)

    def lowest_day(p: dict[str, Any]) -> int:
        return min(((r["closing_fen"], d) for d, r in rows[p["key"]].items()))[1]

    asked = next((p for p in live if p["key"] == "asked"), live[0])
    kinds: dict[int, set[str]] = {days[0]: {"today"}}
    part = next((d for d in days if len(live) > 1 and spread(d) > 0), None)
    if part is not None:
        kinds.setdefault(part, set()).add("paths_part")
    if invoice_day is not None and days[0] <= invoice_day <= last:
        kinds.setdefault(invoice_day, set()).add("invoice_due")
    lowest_by_day: dict[int, list[str]] = {}  # the paths whose lowest point is that day
    for p in live:
        kinds.setdefault(lowest_day(p), set()).add("lowest")
        lowest_by_day.setdefault(lowest_day(p), []).append(p["key"])
    down: set[int] = set()  # the days a path crosses the reserve downwards
    up: set[int] = set()  # and upwards
    crossings: set[int] = set()
    for p in live:
        below_before: bool | None = None
        for d in order[p["key"]]:
            below = rows[p["key"]][d]["closing_fen"] < floor
            if below_before is not None and below != below_before:
                crossings.add(d)
                if below:
                    down.add(d)
                else:
                    up.add(d)
            below_before = below
    for d in crossings:
        kinds.setdefault(d, set()).add("reserve_cross")
    first_below = next((d for d in days if any(closing(p["key"], d) < floor for p in live)), None)
    decisive = first_below if first_below is not None else part if part is not None else lowest_day(asked)

    # the window: past the last of these days by four, a month at least, three months at most, never past the horizon; its end is a moment
    end = min(today + min(max(max(kinds) - today + 4, 30), 90, horizon_days), days[-1])
    picture_days = end - today  # the window ends on the end moment
    kinds.setdefault(end, set()).add("end")

    wanted: list[int | None] = [days[0], part, lowest_day(asked), min(crossings) if crossings else None, end]
    wanted.extend(sorted(kinds))
    chosen: list[int] = []
    for d in wanted:
        if d is not None and d not in chosen and len(chosen) < _MAX_MOMENTS:
            chosen.append(d)
    names = {p["key"]: (say(lang, "As asked", "按对方要求") if p["kind"] == "asked" else p["label"]) for p in live}
    named = len([d for d in chosen if d in lowest_by_day]) > 1  # more than one lowest moment is listed: each says whose it is
    discount = say(lang, "Early-payment discount", "提前付款折扣")  # the row's own label is a whole sentence about one invoice

    out = []
    for d in sorted(chosen):
        values = []
        for p in live:
            c = closing(p["key"], d)
            value: dict[str, Any] = {"key": p["key"], "closing_fen": c, "closing_display": fmt_yuan(c), "closing_short": fmt_short(c),
                                     "below_floor": c < floor, "tone": "bad" if c < floor else "neutral",
                                     "note": say(lang, "Below your minimum", "低于您的最低现金储备") if c < floor else None,
                                     "vs_asked_fen": None, "vs_asked_short": None, "vs_asked_tone": None}
            if p["kind"] != "asked":  # this line against the offer as asked, the difference of two kernel figures taken once, here
                diff = c - closing(asked["key"], d)
                value.update(vs_asked_fen=diff, vs_asked_short=_signed_short(diff),
                             vs_asked_tone="ok" if diff > 0 else "bad" if diff < 0 else "neutral")
            values.append(value)
        shown = {p["key"]: [(discount if e["kind"] == "DISCOUNT" else e["label_short"], e) for e in
                            rows[p["key"]].get(d, {"events": []})["events"]] for p in live}
        events = {k: [f"{label} {e['amount_short']}" for label, e in v] for k, v in shown.items()}
        events_text = {k: [f"{label} {e['amount_display']}" for label, e in v] for k, v in shown.items()}
        below = [v["key"] for v in values if v["below_floor"]]
        text = _moment_text(lang, events, below, names, len(below) == len(live))
        if "paths_part" in kinds[d]:  # the day the paths part is where the owner chooses: say who decides for each reply
            who = _who_decides(lang, live, names)
            text = f"{text} {who}" if who else text
        have = [k for k in _KINDS if k in kinds[d]]
        kind = have[0] if have else "end"
        out.append({"day": d, "label": _chip(d - today, lang), "title": _chip(d - today, lang), "decisive": d == decisive,
                    "kind": kind, "kinds": have, "word": _word(kind, d - today, "both" if d in down and d in up else "down" if d in down else "up", lang,
                                [(say(lang, "as asked", "按对方要求") if k == asked["key"] else names[k]) for k in lowest_by_day[d]]
                                if named and d in lowest_by_day else None), "text": text, "values": values,
                    "events_text": events_text})
    return out, picture_days


def _safe_recheck(recheck: Any, c: Any) -> Any | None:
    """The verifier's verdict on a reply as an agreement, or None (no verdict) when the re-check cannot be run."""
    try:
        return recheck(c)
    except Exception:  # noqa: BLE001  a display read: whatever fails, the reply reads as unpriced and is never offered as sendable
        return None


def build(rt: Any, offer_id: str, lang: str) -> dict[str, Any]:
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
    verdict = latest_verdict_for(rt, offer_id)
    if verdict is None:
        raise HTTPException(404, {"code": "NO_VERDICT_YET", "offer_id": offer_id,
                                  "message": "evaluate the offer first; there is nothing to draw yet"})
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    held = [c for c in rt.store.commitments() if c.offer_id != offer_id]  # the offer as asked, not as it was later booked
    books = current_books(state, held)
    today = max(rt.day, state.as_of_day)
    floor = mandate.min_cash_fen
    try:
        asked = project(books.state, books.with_(verdict.bound_obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    except EngineError:
        # the days the offer named have passed, or its invoice has changed since: there is nothing to draw on today's books
        return {"offer_id": offer_id, "verdict_id": verdict.id, "lang": lang, "day": today, "available": False,
                "unavailable_text": say(lang, "This offer can no longer be drawn on today's books: the days it named have passed or the "
                                              "invoice has changed since.",
                                        "此报价已无法按今天的账目绘制：它所说的日期已过，或发票自那时起已有变动。"),
                "asked": None, "replies": [], "paths": [], "moments": [], "axis": None, "picture_days": None,
                "floor_fen": floor, "floor_short": fmt_short(floor), "horizon_days": mandate.horizon_days}
    breach = first_breach_ahead(asked, today, floor)
    replies = []
    trajs: dict[str, Any] = {}
    flagged: set[str] = set()  # the replies whose funding plan needs the owner's approval
    plan_costs: dict[str, int] = {}  # each reply's own funding plan cost, the router's total
    assumed: dict[str, str] = {}  # each reply's scenario assumption: the legs of its own funding plan, or why it has none
    recheck = counter_recheck(state, mandate, trusted_owner_key_hex=rt.owner_key_hex, day=today, commitments=held)
    for c in verdict.counters:
        label = option_label(c.label, lang)
        try:
            with_counter = books.with_(c.obligations)
            funding = plan(books.state, with_counter, mandate)
            actions = list(funding.actions) if funding.admissible else []
            traj = project(books.state, with_counter, actions, Mode.CONSERVATIVE, mandate.horizon_days, floor)
        except EngineError:
            assumed[c.id] = _scenario_assumption(lang, "reply", None, funded=True, projected=False)
            replies.append({"counter_id": c.id, "label": label, "series": None, "lowest_fen": None, "lowest_short": None,
                            "lowest_when": None, "note": say(lang, "Cash cannot be projected for this reply.", "无法为此回复预测现金。")})
            continue
        trajs[c.id] = traj
        plan_costs[c.id] = funding.total_cost_fen
        assumed[c.id] = _scenario_assumption(lang, "reply", _plan_legs(actions, today, lang), funded=funding.need_fen != 0)
        if funding.needs_owner_approval:
            flagged.add(c.id)
        if actions:
            note = say(lang, "If the buyer accepts, with the funding FLOW would run within your limits.",
                       "若买方接受，并含 FLOW 在您的授权内会办理的融资。")
        elif funding.need_fen == 0:
            note = say(lang, "If the buyer accepts. No funding is needed.", "若买方接受。无需融资。")
        else:
            note = say(lang, "If the buyer accepts. Funding within your limits does not cover the whole gap.",
                       "若买方接受。您授权内的融资无法覆盖全部缺口。")
        replies.append({"counter_id": c.id, "label": label, "series": _line(books.state, traj, today, lang),
                        **_lowest(books.state, traj, today, lang), "note": note})
    asked_series = _line(books.state, asked, today, lang)
    asked_view = {"label": say(lang, "As asked", "按对方要求"), "series": asked_series,
                  **_lowest(books.state, asked, today, lang),
                  "first_breach_day": breach[0] if breach else None,
                  "first_breach_when": _distance(breach[0], today, lang) if breach else None}
    # the verifier's own verdict on each reply as an agreement on these books: the tier, the past-due and autonomy rules, the cap codes
    rechecked = {c.id: _safe_recheck(recheck, c) for c in verdict.counters if c.id in trajs}
    paths = _paths(rt, offer, verdict, books, mandate, today, lang, asked, asked_view, breach, replies, trajs, flagged, rechecked, plan_costs, assumed)
    _same_day_comparison(paths, lang)
    invoice_days = [d for t in (asked, *trajs.values()) if (d := _next_invoice_day(books.state, t, today, offer.counterparty_id)) is not None]
    moments, picture_days = _moments(paths, today, floor, mandate.horizon_days, min(invoice_days) if invoice_days else None, lang)
    return {
        "offer_id": offer_id, "verdict_id": verdict.id, "lang": lang, "day": today,
        "available": True, "unavailable_text": None,
        "asked": asked_view,
        "replies": replies,
        "paths": paths,
        "moments": moments,
        "picture_days": picture_days,
        "axis": series_axis([asked_series, *(r["series"] for r in replies)], floor, picture_days),
        "floor_fen": floor, "floor_short": fmt_short(floor), "horizon_days": mandate.horizon_days,
    }


def cached_picture(rt: Any, offer_id: str, lang: str) -> dict[str, Any]:
    """The picture of an offer, cached per state version (call under `rt.lock`; the route and the Home's deals read share it)."""
    state = rt.store.get_state()
    verdict = latest_verdict_for(rt, offer_id)
    key = (state.state_version, rt.day, offer_id, verdict.id if verdict else None, rt.store.get_mandate().version, lang,
           tuple(c.id + c.status.value for c in rt.store.commitments()))
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit
    out = build(rt, offer_id, lang)
    with _lock:
        _cache[key] = out
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return out


@router.get("/offers/{offer_id}/picture")
def get_picture(offer_id: str, lang: str = "en") -> dict[str, Any]:
    """The cash picture of an offer: `asked` (the offer as it stands, no new funding) and one line per reply. Display only."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        return cached_picture(rt, offer_id, lang)
