"""GET /home: the owner's home in business words, one read.

A presentation view over results the engine already produces: today's alerts (the conservative projection of current
books, with each cure priced by the engine), the approvals queue, the operations log, the reconciliation and the
books. It answers "am I going to run out of money", "what should I do", "what does it cost", "what needs my
decision", "what changed" and "who has not paid me" with sentences the server writes, so the web app renders and
never computes. It decides nothing: the status word is a reading of the alerts' severities and the queue, and every
amount, day and rate is copied from an engine result.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import Alert, AlertKind, Severity, alerts, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.presentation import (
    approval_words,
    buyer_of_receivable,
    cure_legs,
    facility_name,
    fmt_short,
    in_words,
    invoice_words,
    lead_days,
    leg_words,
    party_name,
    receivable_face,
    relative_days,
    t,
    when_text,
)
from app.api.presentation import (
    needs_owner_reason as needs_owner_reason_words,
)
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import (
    FinancialState,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    LedgerEventKind,
    Mandate,
    Mode,
    OperationStatus,
)
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.financial.lots import ensure_lots
from app.funding.recommend import (
    KIND_OF,
    Recommendation,
    cost_lines_by_leg,
    plan_suggestions,
    recommend,
    runnable_plan,
)
from app.operations.log import read_entries

router = APIRouter(dependencies=[Depends(require_owner)])

RECENT_DAYS = 7  # "what changed": the last week of the simulated clock
MAX_CHANGES = 8


def _breach(found: list[Alert]) -> Alert | None:
    return next((a for a in found if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)


def _status(found: list[Alert], pending: int) -> str:
    """CRITICAL: a hard limit fails and no committed fix restores the reserve (or the mandate has lapsed).
    ACTION_NEEDED: a hard limit fails and a fix exists, or something waits for the owner. WATCH: warnings only.
    SAFE: nothing."""
    critical = [a for a in found if a.severity == Severity.CRITICAL]
    for a in critical:
        if a.kind == AlertKind.RESERVE_BREACH_AHEAD and (not a.committed_cure or a.inputs.get("cure_restores_reserve") == "false"):
            return "CRITICAL"
        if a.kind == AlertKind.MANDATE_EXPIRING:
            return "CRITICAL"
        if a.kind != AlertKind.RESERVE_BREACH_AHEAD and not a.suggested:
            return "CRITICAL"
    if critical or pending:
        return "ACTION_NEEDED"
    if any(a.severity == Severity.WARNING for a in found):
        return "WATCH"
    return "SAFE"


def _distance(day: int | None, today: int, lang: str) -> str:
    return when_text(day, today, lang)


def _headline(found: list[Alert], mandate: Mandate, traj: Any, horizon: int, today: int,
              lang: str) -> dict[str, str | None]:
    """Level 1, conclusion first: the one-line answer, the detail that explains it (where cash goes, against the
    reserve), the worst point if nothing is done, and the plan's readiness as a separate note."""
    floor = fmt_short(mandate.min_cash_fen)
    breach = _breach(found)
    low_when = _distance(traj.min_cash_day, today, lang)
    if breach is not None:
        short = fmt_short(breach.amount_fen or 0)
        when = _distance(breach.day, today, lang)
        at = next((d.closing_fen for d in traj.days if d.day == breach.day), None)
        worst = t(lang, f"Worst point: {fmt_short(traj.min_cash_fen)} {low_when} if you do nothing.",
                  f"若不采取行动，最低点为{low_when}的 {fmt_short(traj.min_cash_fen)}。")
        if breach.inputs.get("cure_restores_reserve") == "false":
            zero = breach.inputs.get("zero_day", "")
            head = t(lang, f"Cash goes below zero {_distance(int(zero), today, lang)} if nothing is done.",
                     f"若不采取行动，现金将在{_distance(int(zero), today, lang)}跌破零。")
            note = t(lang, f"Cash can be kept at or above zero, but no committed funding restores your {floor} "
                           f"minimum cash reserve: that needs your decision.",
                     f"现金可以保持在零以上，但没有已承诺的融资能恢复您 {floor} 的最低现金储备，需要您决定。")
            return {"headline": head, "note": note, "worst": worst, "plan_note": None}
        head = t(lang, f"Your cash reserve becomes unsafe {when}.", f"您的现金储备将在{when}不再安全。")
        note = (t(lang, f"Cash falls to {fmt_short(at)}, {short} below your {floor} minimum cash reserve.",
                  f"现金将降至 {fmt_short(at)}，比您 {floor} 的最低现金储备低 {short}。") if at is not None
                else t(lang, f"Cash falls {short} below your {floor} minimum cash reserve.",
                       f"现金将比您 {floor} 的最低现金储备低 {short}。"))
        if breach.committed_cure and any(s.above_apr_cap for s in breach.suggested):
            plan_note = t(lang, "A funding plan is ready. It needs your approval because of its cost.",
                          "融资方案已准备好，因其成本需要您批准。")
        elif breach.committed_cure:
            plan_note = t(lang, "A funding plan is ready, within your signed limits. No approval is needed.",
                          "融资方案已准备好，在您签署的授权内，无需批准。")
        elif not mandate.allow_new_borrowing:
            plan_note = t(lang, "Your limits do not allow new borrowing, so no funding can fix it.",
                          "您的授权不允许新增借款，因此无法通过融资解决。")
        else:
            plan_note = t(lang, "No committed funding can fix it: this needs your decision.",
                          "没有已承诺的融资能解决它，需要您决定。")
        return {"headline": head, "note": note, "worst": worst, "plan_note": plan_note}
    warnings = [a for a in found if a.severity == Severity.WARNING]
    head = t(lang, "You're covered.", "您的现金是安全的。")
    note = t(lang, f"Cash stays above your {floor} minimum cash reserve for the next {horizon} days.",
             f"未来 {horizon} 天现金都保持在您 {floor} 的最低现金储备以上。")
    thin = next((a for a in warnings if a.kind == AlertKind.RESERVE_HEADROOM_LOW), None)
    if thin is not None and thin.day is not None and not thin.amount_fen:
        note += " " + t(lang, f"It comes close: cash sits exactly on the minimum cash reserve {_distance(thin.day, today, lang)}.",
                        f"但会很接近：{_distance(thin.day, today, lang)}现金恰好等于最低现金储备。")
    elif thin is not None and thin.day is not None:
        note += " " + t(lang, f"It comes close: only {fmt_yuan(thin.amount_fen or 0)} above the minimum cash reserve "
                              f"{_distance(thin.day, today, lang)}.",
                        f"但会很接近：{_distance(thin.day, today, lang)}仅高出最低现金储备 {fmt_yuan(thin.amount_fen or 0)}。")
    elif warnings:
        note += " " + relative_days(warnings[0].title, today, lang)
    worst = t(lang, f"Lowest cash ahead: {fmt_short(traj.min_cash_fen)} {low_when}.",
              f"未来最低现金：{low_when}的 {fmt_short(traj.min_cash_fen)}。")
    return {"headline": head, "note": note, "worst": worst, "plan_note": None}


def _drivers(state: FinancialState, traj: Any, today: int, breach_day: int | None, lang: str) -> list[str]:
    """What is driving the cash risk, from the projection's own events: the largest outflows between today and the
    first unsafe day, and the receipt that arrives only after it. At most two sentences; nothing is computed, the
    events are the engine's."""
    if breach_day is None:
        return []
    out: list[tuple[int, str]] = []
    for d in traj.days:
        if today <= d.day <= breach_day:
            for e in d.events:
                if e.amount_fen < 0 and e.kind in (LedgerEventKind.FLOW,):
                    label = in_words(state, e.label.split(" (")[0].split(",")[0])
                    out.append((e.amount_fen, t(lang, f"{label} of {fmt_short(-e.amount_fen)} falls due {when_text(d.day, today, lang)}.",
                                                 f"{label} {fmt_short(-e.amount_fen)} 将于{when_text(d.day, today, lang)}到期。")))
    out.sort(key=lambda x: x[0])
    sentences = [text for _, text in out[:2]]
    nxt = next(((d.day, e) for d in traj.days if d.day > breach_day for e in d.events
                if e.amount_fen > 0 and e.kind in (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)), None)
    if nxt is not None and len(sentences) < 2:
        day, e = nxt
        sentences.append(t(lang, f"The next receipt, {fmt_short(e.amount_fen)}, lands only {when_text(day, today, lang)}.",
                           f"下一笔收款 {fmt_short(e.amount_fen)} 要到{when_text(day, today, lang)}才到账。"))
    return sentences

def _rate_in(reason: str) -> str | None:
    """The effective yearly rate the router's approval reason names ("effective annual cost 16.26% is above ...")."""
    m = re.search(r"effective annual cost (\S+) is above", reason or "")
    return m.group(1) if m else None


def _plan_lines(state: FinancialState, p: FundingPlan, lang: str) -> list[dict[str, Any]]:
    """The router's cost lines, in words, plus one more line when its total is not their sum: the router's total is
    the net change in charges the plan makes to the whole projection, so a plan that lets an existing balance be
    repaid sooner carries that saving as a negative line here, and the lines always add up to the total shown."""
    lines = [{"label": relative_days(in_words(state, cl.label), state.as_of_day, lang), "display": fmt_yuan(cl.fen),
              "formula": cl.formula} for cl in p.costs]
    offset = p.total_cost_fen - sum(cl.fen for cl in p.costs)
    if offset != 0:
        lines.append({"label": t(lang, "Change in interest on balances already drawn", "已提款余额的利息变化"),
                      "display": fmt_yuan(offset), "formula": None})
    return lines


def _plan_legs(state: FinancialState, p: FundingPlan, today: int, lang: str) -> list[dict[str, Any]]:
    """The router plan's legs as business legs: amounts, the cost line the router wrote for each, its landing day."""
    legs: list[dict[str, Any]] = []
    for i, (a, cl) in enumerate(zip(p.actions, p.costs, strict=True)):
        kind = KIND_OF[a.kind]
        legs.append({
            "index": i,
            "operation_kind": kind,
            "label": leg_words(state, kind, a.facility_id, a.receivable_id, a.amount_fen, lang),
            "facility_id": a.facility_id,
            "facility_name": facility_name(state, a.facility_id),
            "receivable_id": a.receivable_id,
            "buyer_name": party_name(state, buyer_of_receivable(state, a.receivable_id)) or None,
            "amount_fen": a.amount_fen,
            "amount_display": fmt_yuan(a.amount_fen),
            "cost_fen": cl.fen,
            "cost_display": fmt_yuan(cl.fen),
            "rate_text": _rate_in(cl.approval_reason),
            "cost_days": None,
            "cost_due_day": a.repay_day,
            "lands_day": a.lands_day if a.lands_day is not None else today + lead_days(state, a.facility_id),
            "lands_when": when_text(a.lands_day if a.lands_day is not None else today + lead_days(state, a.facility_id), today, lang),
            "above_apr_cap": cl.needs_owner_approval,
            "formula": cl.formula,
        })
    return legs


def _plan_basis(state: FinancialState, p: FundingPlan, lang: str) -> str:
    """What the all-in estimate assumes, in words: the line is priced to the day the baseline first recovers (the
    router's own convention), an advance in whole 30-day periods until the invoice is paid."""
    parts: list[str] = []
    for a in p.actions:
        if a.kind == FundingActionKind.DRAW and a.repay_day is not None:
            name = facility_name(state, a.facility_id)
            when = when_text(a.repay_day, state.as_of_day, lang)
            parts.append(t(lang, f"Estimated through the expected repayment of the {name} {when}, the first "
                                 f"receipt that can repay it; the final interest depends on the actual repayment day.",
                           f"按预计{when}（第一笔足以还款的收款）偿还{name}估算；最终利息取决于实际还款日。"))
    if any(a.kind == FundingActionKind.FINANCE_INVOICE for a in p.actions):
        parts.append(t(lang, "Invoice financing is billed in whole 30-day periods until the invoice is paid.",
                       "发票融资按整 30 天计费，直至发票付清。"))
    return " ".join(parts)


def _alert_actions(state: FinancialState, alert: Alert, today: int) -> list[FundingAction]:
    """The alert's suggested cure as projection actions (for the after-state series only; nothing runs)."""
    out: list[FundingAction] = []
    for s in alert.suggested:
        if s.operation_kind == "DRAW_FACILITY" and s.facility_id and s.amount_fen:
            out.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=s.facility_id, day=today, amount_fen=s.amount_fen))
        elif s.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING" and s.facility_id and s.receivable_id and s.amount_fen:
            out.append(FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=s.facility_id, day=today,
                                     amount_fen=s.amount_fen, receivable_id=s.receivable_id))
    return out


def _series(state: FinancialState, traj: Any) -> list[dict[str, Any]]:
    """One projection as the chart's rows: the day, its closing cash (fen for the axis, the display string for the
    reader) and the events that moved it, with ids replaced by names."""
    return [{"day": d.day, "closing_fen": d.closing_fen, "closing_display": fmt_yuan(d.closing_fen),
             "events": [{"kind": e.kind.value, "label": in_words(state, e.label), "amount_fen": e.amount_fen,
                         "amount_display": fmt_yuan(e.amount_fen)} for e in d.events]}
            for d in traj.days]


def _after_words(after: Any, floor: int, today: int, horizon: int, lang: str) -> str:
    """The after-state of a plan from its own projection: the first day cash is below the reserve, if any."""
    first = next((d.day for d in after.days if d.day >= today and d.closing_fen < floor), None)
    if first is None:
        return t(lang, f"Cash stays above your minimum cash reserve for the next {horizon} days.",
                 f"未来 {horizon} 天现金都保持在您的最低现金储备以上。")
    return t(lang, f"Cash stays above your minimum cash reserve for the next {max(first - 1 - today, 0)} days.",
             f"未来 {max(first - 1 - today, 0)} 天现金都保持在最低现金储备以上。")


def _next_action(state: FinancialState, obs: list[Any], mandate: Mandate, found: list[Alert], approvals: list[Any],
                 today: int, state_version: int, lang: str, *, use_router: bool = True) -> dict[str, Any] | None:
    """The one thing to do now, for the first actionable critical alert (a reserve breach), else a repayment the books
    can afford. For a reserve breach the plan shown is the recommendation of `app.funding.recommend`: the router's
    cheapest runnable plan, priced all-in on the router's convention, else the alert's own cure. Its cost, landing day
    and after-state are the engine's; "Go ahead" binds to the exact legs listed in `suggestions`."""
    alert = next((a for a in found if a.actionable and a.severity == Severity.CRITICAL), None)
    if alert is None:
        alert = next((a for a in found if a.actionable and a.kind == AlertKind.FACILITY_REPAYABLE), None)
    if alert is None:
        return None
    cure_legs_ = cure_legs(state, alert, today, lang)
    queued = next((a for a in approvals if str(getattr(a.status, "value", a.status)) == "PENDING"
                   and (a.op_id or "").startswith(f"alert:{alert.id}:")), None)
    horizon = mandate.horizon_days
    floor = mandate.min_cash_fen

    rec = Recommendation("alert", None, None)
    reserve_cure = alert.kind == AlertKind.RESERVE_BREACH_AHEAD and alert.inputs.get("cure_restores_reserve") != "false"
    if use_router and reserve_cure:
        rec = recommend(state, obs, mandate, cure_exists=bool(cure_legs_),
                        cure_approvals=sum(1 for leg in cure_legs_ if leg["above_apr_cap"]))

    if rec.source == "router" and rec.plan is not None:
        p = rec.plan
        legs = _plan_legs(state, p, today, lang)
        needs_owner = p.needs_owner_approval
        needs_owner_reason = in_words(state, p.approval_reason) if needs_owner else None
        cost_total = fmt_yuan(p.total_cost_fen)
        cost_breakdown = _plan_lines(state, p, lang)
        cost_basis = _plan_basis(state, p, lang)
        cost_note = None
        actions = list(p.actions)
        suggestions = plan_suggestions(p)
        why = t(lang, "The cheapest plan your committed facilities can fund in time, within the bounded search.",
                "在有界搜索范围内，您已承诺的额度能及时覆盖缺口的最便宜方案。")
        cheaper = None
    else:
        legs = cure_legs_
        needs_owner = any(leg["above_apr_cap"] for leg in legs) or any(
            leg["operation_kind"] == "APPLY_FOR_FACILITY" for leg in legs)
        needs_owner_reason = needs_owner_reason_words(mandate, legs, lang) if needs_owner else None
        # The engine states the whole cure's cost only when every leg is priced; otherwise the priced legs are quoted
        # and the basis says what is left out: an open-ended draw posts no interest until it is repaid.
        cost_total = alert.inputs.get("cure_cost")
        cost_note = None
        priced = [leg for leg in legs if leg["cost_display"]]
        if cost_total is None and len(priced) == 1:
            cost_total = priced[0]["cost_display"]
        unpriced_draw = [leg for leg in legs if leg["operation_kind"] == "DRAW_FACILITY" and not leg["cost_display"]]
        if unpriced_draw and cost_total:
            names = ", ".join(leg["facility_name"] for leg in unpriced_draw)
            cost_note = t(lang, f"Interest on the {names} draw is not included: it runs only while the balance stays drawn.",
                          f"不含{names}提款的利息：利息只在余额未还期间产生。")
        cost_breakdown = [{"label": leg["label"], "display": leg["cost_display"], "formula": None} for leg in priced]
        cost_basis = cost_note or (t(lang, "Invoice financing is billed in whole 30-day periods until the invoice is paid.",
                                     "发票融资按整 30 天计费，直至发票付清。")
                                   if any(leg["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" for leg in priced) else "")
        actions = _alert_actions(state, alert, today)
        suggestions = [{"operation_kind": s.operation_kind, "facility_id": s.facility_id,
                        "receivable_id": s.receivable_id, "amount_fen": s.amount_fen} for s in alert.suggested]
        cheaper = None
        if rec.cheaper is not None:
            c = rec.cheaper
            n = sum(1 for cl in c.costs if cl.needs_owner_approval)
            words = [leg_words(state, KIND_OF[a.kind], a.facility_id, a.receivable_id, a.amount_fen, lang) for a in c.actions]
            offset = c.total_cost_fen - sum(cl.fen for cl in c.costs)
            saving = (t(lang, f" (including {fmt_yuan(-offset)} less interest on balances already drawn)",
                        f"（含已提款余额少付的利息 {fmt_yuan(-offset)}）") if offset < 0 else "")
            cheaper = {"label": t(lang, " and ".join(words), "，".join(words)), "cost_total_display": fmt_yuan(c.total_cost_fen),
                       "approvals": n, "legs": [f"{x['label']}: {x['display']}" for x in _plan_lines(state, c, lang)]}
            why = t(lang, f"The cheapest option, {fmt_yuan(c.total_cost_fen)} in all{saving}, needs {n} separate approvals; "
                          f"this one needs one. Both are on Compare options.",
                    f"最便宜的方案合计 {fmt_yuan(c.total_cost_fen)}{saving}，但需要 {n} 次单独批准；此方案只需一次。两者都在“比较方案”中。")
        elif alert.kind == AlertKind.RESERVE_BREACH_AHEAD and alert.inputs.get("cure_restores_reserve") == "false":
            why = t(lang, "No committed funding restores the reserve; this is the cheapest way to stay above zero.",
                    "没有已承诺的融资能恢复安全线；这是保持在零以上最便宜的方式。")
        elif alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
            why = t(lang, "A committed funding that covers the whole gap in time.", "能及时覆盖整个缺口的已承诺融资。")
        else:
            why = in_words(state, alert.detail)

    if len(legs) == 1:
        title = legs[0]["label"]
    else:
        title = t(lang, " and ".join([legs[0]["label"]] + [leg["label"][0].lower() + leg["label"][1:] for leg in legs[1:]]),
                  "，".join(leg["label"] for leg in legs))
    lands = [leg["lands_day"] for leg in legs if leg["lands_day"] is not None]
    receive = sum(leg["amount_fen"] or 0 for leg in legs if leg["operation_kind"] in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"))

    receive_short = fmt_short(receive) if receive else None
    components = []
    for leg in legs:
        if leg["operation_kind"] == "DRAW_FACILITY":
            what = leg["facility_name"]
        elif leg["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING":
            face = receivable_face(state, leg["receivable_id"])
            buyer = leg["buyer_name"] or ""
            inv = (t(lang, f"the {fmt_short(face)} invoice to {buyer}", f"{buyer} 的 {fmt_short(face)} 发票") if face is not None and buyer
                   else invoice_words(state, leg["receivable_id"], lang))
            what = t(lang, f"against {inv}", f"以{inv}融资")
        elif leg["operation_kind"] == "REPAY_FACILITY":
            what = t(lang, f"repay {leg['facility_name']}", f"偿还{leg['facility_name']}")
        else:
            what = leg["label"]
        components.append({"amount_short": fmt_short(leg["amount_fen"] or 0), "what": what, "lands_when": leg.get("lands_when")})
    if alert.kind == AlertKind.RESERVE_BREACH_AHEAD and receive:
        outcome_title = t(lang, f"Secure {receive_short} of funding", f"筹措 {receive_short} 资金")
    elif alert.kind == AlertKind.FACILITY_REPAYABLE and receive:
        outcome_title = t(lang, f"Repay {receive_short} of the credit line", f"偿还信用额度 {receive_short}")
    else:
        outcome_title = title
    plan_series: list[dict[str, Any]] | None = None
    after_traj = None
    after_lowest = None
    if actions:
        try:
            after_traj = project(state, obs, actions, Mode.CONSERVATIVE, horizon, floor)
            plan_series = _series(state, after_traj)
            after_lowest = min((d.closing_fen for d in after_traj.days if d.day >= today), default=None)
        except EngineError:
            after_traj = None

    if alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
        short = fmt_yuan(alert.amount_fen or 0)
        if alert.inputs.get("cure_restores_reserve") == "false":
            zero_when = when_text(int(alert.inputs.get("zero_day", today)), today, lang)
            if_nothing = t(lang, f"Cash goes below zero {zero_when}.", f"现金将在{zero_when}跌破零。")
            after = t(lang, f"Cash stays at or above zero, but your minimum cash reserve is still "
                            f"{alert.inputs.get('residual_shortfall')} short on the worst day.",
                      f"现金保持在零以上，但最差的一天仍比最低现金储备低 {alert.inputs.get('residual_shortfall')}。")
        else:
            worst_when = when_text(int(alert.inputs.get("worst_day", alert.day or today)), today, lang)
            if_nothing = t(lang, f"{short} below your minimum cash reserve {when_text(alert.day, today, lang)}; the gap peaks at "
                                 f"{alert.inputs.get('max_shortfall', short)} {worst_when}.",
                           f"{when_text(alert.day, today, lang)}比最低现金储备低 {short}；缺口在{worst_when}最大，为 "
                           f"{alert.inputs.get('max_shortfall', short)}。")
            if after_traj is not None:
                after = _after_words(after_traj, floor, today, horizon, lang)
            else:
                last = int(alert.inputs.get("last_day", alert.day or today))
                after = t(lang, f"Cash stays above your minimum cash reserve for the next {max(last - today, 0)} days.",
                          f"未来 {max(last - today, 0)} 天现金都保持在最低现金储备以上。")
    else:
        if_nothing = t(lang, "Interest keeps running on the drawn balance.", "已提款余额将继续产生利息。")
        after = t(lang, "The balance is repaid and the interest stops.", "余额还清，利息停止。")

    return {
        "alert_id": alert.id,
        "kind": alert.kind.value,
        "plan_source": rec.source,
        "title": title,
        "outcome_title": outcome_title,
        "components": components,
        "receive_short": receive_short,
        "after_lowest_fen": after_lowest,
        "after_lowest_short": fmt_short(after_lowest) if after_lowest is not None else None,
        "legs": legs,
        "receive_fen": receive or None,
        "receive_display": fmt_yuan(receive) if receive else None,
        "cost_display": cost_total,
        "cost_total_display": cost_total,
        "cost_breakdown": cost_breakdown,
        "cost_basis": cost_basis or None,
        "cost_note": cost_note,
        "cheaper_option": cheaper,
        "rate_text": next((leg["rate_text"] for leg in legs if leg["rate_text"]), None),
        "cost_days": next((leg["cost_days"] for leg in legs if leg["cost_days"]), None),
        "lands_day": max(lands) if lands else None,
        "lands_when": when_text(max(lands), today, lang) if lands else None,
        "needs_owner": needs_owner,
        "needs_owner_reason": needs_owner_reason,
        "authority_text": (t(lang, f"Needs your approval: {needs_owner_reason}" if needs_owner_reason else "Needs your approval.",
                             f"需要您批准：{needs_owner_reason}" if needs_owner_reason else "需要您批准。") if needs_owner
                           else t(lang, "Within your signed limits. No additional approval required.",
                                  "在您签署的授权内，无需额外批准。")),
        "if_nothing": if_nothing,
        "after": after,
        "why": why,
        "detail": relative_days(in_words(state, alert.detail), today, lang),
        "formula": alert.formula,
        "pending_approval_id": queued.id if queued is not None else None,
        "state_version": state_version,
        "suggestions": suggestions,
        "plan_series": plan_series,
    }

def _approvals(state: FinancialState, obs: list[Any], mandate: Mandate, approvals: list[Any], found: list[Alert],
               today: int, lang: str, *, use_router: bool = True) -> list[dict[str, Any]]:
    by_id = {a.id: a for a in found}
    plan_costs: dict = {}
    if use_router and any(str(getattr(a.status, "value", a.status)) == "PENDING" for a in approvals):
        plan = runnable_plan(state, obs, mandate)
        plan_costs = cost_lines_by_leg(plan) if plan is not None else {}
    out = []
    for a in approvals:
        if str(getattr(a.status, "value", a.status)) != "PENDING":
            continue
        try:
            op = json.loads(a.op_json)
        except ValueError:
            op = {}
        alert = None
        if (a.op_id or "").startswith("alert:"):
            alert = by_id.get(a.op_id.split(":")[1])
        words = approval_words(state, op, a.kind, today, alert, lang, plan_costs)
        amount = op.get("amount_fen", op.get("advance_fen"))
        out.append({"id": a.id, "kind": a.kind, "reason": relative_days(in_words(state, a.reason), today, lang), "created_day": op.get("day"),
                    "amount_fen": amount if isinstance(amount, int) else None,
                    "amount_display": fmt_yuan(amount) if isinstance(amount, int) else None, **words})
    return out


def _changes(state: FinancialState, store: Any, found: list[Alert], today: int, lang: str,
             since_day: int | None = None) -> list[dict[str, Any]]:
    """Since the owner's last visit when the web says when that was (`since_day`), else the last week of the clock."""
    since = since_day if since_day is not None else today - RECENT_DAYS
    items: list[dict[str, Any]] = []
    entries, _ = read_entries(store.operations())
    for e in entries:
        day = e.day
        if day is None or day < since:
            continue
        if e.result.status == OperationStatus.DUPLICATE or "CLOCK" in e.kind.upper():
            continue  # a clock step is not news; what it posted shows as receipts, landings and alerts
        who = (getattr(e.op, "requested_by", None) or "") if e.op is not None else ""
        who = str(getattr(who, "value", who))
        kind = "REFUSED" if e.result.status == OperationStatus.REFUSED else (
            "WAITING" if e.result.status == OperationStatus.PENDING_APPROVAL else
            ("RECEIPT" if e.kind == "RECEIVE_PAYMENT" else "OPERATION"))
        text = in_words(state, e.result.message or e.kind.replace("_", " ").lower())
        if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and e.result.status == OperationStatus.EXECUTED:
            cmt = next((c for c in store.commitments() if c.id in (e.result.message or "")), None)
            if cmt is not None:
                text = t(lang, f"Agreement with {party_name(state, cmt.counterparty_id)} recorded; future give-aways booked: "
                               f"{fmt_yuan(cmt.forward_value_fen)}.",
                         f"已记录与{party_name(state, cmt.counterparty_id)}的协议；已入账的未来让利：{fmt_yuan(cmt.forward_value_fen)}。")
                kind = "AGREEMENT"
        items.append({"day": day, "seq": e.seq, "kind": kind, "actor": who, "text": relative_days(text, today, lang),
                      "when": when_text(day, today, lang)})
    for a in found:
        if a.kind == AlertKind.RECEIVABLE_PAST_DUE:
            items.append({"day": a.day, "seq": None, "kind": "LATE", "actor": "",
                          "text": relative_days(in_words(state, a.detail.split(". ")[0] + "."), today, lang),
                          "when": when_text(a.day, today, lang)})
    for lot in ensure_lots(state).lots:
        if lot.settled and since <= lot.arrival_day <= today and lot.arrival_day != lot.request_day:
            items.append({"day": lot.arrival_day, "seq": None, "kind": "LANDED", "actor": "",
                          "when": when_text(lot.arrival_day, today, lang),
                          "text": t(lang, f"{fmt_yuan(lot.principal_fen)} from {facility_name(state, lot.facility_id)} landed {when_text(lot.arrival_day, today, lang)}.",
                                    f"来自{facility_name(state, lot.facility_id)}的 {fmt_yuan(lot.principal_fen)} 已于{when_text(lot.arrival_day, today, lang)}到账。")})
    items.sort(key=lambda x: (-(x["day"] or 0), -(x["seq"] or 0)))
    return items[:MAX_CHANGES]


def _receivables(state: FinancialState, store: Any, today: int, lang: str) -> dict[str, Any]:
    report = reconcile(store, day=today)
    rows: list[dict[str, Any]] = []
    for o in report.outstanding:
        rows.append({"receivable_id": o.receivable_id, "buyer_id": o.counterparty_id,
                     "buyer_name": party_name(state, o.counterparty_id), "face_fen": o.face_fen,
                     "face_display": fmt_yuan(o.face_fen), "due_day": o.due_day, "due_when": when_text(o.due_day, today, lang),
                     "past_due": o.past_due,
                     "days_late": max(0, today - o.due_day) if o.past_due else 0,
                     "invoice": invoice_words(state, o.receivable_id, lang)})
    past_due = [r for r in rows if r["past_due"]]
    upcoming = sorted((r for r in rows if not r["past_due"]), key=lambda r: (r["due_day"], r["receivable_id"]))
    nxt = upcoming[0] if upcoming else None
    total = sum(r["face_fen"] for r in rows)
    overdue = sum(r["face_fen"] for r in past_due)
    awaited = [p for p in report.promised if p.status.value == "AWAITED"]
    promise = None
    if awaited:
        p = min(awaited, key=lambda p: (p.promised_day if p.promised_day is not None else 10**6))
        promise = {"receivable_id": p.receivable_id, "buyer_name": party_name(state, p.counterparty_id),
                   "expected_display": fmt_yuan(p.expected_fen), "promised_day": p.promised_day,
                   "when": when_text(p.promised_day, today, lang) if p.promised_day is not None else None}
    return {"open_count": len(rows), "open_total_display": fmt_yuan(total),
            "overdue_total_display": fmt_yuan(overdue), "past_due": past_due,
            "next_receipt": nxt, "promised": promise, "lapsed_promises": report.lapsed_promises}


def _in_transit(state: FinancialState, today: int, lang: str) -> dict[str, Any] | None:
    lots = [lot for lot in ensure_lots(state).lots if not lot.settled]
    if not lots:
        return None
    total = sum(lot.remaining_fen for lot in lots)
    return {"total_display": fmt_yuan(total), "lots": [
        {"facility_name": facility_name(state, lot.facility_id), "amount_display": fmt_yuan(lot.remaining_fen),
         "arrival_day": lot.arrival_day, "arrival_when": when_text(lot.arrival_day, today, lang)}
        for lot in sorted(lots, key=lambda lt: (lt.arrival_day, lt.id))]}


@router.get("/home")
def get_home(lang: str = "en", since_day: int | None = None) -> dict[str, Any]:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        today = max(rt.day, state.as_of_day)
        try:
            found = alerts(state, mandate, rt.store, rt.day)
            books = current_books(state, rt.store.commitments())
            traj = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        approvals = rt.store.approvals()
        pending = [a for a in approvals if str(getattr(a.status, "value", a.status)) == "PENDING"]
        status = _status(found, len(pending))
        words = _headline(found, mandate, traj, mandate.horizon_days, today, lang)
        headline, note = words["headline"], words["note"]
        drivers = _drivers(books.state, traj, today, traj.first_breach_day, lang)
        at_breach = next((d.closing_fen for d in traj.days if d.day == traj.first_breach_day), None) if traj.first_breach_day is not None else None
        action = _next_action(books.state, books.with_([]), mandate, found, approvals, today, state.state_version, lang,
                              use_router=rt.settings.features.debt_desk)
        plan_series = action.pop("plan_series") if action is not None else None
        series = _series(books.state, traj)
        queue = _approvals(books.state, books.with_([]), mandate, approvals, found, today, lang,
                           use_router=rt.settings.features.debt_desk)
        changes = _changes(books.state, rt.store, found, today, lang, since_day)
        receivables = _receivables(books.state, rt.store, today, lang)
        in_transit = _in_transit(books.state, today, lang)
        warnings = [{"id": a.id, "kind": a.kind.value, "title": relative_days(in_words(state, a.title), today, lang),
                     "detail": relative_days(in_words(state, a.detail), today, lang), "day": a.day,
                     "when": when_text(a.day, today, lang)} for a in found if a.severity == Severity.WARNING]
        facilities = [{"id": f.id, "name": f.name, "status": f.status.value, "limit_display": fmt_yuan(f.limit_fen),
                       "drawn_display": fmt_yuan(f.drawn_fen), "available_display": fmt_yuan(max(f.limit_fen - f.drawn_fen, 0)),
                       "lead_time_days": f.lead_time_days}
                      for f in state.facilities if f.status.value == "COMMITTED" and f.limit_fen > 0]
    month1 = traj.months[0] if traj.months else None
    dscr = month1.dscr if month1 is not None else None
    dscr_text = f"{dscr.text}×" if dscr is not None else None
    lev = month1.leverage if month1 is not None else None
    leverage_text = f"{lev.text}×" if lev is not None else None
    return displayed({
        "day": today,
        "state_version": state.state_version,
        "lang": lang,
        "status": status,
        "headline": headline,
        "note": note,
        "worst": words["worst"],
        "plan_note": words["plan_note"],
        "since_day": since_day,
        "cash": {
            "cash_fen": state.cash_fen,
            "floor_fen": mandate.min_cash_fen,
            "lowest_fen": traj.min_cash_fen,
            "lowest_day": traj.min_cash_day,
            "first_breach_day": traj.first_breach_day,
            "first_breach_cash_fen": at_breach,
            "first_breach_cash_short": fmt_short(at_breach) if at_breach is not None else None,
            "cash_short": fmt_short(state.cash_fen),
            "floor_short": fmt_short(mandate.min_cash_fen),
            "lowest_short": fmt_short(traj.min_cash_fen),
            "drivers": drivers,
            "lowest_when": when_text(traj.min_cash_day, today, lang),
            "first_breach_when": when_text(traj.first_breach_day, today, lang) if traj.first_breach_day is not None else None,
            "horizon_days": mandate.horizon_days,
            "in_transit": in_transit,
            "dscr_text": dscr_text,
            "leverage_text": leverage_text,
            "min_dscr_bp": mandate.min_dscr_bp,
            "max_leverage_bp": mandate.max_leverage_bp,
            # One projection for every figure and the chart: the baseline ("if you do nothing") and the same books with
            # the recommended plan applied ("with the recommended plan"). The browser draws these and computes nothing.
            "series": series,
            "plan_series": plan_series,
        },
        "next_action": action,
        "approvals": queue,
        "pending_count": len(pending),
        "changes": changes,
        "receivables": receivables,
        "warnings": warnings,
        "facilities": facilities,
        "counts": {s.value: sum(1 for a in found if a.severity == s) for s in Severity},
        "note_basis": t(lang, "Conservative projection of today's books: unconfirmed receipts are not counted.",
                        "基于今日账目的保守预测：未确认的收款不计入。"),
    })
