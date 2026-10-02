"""Golden cash trajectories (spec v2 §6–7, ADR-0003). Every number comes from golden_values.json."""

from fractions import Fraction

from app.domain.models import LedgerEventKind, Mode
from app.domain.money import bp, gross_up_face
from app.financial import Engine, project, recurring_receivable_id
from tests.financial.builders import draw, early_pay, ex01_package, finance

C = Mode.CONSERVATIVE
FLOOR = 30_000_000


def cost(t) -> int:
    return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen


def closing(t, d: int) -> int:
    return t.days[d].closing_fen


# ---------------------------------------------------------------- baseline


def test_baseline_breaches_on_payroll(state, mandate):
    t = project(state, [], [], C, mandate.horizon_days, mandate.min_cash_fen)
    assert closing(t, 12) == 6_000_000
    assert t.first_breach_day == 12
    assert t.horizon_days == 120 and len(t.days) == 121
    assert cost(t) == 0


def test_baseline_receipts_follow_the_fixture_timeline(state):
    t = project(state, [], [], C, 120)
    # RCV-A (issued day -13, 45-day terms) lands day 32; the day-2 invoice on day 47 before the bill
    assert [e.amount_fen for e in t.days[32].events] == [42_000_000]
    assert [(e.kind, e.amount_fen) for e in t.days[47].events] == [
        (LedgerEventKind.RECEIPT, 42_000_000),
        (LedgerEventKind.FLOW, -10_000_000),
    ]
    assert t.days[47].events[0].ref == recurring_receivable_id("BUYER-1", 2)


# ---------------------------------------------------------------- EX01 package


def test_ex01_package_under_60_day_terms(state, g):
    t = project(state, ex01_package(), [], C, 120, FLOOR)
    assert closing(t, 2) == 40_000_000 + 42_000_000 - g["full_discount_1_2pct"]
    assert closing(t, 20) == g["cash_day20"]
    assert closing(t, 47) == g["cash_day47_60d_terms"]
    assert FLOOR - closing(t, 47) == g["reserve_shortfall_day47"]
    assert t.first_breach_day == 47
    # the day-60 debt payment (D-EQUIP, ¥45,000) falls before the day-2 invoice pays on day 62 under 60-day terms:
    # 209,960 − 45,000 = 164,960 on day 60, the lowest closing; recovery on day 62
    assert closing(t, 60) == g["cash_day60_60d_terms"] == t.min_cash_fen
    assert FLOOR - closing(t, 60) == g["reserve_shortfall_max"]
    assert closing(t, 61) < FLOOR <= closing(t, 62)
    assert t.discounts_posted_fen == g["full_discount_1_2pct"]
    # the contingent rebate sits in the forward ledger at maximum, not in cash
    assert all(p.forward_concession_fen == g["rebate_max"] for p in t.days)


def test_ex01_package_with_45_day_terms_kept(state, g):
    t = project(state, ex01_package(keep_45_days=True), [], C, 120, FLOOR)
    assert closing(t, 20) == g["cash_day20"]
    assert closing(t, 47) == g["cash_day47_45d_terms"]
    assert t.first_breach_day is None


def test_ex01_breach_cured_by_invoice_financing(state, g):
    # ADR-0003: requested on day 0 against the day-2 invoice (requested on its issue day), lands day 5,
    # repaid day 62 -> 57 days -> two 30-day periods. Sized to the deepest shortfall (day 60, after the
    # day-60 debt payment), not the first breach day's: 300,000 − 164,960 = 135,040
    ri = recurring_receivable_id("BUYER-1", 2)
    t = project(state, ex01_package(), [finance(g["reserve_shortfall_max"], ri, day=0)], C, 120, FLOOR)
    assert cost(t) - g["full_discount_1_2pct"] == g["reserve_cure_cost_if"]
    assert t.first_breach_day is None and t.min_cash_fen == FLOOR


def test_immediate_discount_binds_by_face_and_defaults_to_early_pay_lead_time(state, g):
    from tests.financial.builders import early_pay_discount

    t = project(state, [early_pay_discount(receivable_id=None, base_amount=42_000_000)], [], C, 120)
    kinds = [(e.kind, e.amount_fen) for e in t.days[2].events]
    assert kinds == [(LedgerEventKind.EARLY_RECEIPT, 42_000_000),
                     (LedgerEventKind.DISCOUNT, -g["full_discount_1_2pct"])]
    assert t.days[2].events[1].formula == "420,000.00 × 1.2% = 5,040.00"
    assert not t.days[32].events  # settled early: nothing left to receive


# ---------------------------------------------------------------- router plans (spec §7.4)


def test_v2_plan_line_plus_invoice_financing(state, g):
    # the gap before RCV-A lands on day 32 includes the day-30 debt payment: line ¥150,000 + advance ¥255,000
    t = project(state, [], [draw(), finance(g["plan_advance"])], C, 120, FLOOR)
    assert cost(t) == g["v2_optimum_total"]
    assert t.interest_posted_fen + t.fees_posted_fen == g["line_interest_150k_32d"] + g["if_cost_plan_advance"]
    assert t.min_cash_fen == FLOOR and t.first_breach_day is None  # day 30 closes exactly at the floor
    # the advance lands on day 3 (lead time) and is repaid from RCV-A on day 32
    assert [e.kind for e in t.days[3].events] == [LedgerEventKind.ADVANCE]
    assert t.days[3].debt_outstanding_fen - t.days[2].debt_outstanding_fen == g["plan_advance"]
    assert t.days[32].debt_outstanding_fen == t.days[0].debt_outstanding_fen - 15_000_000


def test_line_interest_formula(state, g):
    t = project(state, [], [draw()], C, 120)
    interest = [e for e in t.days[32].events if e.kind == LedgerEventKind.INTEREST]
    assert interest[0].amount_fen == -g["line_interest_150k_32d"]
    assert interest[0].formula == "150,000.00 × 6.4% × 32/365 = 841.64"


def test_v1_plan_line_plus_partial_early_pay(state, g):
    face = g["v1_partial_face"]
    assert face == gross_up_face(g["plan_advance"], bp(120))
    t = project(state, [], [draw(), early_pay(face, 120)], C, 120, FLOOR)
    assert t.discounts_posted_fen == g["v1_partial_discount"]
    assert cost(t) == g["v1_optimum_total"]
    assert t.first_breach_day is None
    # the residual receivable pays on the original due day
    assert closing(t, 32) - t.days[32].opening_fen == (42_000_000 - face) - 15_000_000 - g["line_interest_150k_32d"]


def test_full_discount(state, g):
    t = project(state, [], [early_pay(42_000_000, 120)], C, 120, FLOOR)
    assert cost(t) == g["full_discount_1_2pct"]
    assert t.first_breach_day is None


def test_line_only_breaches_on_payroll(state):
    t = project(state, [], [draw()], C, 120, FLOOR)
    assert t.first_breach_day == 12


def test_example2_line_plus_partial_at_1_5pct(state, g):
    face = gross_up_face(g["plan_advance"], bp(150))
    t = project(state, [], [draw(), early_pay(face, 150)], C, 120, FLOOR)
    assert cost(t) == g["example2_line_plus_partial_1_5pct"]
    assert t.first_breach_day is None


def test_engine_class_satisfies_the_port(state, g):
    from app.domain.ports import TrajectoryEngine

    engine: TrajectoryEngine = Engine()
    t = engine.project(state, [], [draw(), finance(g["plan_advance"])], C, 120, FLOOR)
    assert cost(t) == g["v2_optimum_total"]


# ---------------------------------------------------------------- horizon and months


def test_horizon_extends_past_last_repayment(state):
    t = project(state, [], [draw(repay_day=150)], C, 120)
    assert t.horizon_days == 151
    assert t.days[-1].day == 151


def test_months_debt_service_and_leverage(state, g):
    t = project(state, [], [draw(), finance(g["plan_advance"])], C, 120)
    assert [m.month for m in t.months] == [1, 2, 3, 4]
    m1, m2 = t.months[0], t.months[1]
    assert m1.ebitda_fen == 9_000_000 and m1.debt_service_fen == 4_500_000
    assert m1.dscr is not None and m1.dscr.text == g["dscr_base"]
    # line interest and invoice-financing interest + fee post on day 32 (month 2)
    # (the equipment loan's own payments are cash, not added again: its fixed ¥45,000 is the ratio's service)
    assert m2.debt_service_fen == 4_500_000 + g["line_interest_150k_32d"] + g["if_cost_plan_advance"]
    # month-1 end (day 30): equipment loan after its first ¥45,000 payment + line + advance outstanding
    # = 1,455,000 + 150,000 + 255,000 = 1,860,000; month 2 (day 60): 1,500,000 − 2 × 45,000 = 1,410,000
    assert m1.total_debt_fen == 145_500_000 + 15_000_000 + g["plan_advance"] == 186_000_000
    assert m2.total_debt_fen == 141_000_000
    assert m2.leverage.value == Fraction(141_000_000, 12 * 9_000_000)
    assert m1.leverage.value == Fraction(186_000_000, 12 * 9_000_000)


def test_leverage_with_the_line_drawn_matches_the_covenant_base(state, g):
    # spec §7.6 base leverage counts the ¥150,000 line as drawn: (1,500,000 + 150,000) / (12 × 90,000) = 1.53 on
    # today's books; the projection's month-1 end (day 30) is after the first ¥45,000 payment:
    # (1,455,000 + 150,000) / 1,080,000 = 1.486 -> 1.49
    t = project(state, [], [draw(repay_day=45)], C, 120)
    assert t.days[0].debt_outstanding_fen == 165_000_000
    assert g["leverage_base"] == "1.53"
    assert t.months[0].leverage.text == g["leverage_month1_line_drawn"]
