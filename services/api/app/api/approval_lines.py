"""The approvals queue's two cash lines for a pending funding request: cash if the owner declines (nothing runs) and cash if they approve.
A presentation read over the engine's projector, the one the home and `cure_after` use; nothing is priced, decided or run here."""

from __future__ import annotations

from typing import Any

from app.alerts import Alert
from app.api.home import _alert_actions, _distance, _lowest_ahead, _series
from app.api.presentation import fmt_short, series_axis
from app.domain.models import FinancialState, Mandate, Mode
from app.financial import EngineError, project
from app.funding.admission import action_for
from app.operations.log import parse_operation

NO_LINES = {"series_axis": None, "series_if_declined": None, "series_if_approved": None, "lowest_if_declined_short": None, "lowest_if_declined_when": None,
         "lowest_if_declined_fen": None, "lowest_if_approved_short": None, "lowest_if_approved_when": None,
         "lowest_if_approved_fen": None}

FUNDING_KINDS = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "REPAY_FACILITY")


def approval_lines(state: FinancialState, obs: list[Any], mandate: Mandate, op_json: str, alert: Alert | None, today: int,
                   lang: str) -> dict[str, Any]:
    """`series_if_declined` / `series_if_approved` (the points of `GET /home`'s `cash.plan_series`) and each line's lowest point, for a
    pending draw, invoice financing or repayment. When the request is the cure of a reserve alert, "approved" is that cure run, the
    projection the card's "After" sentence is made from (`home.cure_after`), so the line and the sentence cannot disagree; otherwise it
    is the one operation. All None for a request a cash line means nothing for (an agreement's terms, an application)."""
    op = parse_operation(op_json)
    own = action_for(op, today) if op is not None else None
    if own is None:
        return dict(NO_LINES)
    cure = _alert_actions(state, alert, today) if alert is not None else []
    actions = cure or [own]
    try:
        declined = project(state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
        approved = project(state, obs, actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    except EngineError:
        return dict(NO_LINES)
    (low_d, day_d), (low_a, day_a) = _lowest_ahead(declined, today), _lowest_ahead(approved, today)
    if_declined, if_approved = _series(state, declined, lang, from_day=today), _series(state, approved, lang, from_day=today)
    return {
        "series_if_declined": if_declined,
        "series_if_approved": if_approved,
        "series_axis": series_axis([if_declined, if_approved], mandate.min_cash_fen, 60),
        "lowest_if_declined_fen": low_d, "lowest_if_declined_short": fmt_short(low_d), "lowest_if_declined_when": _distance(day_d, today, lang),
        "lowest_if_approved_fen": low_a, "lowest_if_approved_short": fmt_short(low_a), "lowest_if_approved_when": _distance(day_a, today, lang),
    }
