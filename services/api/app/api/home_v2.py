"""The Home read's Home V2 fields (design/home-v2 rounds 4 and 5, wave 1, the server half): `home_v2` on `GET /home`, behind FEATURE_HOME_V2.

Composed from what the Home hybrid has already read (the position, the facts, the funding lots, the recommended plan, the books' own
trajectory); no figure is computed here and no state word is invented. Every sentence goes through `t(lang, en, zh)` and is the
prototype's (`HomeV2Proto.dc.html`) where the prototype has one.

    kpis.cash_available   today's cash, its room above the minimum, and where the minimum sits on a thin scale (`buffer`, with `headroom_text`:
                          the room as a short signed figure, "+¥100k", negative below the minimum)
    kpis.lowest_ahead     the lowest cash ahead on the CURRENT BOOKS: what the books hold with the plan only if it has run, never the
                          plan ready but not run, never a hypothetical. The planned plan's effect is a hint line (`with_plan_hint`) and, structured, `with_plan` {label, value_text} (null with no plan figure).
    kpis.funding          PROPOSED (the plan is ready; conditional on the owner; not cash), ARRANGED (the plan ran; what landed and what
                          is pending; cash only when it lands) or NONE. `status_text` is its one status word: "Ready to run" (control
                          RUN_PLAN), "Waiting for your approval" (APPROVE_PLAN), "Arranged" (`state_of`, after the run), null for NONE
    action                the one company-side next action (the funding plan, ready or waiting for approval; the unsafe reserve with no
                          plan) or the quiet variant. The commercial decisions are the worklist's (`GET /worklist`), so a healthy
                          company shows no filled primary here. `action.facts` [{label, value}] is the plan's three facts (estimated cost, funding,
                          approval), the very parts `action.text` is built from; empty when the action carries no funding plan.
                          `action.approval_text` is the approval in one sentence: the approval fact's own value while the plan is ready to run
                          ("No approval needed"), "Needs your approval before it runs" wherever the action waits for the owner (APPROVE_PLAN, or
                          the application for a facility, which needs the owner), null when the action has no plan to state it for (no
                          control, or a step with no approval fact); `action.approval_needed` is true exactly when that sentence is given.
                          `action.legs` [{label, amount_display, lands_when, cost_display, repaid_when, state, state_text, authority_text}] is the
                          plan one entry per landing leg, in the sentence's order: PLANNED while the plan is ready, ARRANGED once it ran and
                          RECEIVED once the leg's cash landed (`state_of`); `cost_display` is the engine's own line for that action (null where it
                          priced none), `repaid_when` a draw's repayment day (null otherwise); `lands_day` (days from today) and `amount_fen` are the timeline's
                          data, never shown. `action.cost_basis_text` is the plan's own basis sentence for its cost (how it is estimated; the final interest depends on the
                          actual repayment day); null with no cost and once the plan has run. Legs empty with no plan, ready or run.
    chart                 the scope the chart states, its legend (current / planned / hypothetical), the lowest point's inspector and
                          `lowest.cause` (the rail's lowest row, named by its cause; null when the hybrid names none) and, on a read made with
                          `?decision=` (and `?scenario=late`), `scenario_title_text` ("Foshan · Payment terms · As they asked vs Option A ·
                          Expected payments"; null without a decision)
    links                 where the rest of the company's picture lives

A plan that is ready and has not run is "planned" in these words, the financing vocabulary's own (`state_of` PLANNED, "计划中"), as in the
funding KPI's eyebrow; `funding.state` PROPOSED is its code. A lot that has been run is "arranged" until it lands and "received" once it has (`state_of`).
"""

from __future__ import annotations

import logging
from fractions import Fraction
from typing import Any, NamedTuple
from urllib.parse import quote

from app.api.financing_words import State, state_of, state_word
from app.api.home import _lowest_ahead
from app.api.home_hybrid import (
    HomeRead,
    _cause_event,
    _event_kind,
    _noun,
    _pending_lots,
    _plan_has_run,
    _quote_of,
    _short,
    _signed,
    _sp,
    _tone,
)
from app.api.presentation import party_name, t, when_text, whole
from app.decisions.identity import offer_id_of
from app.domain.models import FundingLot
from app.financial.lots import ensure_lots
from app.strategy import words as basis_words
from app.strategy.payments import STRESS_DELAY_DAYS
from app.strategy.words import share_text

log = logging.getLogger("termsledger.decisions")
_LANDING = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
_BASIS_WORD = {basis_words.OWED: ("owed", "应收"), basis_words.SCHEDULED: ("scheduled", "按计划"), basis_words.AGREED: ("agreed", "已约定"),
               basis_words.PENDING: ("pending", "待对方接受")}


def _planned(lang: str) -> str:
    """The word for a plan that is ready and has not run: the financing vocabulary's own (`state_of` PLANNED: "planned", "计划中")."""
    return state_word(lang, state_of(None, planned=True))


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:]


def _digit_gap(text: str) -> str:
    """A space before a Chinese distance that starts with a number ("30 天后"), as the house writes it."""
    return f" {text}" if text[:1].isdigit() else text


def _eyebrow(lang: str, en: str, zh: str) -> str:
    return t(lang, en.upper(), zh)


# ---------------------------------------------------------------- the three KPIs


def _cash_available(c: HomeRead) -> dict[str, Any]:
    lang, cash, floor = c.lang, c.state.cash_fen, c.floor
    gap = cash - floor
    if gap > 0:
        note = t(lang, f"{_short(gap)} above your {_short(floor)} minimum", f"比您 {_short(floor)} 的最低现金高 {_short(gap)}")
    elif gap == 0:
        note = t(lang, f"at your {_short(floor)} minimum", f"正好是您 {_short(floor)} 的最低现金")
    else:
        note = t(lang, f"{_short(-gap)} below your {_short(floor)} minimum", f"比您 {_short(floor)} 的最低现金低 {_short(-gap)}")
    return {"eyebrow": _eyebrow(lang, "Cash available", "可用现金"), "value_display": whole(cash), "note": note,
            "tone": _tone(cash, floor), "buffer": {"min_fen": floor, "cash_fen": cash, "min_display": _short(floor), "headroom_text": _signed(gap)}}


def _lowest_ahead_kpi(c: HomeRead) -> dict[str, Any]:
    """The lowest cash ahead on the books as they stand (`c.low`, the books' own trajectory): the plan is in it only if it has run."""
    lang, floor = c.lang, c.floor
    low_fen, low_day = c.low
    when = when_text(low_day, c.today, lang)
    gap = low_fen - floor
    if gap > 0:
        where = t(lang, f"{_short(gap)} above your minimum {when}", f"比您的最低现金高 {_short(gap)}（{when}）")
        short = t(lang, f"{_short(gap)} above your minimum {when}", f"{when}高于最低现金 {_short(gap)}")
    elif gap == 0:
        where = t(lang, f"reaches your minimum {when}", f"{when}达到您的最低现金")
        short = t(lang, f"At your minimum {when}", f"{when}正好是最低现金")
    else:
        where = t(lang, f"{_short(-gap)} below your minimum {when}", f"比您的最低现金低 {_short(-gap)}（{when}）")
        short = t(lang, f"{_short(-gap)} shortfall {when}", f"{when}缺口 {_short(-gap)}")
    basis = (t(lang, "current books, the plan ran", "当前账目，方案已执行") if _plan_has_run(c.state)
             else t(lang, "current books, no new funding", "当前账目，未新增融资"))
    if c.plan_traj is not None:
        plan_fen, _ = _lowest_ahead(c.plan_traj, c.today)
        hint = t(lang, f"If FLOW's plan executes: {whole(plan_fen)}, assuming the funds arrive as planned.",
                 f"如果 FLOW 的方案执行：{whole(plan_fen)}，前提是资金按计划到账。")
        with_plan: dict[str, str] | None = {"label": t(lang, "with plan", "采用方案后"), "value_text": whole(plan_fen)}
    else:
        hint = t(lang, "No hypothetical applied.", "未应用任何假设。")
        with_plan = None
    return {"eyebrow": _eyebrow(lang, "Lowest cash ahead", "未来最低现金"), "value_display": whole(low_fen),
            "note": f"{where} · {basis}", "short_note": short, "tone": _tone(low_fen, floor), "with_plan_hint": hint, "with_plan": with_plan}


def _lot_kind(lot: FundingLot, lang: str) -> str:
    return t(lang, "invoice financing", "发票融资") if lot.receivable_id else t(lang, "credit-line draw", "信用额度提款")


def _funding(c: HomeRead, funding_line: dict[str, Any]) -> dict[str, Any]:
    lang = c.lang
    ran = sorted((lot for lot in ensure_lots(c.state).lots if not lot.assumed_date and lot.remaining_fen > 0),
                 key=lambda lot: (lot.arrival_day, lot.id))
    pending = _pending_lots(c.state, c.today)
    a = c.action
    if pending:  # the plan ran: what landed and what is still to land
        parts = []
        for lot in ran:
            amount, kind, when = _short(lot.remaining_fen), _lot_kind(lot, lang), when_text(lot.arrival_day, c.today, lang)
            if lot.settled:
                parts.append(t(lang, f"{amount} {kind} received {when}", f"{amount} {kind}已到账（{when}）"))
            else:
                parts.append(t(lang, f"{amount} {kind} expected {when}", f"{amount} {kind}预计{_digit_gap(when)}到账"))
        owed = whole(sum(lot.remaining_fen for lot in pending))
        return {"state": "ARRANGED", "eyebrow": _eyebrow(lang, "Funding arranged", "已安排的融资"),
                "value_display": t(lang, f"{owed} pending", f"待到账 {owed}"), "note": " · ".join(parts),
                "status_text": _cap(state_word(lang, "ARRANGED")), "hint": t(lang, "Counted as cash only when it lands.", "到账后才计入现金。")}
    if c.plan_traj is not None and a is not None and a["kind"] == "RESERVE_BREACH_AHEAD":
        legs = [leg for leg in a["legs"] if leg["operation_kind"] in _LANDING and leg.get("lands_when") and leg.get("amount_fen")]
        kinds = {"DRAW_FACILITY": t(lang, "credit line", "信用额度"), "SUBMIT_INVOICE_FOR_FINANCING": t(lang, "invoice financing", "发票融资")}
        note = " + ".join(t(lang, f"{_short(leg['amount_fen'])} {kinds[leg['operation_kind']]} {leg['lands_when']}",
                            f"{kinds[leg['operation_kind']]} {_short(leg['amount_fen'])}，{leg['lands_when']}") for leg in legs)
        who = t(lang, "approving", "批准") if c.waiting else t(lang, "running", "执行")
        return {"state": "PROPOSED", "eyebrow": t(lang, f"{_planned(lang).upper()} FUNDING", f"{_planned(lang)}的融资"), "value_display": whole(a["receive_fen"]),
                "note": note, "status_text": (t(lang, "Waiting for your approval", "等待您批准") if c.waiting
                                              else t(lang, "Ready to run", "可以执行")),
                "hint": t(lang, f"Conditional on you {who} the plan; not counted as cash.", f"取决于您是否{who}方案；不计入现金。")}
    return {"state": "NONE", "eyebrow": _eyebrow(lang, "Funding", "融资"), "value_display": t(lang, "None", "无"),
            "note": funding_line["text"], "status_text": None, "hint": None}


# ---------------------------------------------------------------- the one next action


def _landing_legs(a: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan's legs that bring cash, in the plan's order: the sentence's legs and `action.legs` are these."""
    return [leg for leg in a["legs"] if leg["operation_kind"] in _LANDING and leg.get("lands_when") and leg.get("amount_fen")]


def _legs_text(c: HomeRead, a: dict[str, Any]) -> str:
    lang = c.lang
    kinds = {"DRAW_FACILITY": t(lang, "credit-line draw", "信用额度提款"), "SUBMIT_INVOICE_FOR_FINANCING": t(lang, "invoice financing", "发票融资")}
    legs = _landing_legs(a)
    parts = [t(lang, f"{_short(leg['amount_fen'])} {kinds[leg['operation_kind']]} {leg['lands_when']}",
               f"{kinds[leg['operation_kind']]} {_short(leg['amount_fen'])}（{leg['lands_when']}）") for leg in legs]
    planned = t(lang, f"both {_planned(lang)}" if len(parts) > 1 else _planned(lang), f"均为{_planned(lang)}" if len(parts) > 1 else _planned(lang))
    return t(lang, ", ".join(parts) + f", {planned}", "、".join(parts) + f"，{planned}")


def _before_what(c: HomeRead) -> str:
    """"payroll in 12 days": the posting that takes cash below the reserve on the first breach day, and when."""
    lang = c.lang
    day = next((d for d in c.traj.days if c.breach_day is not None and d.day == c.breach_day), None)
    event = _cause_event(day.events) if day is not None else None
    when = when_text(c.breach_day, c.today, lang)
    if event is None:
        return t(lang, f"your reserve is breached {when}", f"现金储备{_digit_gap(when)}被突破")
    noun = _noun(_event_kind(event), lang)
    return t(lang, f"{noun} {when}", f"{noun}（{when}）")


def _breach_eyebrow(c: HomeRead) -> str:
    lang = c.lang
    if c.breach_day is None:
        return _eyebrow(lang, "Next action", "下一步")
    n = max(c.breach_day - c.today, 0)
    return t(lang, f"NEXT ACTION · WITHIN {n} {'DAY' if n == 1 else 'DAYS'}", f"下一步 · {n} 天内")


def _next_arrivals(c: HomeRead) -> str:
    """"¥255k arrives in 3 days; Foshan pays ¥420k in 32 days (owed)": the funding landing and the next receipt, each with the word for what
    it rests on."""
    lang = c.lang
    parts = [t(lang, f"{_short(lot.remaining_fen)} arrives {when_text(lot.arrival_day, c.today, lang)}",
               f"{_short(lot.remaining_fen)} 将于{_digit_gap(when_text(lot.arrival_day, c.today, lang))}到账") for lot in _pending_lots(c.state, c.today)[:2]]
    nxt = c.receivables.get("next_receipt")
    if nxt is not None:
        who = basis_words.buyer_short(nxt["buyer_name"])
        b = c.basis.of_receivable(nxt["receivable_id"]) if c.basis is not None else None
        word = f" ({t(lang, *_BASIS_WORD[b.code])})" if b is not None and b.code in _BASIS_WORD else ""
        word_zh = f"（{t(lang, *_BASIS_WORD[b.code])}）" if b is not None and b.code in _BASIS_WORD else ""
        parts.append(t(lang, f"{who} pays {_short(nxt['face_fen'])} {nxt['due_when']}{word}",
                       f"{who}将于{_digit_gap(nxt['due_when'])}支付 {_short(nxt['face_fen'])}{word_zh}"))
    if not parts:
        return t(lang, "Nothing is expected to arrive in the forecast.", "预测期内没有预计到账的款项。")
    return t(lang, "Next: " + "; ".join(parts) + ".", "接下来：" + "；".join(parts) + "。")


def _worklist_holds(c: HomeRead) -> int:
    """What waits for the owner in the worklist, from the worklist's own count (one count, not a second). A worklist that cannot be read is
    named in `partial` and the sentence about it is left out."""
    from app.api import worklist

    try:
        return worklist.counts(c.rt, c.lang)["needs_you"]
    except Exception:
        log.exception("the worklist could not be counted for the Home V2 action")
        if c.partial is not None:
            c.partial.add("home_v2")
        return 0


class _PlanParts(NamedTuple):
    """The words a funding plan's action sentence is made of: `action.text` is built from them and `action.facts` lists them, so the two
    cannot drift."""

    within: str  # "within your signed limits" / "needs your approval because of its cost"
    legs: str  # "¥150k credit-line draw today, ¥255k invoice financing in 3 days, both planned"
    cost: str | None  # the plan's cost word ("¥3,113.93"), None when the plan carries none
    approval: str  # "no approval needed" / "your approval is needed"


def _plan_parts(c: HomeRead, a: dict[str, Any]) -> _PlanParts:
    lang = c.lang
    within = (t(lang, "needs your approval because of its cost", "因其成本需要您批准") if a["needs_owner"]
              else t(lang, "within your signed limits", "在您签署的授权内"))
    approval = t(lang, "your approval is needed", "需要您批准") if a["needs_owner"] else t(lang, "no approval needed", "无需批准")
    return _PlanParts(within, _legs_text(c, a), a.get("cost_total_display") or None, approval)


def _plan_sentence(lang: str, p: _PlanParts) -> str:
    return t(lang, f"FLOW's plan {p.within}: {p.legs}" + (f" · cost {p.cost}" if p.cost else "") + f" · {p.approval}.",
             f"FLOW 的方案{p.within}：{p.legs}" + (f" · 成本 {p.cost}" if p.cost else "") + f" · {p.approval}。")


def _plan_facts(lang: str, p: _PlanParts) -> list[dict[str, str]]:
    """The plan's three facts, each the sentence's own part (the approval's first letter raised in English: it stands alone as a value)."""
    approval = p.approval[:1].upper() + p.approval[1:] if lang == "en" else p.approval
    return [{"label": t(lang, "Estimated cost", "预计成本"), "value": p.cost or t(lang, "Not priced", "未计价")},
            {"label": t(lang, "Funding", "融资"), "value": p.legs},
            {"label": t(lang, "Approval", "批准"), "value": approval}]


def _is_plan(a: dict[str, Any] | None) -> bool:
    """The action is a funding plan that brings cash: a reserve breach with legs that land and an amount to receive."""
    return a is not None and a["kind"] == "RESERVE_BREACH_AHEAD" and bool(_landing_legs(a)) and bool(a.get("receive_fen"))


def _leg_label(lang: str, kind: str) -> str:
    """The leg's source in the sentence's own words, first letter raised in English: it stands alone as a value. No facility name: the books
    keep it in English only."""
    words = {"DRAW_FACILITY": t(lang, "credit-line draw", "信用额度提款"), "SUBMIT_INVOICE_FOR_FINANCING": t(lang, "invoice financing", "发票融资")}
    return _cap(words[kind])


def _leg(c: HomeRead, *, kind: str, amount_fen: int, lands_day: int, lands_when: str | None, cost_fen: int | None, repay_day: int | None,
         state: State, authority: str) -> dict[str, Any]:
    """One leg. `lands_day` (days from today) and `amount_fen` are data for the timeline's position and the marker's size, never shown: the
    page shows `lands_when` and `amount_display`."""
    lang = c.lang
    return {"label": _leg_label(lang, kind), "amount_display": whole(amount_fen), "amount_fen": amount_fen,
            "lands_when": lands_when or when_text(lands_day, c.today, lang), "lands_day": lands_day - c.today,
            "cost_display": whole(cost_fen) if cost_fen is not None else None,
            "repaid_when": when_text(repay_day, c.today, lang) if kind == "DRAW_FACILITY" and repay_day is not None else None,
            "state": state, "state_text": _cap(state_word(lang, state)), "authority_text": authority}


def _action_legs(c: HomeRead, action: dict[str, Any], funding_line: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str | None]:
    """(`action.legs`, `action.cost_basis_text`): the basis is the plan's own sentence (the hybrid's `cost_basis`: how the cost is estimated and
    that the final interest depends on the actual repayment day), null with no cost and once the plan has run (no basis sentence is carried then).
    One leg per leg that lands, in the order the sentence says them. The plan that is ready: its
    own actions, PLANNED. Once it has run (and nothing else is the action): the stored quote's legs with their lots, ARRANGED until the cash
    lands, RECEIVED once it has (`state_of`). A leg's cost is the engine's own line for that action, null where it priced none (never a share
    of the total); a draw's repayment day is the one the plan or the quote carries. `share_text` is the leg's share of the plan's total (the legs' amounts summed), null when that total is zero."""
    a = c.action
    out: list[dict[str, Any]] = []
    basis: str | None = None
    if _is_plan(a) and a is not None:
        authority = str(a.get("authority_text") or "")
        basis = str(a["cost_basis"]) if a.get("cost_total_display") and a.get("cost_basis") else None
        for leg in _landing_legs(a):
            out.append(_leg(c, kind=leg["operation_kind"], amount_fen=int(leg["amount_fen"]), lands_day=int(leg["lands_day"]), lands_when=str(leg["lands_when"]),
                            cost_fen=leg.get("cost_fen"), repay_day=leg.get("cost_due_day"), state=state_of(None, planned=True), authority=authority))
    elif action["variant"] == "QUIET" and funding_line is not None and funding_line["state"] in ("arranged", "landed"):
        ds = _quote_of(c)
        for leg in ds.quote.legs if ds is not None and ds.quote is not None else ():
            lot = next((x for x in ds.lots if x.id == leg.op_id or x.id.startswith(leg.op_id + "#")), None) if ds is not None else None
            day = lot.arrival_day if lot is not None else leg.lands_day
            if leg.kind not in _LANDING or not leg.amount_fen or day is None:
                continue
            out.append(_leg(c, kind=leg.kind, amount_fen=leg.amount_fen, lands_day=day, lands_when=None, cost_fen=leg.cost_fen,
                            repay_day=leg.cost_end_day, state=state_of(lot, repaid=lot is None), authority=str(funding_line["authority_text"] or "")))
    total = sum(leg["amount_fen"] for leg in out)  # each leg's share of the plan's total, the words layer's own percent word (`share_text`)
    for leg in out:
        leg["share_text"] = share_text(Fraction(leg["amount_fen"], total), c.lang, whole=True) if total > 0 else None
    return out, basis


def _consequence_text(c: HomeRead) -> str | None:
    """"Cash first falls below your minimum in 12 days. Without new funding, the shortfall reaches ¥405k in 30 days.": the first breach day and the
    lowest point's shortfall, the words `kpis.lowest_ahead` and the company alert already use (`when_text`, `_short`, `c.low`, the books' own
    trajectory); no new figure. Null when the books hold no breach."""
    lang = c.lang
    if c.breach_day is None:
        return None
    low_fen, low_day = c.low
    gap = low_fen - c.floor
    if gap >= 0:
        return None
    first = when_text(c.breach_day, c.today, lang)
    at = when_text(low_day, c.today, lang)
    short = _short(-gap)
    if _plan_has_run(c.state):
        return t(lang, f"Cash first falls below your minimum {first}. Even with the plan that ran, the shortfall reaches {short} {at}.",
                 f"现金将在{_digit_gap(first)}首次低于您的最低现金。即使方案已执行，缺口仍将在{_digit_gap(at)}达到 {short}。")
    return t(lang, f"Cash first falls below your minimum {first}. Without new funding, the shortfall reaches {short} {at}.",
             f"现金将在{_digit_gap(first)}首次低于您的最低现金。若没有新增融资，缺口将在{_digit_gap(at)}达到 {short}。")


def _action(c: HomeRead, att: dict[str, Any], funding_line: dict[str, Any] | None = None) -> dict[str, Any]:
    out = _action_body(c, att)
    out["approval_text"], out["approval_needed"] = _approval_words(c, out)
    out["consequence_text"] = _consequence_text(c)
    out["legs"], out["cost_basis_text"] = _action_legs(c, out, funding_line)
    return out


def _approval_words(c: HomeRead, action: dict[str, Any]) -> tuple[str | None, bool]:
    """(`action.approval_text`, `action.approval_needed`): an action that waits for the owner says so, in one fixed sentence: a plan waiting
    for the approval (APPROVE_PLAN) and a step with no plan facts whose own words say it needs the owner (an application for a facility,
    `needs_owner`); a plan ready to run states its approval fact's own value; an action with no plan, or no approval fact to state, has no text."""
    lang = c.lang
    waits = action["control"] == "APPROVE_PLAN" or (
        action["control"] == "RUN_PLAN" and not action["facts"] and bool((c.action or {}).get("needs_owner")))
    if waits:
        return t(lang, "Needs your approval before it runs", "需要您批准后才会执行"), True
    fact = next((f["value"] for f in action["facts"] if f["label"] == t(lang, "Approval", "批准")), None)
    return (fact if action["control"] == "RUN_PLAN" else None), False


def _action_body(c: HomeRead, att: dict[str, Any]) -> dict[str, Any]:
    lang, a = c.lang, c.action
    if a is not None and a["kind"] == "RESERVE_BREACH_AHEAD":
        waiting = bool(a.get("pending_approval_id"))
        if _is_plan(a):  # a plan that brings cash: say how much, before what, and what it is made of
            amount = whole(a["receive_fen"])
            plan = _plan_parts(c, a)
            title = t(lang, f"Secure {amount} before {_before_what(c)}.", f"请在{_before_what(c)}之前筹措 {amount}。")
            text, facts = _plan_sentence(lang, plan), _plan_facts(lang, plan)
        else:  # a step with no cash landing yet (an application for a facility): the action's own words, and who must act
            title = str(a.get("outcome_title") or a.get("title") or c.headline)
            text, facts = f"{c.headline}{_sp(lang)}{a.get('authority_text') or ''}".strip(), []
        key = next((i["key"] for i in att["items"] if i["kind"] == "funding"), None) or (
            f"approval:{a['pending_approval_id']}" if waiting else None)
        return {"variant": "ACTION", "key": key, "tone": "bad" if c.breach_day is not None else "warn", "eyebrow": _breach_eyebrow(c),
                "title": title, "text": text, "facts": facts,
                "primary": ({"label": t(lang, "Review the plan", "查看方案"), "href": f"/approvals#approval-{quote(str(a['pending_approval_id']), safe='')}"}
                            if waiting else {"label": t(lang, "Run the funding plan", "执行融资方案"), "href": "/cash#cash-options"}),
                "secondary": {"label": t(lang, "Compare", "比较"), "href": "/cash#cash-options"},
                "control": "APPROVE_PLAN" if waiting else "RUN_PLAN"}
    if a is not None and a["kind"] == "FACILITY_REPAYABLE":  # the credit line can be repaid: that is the company's action, not a quiet day
        waiting = bool(a.get("pending_approval_id"))
        return {"variant": "ACTION", "key": f"approval:{a['pending_approval_id']}" if waiting else None, "tone": "warn",
                "eyebrow": _eyebrow(lang, "Next action", "下一步"), "title": str(a.get("outcome_title") or a.get("title")),
                "text": f"{a.get('after') or ''}{_sp(lang)}{a.get('authority_text') or ''}".strip(), "facts": [],
                "primary": ({"label": t(lang, "Review the repayment", "查看还款"), "href": f"/approvals#approval-{quote(str(a['pending_approval_id']), safe='')}"}
                            if waiting else {"label": t(lang, "Run the repayment", "执行还款"), "href": "/cash#cash-options"}),
                "secondary": {"label": t(lang, "Compare", "比较"), "href": "/cash#cash-options"},
                "control": "APPROVE_PLAN" if waiting else "RUN_PLAN"}
    if c.breach_day is not None:  # the reserve is unsafe and there is no plan to run: say so, point to the options
        return {"variant": "ACTION", "key": None, "tone": "bad", "eyebrow": _breach_eyebrow(c), "title": c.headline, "text": c.note, "facts": [],
                "primary": {"label": t(lang, "See the options", "查看选项"), "href": "/cash#cash-options"}, "secondary": None, "control": None}
    n = _worklist_holds(c)
    held = (t(lang, f" Your worklist still holds {n} {'item' if n == 1 else 'items'} for you.", f"您的待办列表里还有 {n} 项等您处理。") if n else "")
    return {"variant": "QUIET", "key": None, "tone": "ok",
            "eyebrow": _eyebrow(lang, "Nothing needs you from the company side", "公司层面没有需要您处理的事项"),
            "title": (t(lang, "Your cash is covered on the plan that ran.", "按已执行的方案，您的现金是安全的。") if _plan_has_run(c.state)
                      else t(lang, "Your cash is covered.", "您的现金是安全的。")),
            "text": _next_arrivals(c) + held, "facts": [], "primary": None, "secondary": None, "control": None}


# ---------------------------------------------------------------- the chart


def _lowest_cause(rail: list[dict[str, Any]] | None) -> str | None:
    """What makes the lowest point the lowest: the label of the rail's lowest row, which the hybrid names by its cause (`_cause_label`),
    word for word. A lowest row with no event behind it (the fallback "cash is at its lowest") names no cause: None."""
    row = next((r for r in rail or [] if r["kind"] == "lowest"), None)
    return str(row["label"]) if row is not None and row["amount_fen"] else None


def _chart(c: HomeRead, rail: list[dict[str, Any]] | None) -> dict[str, Any]:
    lang, floor = c.lang, c.floor
    legend = [{"label": (t(lang, "Current books · the plan ran", "当前账目 · 方案已执行") if _plan_has_run(c.state)
                         else t(lang, "Current books · no new funding", "当前账目 · 未新增融资")), "kind": "current"}]
    if c.plan_traj is not None:
        legend.append({"label": t(lang, f"If FLOW's plan runs ({_planned(lang)})", f"如果 FLOW 的方案执行（{_planned(lang)}）"), "kind": "planned"})
    low_fen, low_day = c.low
    gap = low_fen - floor
    if gap < 0:
        third = (t(lang, "Shortfall", "缺口"), whole(-gap))
        if c.plan_traj is not None:
            plan_fen, _ = _lowest_ahead(c.plan_traj, c.today)
            note = t(lang, f"With FLOW's plan ({_planned(lang)}): {whole(plan_fen)}, assuming it runs and the funds arrive as planned.",
                     f"采用 FLOW 的方案（{_planned(lang)}）：{whole(plan_fen)}，前提是方案执行且资金按计划到账。")
        else:
            note = t(lang, "FLOW has no funding plan that closes this yet.", "FLOW 目前没有能补上这一缺口的融资方案。")
    else:
        third = (t(lang, "Above your minimum", "高于您的最低现金"), whole(gap))
        note = (t(lang, "At your minimum; nothing below it in the window.", "正好在您的最低现金上；预测期内没有低于它的时候。") if gap == 0
                else t(lang, f"{_short(gap)} above your minimum; nothing below it in the window.",
                       f"比您的最低现金高 {_short(gap)}；预测期内没有低于它的时候。"))
    when = when_text(low_day, c.today, lang)
    return {"scope_title": t(lang, "COMPANY CASH FORECAST", "公司现金预测"), "legend": legend,
            "lowest_inspector": {"day_text": t(lang, f"The lowest point · {when}", f"最低点 · {when}"),
                                 "projected_display": whole(low_fen), "minimum_display": whole(floor),
                                 "third_label": third[0], "third_display": third[1], "note": note},
            "lowest": {"cause": _lowest_cause(rail)}, "scenario_title_text": _scenario_title(c),
            "note": t(lang, "Current books, nothing new assumed. The same figures as Cash & Funding.",
                      "当前账目，没有假设任何新增事项。数字与现金与融资页一致。")}


def _scenario_title(c: HomeRead) -> str | None:
    """The chart's title for a deal read: "Foshan · Payment terms · As they asked vs Option A · Expected payments", the offer's own subject
    words (the worklist row's), the offer picture's path labels (the asked path and the recommended reply) and the scenario's word. Null
    without a decision, for a decision that is not a deal on the books, or when the deal has no picture to name paths from."""
    if not c.decision:
        return None
    from fastapi import HTTPException

    from app.api.offer_picture import cached_picture
    from app.api.worklist import _topic

    lang = c.lang
    offer_id = offer_id_of(c.decision)
    try:
        offer = c.rt.store.get_offer(offer_id) if offer_id else None
        if offer is None:
            return None
        who = basis_words.buyer_short(party_name(c.state, offer.counterparty_id))
        pic = cached_picture(c.rt, offer.offer_id, lang)
    except HTTPException:  # no verdict yet: there is no picture to name paths from
        return None
    except Exception:
        log.exception("the offer picture could not be read for the Home V2 chart title")
        if c.partial is not None:
            c.partial.add("home_v2")
        return None
    paths = pic.get("paths") or []
    if not pic.get("available") or not paths:
        return None
    asked = next((p for p in paths if p["kind"] == "asked"), paths[0])
    reply = next((p for p in paths if p["kind"] == "reply" and p["recommended"]), None)
    compare = t(lang, f"{asked['label']} vs {reply['label']}", f"{asked['label']} 对比 {reply['label']}") if reply is not None else asked["label"]
    scenario = (t(lang, f"{who} {STRESS_DELAY_DAYS} days late", f"{who}晚付 {STRESS_DELAY_DAYS} 天") if c.scenario == "late"
                else t(lang, "Expected payments", "预期收款"))
    return f"{who} · {_topic(offer, lang)} · {compare} · {scenario}"


def _links(c: HomeRead) -> list[dict[str, str]]:
    lang = c.lang
    return [{"label": t(lang, "Where the cash goes", "现金的去向"), "href": "/cash#where-the-cash-goes"},
            {"label": t(lang, "Facility headroom", "融资额度余量"), "href": "/cash#facility-headroom"},
            {"label": t(lang, "What you are owed, by when", "应收款的到期时间"), "href": "/receivables"},
            {"label": t(lang, "All deals", "全部交易"), "href": "/deals"}]


def build(c: HomeRead, att: dict[str, Any], funding_line: dict[str, Any], rail: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`home_v2` for `GET /home`: the three KPIs, the one action, the chart's scope and the links. `rail` is the cash block's events rail."""
    return {"kpis": {"cash_available": _cash_available(c), "lowest_ahead": _lowest_ahead_kpi(c), "funding": _funding(c, funding_line)},
            "action": _action(c, att, funding_line), "chart": _chart(c, rail), "links": _links(c)}


__all__ = ["build"]
