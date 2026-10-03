"""ADR-0007 checked against figures derived by hand, independently of the implementation.

Every figure below comes from docs/research/early-pay-handcalc-2026-10-01.md (derived from the golden fixture, the
engine semantics and ADR-0002 before the verifier code was read). Money is integer fen; the arithmetic is in the
comments. Offers are typed obligations (no LLM). Verdicts come from app.verifier.evaluate; nothing is imported from
the other early-pay test module.

Golden books: cash 400,000.00, floor 300,000.00, payroll -340,000 day 12, supplier -120,000 day 20, bill -100,000
day 47, RCV-A 420,000 due day 32, recurring 420,000 issued day 2 (due 47), the existing loan's -45,000 on days 30, 60,
90, ... (docs/FINANCIAL_SEMANTICS.md §5; 3 Oct: the figures below were re-derived with it, so the gap before day 32 is
340,000 + 120,000 + 45,000 + 300,000 - 400,000 = 405,000, not 360,000). Line 6.40% (limit 150,000, lead 0).
Invoice financing (IF) 7.80% + 0.25% per whole 30-day period, 80% advance, lead 3. Buyer early pay 1.20% (a router
source too: FAC-EARLYPAY, committed). Early settlement "day 2" is 30 days before RCV-A's due day 32.
"""

from __future__ import annotations

import re
from decimal import Decimal
from fractions import Fraction

import pytest

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
)
from app.funding import break_even_discount
from app.verifier import evaluate
from tests.verifier.conftest import codes

SPAN = [SourceSpan(doc_id="OWNER-DOC", start=0, end=0, text="")]
NEW_CODES = {"EARLY_PAY_NOT_NEEDED", "EARLY_PAY_DEARER_THAN_PLAN"}
WHOLE = 42_000_000  # RCV-A, 420,000.00

# C0, golden books, no offer. Line 15,000,000 x 0.064 x 32/365 = 84,164.38 -> 84,164;
# IF 25,500,000 (405,000 - 150,000) k=1: interest x 0.078 x 30/365 = 163,479.45 -> 163,479, fee x 0.0025 = 63,750
# -> 227,229. (Before the existing loan's day-30 payment was cash: IF 21,000,000 -> 187,130, C0 271,294.)
C0_GOLDEN = 84_164 + 227_229  # 311,393 = 3,113.93

# Per-period IF cost share: 0.078 x 30/365 + 0.0025 = 1301/146000. d* = k x 1301 / (146000 + 1301 k).
C_PERIOD = Fraction(78, 1000) * 30 / 365 + Fraction(25, 10000)


def _leg(rate_bp: int, face: int = WHOLE, day: int = 2, oid: str = "HC-O1") -> Obligation:
    return Obligation(
        id=oid, type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
        effective_day=day, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A", amount_fen=face),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN, confidence=1.0)


def _ev(state, mandate, key, *obs: Obligation):  # type: ignore[no-untyped-def]
    offer = CompiledOffer(offer_id="HC-TEST", counterparty_id="BUYER-1", doc_ids=["OWNER-DOC"], received_day=0,
                          status=CompileStatus.COMPILED, obligations=list(obs), compiler="nl-hc-test",
                          prompt_version="nl-v1")
    return evaluate(offer, state, mandate, trusted_owner_key_hex=key)


def _fen(text: str) -> int:
    return int(Decimal(re.sub(r"[^\d.]", "", text)) * 100)


def _figures(b) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """(C1, C0) in fen as the verdict reports them: from the violation, else from the passed check."""
    for v in b.verdict.violations:
        if v.code.value in NEW_CODES:
            return _fen(v.inputs["cost_with_offer"]), _fen(v.inputs["cost_without_offer"])
    (p,) = [p for p in b.passed_checks if p.code == "EARLY_PAY_VS_PLAN"]
    return _fen(p.inputs["cost_with_offer"]), _fen(p.inputs["cost_without_offer"])


def _early_codes(b) -> list[str]:  # type: ignore[no-untyped-def]
    return [c for c in codes(b.verdict.violations) if c in NEW_CODES or c == "DISCOUNT_ABOVE_BREAK_EVEN"]


def _due_in(state, days_after_settlement: int, settle_day: int = 2):  # type: ignore[no-untyped-def]
    """RCV-A due `days_after_settlement` days after the settlement day (terms_days = due - issue_day)."""
    return state.model_copy(update={"receivables": [
        r.model_copy(update={"terms_days": settle_day + days_after_settlement - r.issue_day}) if r.id == "RCV-A" else r
        for r in state.receivables]})


def _rich(state):  # type: ignore[no-untyped-def]
    """Cash 1,000,000.00: the worst day (day 30: 1,000,000 - 460,000 - 45,000 = 495,000) is far above the floor."""
    return state.model_copy(update={"cash_fen": 100_000_000})


# ------------------------------------------------------------------------------------------- 2a. break-even d*(n)


@pytest.mark.parametrize(("n", "k", "floor_bp"), [(3, 1, 88), (30, 1, 88), (31, 2, 175), (60, 2, 175), (90, 3, 260)])
def test_break_even_by_tenor_is_billed_in_whole_periods(state, mandate, n, k, floor_bp):
    # c = k x 1301/146000, d* = 1301k / (146000 + 1301k): 1301/147301 (88.32 bp), 1301/74301 (175.10 bp), 3903/149903 (260.37 bp)
    d, bp = break_even_discount(state, mandate, n)
    assert d.value == Fraction(1301 * k, 146000 + 1301 * k)
    assert d.value == (k * C_PERIOD) / (1 + k * C_PERIOD)
    assert bp == floor_bp


# ------------------------------------------------------------------------------------------- 2b/2c. the ADR table


def test_row1_whole_invoice_85bp_day2_costs_3570_and_is_dearer_than_the_plan(state, mandate, key):
    # disc 42,000,000 x 0.0085 = 357,000; net 41,643,000; cash day 20 = 400,000 + 416,430 - 340,000 - 120,000 = 356,430,
    # day 30 = 356,430 - 45,000 = 311,430 >= 300,000: no funding
    b = _ev(state, mandate, key, _leg(85))
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]  # 85 bp < 88.32 bp: test 1 passes; 357,000 >= 311,393
    assert _figures(b) == (357_000, 311_393)
    assert b.verdict.outcome == Outcome.COUNTER


def test_row2_whole_invoice_64bp_costs_2688_and_is_accepted(state, mandate, key):
    # 42,000,000 x 0.0064 = 268,800 < 311,393; day 30 = 400,000 + 413,120 - 505,000 = 308,120 >= 300,000
    b = _ev(state, mandate, key, _leg(64))
    assert _early_codes(b) == []
    assert _figures(b) == (268_800, 311_393)
    assert b.verdict.outcome == Outcome.ACCEPT


def test_row3_whole_invoice_75bp_costs_3150_and_is_countered(state, mandate, key):
    # The plan now costs 311,393, so the boundary moved from 64/65 bp to 74/75 bp:
    # 42,000,000 x 0.0074 = 310,800 < 311,393 (day 30 = 400,000 + 416,892 - 505,000 = 311,892, no funding): accepted;
    # 42,000,000 x 0.0075 = 315,000 > 311,393: countered. (65 bp, 273,000, is now below the plan and accepted.)
    below = _ev(state, mandate, key, _leg(74))
    assert _early_codes(below) == [] and _figures(below) == (310_800, 311_393)
    assert below.verdict.outcome == Outcome.ACCEPT
    b = _ev(state, mandate, key, _leg(75))
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert _figures(b) == (315_000, 311_393)
    assert b.verdict.outcome == Outcome.COUNTER


def test_row4_counter_a_257200_at_85bp_costs_3027_77_and_is_accepted(state, mandate, key):
    # face: 255,000 / (1 - 0.0085) = 257,186.08 -> up to a whole 100: 257,200 (was 211,900 on a 360,000 gap)
    # disc 25,720,000 x 0.0085 = 218,620; net 25,501,380; the line carries 40,500,000 - 25,501,380 = 14,998,620:
    # 14,998,620 x 0.064 x 32/365 = 84,156.6 -> 84,157; C1 = 302,777 < 311,393
    b = _ev(state, mandate, key, _leg(85, face=25_720_000))
    assert _early_codes(b) == []
    assert _figures(b) == (218_620 + 84_157, 311_393) == (302_777, 311_393)
    assert b.verdict.outcome == Outcome.ACCEPT


def test_row5_no_cash_need_any_positive_discount_buys_nothing(state, mandate, key):
    rich = _rich(state)
    for bp in (1, 50, 85):  # every one is below the 88.32 bp first screen  # C0 = 0 (nothing short, nothing drawn); C1 = 42,000,000 x bp/10000 > 0
        b = _ev(rich, mandate, key, _leg(bp))
        assert "EARLY_PAY_NOT_NEEDED" in codes(b.verdict.violations)
        assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(b.verdict.violations)
        assert _figures(b) == (WHOLE * bp // 10_000, 0)


def test_row6_whole_invoice_89bp_30_days_early_is_above_the_break_even(state, mandate, key):
    b = _ev(state, mandate, key, _leg(89))  # 89 bp >= 88.3226 bp
    assert "DISCOUNT_ABOVE_BREAK_EVEN" in codes(b.verdict.violations)
    v = next(x for x in b.verdict.violations if x.code.value == "DISCOUNT_ABOVE_BREAK_EVEN")
    assert v.inputs["break_even"] == "0.8832%" and v.inputs["break_even_days"] == "30"
    assert b.verdict.outcome == Outcome.COUNTER


# ------------------------------------------------------------------------------------------- 2d. neighbours of the break-even


@pytest.mark.parametrize(("bp", "c1", "first_screen"), [
    (87, 365_400, False),  # 42,000,000 x 0.0087 = 365,400; 87 < 88.3226 so test 1 passes
    (88, 369_600, False),  # 42,000,000 x 0.0088 = 369,600; 88 < 88.3226: the last whole bp that passes test 1
    (89, 373_800, True),  # 42,000,000 x 0.0089 = 373,800; 89 >= 88.3226: test 1 fails (test 3 would too)
])
def test_break_even_neighbours_on_the_whole_invoice(state, mandate, key, bp, c1, first_screen):
    b = _ev(state, mandate, key, _leg(bp))
    found = codes(b.verdict.violations)
    assert ("DISCOUNT_ABOVE_BREAK_EVEN" in found) is first_screen
    assert "EARLY_PAY_DEARER_THAN_PLAN" in found  # every one is dearer than 311,393
    assert _figures(b) == (c1, 311_393)
    assert b.verdict.outcome == Outcome.COUNTER


def test_three_days_early_has_the_same_break_even_as_thirty(state, mandate, key):
    # n = 3 (due day 32, settled day 29), k = 1 so limit 1301/147301 = 88.32 bp: 85 bp passes test 1, 89 bp does not.
    b = _ev(state, mandate, key, _leg(85, day=29))
    assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(b.verdict.violations)
    assert "DISCOUNT_ABOVE_BREAK_EVEN" in codes(_ev(state, mandate, key, _leg(89, day=29)).verdict.violations)
    # Funding is still needed day 12..28 (day-20 short 360,000; the receipt on day 29 comes before the day-30 debt
    # payment), so the whole invoice at 85 bp (357,000) is dearer than the plan (311,393).
    assert "EARLY_PAY_DEARER_THAN_PLAN" in codes(b.verdict.violations)
    assert _figures(b)[1] == 311_393


# The independent check first disagreed here: the router re-priced the buyer's early-pay facility at the OFFER's
# rate and used it on other money. The lead fixed that at the root (the facility is always priced at its standing
# rate), after which the partial-gap figure below matches the hand figure exactly.
#
# Three days early is the one place the hand figure and the engine still differ, by a modelling convention, not
# arithmetic: an invoice the buyer has agreed to settle early cannot also be financed, so the ¥210,000 the line does
# not cover comes from the buyer's standing 1.2% early-pay facility on the next invoice (face 21,000,000/0.988 =
# 21,255,060.73 -> 21,255,061, discount 255,061) instead of 26 days of invoice financing on RCV-A (187,130). The line
# is repaid on day 29: 15,000,000 x 0.064 x 29/365 = 76,273.97 -> 76,274. Funding the gap = 76,274 + 255,061 = 331,335.
# (The early receipt on day 29 lands before the existing loan's day-30 payment, so this gap is still 360,000.)
# The convention only ever makes an early payment look dearer, so it cannot cause a wrong accept.
_GAP_3_DAYS = 76_274 + 255_061


def test_three_days_early_85bp_c1_figure(state, mandate, key):
    # C1 = 357,000 + 331,335 = 688,335 (hand figure with RCV-A financed instead: 620,404). Dearer either way.
    b = _ev(state, mandate, key, _leg(85, day=29))
    assert _figures(b) == (357_000 + _GAP_3_DAYS, 311_393) == (688_335, 311_393)
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]


def test_three_days_early_1bp_is_dearer_under_the_no_financing_convention(state, mandate, key):
    # C1 = 4,200 + 331,335 = 335,535 >= 311,393. With RCV-A financed the hand figure is 4,200 + 76,274 + 187,130 =
    # 267,604 and the offer would be taken; the engine's convention refuses it. Conservative, accepted.
    b = _ev(state, mandate, key, _leg(1, day=29))
    assert _figures(b) == (4_200 + _GAP_3_DAYS, 311_393) == (335_535, 311_393)
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert b.verdict.outcome != Outcome.ACCEPT


def test_three_days_early_2bp_is_dearer_than_the_plan(state, mandate, key):
    # 8,400 + 331,335 = 339,735 >= 311,393 (hand figure with RCV-A financed: 271,804, which would now be cheaper than
    # the plan: the same no-financing convention, conservative).
    b = _ev(state, mandate, key, _leg(2, day=29))
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert _figures(b) == (339_735, 311_393)


def test_ninety_days_early_at_1_2pct_passes_the_first_screen_but_not_the_plan(state, mandate, key):
    # RCV-A due day 92 (terms 105). Test 1: n = 90, k = 3, limit 3903/149903 = 2.6037%; 1.2% passes (the old 0.8832% did not).
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(120))
    assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(b.verdict.violations)
    # C0 on these books. Short 240,000 day 12, 360,000 day 20..29, 405,000 day 30..46 (the day-30 debt payment),
    # 85,000 on day 47 (cash 215,000), 130,000 from day 60 (the day-60 payment), cured day 77.
    # Line 150,000 to day 47: 15,000,000 x 0.064 x 47/365 = 123,616.44 -> 123,616. The other 255,000 net:
    #   IF, arrival day 3 to repayment day 92 = 89 days = 3 periods: 3 x 227,229 = 681,687;
    #   the buyer's own early pay at 1.2% (FAC-EARLYPAY): face = 25,500,000/0.988 = 25,809,716.6 -> 25,809,717,
    #   discount 309,717 (3,097.17). Early pay is cheaper, so C0 was 123,616 + 309,717 = 433,333.
    # Red team d, F1: no operation asks the buyer to pay early, so the router's plan is the cheapest one that can run:
    # the line and the advance. The IF charges for the 89 days post as one 90-day posting: 25,500,000 x 0.078 x
    # 90/365 = 490,438 + fees 3 x 63,750 = 191,250 -> 681,688. C0 = 123,616 + 681,688 = 805,304.
    # C1: the whole invoice at 1.2%: 42,000,000 x 0.012 = 504,000; cash stays >= 354,960 - 45,000 = 309,960; no
    # funding. 504,000 < 805,304: the offer now beats the plan that can run (before: 504,000 >= 433,333, rejected).
    assert _figures(b) == (504_000, 123_616 + 681_688) == (504_000, 805_304)
    assert codes(b.verdict.violations) == []


def test_ninety_days_early_a_discount_that_beats_the_plan_is_accepted(state, mandate, key):
    # Same books (C0 = 805,304 since red team d F1; 433,333 before). 0.85% whole: 42,000,000 x 0.0085 = 357,000 < C0,
    # and 85 bp < 260.37 bp.
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(85))
    assert _early_codes(b) == []
    assert _figures(b) == (357_000, 805_304)
    assert b.verdict.outcome == Outcome.ACCEPT


def test_ninety_days_early_the_plan_cost_tie_fails_the_strict_inequality(state, mandate, key):
    # 21,255,061 at 1.2%: disc round(21,255,061 x 0.012) = round(255,060.73) = 255,061; net exactly 21,000,000.
    # Remaining gap 195,000: the line to day 47 (123,616) + 45,000 net of the buyer's early pay at the same 1.2%
    # (face 45,000/0.988 = 45,546.56, discount 546.56 = 54,656). C1 = 255,061 + 123,616 + 54,656 = 433,333 = C0
    # (255,061 + 54,656 = 309,717, the discount on the one face C0 used): test 3 needs C1 < C0, and the tie failed it.
    # Red team d, F1: C0 is now the plan that can run (805,304, see the 1.2% test above), so C1 = 433,333 beats it.
    # C1 itself is unchanged: with the offer the buyer's early pay is part of the deal, priced as before.
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(120, face=21_255_061))
    assert _figures(b) == (433_333, 805_304)
    assert _early_codes(b) == []


def test_the_break_even_violation_states_the_tenor(state, mandate, key):
    # 300 bp at 90 days early: above 2.6037% (3 periods). (It also breaches the 150 bp discount cap; ignored here.)
    b = _ev(_due_in(state, 90), mandate, key, _leg(300))
    v = next(x for x in b.verdict.violations if x.code.value == "DISCOUNT_ABOVE_BREAK_EVEN")
    assert v.inputs["break_even_days"] == "90" and v.inputs["break_even"] == "2.6037%"
    # 31 days early: 2 periods, limit 1301/74301 = 1.7510%: 176 bp fails, 170 bp passes test 1
    s31 = _due_in(state, 31)
    v31 = next(x for x in _ev(s31, mandate, key, _leg(176)).verdict.violations if x.code.value == "DISCOUNT_ABOVE_BREAK_EVEN")
    assert v31.inputs["break_even_days"] == "31" and v31.inputs["break_even"] == "1.7510%"
    assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(_ev(s31, mandate, key, _leg(170)).verdict.violations)


def test_zero_days_early_is_not_an_early_payment(state, mandate, key):
    # Settled on the due day (32): n = 0, no test applies, even though 140 bp is far above any break-even for n = 0.
    b = _ev(state, mandate, key, _leg(140, day=32))
    assert _early_codes(b) == []
    assert not any(p.code == "EARLY_PAY_VS_PLAN" for p in b.passed_checks)


def test_no_cash_need_reports_not_needed_whatever_the_size(state, mandate, key):
    # 0.5% whole: 42,000,000 x 0.005 = 210,000 (2,100.00) > C0 = 0; 50 bp < 88.32 bp so test 1 passes
    b = _ev(_rich(state), mandate, key, _leg(50))
    assert "EARLY_PAY_NOT_NEEDED" in codes(b.verdict.violations)
    assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(b.verdict.violations)
    assert _figures(b) == (210_000, 0)
    assert b.verdict.outcome in (Outcome.REJECT, Outcome.COUNTER)  # a pricing fault, never an accept


def test_partial_gap_early_pay_still_funds_the_rest(state, mandate, key):
    # 100,000 of RCV-A at 0.5%, day 2: disc 10,000,000 x 0.005 = 50,000; net 9,950,000; residual RCV-A 320,000 due day 32.
    # Cash day 30 = 400,000 + 99,500 - 460,000 - 45,000 = -5,500, short 305,500 that must still be funded (not "no
    # funding needed"). The rest is dearer than the plan's advance (see the next test), so it is countered.
    b = _ev(state, mandate, key, _leg(50, face=10_000_000))
    assert _early_codes(b) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert b.verdict.outcome == Outcome.COUNTER
    c1, c0 = _figures(b)
    assert c0 == 311_393 and 50_000 < c1  # more than the discount alone: the rest of the gap costs something
    v = next(x for x in b.verdict.violations if x.code.value == "EARLY_PAY_DEARER_THAN_PLAN")
    assert v.inputs["plan_with_offer"] != "no funding needed"


def test_partial_gap_c1_figure(state, mandate, key):
    # Funding 305,500. An invoice under an early-payment agreement cannot also be financed (ADR-0007 note; enforced
    # in the engine since the 3 Oct red team), so the rest is not an advance on RCV-A's residual. The plan is:
    # line 150,000 for 32 days (84,164) + more early payment on RCV-A at the buyer's standing 1.2%: to net 155,500
    # the face is 155,500 / (1 - 0.012) = 157,388.66 -> 15,738,866 fen; discount 15,738,866 x 0.012 =
    # 188,866.39 -> 188,866. C1 = 50,000 + 84,164 + 188,866 = 323,030 (3,230.30), now above C0 = 311,393.
    # (Before the existing loan's day-30 payment was cash the gap was 260,500 and C1 268,375 < C0 271,294.)
    b = _ev(state, mandate, key, _leg(50, face=10_000_000))
    assert _figures(b) == (323_030, 311_393)


def test_golden_c0_is_reported_the_same_for_every_early_pay_offer(state, mandate, key):
    # C0 never depends on the discount rate or face: the standing plan of the golden books
    for leg in (_leg(10), _leg(64, face=25_720_000), _leg(120)):
        assert _figures(_ev(state, mandate, key, leg))[1] == C0_GOLDEN
