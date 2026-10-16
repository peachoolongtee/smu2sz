"""A facility not yet in place states its cash day as its lead time ("cash on day 21", "arrives day 21"); once the clock
is past that day the Business words never say "13 days ago" (owner, 16 Oct). On day 34 of the golden story the
guaranteed-loan row appears because the rounded early-pay face (R-10) leaves the line ¥2,790 of room."""

from __future__ import annotations

from app.api.presentation import engine_sentence, relative_days
from app.domain.fixtures import load_scenario


def test_a_past_cash_day_says_when_approved_in_english_and_chinese():
    state, _ = load_scenario()
    note = "not applied; cash on day 21, gap opens on day 42"
    assert relative_days(note, 34, "en") == "not applied; cash when approved, gap opens in 8 days"
    assert "ago" not in engine_sentence(state, note, 34, "en")
    zh = engine_sentence(state, note, 34, "zh")
    assert zh == "尚未申请；资金获批后到账，缺口8 天后出现" and "前" not in zh
    comp = "Government-guaranteed working-capital loan: draw ¥197,210.00 (arrives day 21)"
    assert relative_days(comp, 34, "en").endswith("(arrives when approved)")
    assert "获批后到账" in engine_sentence(state, comp, 34, "zh")


def test_a_cash_day_ahead_is_still_a_distance():
    assert relative_days("not applied; cash on day 21, gap opens on day 42", 0, "en") == (
        "not applied; cash in 21 days, gap opens in 42 days")
