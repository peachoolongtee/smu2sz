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
import logging
import re
from types import SimpleNamespace
from typing import Any, ClassVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.alerts import Alert, AlertKind, Severity, alerts, reconcile
from app.api.auth import require_owner
from app.api.causality import Causality, forecast_of, mark_changed
from app.api.decisions import Reconciled, decision_summary, load_context, remaining_links, remaining_task_view
from app.api.display import displayed
from app.api.financing_words import financing_state_words
from app.api.presentation import (
    COMMERCIAL_KINDS,
    RECOMMENDED_PLAN_KEY,
    agreement_ref,
    agreement_terms,
    agreement_words,
    approval_reason_words,
    approval_words,
    business_text,
    buyer_of_receivable,
    cure_legs,
    engine_sentence,
    event_words,
    facility_name,
    find_agreement,
    first_breach_ahead,
    fmt_short,
    in_language,
    in_words,
    invoice_words,
    lead_days,
    leg_names,
    leg_words,
    live_windows,
    lowest_point_words,
    party_name,
    point_words,
    receivable_face,
    relative_days,
    series_axes,
    series_axis,
    t,
    when_text,
    window_is_live,
)
from app.api.presentation import (
    needs_owner_reason as needs_owner_reason_words,
)
from app.api.receipt import plan_receipt
from app.api.receipt_basis import BasisReader, agreement_days, annotate
from app.api.runtime import get_runtime
from app.books import current_books
from app.decisions.identity import deal_id, decision_id_for
from app.domain.models import (
    FinancialState,
    FundingAction,
    FundingActionKind,
    FundingLot,
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
    cost_lines_by_leg,
    plan_suggestions,
    recommend_for_alert,
    runnable_plan,
)
from app.operations.log import CONFIRM_DOCUMENT_KIND, REJECT_DOCUMENT_KIND, read_entries

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


def _lowest_ahead(traj: Any, today: int) -> tuple[int, int]:
    """The lowest cash from today on (fen, day). The projection's days are absolute and the closed days before today
    carry the opening cash, so the trajectory's own minimum can sit in the past ("34 days ago"); the home speaks of
    what is ahead."""
    ahead = [d for d in traj.days if d.day >= today] or list(traj.days)
    low = min(ahead, key=lambda d: (d.closing_fen, d.day))
    return low.closing_fen, low.day


def _headline(found: list[Alert], mandate: Mandate, traj: Any, horizon: int, today: int,
              lang: str, low: tuple[int, int] | None = None, funding_counted: bool = False,
              state: FinancialState | None = None) -> dict[str, str | None]:
    """Level 1, conclusion first: the one-line answer, the detail that explains it (where cash goes, against the
    reserve), the worst point if nothing is done, and the plan's readiness as a separate note."""
    floor = fmt_short(mandate.min_cash_fen)
    breach = _breach(found)
    low_fen, low_day = low if low is not None else _lowest_ahead(traj, today)
    low_when = _distance(low_day, today, lang)
    if breach is not None:
        short = fmt_short(breach.amount_fen or 0)
        when = _distance(breach.day, today, lang)
        at = next((d.closing_fen for d in traj.days if d.day == breach.day), None)
        # The projection counts funding already requested and in transit (its lot lands in the projection); then the worst
        # point is not "if you do nothing" (R04).
        worst: str | None = (t(lang, f"Lowest point: {fmt_short(low_fen)} {low_when} if nothing more is done.",
                               f"若不再采取其他行动，最低点为{low_when}的 {fmt_short(low_fen)}。") if funding_counted else
                             t(lang, f"Worst point: {fmt_short(low_fen)} {low_when} if you do nothing.",
                               f"若不采取行动，最低点为{low_when}的 {fmt_short(low_fen)}。"))
        if breach.inputs.get("cure_restores_reserve") == "false":
            zero = breach.inputs.get("zero_day", "")
            zero_when = _distance(int(zero), today, lang)
            if breach.day is not None and breach.day <= today:
                # Already under the reserve (F01): the headline says so; the zero day is the note's fact.
                head = t(lang, "Below reserve today.", "今天现金低于储备。")
                note = t(lang, f"Cash is {short} below your {floor} minimum cash reserve and goes below zero {zero_when} "
                               f"if nothing is done. It can be kept at or above zero, but no committed funding restores the "
                               f"reserve: that needs your decision.",
                         f"现金比您 {floor} 的最低现金储备低 {short}，若不采取行动将在{zero_when}跌破零。现金可以保持在零以上，"
                         f"但没有已承诺的融资能恢复储备，需要您决定。")
            else:
                head = t(lang, f"Cash goes below zero {zero_when} if nothing is done.", f"若不采取行动，现金将在{zero_when}跌破零。")
                note = t(lang, f"Cash can be kept at or above zero, but no committed funding restores your {floor} "
                               f"minimum cash reserve: that needs your decision.",
                         f"现金可以保持在零以上，但没有已承诺的融资能恢复您 {floor} 的最低现金储备，需要您决定。")
            return {"headline": head, "note": note, "worst": worst, "plan_note": None}
        if breach.day == low_day:
            worst = None  # the headline and note already say where cash falls; a second sentence would repeat it
        if breach.day is not None and breach.day <= today:
            # Already under the reserve: it is not something that "becomes" so (F01).
            head = t(lang, "Below reserve today.", "今天现金低于储备。")
            note = t(lang, f"Cash is {short} below your {floor} minimum cash reserve.", f"现金比您 {floor} 的最低现金储备低 {short}。")
        else:
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
    if low_fen == mandate.min_cash_fen:  # the lowest point sits exactly on the reserve: "at or above", not "above"
        note = t(lang, f"Cash stays at or above your {floor} minimum cash reserve for the next {horizon} days.",
                 f"未来 {horizon} 天现金都不低于您 {floor} 的最低现金储备。")
    else:
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
        note += " " + ((business_text(state, warnings[0].title, today, lang) or "") if state is not None
                       else agreement_ref(relative_days(warnings[0].title, today, lang)))
    worst = t(lang, f"Lowest cash ahead: {fmt_short(low_fen)} {low_when}.",
              f"未来最低现金：{low_when}的 {fmt_short(low_fen)}。")
    return {"headline": head, "note": note, "worst": worst, "plan_note": None}


def _status_text(status: str, found: list[Alert], lang: str) -> str:
    """The status in the owner's words. WATCH with thin headroom is "Covered, but tight": the business is not
    projected to fail, the margin is thin (owner decision, wayfinder #28)."""
    if status == "SAFE":
        return t(lang, "Covered", "安全")
    if status == "WATCH":
        if any(a.kind == AlertKind.RESERVE_HEADROOM_LOW for a in found):
            return t(lang, "Covered, but tight", "安全，但余量不多")
        return t(lang, "Covered, with warnings", "安全，但有提醒")
    if status == "ACTION_NEEDED":
        return t(lang, "Action needed", "需要行动")
    return t(lang, "Critical", "紧急")


def _funding_lots(state: FinancialState, today: int, lang: str) -> list[dict[str, Any]]:
    """Every funding lot on the books, landed or still arriving, so Cash & funding can state the current position."""
    return [{"facility_name": facility_name(state, lot.facility_id), "amount_display": fmt_yuan(lot.principal_fen),
             "remaining_display": fmt_yuan(lot.remaining_fen), "landed": bool(lot.settled),
             "opening": bool(lot.assumed_date),  # a balance older than the books, not funding received today

             "arrival_day": lot.arrival_day, "arrival_when": when_text(lot.arrival_day, today, lang),
             "maturity_day": lot.maturity_day,
             "maturity_when": when_text(lot.maturity_day, today, lang) if lot.maturity_day is not None else None}
            for lot in sorted(ensure_lots(state).lots, key=lambda lt: (lt.arrival_day, lt.id))]


def _drivers(state: FinancialState, traj: Any, today: int, breach_day: int | None, lang: str,
             through_day: int | None = None) -> list[str]:
    """What is driving the cash risk, from the projection's own events: the largest outflows between today and the
    first unsafe day, and the receipt that arrives only after it. At most two sentences; nothing is computed, the
    events are the engine's. When cash is already under the reserve today, the outflows that matter run to `through_day`
    (the lowest point ahead), since "between today and today" would name none (R02)."""
    if breach_day is None:
        return []
    last = max(breach_day, through_day) if through_day is not None and breach_day <= today else breach_day
    out: list[tuple[int, str]] = []
    for d in traj.days:
        if today <= d.day <= last:
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
    lines = [{"label": engine_sentence(state, cl.label, state.as_of_day, lang), "display": fmt_yuan(cl.fen),
              "formula": cl.formula} for cl in p.costs]
    offset = p.total_cost_fen - sum(cl.fen for cl in p.costs)
    if offset != 0:
        lines.append({"label": t(lang, "Change in other interest and fees across the forecast", "预测期内其他利息与费用的变化"),
                      "display": fmt_yuan(offset), "formula": None})
    return lines


def plan_legs(state: FinancialState, p: FundingPlan, today: int, lang: str) -> list[dict[str, Any]]:
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
    for leg, name in zip(legs, leg_names(state, [(x["facility_id"], x["amount_fen"]) for x in legs]), strict=True):
        leg["name_display"] = name
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


_FROM = re.compile(r".* from (.+)$")


def _label_short(kind: str, label: str, lang: str, state: FinancialState | None = None) -> str:
    """A chart annotation's words: "Receipt from Foshan Home Retail Co.", "Payroll", "Invoice financing lands"; the
    full sentence stays in `label` for the table. Written here so the browser never truncates a sentence."""
    if kind in ("RECEIPT", "EARLY_RECEIPT"):
        m = _FROM.match(label)
        who = m.group(1) if m else ""
        return t(lang, f"Receipt from {who}" if who else "Receipt", f"来自{who}的收款" if who else "收款")
    if kind == "ADVANCE":
        return t(lang, "Invoice financing lands", "发票融资到账")
    if kind == "DRAW":
        return t(lang, "Credit line draw", "信用额度提款")
    if kind == "REPAYMENT":
        return t(lang, "Repayment", "还款")
    return in_language(label.split(" (")[0].split(", ")[0].strip(), lang, state) or ""


def _series(state: FinancialState, traj: Any, lang: str = "en", from_day: int = 0) -> list[dict[str, Any]]:
    """One projection as the chart's rows: the day, its closing cash (fen for the axis, the display string for the
    reader) and the events that moved it, with ids replaced by names and a short label for the chart. The rows start at
    `from_day` (today): the closed days before it carry the opening cash and are not a forecast (R02)."""
    rows = []
    for d in traj.days:
        if d.day < from_day:
            continue
        events = []
        for e in d.events:
            label = in_words(state, e.label)
            events.append({"kind": e.kind.value, "label": in_language(label, lang, state), "label_short": _label_short(e.kind.value, label, lang, state),
                           "amount_fen": e.amount_fen, "amount_display": fmt_yuan(e.amount_fen), "amount_short": fmt_short(e.amount_fen)})
        # The day's net movement: the sum of the engine's own postings for the day, so a page can label the day by its net and never
        # let one large outflow look like the cause of a rising line (the components stay in `events`).
        net = sum(e.amount_fen for e in d.events)
        rows.append({"day": d.day, "closing_fen": d.closing_fen, "closing_display": fmt_yuan(d.closing_fen), "events": events,
                     "net_fen": net, "net_display": fmt_yuan(net), "net_short": fmt_short(net)})
    return rows


_EXPECTED_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)


def forecast_basis(state: FinancialState, store: Any, traj: Any, action: dict[str, Any] | None, today: int, lang: str,
                   entries: Any = None) -> dict[str, Any]:
    """What the cash chart counts, in words and in two sums (audit section 16): the invoice payments the engine expects at their due
    dates and the funding already committed; overdue payments are not counted. `confirmed_receipts_fen` is the sum of the receipts in
    the log; `expected_receipts_fen` the sum of the receipts the projection already posted from today on. Both are sums of amounts
    that exist elsewhere; nothing is projected here. The assumed repayment day of the line is the plan's own (None without one)."""
    if entries is None:  # the request's log, when the decision context has already parsed it
        entries, _ = read_entries(store.operations())
    confirmed = sum(_receipt_fen(e.payload) for e in entries
                    if e.kind == "RECEIVE_PAYMENT" and e.result.status == OperationStatus.EXECUTED)
    expected = sum(ev.amount_fen for d in traj.days if d.day >= today for ev in d.events
                   if ev.kind in _EXPECTED_RECEIPTS and ev.amount_fen > 0)
    repay_days = [leg["cost_due_day"] for leg in (action or {}).get("legs") or []
                  if leg.get("operation_kind") == "DRAW_FACILITY" and isinstance(leg.get("cost_due_day"), int)]
    repay = max(repay_days) if repay_days else None
    base = t(lang, "Expected invoice payments at their due dates and committed funding; overdue payments are excluded",
             "按到期日预计的发票回款和已承诺的融资；已逾期未付的款项不计入")
    tail = (t(lang, f"; assumed line repayment {when_text(repay, today, lang)}.", f"；假定额度于{when_text(repay, today, lang)}还款。")
            if repay is not None else t(lang, ".", "。"))
    return {
        "forecast_basis_text": base + tail,
        "forecast_basis": {
            "scheduled_receipts_counted": True, "overdue_excluded": True,
            "confirmed_receipts_fen": confirmed, "confirmed_receipts_display": fmt_yuan(confirmed),
            "expected_receipts_fen": expected, "expected_receipts_display": fmt_yuan(expected),
            "assumed_repayment_day": repay,
            "assumed_repayment_when": when_text(repay, today, lang) if repay is not None else None,
        },
        "last_read_when": t(lang, "today", "今天"), "last_read_day": today,
    }


def _receipt_fen(payload: dict[str, Any]) -> int:
    amount = payload.get("amount_fen")
    return amount if isinstance(amount, int) else 0


def _after_words(after: Any, floor: int, today: int, horizon: int, lang: str) -> str:
    """The after-state of a plan from its own projection: the first day cash is below the reserve, if any."""
    first = next((d.day for d in after.days if d.day >= today and d.closing_fen < floor), None)
    if first is None:
        lowest = min((d.closing_fen for d in after.days if d.day >= today), default=None)
        if lowest is not None and lowest == floor:  # the plan's lowest point is exactly the reserve
            return t(lang, f"Cash stays at or above your minimum cash reserve for the next {horizon} days.",
                     f"未来 {horizon} 天现金都不低于您的最低现金储备。")
        return t(lang, f"Cash stays above your minimum cash reserve for the next {horizon} days.",
                 f"未来 {horizon} 天现金都保持在您的最低现金储备以上。")
    return t(lang, f"Cash stays above your minimum cash reserve for the next {max(first - 1 - today, 0)} days.",
             f"未来 {max(first - 1 - today, 0)} 天现金都保持在最低现金储备以上。")


def cure_after(state: FinancialState, obs: list[Any], mandate: Mandate, alert: Alert | None, today: int,
               lang: str) -> tuple[str | None, dict[str, Any] | None]:
    """The after-state of an alert's own cure, projected on the books like the home's next action: the sentence the home
    and the approval card both say (so one cure never says two horizons) and, when the cure keeps cash up but does not restore
    the reserve, the residual as data (`shortfall_display`, `from_when`, `restores_reserve` false). Both None when the alert has
    no committed cure to project."""
    if alert is None or alert.kind != AlertKind.RESERVE_BREACH_AHEAD:
        return None, None
    # A cure that restores the reserve is a committed one; one that only keeps cash above zero (`cure_restores_reserve` false)
    # is still the cure the alert suggests and the owner may approve.
    if not alert.committed_cure and alert.inputs.get("cure_restores_reserve") != "false":
        return None, None
    actions = _alert_actions(state, alert, today)
    if not actions:
        return None, None
    try:
        traj = project(state, obs, actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    except EngineError:
        return None, None
    floor = mandate.min_cash_fen
    if alert.inputs.get("cure_restores_reserve") != "false":
        return _after_words(traj, floor, today, mandate.horizon_days, lang), None
    # The cure does not restore the reserve: say what it does do, from its own projection (F12). The shortfall and the lowest
    # point are those of the first stretch below the reserve (the alert's own `residual_shortfall` is that episode's minimum).
    first = first_breach_ahead(traj, today, floor)
    if first is None:  # the cure's own projection stays above the reserve; the alert's flag is stale
        return _after_words(traj, floor, today, mandate.horizon_days, lang), None
    low_fen, low_day = _episode_low(traj, first[0], floor)
    from_when, low_when = _distance(first[0], today, lang), _distance(low_day, today, lang)
    gap = floor - low_fen
    now = alert.amount_fen if alert.day is not None and alert.day <= today else None  # today's gap: the alert's own first shortfall
    if _lowest_ahead(traj, today)[0] < 0:
        words = t(lang, f"Does not fully prevent negative cash: cash still falls to {fmt_short(_lowest_ahead(traj, today)[0])} "
                        f"{_distance(_lowest_ahead(traj, today)[1], today, lang)}, below your {fmt_short(floor)} minimum cash reserve.",
                  f"不能完全避免现金为负：现金仍将在{_distance(_lowest_ahead(traj, today)[1], today, lang)}降至 "
                  f"{fmt_short(_lowest_ahead(traj, today)[0])}，低于 {fmt_short(floor)} 的最低现金储备。")
    else:
        words = lowest_point_words(gap, low_day, now, today, lang)
    return words, {"shortfall_display": fmt_yuan(gap), "from_when": from_when, "restores_reserve": False, "lowest_when": low_when,
                   "shortfall_today_display": fmt_yuan(now) if now is not None else None, "text": words}


def _episode_low(traj: Any, first_day: int, floor: int) -> tuple[int, int]:
    """(closing cash, day) of the lowest point of the stretch below the reserve that starts on `first_day`."""
    episode = []
    for d in traj.days:
        if d.day >= first_day:
            if d.closing_fen >= floor:
                break
            episode.append(d)
    low = min(episode, key=lambda d: (d.closing_fen, d.day))
    return low.closing_fen, low.day


def after_facts(state: FinancialState, obs: list[Any], mandate: Mandate, actions: list[FundingAction],
                today: int) -> tuple[bool | None, int | None, int | None]:
    """The after-state of the legs that run, as numbers for the decision record's quote: whether cash stays at or above the
    reserve through the horizon and, if not, the first day it is below it. The same projection `next_action` and `cure_after`
    say in words, and the day cash is lowest in that stretch; (None, None, None) when the legs cannot be projected."""
    if not actions:
        return None, None, None
    try:
        traj = project(state, obs, actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    except EngineError:
        return None, None, None
    first = first_breach_ahead(traj, today, mandate.min_cash_fen)
    if first is None:
        return True, None, None
    return False, first[0], _episode_low(traj, first[0], mandate.min_cash_fen)[1]


def next_action(state: FinancialState, obs: list[Any], mandate: Mandate, found: list[Alert], approvals: list[Any],
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

    rec = recommend_for_alert(alert, state, obs, mandate, enabled=use_router)

    if rec.source == "router" and rec.plan is not None:
        p = rec.plan
        legs = plan_legs(state, p, today, lang)
        needs_owner = p.needs_owner_approval
        needs_owner_reason = engine_sentence(state, p.approval_reason, today, lang) if needs_owner else None
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
            saving = (t(lang, f" (including {fmt_yuan(-offset)} less in other interest and fees across the forecast)",
                        f"（含预测期内其他利息与费用少付的 {fmt_yuan(-offset)}）") if offset < 0 else "")
            cheaper = {"label": t(lang, " and ".join(words), "，".join(words)), "cost_total_display": fmt_yuan(c.total_cost_fen),
                       "approvals": n, "legs": [f"{x['label']}: {x['display']}" for x in _plan_lines(state, c, lang)]}
            why = t(lang, f"The cheapest option, {fmt_yuan(c.total_cost_fen)} in all{saving}, needs {n} separate approvals; "
                          f"this one needs one. Both are under your funding options.",
                    f"最便宜的方案合计 {fmt_yuan(c.total_cost_fen)}{saving}，但需要 {n} 次单独批准；此方案只需一次。两者都在“您的融资方案”中。")
        elif alert.kind == AlertKind.RESERVE_BREACH_AHEAD and alert.inputs.get("cure_restores_reserve") == "false":
            why = t(lang, "No committed funding restores the reserve; this is the cheapest way to stay above zero.",
                    "没有已承诺的融资能恢复安全线；这是保持在零以上最便宜的方式。")
        elif alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
            why = t(lang, "A committed funding that covers the whole gap in time.", "能及时覆盖整个缺口的已承诺融资。")
        else:
            why = engine_sentence(state, alert.detail, today, lang)

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
        components.append({"amount_fen": leg["amount_fen"] or 0, "amount_short": fmt_short(leg["amount_fen"] or 0),
                           "what": what, "lands_when": leg.get("lands_when"),
                           "name_display": leg["name_display"], "cost_display": leg["cost_display"]})
    repay = sum(leg["amount_fen"] or 0 for leg in legs if leg["operation_kind"] == "REPAY_FACILITY")
    if alert.kind == AlertKind.RESERVE_BREACH_AHEAD and receive:
        outcome_title = t(lang, f"Secure {receive_short} of funding", f"筹措 {receive_short} 资金")
    elif alert.kind == AlertKind.FACILITY_REPAYABLE and repay:
        outcome_title = t(lang, f"Repay {fmt_short(repay)} of the credit line", f"偿还信用额度 {fmt_short(repay)}")
    else:
        outcome_title = title
    plan_series: list[dict[str, Any]] | None = None
    after_traj = None
    after_lowest = None
    if actions:
        try:
            after_traj = project(state, obs, actions, Mode.CONSERVATIVE, horizon, floor)
            plan_series = _series(state, after_traj, from_day=today)
            after_lowest = min((d.closing_fen for d in after_traj.days if d.day >= today), default=None)
        except EngineError:
            after_traj = None

    if alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
        short = fmt_yuan(alert.amount_fen or 0)
        if alert.inputs.get("cure_restores_reserve") == "false":
            zero_when = when_text(int(alert.inputs.get("zero_day", today)), today, lang)
            if_nothing = t(lang, f"Cash goes below zero {zero_when}.", f"现金将在{zero_when}跌破零。")
            # the card's `protects` says the same sentence, from the same function (`cure_after`)
            after = cure_after(state, obs, mandate, alert, today, lang)[0] or t(
                lang, f"Cash stays at or above zero, but your minimum cash reserve is still "
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

    result: dict[str, Any] = {
        "alert_id": alert.id,
        "kind": alert.kind.value,
        "plan_source": rec.source,
        # The row of the comparison (POST /router/plan) that is this plan. The router's cheapest plan is "router_optimum"
        # (the comparison names the exact row in its own `recommended_key`); the alert's cure is a row the comparison adds.
        "recommended_key": (None if alert.kind != AlertKind.RESERVE_BREACH_AHEAD else
                            "router_optimum" if rec.source == "router" and rec.plan is not None else RECOMMENDED_PLAN_KEY),
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
        "detail": engine_sentence(state, alert.detail, today, lang, fallback=rec.source == "router"),
        "formula": alert.formula,
        "pending_approval_id": queued.id if queued is not None else None,
        "state_version": state_version,
        "suggestions": suggestions,
        "plan_series": plan_series,
        "plan_traj": after_traj,
    }
    # the plan-run confirmation: the plan's own words in the commitment receipt's order (nothing is computed for it)
    result["receipt"] = plan_receipt(lang, action=result, restores_reserve=not (
        alert.kind == AlertKind.RESERVE_BREACH_AHEAD and alert.inputs.get("cure_restores_reserve") == "false"))
    return result

def _approvals(state: FinancialState, obs: list[Any], mandate: Mandate, approvals: list[Any], found: list[Alert],
               today: int, lang: str, *, use_router: bool = True, commitments: list[Any] | None = None) -> list[dict[str, Any]]:
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
        after, residual = cure_after(state, obs, mandate, alert, today, lang)
        terms = agreement_terms(state, find_agreement(op, commitments or []), today, lang,
                                 horizon_days=mandate.forward_concession_horizon_days) if a.kind in COMMERCIAL_KINDS else None
        words = approval_words(state, op, a.kind, today, alert, lang, plan_costs, after=after, agreement=terms)
        words["residual"] = residual
        words["execution_status"] = "PENDING"
        amount = op.get("amount_fen", op.get("advance_fen"))
        out.append({"id": a.id, "kind": a.kind, "reason": approval_reason_words(state, a.reason, today, lang), "created_day": op.get("day"),
                    "amount_fen": amount if isinstance(amount, int) else None,
                    "amount_display": (fmt_yuan(amount) if isinstance(amount, int) else None), **words})
    return out


def _new_reconciled(store: Any) -> Reconciled:
    """One request's reconciliation, once. It asks this module's `reconcile` at the moment it is needed (never a copy taken at import)."""
    return Reconciled(store, lambda st, day: reconcile(st, day=day))


class Partial:
    """The supporting reads that failed while the home was built (F21). The home never fails for one: the conclusion and the plan stand, and
    `partial` names what could not be read so the page can say "Some supporting facts could not be read: ..." beside them."""

    LABELS: ClassVar[dict[str, tuple[str, str]]] = {"decision_record": ("the record of your decisions", "您的决策记录"),
              "reconciliation": ("the check of receipts against promises", "收款与约定的核对"),
              "summary": ("the summary of what needs you", "待办事项摘要"),
              "receipt_basis": ("what each receipt rests on", "每笔收款的依据"),
              "home_v2": ("the Home V2 summary", "新版首页摘要"),
              "offer_picture": ("the cash picture of an open offer", "未决报价的现金图景"),
              "customer_shares": ("each customer's share of what you are owed", "各客户占您应收款的比例")}

    def __init__(self) -> None:
        self.missing: list[str] = []

    def add(self, name: str) -> None:
        if name not in self.missing:
            self.missing.append(name)

    def view(self, lang: str) -> dict[str, Any] | None:
        if not self.missing:
            return None
        names = [t(lang, self.LABELS[m][0], self.LABELS[m][1]) for m in self.missing]
        return {"missing": list(self.missing), "missing_text": names,
                "text": t(lang, f"Some supporting facts could not be read: {', '.join(names)}.",
                          f"部分辅助信息未能读取：{'、'.join(names)}。")}


class _Reconciliation:
    """The reconciliation of the log against the books, read once and only when a sentence needs it: the early-payment
    promises (`report`) and which of their windows are still open (`live`). When it cannot be read the promises read as none and the
    home says so (`Partial`)."""

    def __init__(self, state: FinancialState, store: Any, today: int, partial: Partial | None = None,
                 reconciled: Reconciled | None = None) -> None:
        self._state, self._store, self._today = state, store, today
        self._partial = partial
        self._reconciled = reconciled if reconciled is not None else _new_reconciled(store)
        self._report: Any = None
        self._live: frozenset[tuple[str, str]] | None = None

    @property
    def report(self) -> Any:
        if self._report is None:
            try:
                self._report = self._reconciled.report(self._today)
            except Exception:
                logging.getLogger("termsledger.decisions").exception("the reconciliation could not be read for the home")
                if self._partial is not None:
                    self._partial.add("reconciliation")
                self._report = SimpleNamespace(promised=[], receipts=[])
        return self._report

    def window_live(self, receivable_id: str | None) -> bool:
        if self._live is None:
            self._live = live_windows(self.report, self._store.commitments(), self._state)
        return window_is_live(self._live, receivable_id)


def _part_arrived(state: FinancialState, report: Any, commitment_id: str, obligation_id: str | None, today: int, lang: str) -> dict[str, Any] | None:
    """The change row for an early-payment promise that was kept in part: four facts (what arrived and when, what it cleared,
    what remains and whether it is overdue, whether the early-payment window has ended) from the reconciliation's own rows.
    Several payments under one promise read as "Received 2 payments totalling ¥X (the last …)". None when nothing arrived
    under the promise, so the alert's "did not arrive" stands. Nothing is computed here."""
    row = next((p for p in report.promised if p.commitment_id == commitment_id and (obligation_id is None or p.obligation_id == obligation_id)
                and p.receipt_seq is not None and p.status.value == "RECEIVED"), None)
    if row is None:
        return None
    paid = sorted((r for r in report.receipts if r.commitment_id == commitment_id and r.receivable_id == row.receivable_id
                   and r.agreed_discount_fen > 0), key=lambda r: r.seq)
    last = paid[-1] if paid else next((r for r in report.receipts if r.seq == row.receipt_seq), None)
    buyer = party_name(state, row.counterparty_id)
    left = next((o for o in report.outstanding if o.receivable_id == row.receivable_id), None)
    ended = row.promised_day is None or row.promised_day < today
    received, cleared, discount = fmt_yuan(row.expected_fen), fmt_yuan(row.face_fen), fmt_yuan(row.discount_fen)
    when = when_text(last.day, today, lang) if last is not None and last.day is not None else ""
    remains = ""
    if left is not None:
        remains = (t(lang, f"; {fmt_yuan(left.face_fen)} remains and is overdue", f"；还有 {fmt_yuan(left.face_fen)} 未收，且已逾期") if left.past_due
                   else t(lang, f"; {fmt_yuan(left.face_fen)} remains, due {when_text(left.due_day, today, lang)}",
                          f"；还有 {fmt_yuan(left.face_fen)} 未收，{when_text(left.due_day, today, lang)}到期"))
    window = (t(lang, "; the early-payment window has ended", "；提前付款期限已结束") if ended
              else t(lang, "; the early-payment window is still open", "；提前付款期限仍未结束"))
    if len(paid) > 1:
        head = t(lang, f"Received {len(paid)} payments totalling {received} from {buyer}{f' (the last {when})' if when else ''}: together they",
                 f"{when}最后一笔，共收到{buyer}的 {len(paid)} 笔付款，合计 {received}：它们共")
    else:
        head = t(lang, f"Received {received} from {buyer}{f' {when}' if when else ''}: it",
                 f"{when}已收到{buyer}的 {received}：")
    text = t(lang, f"{head} cleared {cleared} of the invoice, including a {discount} early-payment discount{remains}{window}.",
             f"{head}抵清了发票的 {cleared}，其中含 {discount} 提前付款折扣{remains}{window}。")
    return {"event_text": text, "received_display": received, "face_cleared_display": cleared, "discount_display": discount,
            "remaining_display": fmt_yuan(left.face_fen) if left is not None else None,
            "window_state": "ended" if ended else "open"}


def _warning_words(state: FinancialState, a: Alert, recon: _Reconciliation, today: int, lang: str,
                   agreements: dict[str, str]) -> dict[str, str | None]:
    """A warning's title and detail in the owner's words. The early-payment alert says the promised payment "did not arrive";
    when part of it did, the title says it was only partly paid and the detail gives the same four facts as the change row."""
    title = business_text(state, a.title, today, lang, agreements) or ""
    detail = business_text(state, a.detail, today, lang, agreements) or ""
    cid = a.inputs.get("commitment_id")
    if cid and a.kind == AlertKind.RECEIVABLE_PAST_DUE and "did not arrive" in title:
        part = _part_arrived(state, recon.report, cid, a.inputs.get("obligation_id"), today, lang)
        if part is not None:
            title = title.removesuffix(" did not arrive") + " was only partly paid"
            raw_rest = a.detail.split(". ", 1)[1] if ". " in a.detail else ""  # the alert's sentences after "did not arrive."
            rest = business_text(state, raw_rest, today, lang, agreements) or ""
            detail = part["event_text"] + (f" {rest[:1].upper()}{rest[1:]}" if rest else "")
    return {"title": title, "detail": detail}


def _row_ids(row_id: str, *, receivable_id: Any = None, commitment_id: Any = None, decision_id: str | None = None) -> dict[str, Any]:
    """The ids a change row carries so the web needs no reading of its sentences: its own `id`, and the invoice, the agreement and the
    decision it is about (null where none applies). `superseded_by` is set later, by `_mark_superseded`."""
    return {"id": row_id, "receivable_id": receivable_id if isinstance(receivable_id, str) else None,
            "commitment_id": commitment_id if isinstance(commitment_id, str) else None, "decision_id": decision_id,
            "superseded_by": None}


def _mark_superseded(items: list[dict[str, Any]]) -> None:
    """A LATE row that repeats an invoice a part-paid row already tells better says so: `superseded_by` is the `id` of that row, so the web
    drops it without logic of its own. The part-paid row is the LATE row that carries the four facts (`window_state`: what arrived, what it
    cleared, what remains, whether the early-payment window has ended). Only a row that is on the list can supersede, so dropping the
    other never loses the invoice from the page; a no-receipt invoice has no such row and nothing is marked."""
    told = {r["receivable_id"]: r["id"] for r in items
            if r["kind"] == "LATE" and r.get("window_state") and r.get("receivable_id")}
    for r in items:
        if r["kind"] == "LATE" and not r.get("window_state") and r.get("receivable_id") in told:
            r["superseded_by"] = told[r["receivable_id"]]


def _changes(state: FinancialState, store: Any, found: list[Alert], today: int, lang: str,
             since_day: int | None = None, causality: Causality | None = None, partial: Partial | None = None,
             reconciled: Reconciled | None = None, entries: Any = None) -> list[dict[str, Any]]:
    """Since the owner's last visit when the web says when that was (`since_day`), else the last week of the clock. With a `Causality`
    each row also says `what_changed`, `why_it_matters` (the forecast as of now, not a replay) and `what_remains` (the decision record's)."""
    since = since_day if since_day is not None else today - RECENT_DAYS
    items: list[dict[str, Any]] = []
    commitments = store.commitments()
    agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
    recon = _Reconciliation(state, store, today, partial, reconciled)
    if entries is None:  # the request's log, parsed once by the decision context when it has one
        entries, _ = read_entries(store.operations())
    # An approval the owner has answered: its "waiting" entry is history, and when the decision itself is in the window the
    # decision is the news (one operation never reads "You approved" and "Waiting for your approval" together).
    decided_ids = {a.id for a in store.approvals() if str(getattr(a.status, "value", a.status)) != "PENDING"}
    answered = {e.result.approval_id for e in entries
                if e.result.approval_id and e.result.status != OperationStatus.PENDING_APPROVAL and e.day is not None and e.day >= since}
    for e in entries:
        day = e.day
        if day is None or day < since:
            continue
        if e.result.status == OperationStatus.DUPLICATE or "CLOCK" in e.kind.upper():
            continue  # a clock step is not news; what it posted shows as receipts, landings and alerts
        if e.result.status == OperationStatus.PENDING_APPROVAL and e.result.approval_id in decided_ids and e.result.approval_id in answered:
            continue
        if e.kind in (CONFIRM_DOCUMENT_KIND, REJECT_DOCUMENT_KIND):
            continue  # the owner's decision on a contract the agent read changes no books; Activity and Deals show it
        who = (getattr(e.op, "requested_by", None) or "") if e.op is not None else ""
        who = str(getattr(who, "value", who))
        kind = "REFUSED" if e.result.status == OperationStatus.REFUSED else (
            "WAITING" if e.result.status == OperationStatus.PENDING_APPROVAL else
            ("RECEIPT" if e.kind == "RECEIVE_PAYMENT" else "OPERATION"))
        text = e.result.message or e.kind.replace("_", " ").lower()
        cmt = None
        if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and e.result.status == OperationStatus.EXECUTED:
            cmt = next((c for c in commitments if c.id in (e.result.message or "")), None)
            if cmt is not None:
                text = agreement_words(state, cmt.counterparty_id, cmt.forward_value_fen, lang)
                kind = "AGREEMENT"
        live = e.kind == "RECEIVE_PAYMENT" and recon.window_live((e.payload or {}).get("receivable_id"))
        shown = business_text(state, text, today, lang, agreements, live) or text
        words = (event_words(state, kind=e.kind, status=e.result.status.value, payload=e.payload, message=e.result.message,
                             approval_id=e.result.approval_id, day=day, today=today, lang=lang,
                             decided=e.result.approval_id in decided_ids, agreements=agreements, window_live=live)
                 if kind != "AGREEMENT" else {"event_text": None, "event_detail": None})
        did = decision_id_for(e.payload, e.idempotency_key, commitments, approval_id=e.result.approval_id)
        item: dict[str, Any] = {"day": day, "seq": e.seq, "kind": kind, "actor": who, "text": shown,
                "event_text": words["event_text"] or shown, "event_detail": words["event_detail"],
                "when": when_text(day, today, lang),
                **_row_ids(f"op:{e.seq}", receivable_id=(e.payload or {}).get("receivable_id"),
                           commitment_id=cmt.id if kind == "AGREEMENT" and cmt is not None else (e.payload or {}).get("commitment_id"),
                           decision_id=did)}
        if causality is not None:
            item.update(causality.fields(status=e.result.status.value, event_text=item["event_text"], decision_id=did,
                                         decided=e.result.approval_id in decided_ids))
        items.append(item)
    for a in found:
        if a.kind == AlertKind.RECEIVABLE_PAST_DUE:
            late = business_text(state, a.detail.split(". ")[0] + ".", today, lang, agreements) or ""
            promised = next((c for c in commitments if c.id == a.commitment_id), None) if a.commitment_id else None
            row: dict[str, Any] = {"day": a.day, "seq": None, "kind": "LATE", "actor": "", "text": late,
                                   "event_text": late, "event_detail": None, "when": when_text(a.day, today, lang),
                                   **_row_ids(f"alert:{a.id}", receivable_id=a.receivable_id, commitment_id=a.commitment_id,
                                              decision_id=deal_id(promised.offer_id) if promised is not None else None)}
            cid, oid = a.inputs.get("commitment_id"), a.inputs.get("obligation_id")
            if cid and "did not arrive" in a.detail.split(". ")[0]:  # the alert's own sentence, so the Chinese home reads it too
                part = _part_arrived(state, recon.report, cid, oid, today, lang)
                if part is not None:  # the promise was part kept: say what arrived, never "did not arrive" (F25)
                    row.update(part)
                    row["text"] = row["event_text"] = part["event_text"]
            items.append(row)
    for lot in ensure_lots(state).lots:
        if lot.settled and since <= lot.arrival_day <= today and lot.arrival_day != lot.request_day:
            landed = t(lang, f"{fmt_yuan(lot.principal_fen)} from {facility_name(state, lot.facility_id)} landed {when_text(lot.arrival_day, today, lang)}.",
                       f"来自{facility_name(state, lot.facility_id)}的 {fmt_yuan(lot.principal_fen)} 已于{when_text(lot.arrival_day, today, lang)}到账。")
            items.append({"day": lot.arrival_day, "seq": None, "kind": "LANDED", "actor": "",
                          "when": when_text(lot.arrival_day, today, lang), "text": landed,
                          "event_text": landed, "event_detail": None, **_row_ids(f"lot:{lot.id}")})
    items.sort(key=lambda x: (-(x["day"] or 0), -(x["seq"] or 0)))
    items = items[:MAX_CHANGES]
    _mark_superseded(items)
    if causality is not None:
        for item in items:
            if "what_changed" not in item:  # a late payment or a landing: the forecast now is its consequence
                item.update(causality.fields(status="EXECUTED", event_text=item["event_text"], decision_id=None))
    mark_changed(items)
    return items


def _picture_days(traj: Any, today: int, floor: int, breach_day: int | None, low_day: int, action: dict[str, Any] | None,
                  horizon_days: int) -> int:
    """How many days from today the cash picture should show: 30, or four days past the last of the first breach, the lowest point, the day
    the do-nothing line is back at or above the reserve and the plan's last landing day, whichever is later; never past 60 or the
    horizon. Days only: nothing is computed that the projection and the plan do not already hold."""
    marks = [low_day]
    if breach_day is not None:
        marks.append(breach_day)
        back = next((d.day for d in traj.days if d.day > breach_day and d.closing_fen >= floor), None)
        if back is not None:
            marks.append(back)
    marks += [leg["lands_day"] for leg in (action or {}).get("legs") or [] if isinstance(leg.get("lands_day"), int)]
    return max(1, min(60, horizon_days, max(30, max(m - today for m in marks) + 4)))


def _receivables_headline(past_due: list[dict[str, Any]], nxt: dict[str, Any] | None, today: int, lang: str,
                          no_plan: bool, open_count: int) -> dict[str, Any]:
    """The one sentence the receivables card leads with, from the block's own rows, and its tone: the lead late invoice (the longest
    overdue, then the largest), else the next one due, else nothing owed. `headline_note` is the quiet caveat when what collecting each
    invoice saves cannot be priced (no committed plan covers the shortfall), in the words the receivables-worth read writes."""
    from app.strategy.collections import NO_PLAN_NOTE

    if past_due:
        lead = min(past_due, key=lambda r: (-r["days_late"], -r["face_fen"], r["receivable_id"]))
        n = lead["days_late"]
        text = t(lang, f"{lead['face_display']} from {lead['buyer_name']} is {n} {'day' if n == 1 else 'days'} late.",
                 f"来自{lead['buyer_name']}的 {lead['face_display']} 已逾期 {n} 天。")
        tone = "bad"
    elif nxt is not None:
        text = t(lang, f"Nobody is late. Next: {nxt['face_display']} from {nxt['buyer_name']}, due {nxt['due_when']}.",
                 f"没有逾期。下一笔：来自{nxt['buyer_name']}的 {nxt['face_display']}，{nxt['due_when']}到期。")
        tone = "warn" if nxt["due_day"] <= today else "ok"
    else:
        text, tone = t(lang, "Nothing is owed to you right now.", "目前没有应收款。"), "ok"
    return {"headline": text, "headline_tone": tone, "headline_note": t(lang, *NO_PLAN_NOTE) if no_plan and open_count else None}


def _receivables(state: FinancialState, store: Any, today: int, lang: str, partial: Partial | None = None,
                 reconciled: Reconciled | None = None, no_plan: bool = False) -> dict[str, Any]:
    try:
        report = (reconciled if reconciled is not None else _new_reconciled(store)).report(today)
    except Exception:  # the block is a supporting read: it reads as unknown, never as "nothing owed", and the home says so
        logging.getLogger("termsledger.decisions").exception("the reconciliation could not be read for the receivables")
        if partial is not None:
            partial.add("reconciliation")
        return {"open_count": 0, "open_total_fen": None, "open_total_display": None, "overdue_total_fen": None,
                "overdue_total_display": None, "past_due": [], "next_receipt": None,
                "promised": None, "lapsed_promises": 0,
                "headline": t(lang, "Receivables could not be read just now.", "暂时无法读取应收款。"), "headline_tone": "warn",
                "headline_note": None}
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
    return {"open_count": len(rows), "open_total_fen": total, "open_total_display": fmt_yuan(total),
            "overdue_total_fen": overdue, "overdue_total_display": fmt_yuan(overdue), "past_due": past_due,
            "next_receipt": nxt, "promised": promise, "lapsed_promises": report.lapsed_promises,
            **_receivables_headline(past_due, nxt, today, lang, no_plan, len(rows))}


def _financing_fields(lot: FundingLot, today: int, lang: str) -> dict[str, str]:
    """The lot's financing state in the one vocabulary (ARRANGED / RECEIVED / REPAID, `app.api.financing_words`)."""
    words = financing_state_words(lang, lot, today)
    return {"financing_state": words["state"], "financing_state_text": words["text"]}


def _in_transit(state: FinancialState, today: int, lang: str) -> dict[str, Any] | None:
    lots = [lot for lot in ensure_lots(state).lots if not lot.settled]
    if not lots:
        return None
    total = sum(lot.remaining_fen for lot in lots)
    return {"total_display": fmt_yuan(total), "lots": [
        {"facility_name": facility_name(state, lot.facility_id), "amount_display": fmt_yuan(lot.remaining_fen),
         "arrival_day": lot.arrival_day, "arrival_when": when_text(lot.arrival_day, today, lang),
         **_financing_fields(lot, today, lang),
         "headline": t(lang, f"{fmt_short(lot.remaining_fen)} funding arriving {when_text(lot.arrival_day, today, lang)}",
                       f"{fmt_short(lot.remaining_fen)} 资金将于{when_text(lot.arrival_day, today, lang)}到账")}
        for lot in sorted(lots, key=lambda lt: (lt.arrival_day, lt.id))]}


def _context(rt: Any, partial: Partial | None = None, found: list[Alert] | None = None,
             reconciled: Reconciled | None = None) -> Any:
    """The decision record's context, read once for the home (None when it cannot be read: the home never goes down for it). It is given
    the alerts and the reconciliation the home already holds, so neither runs a second time."""
    try:
        return load_context(rt, found=found, reconciled=reconciled)
    except Exception:
        logging.getLogger("termsledger.decisions").exception("the decision record could not be read for the home")
        if partial is not None:
            partial.add("decision_record")
        return None


def _decision_record(rt: Any, lang: str, ctx: Any = None, partial: Partial | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The decision record's two reads for the home: up to three open decisions (newest first) and, when a cure left the reserve
    at risk, what is left to decide (F17). A failure here never takes the home down: it reads as nothing open."""
    try:
        ctx = ctx if ctx is not None else load_context(rt)
        ranked = sorted(ctx.states().values(), key=lambda p: (p[0].updated_day if p[0].updated_day is not None else -1, p[0].updated_seq),
                        reverse=True)
        rows: list[dict[str, Any]] = []
        for ds, inp in ranked:
            if ds.terminal or (ds.family == "DEAL" and ds.offer is None and ds.commitment is None):
                continue
            try:
                rows.append(decision_summary(ctx, ds, inp, lang))
            except Exception:
                logging.getLogger("termsledger.decisions").exception("decision %s could not be summarised", ds.decision_id)
                continue
            if len(rows) == 3:
                break
        remaining = None
        for ds, inp in ranked:
            if ds.residual is not None:
                view = remaining_task_view(ctx, ds, inp, lang)
                if view["code"] == "OWNER_DECISION":
                    remaining = {"text": view["text"], "links": remaining_links(ctx, ds, lang), "decision_id": ds.decision_id}
                break
        return rows, remaining
    except Exception:
        logging.getLogger("termsledger.decisions").exception("the decision record could not be read for the home")
        if partial is not None:
            partial.add("decision_record")
        return [], None


@router.get("/home")
def get_home(lang: str = "en", since_day: int | None = None, decision: str | None = Query(None, max_length=120),
             scenario: str | None = Query(None, max_length=20)) -> dict[str, Any]:
    return read_home(lang, since_day, decision=decision, scenario=scenario)


def read_home(lang: str = "en", since_day: int | None = None, *, v2: bool = True, decision: str | None = None,
              scenario: str | None = None) -> dict[str, Any]:
    """The Home read. `v2=False` leaves out the Home V2 fields (the Home carries them always): a caller that reads only the company's status,
    plan and approvals (the worklist) neither pays for them nor depends on them. `decision` (a deal decision id) and `scenario` ("late",
    else expected) say which deal and payment timing the Home V2 chart is titled for (`home_v2.chart.scenario_title_text`); no figure moves."""
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
        if since_day is not None and since_day > today:  # a marker from before a reset: the last week instead
            since_day = None
        low_fen, low_day = _lowest_ahead(traj, today)
        funding_counted = any(e.kind in (LedgerEventKind.DRAW, LedgerEventKind.ADVANCE) and e.amount_fen > 0
                              for d in traj.days if d.day >= today for e in d.events)
        words = _headline(found, mandate, traj, mandate.horizon_days, today, lang, (low_fen, low_day), funding_counted, books.state)
        headline, note = words["headline"], words["note"]
        # The first breach is the first day from today on (never the projection's day 0 fill, F01).
        ahead = first_breach_ahead(traj, today, mandate.min_cash_fen)
        breach_day, at_breach = ahead if ahead is not None else (None, None)
        drivers = _drivers(books.state, traj, today, breach_day, lang, low_day)
        action = next_action(books.state, books.with_([]), mandate, found, approvals, today, state.state_version, lang,
                              use_router=rt.settings.features.debt_desk)
        plan_series = action.pop("plan_series") if action is not None else None
        plan_traj = action.pop("plan_traj") if action is not None else None
        if action is not None and action["kind"] == "RESERVE_BREACH_AHEAD" and words["plan_note"] is not None:
            # The readiness note follows the plan actually shown (router plan or cure), never the alert's own flag
            words["plan_note"] = (t(lang, "A funding plan is ready. It needs your approval because of its cost.",
                                    "融资方案已准备好，因其成本需要您批准。") if action["needs_owner"]
                                  else t(lang, "A funding plan is ready, within your signed limits. No approval is needed.",
                                         "融资方案已准备好，在您签署的授权内，无需批准。"))
        series = _series(books.state, traj, lang, today)
        point_words(series, today, lang)
        point_words(plan_series, today, lang)
        picture_days = _picture_days(traj, today, mandate.min_cash_fen, breach_day, low_day, action, mandate.horizon_days)
        # One reconciliation, one set of alerts and one parse of the log for the whole request: the decision record is read first and the
        # rest of the home reuses what it holds.
        partial = Partial()
        reconciled = _new_reconciled(rt.store)
        record = _context(rt, partial, found, reconciled)
        basis = forecast_basis(books.state, rt.store, traj, action, today, lang, record.entries if record is not None else None)
        receipt_reader: BasisReader | None = None
        try:  # what each receipt rests on is a supporting read: the series stand without it, and the home says so
            entries = record.entries if record is not None else read_entries(rt.store.operations())[0]
            receipt_reader = BasisReader(books, today, lang, agreement_days(entries, rt.store.commitments()))
            annotate(series, traj, receipt_reader)
            annotate(plan_series, plan_traj, receipt_reader)
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the basis of the receipts could not be read for the home")
            partial.add("receipt_basis")
            receipt_reader = None
        queue = _approvals(books.state, books.with_([]), mandate, approvals, found, today, lang,
                           use_router=rt.settings.features.debt_desk, commitments=rt.store.commitments())
        causality = Causality(record, forecast_of(traj, today, mandate.min_cash_fen), today, lang)
        changes = _changes(books.state, rt.store, found, today, lang, since_day, causality, partial, reconciled,
                           record.entries if record is not None else None)
        breach_alert = _breach(found)  # no committed plan covers the shortfall: the router found none to price a receipt against
        receivables = _receivables(books.state, rt.store, today, lang, partial, reconciled,
                                   no_plan=breach_alert is not None and not breach_alert.committed_cure)
        in_transit = _in_transit(books.state, today, lang)
        funding_lots = _funding_lots(books.state, today, lang)
        agreements = {c.id: party_name(state, c.counterparty_id) for c in rt.store.commitments()}
        recon = _Reconciliation(books.state, rt.store, today, partial, reconciled)
        warnings = [{"id": a.id, "kind": a.kind.value, **_warning_words(state, a, recon, today, lang, agreements), "day": a.day,
                     "when": when_text(a.day, today, lang)} for a in found if a.severity == Severity.WARNING]
        open_decisions, remaining = _decision_record(rt, lang, record, partial)
        facilities = [{"id": f.id, "name": f.name, "status": f.status.value, "limit_display": fmt_yuan(f.limit_fen), "limit_fen": f.limit_fen,
                       "drawn_fen": f.drawn_fen, "drawn_display": fmt_yuan(f.drawn_fen),
                       "available_display": fmt_yuan(max(f.limit_fen - f.drawn_fen, 0) if f.owner_approved else 0),
                       "lead_time_days": f.lead_time_days}
                      for f in state.facilities if f.status.value == "COMMITTED" and f.limit_fen > 0]
        # imported here, after this module is loaded: the hybrid reads this module's own helpers
        from app.api import home_hybrid

        status_text = _status_text(status, found, lang)
        try:  # the hybrid is a supporting read: the conclusion and the plan stand without it, and the home says so
            hybrid: dict[str, Any] = home_hybrid.build(home_hybrid.HomeRead(
                rt=rt, books=books, mandate=mandate, today=today, lang=lang, traj=traj, plan_traj=plan_traj, plan_series=plan_series,
                action=action, status=status, status_text=status_text, headline=headline or "", note=note or "",
                low=(low_fen, low_day), breach_day=breach_day, picture_days=picture_days, queue=queue, receivables=receivables,
                changes=changes, record=record, open_decisions=open_decisions, basis=receipt_reader, partial=partial,
                decision=decision, scenario=scenario), v2=v2)
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the home summary could not be built")
            partial.add("summary")
            hybrid = {"cash": {}, "attention": None, "funding_line": None, "deals_card": None, "receivables_card": None,
                      "changes_card": None}
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
        "status_text": status_text,
        "headline": headline,
        "note": note,
        "worst": words["worst"],
        "plan_note": words["plan_note"],
        "since_day": since_day,
        "cash": {
            "cash_fen": state.cash_fen,
            "floor_fen": mandate.min_cash_fen,
            "lowest_fen": low_fen,
            "lowest_day": low_day,
            # The lowest point's tone, said by the server: "bad" below zero, "warn" below the minimum cash reserve, else "ok".
            "lowest_tone": "bad" if low_fen < 0 else "warn" if low_fen < mandate.min_cash_fen else "ok",
            # Headroom: cash minus the minimum cash reserve, today and at the lowest point ahead (the owner reads the
            # distance to the reserve, not the subtraction).
            "headroom_fen": state.cash_fen - mandate.min_cash_fen,
            "headroom_short": fmt_short(state.cash_fen - mandate.min_cash_fen),
            "lowest_headroom_fen": low_fen - mandate.min_cash_fen,
            "lowest_headroom_short": fmt_short(low_fen - mandate.min_cash_fen),
            "first_breach_day": breach_day,
            "below_reserve_today": breach_day == today,
            "first_breach_cash_fen": at_breach,
            "first_breach_cash_short": fmt_short(at_breach) if at_breach is not None else None,
            "cash_short": fmt_short(state.cash_fen),
            "floor_short": fmt_short(mandate.min_cash_fen),
            "lowest_short": fmt_short(low_fen),
            "drivers": drivers,
            "lowest_when": when_text(low_day, today, lang),
            "first_breach_when": when_text(breach_day, today, lang) if breach_day is not None else None,
            "horizon_days": mandate.horizon_days,
            "in_transit": in_transit,
            "funding_lots": funding_lots,
            "dscr_text": dscr_text,
            "leverage_text": leverage_text,
            "min_dscr_bp": mandate.min_dscr_bp,
            "max_leverage_bp": mandate.max_leverage_bp,
            # One projection for every figure and the chart: the baseline ("if you do nothing") and the same books with
            # the recommended plan applied ("with the recommended plan"). The browser draws these and computes nothing.
            "series": series,
            "plan_series": plan_series,
            # the money axis of the days the picture shows (`picture_days`), and of each view the Cash page switches between
            "axis": series_axis([series, plan_series], mandate.min_cash_fen, picture_days),
            "axes": series_axes([series, plan_series], mandate.min_cash_fen, (30, 60, 120, picture_days)),
            "picture_days": picture_days,
            "picture_title": t(lang, f"Your cash, next {picture_days} {'day' if picture_days == 1 else 'days'}", f"未来 {picture_days} 天的现金"),
            **basis,
            **hybrid["cash"],
        },
        "attention": hybrid["attention"],
        "funding_line": hybrid["funding_line"],
        "deals_card": hybrid["deals_card"],
        "receivables_card": hybrid["receivables_card"],
        "changes_card": hybrid["changes_card"],
        **({"home_v2": hybrid.get("home_v2")} if v2 else {}),  # a caller that passes v2=False (the worklist) reads without them
        "next_action": action,
        "approvals": queue,
        "pending_count": len(pending),
        "open_decisions": open_decisions,
        "remaining_task": remaining["text"] if remaining else None,
        "remaining_task_links": remaining["links"] if remaining else [],
        "remaining_task_decision_id": remaining["decision_id"] if remaining else None,
        "changes": changes,
        "receivables": receivables,
        "warnings": warnings,
        "facilities": facilities,
        "counts": {s.value: sum(1 for a in found if a.severity == s) for s in Severity},
        "note_basis": t(lang, "Conservative projection of today's books: unconfirmed receipts are not counted.",
                        "基于今日账目的保守预测：未确认的收款不计入。"),
        "partial": partial.view(lang),
    })
