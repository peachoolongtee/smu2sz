"""`in_words`: invoice ids inside a server sentence become business words, and only where they stand as whole tokens."""

from __future__ import annotations

import pytest

from app.api.presentation import in_words
from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState

BUYER = "Foshan Home Retail Co."


@pytest.fixture(scope="module")
def golden() -> FinancialState:
    return load_scenario()[0]


def only(state: FinancialState, *, issued: bool) -> FinancialState:
    """The golden books with a single invoice of the buyer: the issued one, or the recurring one (which then never repeats)."""
    if issued:
        return state.model_copy(update={"recurring_invoices": []})
    ri = state.recurring_invoices[0].model_copy(update={"every_days": 0})
    return state.model_copy(update={"receivables": [], "recurring_invoices": [ri]})


def test_an_issued_invoice_id_becomes_the_invoice_to_the_buyer(golden: FinancialState):
    state = only(golden, issued=True)
    assert in_words(state, "Advance on RCV-A, repaid day 30.") == f"Advance on the ¥420,000.00 invoice to {BUYER}, repaid day 30."
    assert in_words(state, "RCV-A") == f"the ¥420,000.00 invoice to {BUYER}"


def test_a_recurring_invoice_id_becomes_the_invoice_to_the_buyer(golden: FinancialState):
    state = only(golden, issued=False)
    assert in_words(state, "Advance on RI:BUYER-1:2.") == f"Advance on the ¥420,000.00 invoice to {BUYER}."


def test_two_invoices_of_the_same_buyer_and_face_are_told_apart_by_their_due_day(golden: FinancialState):
    out = in_words(golden, "Finance ¥80,000.00 on RI:BUYER-1:32 and ¥120,000.00 on RI:BUYER-1:2, then RCV-A.")
    assert out == (f"Finance ¥80,000.00 on the ¥420,000.00 invoice to {BUYER} due in 77 days and ¥120,000.00 on the "
                   f"¥420,000.00 invoice to {BUYER} due in 47 days, then the ¥420,000.00 invoice to {BUYER} due in 32 days.")
    assert "RI:" not in out and "RCV-A" not in out


def test_operation_hash_and_unknown_ids_are_left_alone(golden: FinancialState):
    for text in ("alert:RI:BUYER-1:2:plan:0", "alert:9f2c:v3:plan:1", "OFF-1234", "op-RCV-A-1", "RCV-AB", "RI:BUYER-9:2",
                 "RI:BUYER-1:2:plan:0", "sha 3f8aRCV-A"):
        assert in_words(golden, text) == text
    assert in_words(golden, "Run alert:RI:BUYER-1:2:plan:0 for RCV-A").startswith("Run alert:RI:BUYER-1:2:plan:0 for the ")
    assert in_words(golden, "Drawn on BANK-1 for BUYER-1") == f"Drawn on Main bank for {BUYER}"


# ---------------------------------------------------------------- overview figures and distances


def test_fmt_short_rounds_half_up_to_whole_thousands_and_keeps_small_figures_exact():
    from app.api.presentation import fmt_short

    assert fmt_short(24_000_000) == "¥240k" and fmt_short(-10_500_000) == "−¥105k" and fmt_short(40_500_000) == "¥405k"
    assert fmt_short(49_950_000) == "¥500k" and fmt_short(49_949_999) == "¥499k" and fmt_short(145_500_000) == "¥1,455k"
    assert fmt_short(84_164) == "¥841.64" and fmt_short(0) == "¥0.00"


def test_when_text_is_a_distance_from_today():
    from app.api.presentation import when_text

    assert [when_text(d, 34, "en") for d in (34, 35, 33, 37, 32, None)] == ["today", "tomorrow", "yesterday", "in 3 days", "2 days ago", ""]
    assert [when_text(d, 34, "zh") for d in (34, 37, 32)] == ["今天", "3 天后", "2 天前"]


def test_relative_days_rewrites_the_engine_phrases_and_leaves_counts_alone():
    from app.api.presentation import relative_days

    r = lambda text: relative_days(text, 34, "en")
    assert r("the cash lands on day 37 after the 3-day lead time") == "the cash lands in 3 days after the 3-day lead time"
    assert r("it will cost ¥1,782.19 by day 47") == "it will cost ¥1,782.19 within 13 days"
    # a deadline is "by today" only on the day itself; a day already past is never "by today" (F03)
    assert r("by day 34") == "by today" and r("by day 35") == "by tomorrow" and r("by day 36") == "within 2 days"
    assert r("by day 30") == "by a deadline that passed 4 days ago" and r("by day 33") == "by a deadline that passed yesterday"
    assert r("the gap lasts to day 41") == "the gap lasts until 7 days from now"
    assert r("repaid day 32, draw ¥150,000.00 (day 12)") == "repaid 2 days ago, draw ¥150,000.00 (22 days ago)"
    assert r("due day 47; stays above the floor for 90 days; day 0 opening") == "due in 13 days; stays above the floor for 90 days; day 0 opening"
    # English engine text inside a Chinese page is rewritten too, and the Chinese day form as well
    assert relative_days("第 37 天 lands on day 37", 34, "zh") == "3 天后 lands in 3 days"


def test_the_alerts_own_cure_reads_as_a_fallback_beside_a_different_recommendation():
    from app.api.presentation import fallback_words

    raw = ("Projected cash closes at ¥60,000.00 in 12 days. A committed cure exists: draw on Bank credit line ¥150,000.00 + finance "
           "an invoice on Invoice financing (onboarded platform) ¥336,000.00, cost ¥2,994.08 (11.2% a year for 29 days).")
    out = fallback_words(raw)
    assert out.endswith("A fallback also exists: draw on Bank credit line ¥150,000.00 and finance an invoice on Invoice financing "
                        "(onboarded platform) for ¥336,000.00, at ¥2,994.08 (11.2% a year for 29 days); FLOW recommends the plan above.")
    assert "committed cure" not in out
    # a sentence with no cure clause is left alone
    assert fallback_words("Projected cash closes at ¥60,000.00 in 12 days.") == "Projected cash closes at ¥60,000.00 in 12 days."


def test_the_cards_reason_has_no_working_and_says_the_yearly_cost_as_the_home_does():
    from app.api.presentation import approval_reason_words
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    raw = ("effective annual cost 32.52% is above the mandate's 15.00% ceiling for what the agent may borrow alone "
           "(all charges on ¥200,000.00 held 10 days (day 37 to day 47), annualised = 32.52%)")
    out = approval_reason_words(state, raw, 34, "en")
    assert out == "The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval, so it waits for your approval."
    assert "annualised" not in out and "day 37" not in out and "agent" not in out


def test_the_engines_admissible_reads_as_within_your_limits_in_business_text():
    from app.api.presentation import business_text
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    assert business_text(state, "admissible but dearer than the selected plan", 0) == "within your limits but dearer than the selected plan"
    assert business_text(state, "cost ¥5,040.00; admissible, but the owner must approve it: x", 0) == (
        "cost ¥5,040.00; within your limits, but you must approve it: x")
    assert business_text(state, "NOT_ADMISSIBLE: RESERVE_BREACH", 0) == "NOT_ADMISSIBLE: RESERVE_BREACH"
