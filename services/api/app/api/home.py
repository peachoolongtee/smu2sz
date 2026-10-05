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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import Alert, AlertKind, Severity, alerts, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.presentation import (
    approval_words,
    cure_legs,
    facility_name,
    in_words,
    invoice_words,
    needs_owner_reason,
    party_name,
    t,
)
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import FinancialState, Mandate, Mode, OperationStatus
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.financial.lots import ensure_lots
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
    if day is None:
        return ""
    n = day - today
    if n <= 0:
        return t(lang, "today", "今天")
    if n == 1:
        return t(lang, "tomorrow", "明天")
    return t(lang, f"in {n} days", f"{n} 天后")


def _headline(found: list[Alert], mandate: Mandate, t_min_fen: int, t_min_day: int, horizon: int, today: int,
              lang: str) -> tuple[str, str]:
    floor = fmt_yuan(mandate.min_cash_fen)
    breach = _breach(found)
    if breach is not None:
        short = fmt_yuan(breach.amount_fen or 0)
        when = _distance(breach.day, today, lang)
        if breach.inputs.get("cure_restores_reserve") == "false":
            zero = breach.inputs.get("zero_day", "")
            head = t(lang, f"Cash goes below zero on day {zero} ({_distance(int(zero), today, lang)}) if nothing is done.",
                     f"若不采取行动，现金将在第 {zero} 天（{_distance(int(zero), today, lang)}）跌破零。")
            note = t(lang, f"The agent can keep cash at or above zero, but no committed funding restores your {floor} "
                           f"safe level: that needs your decision.",
                     f"代理可以让现金保持在零以上，但没有已承诺的融资能恢复您 {floor} 的安全线，需要您决定。")
            return head, note
        head = t(lang, f"Cash falls {short} below your {floor} safe level on day {breach.day} ({when}).",
                 f"现金将在第 {breach.day} 天（{when}）比您 {floor} 的安全线低 {short}。")
        if breach.committed_cure and any(s.above_apr_cap for s in breach.suggested):
            note = t(lang, "The agent has a fix ready. It needs your approval because of its cost.",
                     "代理已准备好解决方案，因其成本需要您批准。")
        elif breach.committed_cure:
            note = t(lang, "The agent has a fix ready and can run it alone.", "代理已准备好解决方案，可自行执行。")
        elif not mandate.allow_new_borrowing:
            note = t(lang, "Your limits do not allow new borrowing, so no funding can fix it.",
                     "您的授权不允许新增借款，因此无法通过融资解决。")
        else:
            note = t(lang, "No committed funding can fix it: this needs your decision.",
                     "没有已承诺的融资能解决它，需要您决定。")
        return head, note
    warnings = [a for a in found if a.severity == Severity.WARNING]
    head = t(lang, f"Cash stays above your {floor} safe level for the next {horizon} days.",
             f"未来 {horizon} 天现金都保持在您 {floor} 的安全线以上。")
    if warnings:
        thin = next((a for a in warnings if a.kind == AlertKind.RESERVE_HEADROOM_LOW), None)
        if thin is not None and thin.day is not None and not thin.amount_fen:
            note = t(lang, f"It comes close: cash sits exactly on the safe level on day {thin.day} "
                           f"({_distance(thin.day, today, lang)}).",
                     f"但会很接近：第 {thin.day} 天（{_distance(thin.day, today, lang)}）现金恰好等于安全线。")
        elif thin is not None and thin.day is not None:
            note = t(lang, f"It comes close: only {fmt_yuan(thin.amount_fen or 0)} above the safe level on day {thin.day} "
                           f"({_distance(thin.day, today, lang)}).",
                     f"但会很接近：第 {thin.day} 天（{_distance(thin.day, today, lang)}）仅高出安全线 "
                     f"{fmt_yuan(thin.amount_fen or 0)}。")
        else:
            note = warnings[0].title
        return head, note
    return head, t(lang, f"Lowest cash ahead is {fmt_yuan(t_min_fen)} on day {t_min_day}.",
                   f"未来最低现金为第 {t_min_day} 天的 {fmt_yuan(t_min_fen)}。")


def _next_action(state: FinancialState, mandate: Mandate, found: list[Alert], approvals: list[Any], today: int,
                 state_version: int, lang: str) -> dict[str, Any] | None:
    """The one thing to do now: the cure of the first actionable critical alert (a reserve breach), else a repayment
    the books can afford. Its cost, rate, landing day and after-state are the alert's own."""
    alert = next((a for a in found if a.actionable and a.severity == Severity.CRITICAL), None)
    if alert is None:
        alert = next((a for a in found if a.actionable and a.kind == AlertKind.FACILITY_REPAYABLE), None)
    if alert is None:
        return None
    legs = cure_legs(state, alert, today, lang)
    queued = next((a for a in approvals if str(getattr(a.status, "value", a.status)) == "PENDING"
                   and (a.op_id or "").startswith(f"alert:{alert.id}:")), None)
    needs_owner = any(leg["above_apr_cap"] for leg in legs) or any(
        leg["operation_kind"] == "APPLY_FOR_FACILITY" for leg in legs)
    if len(legs) == 1:
        title = legs[0]["label"]
    else:
        title = t(lang, " and ".join([legs[0]["label"]] + [leg["label"][0].lower() + leg["label"][1:] for leg in legs[1:]]),
                  "，".join(leg["label"] for leg in legs))
    # The engine states the whole cure's cost only when every leg is priced; otherwise the priced legs are quoted (as the
    # opener does) and the note says what is left out: an open-ended draw posts no interest until it is repaid.
    cost_display = alert.inputs.get("cure_cost")
    cost_note = None
    if cost_display is None:
        priced = [leg for leg in legs if leg["cost_display"]]
        if len(priced) == 1:
            cost_display = priced[0]["cost_display"]
        unpriced_draw = [leg for leg in legs if leg["operation_kind"] == "DRAW_FACILITY" and not leg["cost_display"]]
        if unpriced_draw and cost_display:
            names = ", ".join(leg["facility_name"] for leg in unpriced_draw)
            cost_note = t(lang, f"Interest on the {names} draw is not included: it runs only while the balance stays drawn.",
                          f"不含{names}提款的利息：利息只在余额未还期间产生。")
    lands = [leg["lands_day"] for leg in legs if leg["lands_day"] is not None]
    receive = sum(leg["amount_fen"] or 0 for leg in legs if leg["operation_kind"] in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"))
    if alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
        short = fmt_yuan(alert.amount_fen or 0)
        if alert.inputs.get("cure_restores_reserve") == "false":
            if_nothing = t(lang, f"Cash goes below zero on day {alert.inputs.get('zero_day')}.",
                           f"现金将在第 {alert.inputs.get('zero_day')} 天跌破零。")
            after = t(lang, f"Cash stays at or above zero, but your safe level is still {alert.inputs.get('residual_shortfall')} "
                            f"short on the worst day.",
                      f"现金保持在零以上，但最差的一天仍比安全线低 {alert.inputs.get('residual_shortfall')}。")
            why = t(lang, "No committed funding restores the reserve; this is the cheapest way to stay above zero.",
                    "没有已承诺的融资能恢复安全线；这是保持在零以上最便宜的方式。")
        else:
            if_nothing = t(lang, f"{short} below your safe level on day {alert.day}; the gap peaks at "
                                 f"{alert.inputs.get('max_shortfall', short)} on day {alert.inputs.get('worst_day', alert.day)}.",
                           f"第 {alert.day} 天比安全线低 {short}；缺口在第 {alert.inputs.get('worst_day', alert.day)} 天最大，为 "
                           f"{alert.inputs.get('max_shortfall', short)}。")
            after = t(lang, f"Cash stays above your safe level through day {alert.inputs.get('last_day', alert.day)}.",
                      f"现金在第 {alert.inputs.get('last_day', alert.day)} 天前都保持在安全线以上。")
            why = t(lang, "The cheapest committed funding that covers the whole gap in time.",
                    "能及时覆盖整个缺口的最便宜的已承诺融资。")
    else:
        if_nothing = t(lang, "Interest keeps running on the drawn balance.", "已提款余额将继续产生利息。")
        after = t(lang, "The balance is repaid and the interest stops.", "余额还清，利息停止。")
        why = in_words(state, alert.detail)
    return {
        "alert_id": alert.id,
        "kind": alert.kind.value,
        "title": title,
        "legs": legs,
        "receive_fen": receive or None,
        "receive_display": fmt_yuan(receive) if receive else None,
        "cost_display": cost_display,
        "cost_note": cost_note,
        "rate_text": next((leg["rate_text"] for leg in legs if leg["rate_text"]), None),
        "cost_days": next((leg["cost_days"] for leg in legs if leg["cost_days"]), None),
        "lands_day": max(lands) if lands else None,
        "needs_owner": needs_owner,
        "needs_owner_reason": needs_owner_reason(mandate, legs, lang) if needs_owner else None,
        "if_nothing": if_nothing,
        "after": after,
        "why": why,
        "detail": in_words(state, alert.detail),
        "formula": alert.formula,
        "pending_approval_id": queued.id if queued is not None else None,
        "state_version": state_version,
        "suggestions": [{"operation_kind": s.operation_kind, "facility_id": s.facility_id,
                         "receivable_id": s.receivable_id, "amount_fen": s.amount_fen} for s in alert.suggested],
    }


def _approvals(state: FinancialState, approvals: list[Any], found: list[Alert], today: int, lang: str) -> list[dict[str, Any]]:
    by_id = {a.id: a for a in found}
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
        words = approval_words(state, op, a.kind, today, alert, lang)
        amount = op.get("amount_fen", op.get("advance_fen"))
        out.append({"id": a.id, "kind": a.kind, "reason": in_words(state, a.reason), "created_day": op.get("day"),
                    "amount_fen": amount if isinstance(amount, int) else None,
                    "amount_display": fmt_yuan(amount) if isinstance(amount, int) else None, **words})
    return out


def _changes(state: FinancialState, store: Any, found: list[Alert], today: int, lang: str) -> list[dict[str, Any]]:
    since = today - RECENT_DAYS
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
        items.append({"day": day, "seq": e.seq, "kind": kind, "actor": who, "text": text})
    for a in found:
        if a.kind == AlertKind.RECEIVABLE_PAST_DUE:
            items.append({"day": a.day, "seq": None, "kind": "LATE", "actor": "",
                          "text": in_words(state, a.detail.split(". ")[0] + ".")})
    for lot in ensure_lots(state).lots:
        if lot.settled and since <= lot.arrival_day <= today and lot.arrival_day != lot.request_day:
            items.append({"day": lot.arrival_day, "seq": None, "kind": "LANDED", "actor": "",
                          "text": t(lang, f"{fmt_yuan(lot.principal_fen)} from {facility_name(state, lot.facility_id)} landed on day {lot.arrival_day}.",
                                    f"来自{facility_name(state, lot.facility_id)}的 {fmt_yuan(lot.principal_fen)} 已于第 {lot.arrival_day} 天到账。")})
    items.sort(key=lambda x: (-(x["day"] or 0), -(x["seq"] or 0)))
    return items[:MAX_CHANGES]


def _receivables(state: FinancialState, store: Any, today: int, lang: str) -> dict[str, Any]:
    report = reconcile(store, day=today)
    rows = []
    for o in report.outstanding:
        rows.append({"receivable_id": o.receivable_id, "buyer_id": o.counterparty_id,
                     "buyer_name": party_name(state, o.counterparty_id), "face_fen": o.face_fen,
                     "face_display": fmt_yuan(o.face_fen), "due_day": o.due_day, "past_due": o.past_due,
                     "days_late": max(0, today - o.due_day) if o.past_due else 0,
                     "invoice": invoice_words(state, o.receivable_id, lang)})
    past_due = [r for r in rows if r["past_due"]]
    upcoming = sorted((r for r in rows if not r["past_due"]), key=lambda r: (r["due_day"], r["receivable_id"]))
    nxt = upcoming[0] if upcoming else None
    total = sum(r["face_fen"] for r in rows)
    awaited = [p for p in report.promised if p.status.value == "AWAITED"]
    promise = None
    if awaited:
        p = min(awaited, key=lambda p: (p.promised_day if p.promised_day is not None else 10**6))
        promise = {"receivable_id": p.receivable_id, "buyer_name": party_name(state, p.counterparty_id),
                   "expected_display": fmt_yuan(p.expected_fen), "promised_day": p.promised_day}
    return {"open_count": len(rows), "open_total_display": fmt_yuan(total), "past_due": past_due,
            "next_receipt": nxt, "promised": promise, "lapsed_promises": report.lapsed_promises}


def _in_transit(state: FinancialState) -> dict[str, Any] | None:
    lots = [lot for lot in ensure_lots(state).lots if not lot.settled]
    if not lots:
        return None
    total = sum(lot.remaining_fen for lot in lots)
    return {"total_display": fmt_yuan(total), "lots": [
        {"facility_name": facility_name(state, lot.facility_id), "amount_display": fmt_yuan(lot.remaining_fen),
         "arrival_day": lot.arrival_day} for lot in sorted(lots, key=lambda lt: (lt.arrival_day, lt.id))]}


@router.get("/home")
def get_home(lang: str = "en") -> dict[str, Any]:
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
        headline, note = _headline(found, mandate, traj.min_cash_fen, traj.min_cash_day, mandate.horizon_days, today, lang)
        action = _next_action(books.state, mandate, found, approvals, today, state.state_version, lang)
        queue = _approvals(books.state, approvals, found, today, lang)
        changes = _changes(books.state, rt.store, found, today, lang)
        receivables = _receivables(books.state, rt.store, today, lang)
        in_transit = _in_transit(books.state)
        warnings = [{"id": a.id, "kind": a.kind.value, "title": in_words(state, a.title), "detail": in_words(state, a.detail),
                     "day": a.day} for a in found if a.severity == Severity.WARNING]
        facilities = [{"id": f.id, "name": f.name, "status": f.status.value, "limit_display": fmt_yuan(f.limit_fen),
                       "drawn_display": fmt_yuan(f.drawn_fen), "available_display": fmt_yuan(max(f.limit_fen - f.drawn_fen, 0)),
                       "lead_time_days": f.lead_time_days}
                      for f in state.facilities if f.status.value == "COMMITTED" and f.limit_fen > 0]
    month1 = traj.months[0] if traj.months else None
    return displayed({
        "day": today,
        "state_version": state.state_version,
        "lang": lang,
        "status": status,
        "headline": headline,
        "note": note,
        "cash": {
            "cash_fen": state.cash_fen,
            "floor_fen": mandate.min_cash_fen,
            "lowest_fen": traj.min_cash_fen,
            "lowest_day": traj.min_cash_day,
            "first_breach_day": traj.first_breach_day,
            "horizon_days": mandate.horizon_days,
            "in_transit": in_transit,
            "dscr_text": month1.dscr.text + "×" if month1 is not None and month1.dscr is not None else None,
            "leverage_text": month1.leverage.text + "×" if month1 is not None else None,
            "min_dscr_bp": mandate.min_dscr_bp,
            "max_leverage_bp": mandate.max_leverage_bp,
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
