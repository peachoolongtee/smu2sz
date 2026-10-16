"""ADR-0013, phase 3: the capex screen on a contract's real payment schedule, and the vendor's early-payment discount priced
with the sell side's own rule (d / (1 − d) against the marginal committed source's cost share for the days)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.capex import CapexRequest, evaluate_capex
from app.capex.appraisal import npv_fen, npv_schedule_fen, payback_month, payback_month_schedule, payment_month
from app.capex.buyside import CapexEstimate, NotACapexContract, evaluate_contract
from app.capex.models import CapexPayment
from app.capex.schedule import Timeline
from app.contracts import read_document
from app.domain.fixtures import capex_contract_fixture_bytes, contract_fixture_bytes
from app.domain.models import DocumentKind
from app.funding.rates import break_even_cost_share


@pytest.fixture
def record(state):
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    return read_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM", title="GZPM", source="test", day=0,
                         facilities=state.facilities)


# ---------------------------------------------------------------- the appraisal on a schedule


def test_one_payment_today_is_exactly_the_original_npv_and_payback():
    assert npv_schedule_fen([(0, 60_000_000)], 2_200_000, 4, 60, 1000) == npv_fen(60_000_000, 2_200_000, 4, 60, 1000)
    assert payback_month_schedule([(0, 60_000_000)], 2_200_000, 4, 60) == payback_month(60_000_000, 2_200_000, 4, 60)


def test_paying_later_is_worth_more():
    lump = npv_fen(60_000_000, 2_200_000, 4, 60, 1000)
    later = npv_schedule_fen([(1, 18_000_000), (4, 36_000_000), (15, 6_000_000)], 2_200_000, 4, 60, 1000)
    assert later > lump


def test_payback_is_the_month_from_which_the_cumulative_stays_recovered():
    # 100 now, 100 in month 6, +20 a month from month 1: recovered in month 5, under water again in month 6, back in 10
    assert payback_month_schedule([(0, 100), (6, 100)], 20, 1, 20) == 10
    # a payment after the life is never recovered
    assert payback_month_schedule([(0, 100), (30, 1_000)], 20, 1, 20) is None


@pytest.mark.parametrize(("day", "month"), [(0, 0), (1, 1), (30, 1), (31, 2), (105, 4), (440, 15)])
def test_a_payment_falls_in_the_engines_month(day, month):
    assert payment_month(day, 0) == month


def test_a_request_whose_payments_do_not_sum_to_the_price_is_refused():
    with pytest.raises(ValueError, match="sum to price_fen"):
        CapexRequest(price_fen=100, payments=[CapexPayment(day=1, amount_fen=60)])


def test_without_a_schedule_the_request_and_result_serialise_as_before(state, mandate):
    r = evaluate_capex(CapexRequest(), state, mandate)
    data = r.model_dump(mode="json")
    assert "payments" not in data["request"] and "horizon_end_day" not in data and "beyond_horizon_fen" not in data


def test_a_payment_before_today_is_refused(state, mandate):
    moved = state.model_copy(update={"as_of_day": 10})
    with pytest.raises(ValueError, match="before today"):
        evaluate_capex(CapexRequest(price_fen=100, payments=[CapexPayment(day=5, amount_fen=100)]), moved, mandate)


# ---------------------------------------------------------------- one contract on two timelines


def test_signing_before_any_loan_lands_breaks_the_reserve_and_says_why(record, state, mandate):
    ev = evaluate_contract(record, Timeline(delivery_day=60, acceptance_day=80), CapexEstimate(), state, mandate)
    r = ev.evaluation
    assert r is not None and r.selected_id is None and r.npv_fen == 40_030_608
    assert (r.horizon_end_day, r.beyond_horizon_fen) == (120, 6_000_000)  # the retention, day 440
    by = {s.facility_id: s for s in r.structures if s.facility_id}
    # every owner-approved term facility on the menu is screened at its own term (ADR-0013 phase 6 default)
    assert set(by) == {"FAC-GGL", "FAC-ETL", "FAC-LEASE"} and not any(s.hypothetical for s in r.structures)
    # the guaranteed loan's ¥500,000 limit is below the price: refused before any cash test
    assert by["FAC-GGL"].violations[0].code.value == "PRECONDITION_FAILED" and "above the" in by["FAC-GGL"].violations[0].message
    for fid in ("FAC-ETL", "FAC-LEASE"):
        breach = next(v for v in by[fid].violations if v.code.value == "RESERVE_BREACH")
        assert breach.day == 7 and breach.cure_note is not None and "before the" in breach.cure_note
    assert ev.early_pay is not None and ev.early_pay.worth_it and not ev.early_pay.liquidity_ok
    assert not ev.early_pay.take


def test_signing_after_the_loan_lands_selects_the_term_loan_and_takes_the_discount(record, state, mandate):
    ev = evaluate_contract(record, Timeline(signing_day=20, delivery_day=60, acceptance_day=80), CapexEstimate(), state,
                           mandate)
    r = ev.evaluation
    assert r is not None and r.selected_id == "loan_36m" and r.selected_facility_id == "FAC-ETL"
    assert [(p.day, p.amount_fen) for p in r.request.payments or []] == [(20, 18_000_000), (105, 36_000_000),
                                                                         (440, 6_000_000)]
    assert (ev.uplift_start_month, ev.uplift_start_basis) == (4, "the month after acceptance (day 80)")
    e = ev.early_pay
    assert e is not None and e.take and e.option.days_earlier == 40
    assert e.return_share.value == Fraction(2, 98)
    assert e.cost_share is not None and e.cost_share.value == break_even_cost_share(state, mandate, 40)[0]
    assert e.return_share.value > e.cost_share.value
    early = ev.early_pay_evaluation
    assert early is not None and early.selected_id is not None
    assert early.request.price_fen == 60_000_000 - 720_000
    assert (65, 35_280_000) in [(p.day, p.amount_fen) for p in early.request.payments or []]


def test_a_discount_cheaper_than_the_cost_of_carrying_it_is_not_taken(record, state, mandate):
    """The same contract with a 0.5% discount: 0.5025% return for 40 days is below the 1.78% carrying cost."""
    text = record.document.text.replace("a discount of 2% of that payment", "a discount of 0.5% of that payment")
    low = read_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-GZPM", title="GZPM", source="test", day=0,
                        facilities=state.facilities)
    ev = evaluate_contract(low, Timeline(signing_day=20, delivery_day=60, acceptance_day=80), CapexEstimate(), state,
                           mandate)
    assert ev.early_pay is not None and not ev.early_pay.worth_it and not ev.early_pay.take
    assert ev.early_pay.text.startswith("Not worth it")


def test_no_schedule_means_no_screen(record, state, mandate):
    ev = evaluate_contract(record, Timeline(), CapexEstimate(), state, mandate)
    assert ev.evaluation is None and ev.early_pay is None
    assert ev.schedule.needs == ["delivery_day", "acceptance_day"] and ev.summary.startswith("No payment schedule")


def test_the_owners_uplift_month_wins(record, state, mandate):
    ev = evaluate_contract(record, Timeline(signing_day=20, delivery_day=60, acceptance_day=80),
                           CapexEstimate(uplift_start_month=6), state, mandate)
    assert (ev.uplift_start_month, ev.uplift_start_basis) == (6, "your estimate")
    assert ev.evaluation is not None and ev.evaluation.request.uplift_start_month == 6


def test_only_a_capex_contract_is_screened(state, mandate):
    text = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode("utf-8")
    buyer = read_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1", title="FHR", source="test", day=0,
                          facilities=state.facilities)
    with pytest.raises(NotACapexContract):
        evaluate_contract(buyer, Timeline(), CapexEstimate(), state, mandate)


def test_the_screen_on_a_schedule_writes_nothing(record, state, mandate):
    before = state.model_dump_json()
    evaluate_contract(record, Timeline(signing_day=20, delivery_day=60, acceptance_day=80), CapexEstimate(), state,
                      mandate)
    assert state.model_dump_json() == before
