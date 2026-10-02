"""When funding cash lands (ADR-0010), in the owner's words.

A draw or an invoice advance requested on day d on a facility with a lead time becomes cash on day d + lead time, not
today. Every chat reply that proposes or reports one says so: at proposal time from the facility's `lead_time_days`,
after execution from the state's lots (a lot not yet settled is cash that has not landed). Nothing here changes the
books; it only reads them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.models import DrawFacility, FinancialState, SubmitInvoiceForFinancing
from app.domain.money import fmt_yuan
from app.financial.lots import ensure_lots, first_unsettled
from app.nl.context import NlContext

Item = tuple[str, int, int]  # (facility id, amount in fen, day the cash lands)


def _t(ctx: NlContext, en: str, zh: str) -> str:
    return zh if ctx.lang == "zh" else en


def is_funding(op: Any) -> bool:
    return isinstance(op, DrawFacility | SubmitInvoiceForFinancing)


def amount_of(op: Any) -> int:
    return op.advance_fen if isinstance(op, SubmitInvoiceForFinancing) else op.amount_fen


def lead_days(state: FinancialState, facility_id: str) -> int:
    return next((f.lead_time_days for f in state.facilities if f.id == facility_id), 0)


def landing_day(ctx: NlContext, op: Any, *, executed: bool) -> int:
    """The day the cash of `op` lands. Proposed: today plus the facility's lead time. Executed: the arrival day of the
    unsettled lot it created, or today when its lot is already settled (no lead time)."""
    state = ctx.state()
    if executed:
        rid = getattr(op, "receivable_id", None)
        lots = [lot for lot in ensure_lots(state).lots
                if lot.facility_id == op.facility_id and not lot.settled and lot.request_day >= op.day
                and (rid is None or lot.receivable_id == rid)]
        if lots:
            return min(lot.arrival_day for lot in lots)
        return op.day
    return op.day + lead_days(state, op.facility_id)


def items(ctx: NlContext, ops: Sequence[Any], *, executed: bool) -> list[Item]:
    return [(o.facility_id, amount_of(o), landing_day(ctx, o, executed=executed)) for o in ops if is_funding(o)]


def clause(ctx: NlContext, day: int) -> str:
    """"requested today, cash lands on day 3": the words for one leg whose cash is not in today."""
    return _t(ctx, f"requested today, cash lands on day {day}", f"今日申请，第 {day} 天到账")


def leg_clause(ctx: NlContext, op: Any, *, executed: bool) -> str:
    """The clause for one funding operation, or "" when its cash is in today (or it is not a funding operation)."""
    if not is_funding(op):
        return ""
    day = landing_day(ctx, op, executed=executed)
    return clause(ctx, day) if day > op.day else ""


def line(ctx: NlContext, ops: Sequence[Any], *, executed: bool) -> str:
    """One sentence that separates cash in today from cash landing later. Proposed legs: "" when all of it is in today
    (nothing to warn about). Executed legs: always, so that the total never reads as cash in hand."""
    its = items(ctx, ops, executed=executed)
    if not its:
        return ""
    today = ctx.day
    now = sum(a for _f, a, d in its if d <= today)
    later = [(f, a, d) for f, a, d in its if d > today]
    if not later and not executed:
        return ""
    if executed:
        head_en = f"Cash in now: {fmt_yuan(now)}." if now else "No cash in yet."
        head_zh = f"已到账：{fmt_yuan(now)}。" if now else "目前尚无到账。"
        later_en, later_zh = "Still to land: ", "待到账："
    else:
        head_en = f"Cash today: {fmt_yuan(now)}." if now else "No cash today."
        head_zh = f"今日到账：{fmt_yuan(now)}。" if now else "今日无到账。"
        later_en, later_zh = "Cash later: ", "稍后到账："
    if not later:
        return _t(ctx, head_en, head_zh)
    en = "; ".join(f"{fmt_yuan(a)} on {f}, requested today, lands on day {d}" for f, a, d in later)
    zh = "；".join(f"{f} {fmt_yuan(a)}，今日申请，第 {d} 天到账" for f, a, d in later)
    return _t(ctx, f"{head_en} {later_en}{en}.", f"{head_zh}{later_zh}{zh}。")


def not_repayable(ctx: NlContext, facility_id: str) -> str:
    """What cannot be repaid yet on a facility: the balance whose cash has not landed, and the day it does (ADR-0010 §6).
    Empty when everything drawn has landed."""
    lots = ensure_lots(ctx.state()).lots
    first = first_unsettled(lots, facility_id)
    if first is None:
        return ""
    fen = sum(lot.remaining_fen for lot in lots if lot.facility_id == facility_id and not lot.settled)
    return _t(ctx, f" A further {fmt_yuan(fen)} on {facility_id}, requested on day {first.request_day}, lands on day "
                   f"{first.arrival_day} and cannot be repaid before then.",
              f" {facility_id} 另有 {fmt_yuan(fen)}（第 {first.request_day} 天申请）将于第 {first.arrival_day} 天到账，"
              f"到账前不能偿还。")


def executor_note(ctx: NlContext, op: Any, message: str) -> str:
    """For an executed draw or advance: the landing clause when the executor's own message (English only) does not
    already say it, so a Chinese reply carries the landing day too."""
    c = leg_clause(ctx, op, executed=True)
    if not c or (ctx.lang != "zh" and "lands on day" in message):
        return ""
    return c


__all__ = ["amount_of", "clause", "executor_note", "is_funding", "items", "landing_day", "lead_days", "leg_clause", "line", "not_repayable"]
