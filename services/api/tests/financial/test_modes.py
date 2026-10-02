"""Conservative vs expected mode (INVARIANTS 4, 5, 11) and input validation."""

import pytest

from app.domain.models import (
    CashFlow,
    Contingency,
    FacilityStatus,
    FlowKind,
    FundingAction,
    FundingActionKind,
    Mode,
)
from app.financial import FundingActionError, ObligationError, UncommittedFacilityError, project
from tests.financial.builders import draw, early_pay_discount, extension, finance, ob, rebate

C, E = Mode.CONSERVATIVE, Mode.EXPECTED


def with_facility_status(state, fid, status):
    facs = [f.model_copy(update={"status": status}) if f.id == fid else f for f in state.facilities]
    return state.model_copy(update={"facilities": facs})


def test_conservative_rejects_a_not_applied_facility(state):
    with pytest.raises(UncommittedFacilityError) as err:
        project(state, [], [draw("FAC-GGL", 10_000_000, repay_day=60)], C, 120)
    assert err.value.facility_id == "FAC-GGL" and err.value.status == FacilityStatus.NOT_APPLIED
    with pytest.raises(UncommittedFacilityError):  # NOT_APPLIED is zero in expected mode too
        project(state, [], [draw("FAC-GGL", 10_000_000, repay_day=60)], E, 120)


def test_pending_facility_only_in_expected_mode(state):
    s = with_facility_status(state, "FAC-GGL", FacilityStatus.PENDING)
    act = [draw("FAC-GGL", 10_000_000, repay_day=60)]
    with pytest.raises(UncommittedFacilityError):
        project(s, [], act, C, 120)
    t = project(s, [], act, E, 120)
    assert t.days[21].events[0].amount_fen == 10_000_000  # lands after the 21-day lead time


def test_unconfirmed_inflow_ignored_only_in_conservative(state):
    flow = CashFlow(id="F-MAYBE", day=5, amount_fen=5_000_000, kind=FlowKind.OTHER, label="Maybe", confirmed=False)
    s = state.model_copy(update={"flows": [*state.flows, flow]})
    tc = project(s, [], [], C, 120)
    te = project(s, [], [], E, 120)
    assert tc.days[5].closing_fen == 40_000_000
    assert te.days[5].closing_fen == 45_000_000


def test_contingent_gain_counts_as_zero_in_conservative(state):
    shorter = extension(-15, contingency=Contingency.CONTINGENT)
    tc = project(state, [shorter], [], C, 120)
    te = project(state, [shorter], [], E, 120)
    assert tc.days[47].events[0].amount_fen == 42_000_000  # day-2 invoice still on 45 days
    assert te.days[32].events[-1].amount_fen == 42_000_000  # 30 days in expected mode


def test_rebate_with_effective_day_is_paid_in_cash(state, g):
    t = project(state, [rebate(effective_day=90)], [], C, 120)
    assert t.days[89].forward_concession_fen == g["rebate_max"]
    assert t.days[90].forward_concession_fen == 0
    # day 90 also carries the existing loan's third ¥45,000 payment (days 30, 60, 90)
    assert t.days[90].closing_fen - t.days[90].opening_fen == -g["rebate_max"] - 4_500_000


def test_claimed_prior_concession_books_nothing(state):
    from app.domain.models import ObligationType

    o = ob("OB-CL", ObligationType.CLAIMED_PRIOR_CONCESSION, rate_bp=200, base_amount=42_000_000,
           contingency=Contingency.CLAIMED_UNEVIDENCED)
    assert project(state, [o], [], C, 120) == project(state, [], [], C, 120)


def test_bounded_extension_touches_only_n_invoices(state):
    from app.domain.models import DurationKind

    t = project(state, [extension(15, duration=DurationKind.RECURRING_BOUNDED, invoices=1)], [], C, 120)
    receipts = {e.ref: d.day for d in t.days for e in d.events if e.kind.value == "RECEIPT"}
    assert receipts["RI:BUYER-1:2"] == 62  # the first invoice on or after day 0 moves
    assert receipts["RI:BUYER-1:32"] == 77  # the next one keeps 45-day terms


def test_invalid_actions_raise(state):
    with pytest.raises(FundingActionError):  # above the ¥150,000 line limit
        project(state, [], [draw(amount=15_000_001)], C, 120)
    with pytest.raises(FundingActionError):  # above 80% of the invoice
        project(state, [], [finance(33_600_001)], C, 120)
    with pytest.raises(FundingActionError):
        project(state, [], [draw("NOPE")], C, 120)
    with pytest.raises(FundingActionError):  # no bills held (limit 0)
        bill = FundingAction(kind=FundingActionKind.DISCOUNT_BILL, facility_id="FAC-BILL", day=0,
                             amount_fen=100, repay_day=90)
        project(state, [], [bill], C, 120)


def test_ambiguous_discount_binding_raises(state):
    with pytest.raises(ObligationError):
        project(state, [early_pay_discount(receivable_id=None, base_amount=41_000_000)], [], C, 120)


def test_open_draw_and_repay(state, g):
    open_draw = draw(repay_day=None)
    repay = FundingAction(kind=FundingActionKind.REPAY, facility_id="FAC-LINE", day=32, amount_fen=15_000_000)
    t = project(state, [], [open_draw, repay], C, 120)
    assert t.interest_posted_fen == g["line_interest_150k_32d"]
    assert t.days[32].debt_outstanding_fen == 150_000_000 - 4_500_000  # the existing loan after its day-30 payment
