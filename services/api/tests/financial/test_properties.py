"""Invariants under random inputs: conservation, integer money, half-up posting boundaries."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.fixtures import load_scenario
from app.domain.models import (
    CashFlow,
    DurationKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FlowKind,
    Mode,
    Repayment,
)
from app.domain.money import Ratio, bp, post
from app.financial import project, value_concessions
from tests.financial.builders import draw, early_pay, extension, finance, rebate

STATE, _ = load_scenario("golden_sme")

flows = st.lists(
    st.builds(
        lambda i, d, a, c: CashFlow(id=f"F{i}", day=d, amount_fen=a, kind=FlowKind.OTHER, label="random", confirmed=c),
        st.integers(0, 10**6), st.integers(-5, 150), st.integers(-10**9, 10**9), st.booleans(),
    ),
    max_size=8,
    unique_by=lambda f: f.id,
)
plans = st.lists(
    st.one_of(
        st.builds(lambda a, d, r: draw(amount=a, day=d, repay_day=d + r),
                  st.integers(1, 5_000_000), st.integers(0, 60), st.integers(0, 90)),
        st.builds(lambda a: finance(a), st.integers(1, 10_000_000)),
        st.builds(lambda f, r: early_pay(f, r, receivable_id="RI:BUYER-1:32"),
                  st.integers(1, 42_000_000), st.integers(0, 300)),
    ),
    max_size=3,
    unique_by=lambda a: a.kind,
)


def assert_no_float(obj, path="trajectory"):
    assert not isinstance(obj, float), path
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_no_float(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_no_float(v, f"{path}[{i}]")


@settings(max_examples=60, deadline=None)
@given(flows, plans, st.sampled_from(list(Mode)), st.integers(0, 200), st.booleans())
def test_conservation_and_integer_money(extra_flows, actions, mode, horizon, with_offer):
    state = STATE.model_copy(update={"flows": [*STATE.flows, *extra_flows]})
    obligations = [extension(15), rebate()] if with_offer else []
    t = project(state, obligations, actions, mode, horizon, 30_000_000)
    assert t.horizon_days >= horizon and [p.day for p in t.days] == list(range(t.horizon_days + 1))
    assert t.days[0].opening_fen == state.cash_fen
    for prev, cur in zip(t.days, t.days[1:], strict=False):
        assert cur.opening_fen == prev.closing_fen
    for p in t.days:
        assert p.closing_fen == p.opening_fen + sum(e.amount_fen for e in p.events)
        assert all(type(e.amount_fen) is int for e in p.events)
    assert t.min_cash_fen == min(p.closing_fen for p in t.days)
    assert t.days[-1].debt_outstanding_fen == sum(d.principal_fen for d in state.debts)  # all repaid
    assert_no_float(t.model_dump(mode="python"))


@given(st.integers(0, 10**9))
def test_post_rounds_exact_halves_up(k):
    assert post(Fraction(2 * k + 1, 2)) == k + 1
    assert post(Fraction(-(2 * k + 1), 2)) == -(k + 1)


LINE_1PCT = Facility(id="FAC-T", name="Test line", kind=FacilityKind.CREDIT_LINE, lender_id="BANK-1",
                     status=FacilityStatus.COMMITTED, owner_approved=True, limit_fen=10**12, rate_bp=100,
                     lead_time_days=0, repayment=Repayment.BULLET)


@given(st.integers(0, 10**7))
def test_interest_posting_boundary_rounds_half_up(k):
    # 1% for 365 days on 100k + 50 fen is exactly k + 0.5 fen of interest -> k + 1
    state = STATE.model_copy(update={"facilities": [LINE_1PCT]})
    t = project(state, [], [draw("FAC-T", 100 * k + 50, day=0, repay_day=365)], Mode.CONSERVATIVE, 10)
    assert t.interest_posted_fen == k + 1
    assert t.horizon_days == 366


@given(st.integers(1, 10**9), st.integers(-120, 120), st.integers(1, 2000))
def test_valuation_is_integer_and_antisymmetric(face, delta, rate_bp):
    # One invoice, issued on day 2 with 200-day terms: its due day stays inside W = [0, 365) for every delta in
    # -120..120, so a shortening (a gain, which counts only on cash inside W) is the exact mirror of the extension.
    s = STATE.model_copy(update={"recurring_invoices": [STATE.recurring_invoices[0].model_copy(
        update={"face_fen": face, "terms_days": 200})]})
    rate = Ratio.of(bp(rate_bp))
    one_off = DurationKind.ONE_OFF
    [up] = value_concessions([extension(delta, duration=one_off)], s, rate, "test", 365)
    [down] = value_concessions([extension(-delta, duration=one_off)], s, rate, "test", 365)
    assert type(up.value_fen) is int and up.value_fen == -down.value_fen
