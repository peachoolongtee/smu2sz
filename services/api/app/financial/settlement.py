"""Resolve typed settlement promises on the books' day calendar; no text parsing.

`as_of` names day zero. SourceDocument.received_day is already a books-local day,
not a timestamp; host time and timezone never enter this calculation. Business-day,
holiday, cross-zone and intraday expressions have no supported typed representation.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.domain.models import PaymentTiming


def resolve_payment_day(timing: PaymentTiming, anchor_iso: str) -> int | None:
    try:
        anchor = date.fromisoformat(anchor_iso)
        reference = anchor + timedelta(days=timing.reference_day)
        match timing.basis:
            case "relative_days":
                if timing.offset_days is None or not 0 <= timing.offset_days <= 99:
                    return None
                target = reference + timedelta(days=timing.offset_days)
            case "this_weekday":
                if timing.weekday is None or not 0 <= timing.weekday <= 6:
                    return None
                target = reference + timedelta(days=timing.weekday - reference.weekday())
            case "week_end":
                target = reference + timedelta(days=6 - reference.weekday())
            case "calendar_date":
                if timing.calendar_date is None:
                    return None
                target = date.fromisoformat(timing.calendar_date)
            case _:
                return None
        day = (target - anchor).days
        return day if day >= timing.reference_day else None
    except (ValueError, OverflowError):
        return None
