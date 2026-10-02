"""Forward-concession valuation (spec v2 §6.5, §7.5) against golden_values.json."""

from fractions import Fraction

import pytest

from app.domain.models import BaseKind, Contingency, DurationKind, ObligationType
from app.domain.money import Ratio, bp, fmt_pct
from app.financial import ObligationError, if_all_in_rate, value_concessions
from tests.financial.builders import early_pay_discount, extension, ob, rebate

H = 365


@pytest.fixture(scope="module")
def if_rate(state):
    fac = next(f for f in state.facilities if f.id == "FAC-IF")
    return Ratio.of(if_all_in_rate(fac))


def one(obligation, state, rate, label="committed marginal source: invoice financing"):
    [cv] = value_concessions([obligation], state, rate, label, H)
    return cv


def test_if_all_in_rate(state, g, if_rate):
    assert if_rate.value == bp(780) + bp(25) * Fraction(365, 30)
    assert fmt_pct(if_rate.value, 4) == g["if_all_in_rate_display"]
    line = next(f for f in state.facilities if f.id == "FAC-LINE")
    assert if_all_in_rate(line) == bp(640)


def test_extension_committed(state, g, if_rate):
    cv = one(extension(15), state, if_rate)
    assert cv.value_fen == g["extension_committed_12m"]
    assert cv.per_invoice_fen == g["extension_committed_per_invoice"]
    assert "invoice financing" in cv.basis
    assert "13 invoices" in cv.formula  # issue days 2, 32, ..., 362 are in W = [0, 365)


def test_extension_notional_line(state, g):
    cv = one(extension(15), state, Ratio.of(bp(640)), "notional credit line")
    assert cv.value_fen == g["extension_notional_line_12m"]
    assert cv.per_invoice_fen == g["extension_notional_line_per_invoice"]


def test_shortening_is_a_gain_counted_on_cash_inside_the_window(state, g, if_rate):
    cv = one(extension(-15), state, if_rate)
    # A gain counts only if its cash (the shortened due day) is inside W: the day-362 invoice falls due on day 392.
    assert cv.value_fen == g["extension_shortening_gain_12m"]
    assert cv.per_invoice_fen == -g["extension_committed_per_invoice"]


def test_ex06_three_invoices_bounded(state, g, if_rate):
    cv = one(extension(15, duration=DurationKind.RECURRING_BOUNDED, invoices=3), state, if_rate)
    assert cv.value_fen == 561390
    assert cv.per_invoice_fen == g["extension_committed_per_invoice"]


def test_rebate_at_maximum(state, g, if_rate):
    cv = one(rebate(), state, if_rate)
    assert cv.value_fen == g["rebate_max"]
    assert "maximum" in cv.basis


def test_ex01_forward_ledger_total(state, g, if_rate):
    obs = [early_pay_discount(), extension(15), rebate()]
    values = value_concessions(obs, state, if_rate, "committed", H)
    assert [v.obligation_id for v in values] == ["OB-DISC", "OB-EXT", "OB-REB"]
    assert values[0].value_fen == 0 and "immediate" in values[0].basis
    assert sum(v.value_fen for v in values) == g["forward_ledger_total"]


def test_price_adjustment_is_a_gain(state, g, if_rate):
    cv = one(ob("OB-PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=45), state, if_rate)
    assert cv.per_invoice_fen == -g["counter_b_price_adj_per_invoice"]
    assert cv.value_fen == g["counter_b_price_gain_12m"]  # 11 invoices whose cash is inside W


def test_operational_concession(state, if_rate):
    o = ob("OB-OP", ObligationType.OPERATIONAL_CONCESSION, amount_fen=15000, base_kind=BaseKind.PER_EVENT,
           events_per_year=52)
    assert one(o, state, if_rate).value_fen == 15000 * 52


def test_claimed_prior_concession_is_not_booked(state, if_rate):
    o = ob("OB-CL", ObligationType.CLAIMED_PRIOR_CONCESSION, rate_bp=200, base_amount=42_000_000,
           contingency=Contingency.CLAIMED_UNEVIDENCED)
    cv = one(o, state, if_rate)
    assert cv.value_fen == 0 and cv.basis == "unevidenced, not booked"


def test_missing_fields_raise(state, if_rate):
    with pytest.raises(ObligationError):
        one(ob("OB-X", ObligationType.TERMS_EXTENSION), state, if_rate)
    with pytest.raises(ObligationError):
        one(extension(15, cp="BUYER-2"), state, if_rate)  # no recurring invoice to size it
