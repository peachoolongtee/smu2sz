"""Forward concessions valued on dated invoices (docs/FINANCIAL_SEMANTICS.md section 6, A11, F-FIN-01/06/07/09).

Every reference figure is hard-coded from docs/research/concession-valuation-handcalc-2026-10-03.md (tables of
parts 3, 4, 5, 6, 8), under its row label; nothing is imported from scripts/handcalc_concessions.py.

Two places where the decided rules differ from the document's tables, both stated at the row:
- the window is half-open, W = [today, today + H): the document's closed window counts the day-362 invoice at
  H = 362 (row P362); the half-open window does not (12 invoices, not 13);
- a GAIN counts only if its cash, the invoice's due day, is also inside W (rule 4, the answer to the document's
  objection 1). The document's gain rows (parts 3.3 mirror and 4) are by issue day; the gain tests below say
  how many invoices fall due inside W.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.fixtures import load_scenario
from app.domain.models import ConcessionValue, Contingency, DurationKind, ObligationType, ViolationCode
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import (
    extension_pro_forma,
    finance_invoice_charges,
    if_all_in_rate,
    pro_forma_scale,
    upfront_fee,
    value_concessions,
)
from app.funding.rates import break_even_cost_share, break_even_discount
from app.mandate.predicates import check_concession_caps
from app.verifier.evaluate import _extension_pro_forma
from tests.financial.builders import extension, ob

STATE0, MANDATE = load_scenario("golden_sme")
FAC_IF = next(f for f in STATE0.facilities if f.id == "FAC-IF")
R1 = Ratio.of(Fraction(1, 10))  # the document's 10% funding rate
R2 = Ratio.of(if_all_in_rate(FAC_IF))  # golden marginal rate 10.8417% = 1301/12000
PERP, BOUND, ONE = DurationKind.RECURRING_PERPETUAL, DurationKind.RECURRING_BOUNDED, DurationKind.ONE_OFF


def at(today: int):
    return STATE0.model_copy(update={"as_of_day": today})


def value(o, state, rate, horizon) -> int:
    [cv] = value_concessions([o], state, rate, "test", horizon)
    return cv.value_fen


# (label, today, H, obligation kwargs, +15 days at 10% (part 3.1), at 10.8417% (part 3.2), price cut 45 bp (part 4.1, mirrored))
ROWS = [
    ("P90", 0, 90, {}, 517_808, 561_390, 567_000),
    ("P180", 0, 180, {}, 1_035_616, 1_122_781, 1_134_000),
    ("P365", 0, 365, {}, 2_243_836, 2_432_692, 2_457_000),
    ("P730", 0, 730, {}, 4_315_068, 4_678_253, 4_725_000),
    ("P360", 0, 360, {}, 2_071_233, 2_245_562, 2_268_000),
    ("P361", 0, 361, {}, 2_071_233, 2_245_562, 2_268_000),
    # Half-open W: the day-362 invoice is not in [0, 362). The document's closed window gives 13 invoices
    # (2,243,836 / 2,432,692 / 2,457,000); the half-open figure is 12, the same as P361.
    ("P362 (half-open)", 0, 362, {}, 2_071_233, 2_245_562, 2_268_000),
    ("B90", 0, 90, {"duration": BOUND, "invoices": 3}, 517_808, 561_390, 567_000),
    ("B180", 0, 180, {"duration": BOUND, "invoices": 6}, 1_035_616, 1_122_781, 1_134_000),
    ("B365", 0, 365, {"duration": BOUND, "invoices": 13}, 2_243_836, 2_432_692, 2_457_000),
    ("B730", 0, 730, {"duration": BOUND, "invoices": 25}, 4_315_068, 4_678_253, 4_725_000),
    ("Q365", 0, 365, {"duration": BOUND, "invoices": 12}, 2_071_233, 2_245_562, 2_268_000),
    ("Q730", 0, 730, {"duration": BOUND, "invoices": 24}, 4_142_466, 4_491_123, 4_536_000),
    ("T90 (N=100 cut by W)", 0, 90, {"duration": BOUND, "invoices": 100}, 517_808, 561_390, 567_000),
    ("D100", 0, 365, {"duration": BOUND, "end_day": 100}, 690_411, 748_521, 756_000),
    ("D400 (cut by W)", 0, 365, {"duration": BOUND, "end_day": 400}, 2_243_836, 2_432_692, 2_457_000),
    ("O365", 0, 365, {"duration": ONE}, 172_603, 187_130, 189_000),
    ("O100", 0, 365, {"duration": ONE, "effective_day": 100}, 172_603, 187_130, 189_000),
    ("N3", 0, 365, {"duration": BOUND, "invoices": 3}, 517_808, 561_390, 567_000),
    ("N3e300", 0, 365, {"duration": BOUND, "invoices": 3, "effective_day": 300}, 517_808, 561_390, 567_000),
    ("N3e330 (cut by W)", 0, 365, {"duration": BOUND, "invoices": 3, "effective_day": 330}, 345_205, 374_260, 378_000),
    ("E100", 0, 365, {"effective_day": 100}, 1_553_425, 1_684_171, 1_701_000),
    ("E362 (issue on 362)", 0, 365, {"effective_day": 362}, 172_603, 187_130, 189_000),
    ("E363", 0, 365, {"effective_day": 363}, 0, 0, 0),
    ("E365", 0, 365, {"effective_day": 365}, 0, 0, 0),
    ("E1000 (beyond W)", 0, 365, {"effective_day": 1000}, 0, 0, 0),
    ("T34", 34, 365, {}, 2_071_233, 2_245_562, 2_268_000),
    ("T34h90", 34, 90, {}, 517_808, 561_390, 567_000),
    ("T34e100", 34, 365, {"effective_day": 100}, 1_726_027, 1_871_301, 1_890_000),
    ("T34o", 34, 365, {"duration": ONE}, 172_603, 187_130, 189_000),
    ("T34n3", 34, 365, {"duration": BOUND, "invoices": 3}, 517_808, 561_390, 567_000),
]
IDS = [r[0] for r in ROWS]


@pytest.mark.parametrize(("label", "today", "horizon", "kw", "at_10", "at_golden", "_cut"), ROWS, ids=IDS)
def test_terms_extension_tables(label, today, horizon, kw, at_10, at_golden, _cut):
    state = at(today)
    assert value(extension(15, **kw), state, R1, horizon) == at_10
    assert value(extension(15, **kw), state, R2, horizon) == at_golden


@pytest.mark.parametrize(("label", "today", "horizon", "kw", "_a", "_b", "cut_45bp"), ROWS, ids=IDS)
def test_price_cut_tables(label, today, horizon, kw, _a, _b, cut_45bp):
    """Part 4.1 mirrored: a price CUT is a cost (counted on the issue day), so the document's invoice counts
    apply unchanged. The 1% table is the same counts times 420,000."""
    state = at(today)
    n = cut_45bp // 189_000
    assert value(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=-45, **kw), state, R2, horizon) == cut_45bp
    assert value(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=-100, **kw), state, R2, horizon) == n * 420_000


@pytest.mark.parametrize(
    ("horizon", "gain_045", "gain_1pct"),
    [
        # +p% is a gain: only the invoices whose cash (issue + 45) is inside [0, H) count (rule 4).
        (90, -378_000, -840_000),        # issues 2, 32 (dues 47, 77); 62 falls due on 107
        (180, -945_000, -2_100_000),     # issues 2..122; 152 falls due on 197
        (365, -2_079_000, -4_620_000),   # issues 2..302 (11); 332 and 362 fall due on 377, 407
        (730, -4_347_000, -9_660_000),   # issues 2..662 (23); 692 and 722 fall due on 737, 767
    ],
)
def test_price_gain_counts_only_cash_inside_the_window(horizon, gain_045, gain_1pct):
    assert value(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=45), STATE0, R2, horizon) == gain_045
    assert value(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=100), STATE0, R2, horizon) == gain_1pct


def test_shortening_gain_counts_only_cash_inside_the_window():
    # -15 days on 45-day terms: due = issue + 30, so issues 2..332 (12 invoices); the day-362 invoice falls due on 392.
    assert value(extension(-15), STATE0, R2, 365) == -2_245_562  # 12 x 13,660,500/73 posted once; part 3.2 N=12


def test_identical_invoice_sets_give_identical_values():
    """Perpetual, count-bounded, date-bounded and truncated wordings of the same invoices agree to the fen."""
    for horizon, n in [(90, 3), (180, 6), (365, 13), (730, 25)]:
        for rate in (R1, R2):
            perpetual = value(extension(15), STATE0, rate, horizon)
            assert value(extension(15, duration=BOUND, invoices=n), STATE0, rate, horizon) == perpetual
            assert value(extension(15, duration=BOUND, invoices=n + 50), STATE0, rate, horizon) == perpetual
            assert value(extension(15, duration=BOUND, end_day=10_000), STATE0, rate, horizon) == perpetual


# ---------------------------------------------------------------- F-FIN-01 and rule 4 through the cap


def _cap_breached(price_obligation) -> tuple[bool, int]:
    """(AGG cap breached?, price value) for a 6,000-yuan firm rebate plus `price_obligation`, cap 5,000 yuan."""
    rebate = ob("REB", ObligationType.CONTINGENT_REBATE, amount_fen=600_000, contingency=Contingency.FIRM,
                duration=ONE)
    obs = [rebate, price_obligation]
    values = value_concessions(obs, STATE0, R2, "test", MANDATE.forward_concession_horizon_days)
    assert MANDATE.max_aggregate_forward_concession_fen == 500_000 and MANDATE.forward_concession_horizon_days == 365
    violations = check_concession_caps(obs, values, STATE0, MANDATE, "BUYER-1")
    return any(v.code == ViolationCode.AGG_CONCESSION_EXCEEDED for v in violations), values[1].value_fen


def test_ffin01_gain_from_day_1000_is_worth_nothing_and_the_cap_is_breached():
    breached, gain = _cap_breached(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=100, effective_day=1000))
    assert gain == 0 and breached  # part 5, row "F-FIN-01": 600,000 against 500,000


def test_gain_issued_inside_w_but_paid_outside_does_not_offset():
    """Objection 1 / rule 4: firm +1% from day 362. The invoice is issued on day 362 (inside W) and paid on
    day 407 (outside): the gain is not there to offset the rebate. The document's part 5 row counts -420,000
    and passes; the decided rule gives 0 and a breach by 100,000 fen."""
    breached, gain = _cap_breached(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=100, effective_day=362))
    assert gain == 0 and breached


def test_firm_gain_with_cash_inside_w_still_offsets():
    # from day 100: issues 122..302 fall due by 347 (7 invoices, 420,000 each); the document counts 9 by issue day
    breached, gain = _cap_breached(ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=100, effective_day=100))
    assert gain == -2_940_000 and not breached


def test_contingent_gain_never_offsets():
    breached, gain = _cap_breached(
        ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=100, effective_day=100, contingency=Contingency.CONTINGENT))
    assert gain == -2_940_000 and breached  # part 5, row "NOT firm": the existing FIRM-only netting is unchanged


# ---------------------------------------------------------------- properties


@settings(max_examples=60, deadline=None)
@given(horizon=st.integers(1, 800), today=st.integers(0, 60), delta=st.integers(1, 90),
       rate_bp=st.integers(1, 3000))
def test_property_wording_does_not_change_the_value(horizon, today, delta, rate_bp):
    """(a) The same invoice set gives the same value under bounded and perpetual wording."""
    state, rate = at(today), Ratio.of(bp(rate_bp))
    perpetual = value(extension(delta), state, rate, horizon)
    n = max(0, len(range(2, today + horizon, 30)) - len(range(2, today, 30)))
    assert value(extension(delta, duration=BOUND, invoices=n), state, rate, horizon) == perpetual
    assert value(extension(delta, duration=BOUND, end_day=today + horizon + 90), state, rate, horizon) == perpetual


@settings(max_examples=60, deadline=None)
@given(horizon=st.integers(1, 700), today=st.integers(0, 60), delta=st.integers(1, 90),
       rate_bp=st.integers(1, 3000))
def test_property_extending_the_horizon_by_one_interval_adds_one_invoice(horizon, today, delta, rate_bp):
    """(b) Linear, not quadratic: H + 30 days adds exactly one invoice (the exact value is N x per-invoice)."""
    state, rate = at(today), Ratio.of(bp(rate_bp))
    face = state.recurring_invoices[0].face_fen
    per_invoice = Fraction(face) * delta * rate.value / 365

    def n_of(h: int) -> int:
        return len(range(2, today + h, 30)) - len(range(2, today, 30))

    assert n_of(horizon + 30) == n_of(horizon) + 1
    for h in (horizon, horizon + 30):
        assert value(extension(delta), state, rate, h) == post(n_of(h) * per_invoice)
    diff = value(extension(delta), state, rate, horizon + 30) - value(extension(delta), state, rate, horizon)
    assert abs(diff - per_invoice) <= 1


def test_property_value_grows_linearly_with_the_horizon():
    """H = 90 / 180 / 365 / 730 hold 3 / 6 / 13 / 25 invoices: the value is that many invoices, never H squared."""
    for horizon, n in [(90, 3), (180, 6), (365, 13), (730, 25)]:
        assert value(extension(15), STATE0, R2, horizon) == post(Fraction(13_660_500 * n, 73))


@settings(max_examples=60, deadline=None)
@given(effective_day=st.integers(365, 5000), rate_bp=st.integers(1, 3000))
def test_property_a_gain_wholly_outside_w_never_changes_headroom(effective_day, rate_bp):
    """(c) A firm gain dated on or after today + H has value 0, so the cap verdict is exactly the one without it."""
    gain = ob("PA", ObligationType.PRICE_ADJUSTMENT, rate_bp=rate_bp, effective_day=effective_day)
    breached_with, v = _cap_breached(gain)
    assert v == 0 and breached_with  # the 600,000 rebate alone exceeds the 500,000 cap, whatever the gain
    rebate = ob("REB", ObligationType.CONTINGENT_REBATE, amount_fen=600_000, duration=ONE)
    [rv] = value_concessions([rebate], STATE0, R2, "test", 365)
    alone = check_concession_caps([rebate], [rv], STATE0, MANDATE, "BUYER-1")
    with_gain = check_concession_caps([rebate, gain], [rv, ConcessionValue(
        obligation_id="PA", value_fen=v, basis="t", formula="t")], STATE0, MANDATE, "BUYER-1")
    assert [(x.code, x.observed) for x in alone] == [(x.code, x.observed) for x in with_gain]


# ---------------------------------------------------------------- pro forma of an extension (F-FIN-07)

PRO_FORMA_ROWS = [  # part 6 / part 7: every_days, monthly service at 10%, at 10.8417%, extra debt (fen)
    (15, 350_000, 379_458, 42_000_000),
    (30, 175_000, 189_729, 21_000_000),
    (60, 87_500, 94_865, 10_500_000),
    (365, 14_384, 15_594, 1_726_027),
]


def _state_every(e: int, **kw):
    rec = STATE0.recurring_invoices[0].model_copy(update={"every_days": e, **kw})
    return STATE0.model_copy(update={"recurring_invoices": [rec]})


@pytest.mark.parametrize(("every", "svc_10", "svc_golden", "debt"), PRO_FORMA_ROWS)
def test_pro_forma_tables(every, svc_10, svc_golden, debt):
    state = _state_every(every)
    for rate, svc in ((R1, svc_10), (R2, svc_golden)):
        pf = extension_pro_forma(extension(15), state, rate.value, 365)
        assert pf is not None
        assert post(pf.extra_debt) == debt and post(pf.monthly_service) == svc
        assert post(pf.extra_debt * rate.value / 12) == svc  # the identity: service = extra debt x r / 12


def test_golden_pro_forma_in_the_verifier():
    _, _, inputs = _extension_pro_forma([extension(15)], R2.value, STATE0, MANDATE)
    assert inputs["extra_receivables"] == fmt_yuan(21_000_000) == "¥210,000.00"
    assert inputs["extra_monthly_debt_service"] == fmt_yuan(189_729) == "¥1,897.29"


@settings(max_examples=60, deadline=None)
@given(e=st.integers(1, 180), delta=st.integers(1, 90), rate_bp=st.integers(1, 3000))
def test_property_halving_every_days_doubles_the_monthly_service(e, delta, rate_bp):
    """(d) Exactly, on the unposted values."""
    rate = bp(rate_bp)
    slow = extension_pro_forma(extension(delta), _state_every(2 * e), rate, 365)
    fast = extension_pro_forma(extension(delta), _state_every(e), rate, 365)
    assert slow is not None and fast is not None
    assert fast.monthly_service == 2 * slow.monthly_service and fast.extra_debt == 2 * slow.extra_debt


def test_pro_forma_scope_rules():
    """Perpetual from an effective day inside W is the steady state; a finite scope carries min(1, in scope /
    in W) of it (the window holds 13 monthly invoices); a scope with no invoice in W carries none."""
    steady = Fraction(21_000_000)

    def debt(o):
        pf = extension_pro_forma(o, STATE0, R2.value, 365)
        return None if pf is None else pf.extra_debt

    assert debt(extension(15)) == steady
    assert debt(extension(15, effective_day=100)) == steady
    assert debt(extension(15, effective_day=1000)) == 0  # no invoice of the scope is issued in W
    assert debt(extension(15, duration=BOUND, invoices=3)) == steady * 3 / 13
    assert debt(extension(15, duration=BOUND, invoices=40)) == steady  # more than the window holds: capped at 1
    assert debt(extension(15, duration=ONE)) == steady / 13
    assert debt(extension(-15)) is None  # a shortening adds no debt
    assert pro_forma_scale(0, 13, perpetual=False) == 0 and pro_forma_scale(3, 0, perpetual=True) == 0


# ---------------------------------------------------------------- non-positive EBITDA


@pytest.mark.parametrize("ebitda", [0, -9_000_000])
def test_pro_forma_with_non_positive_ebitda_is_a_breach_not_an_exception(ebitda):
    state = STATE0.model_copy(update={"monthly_ebitda_fen": ebitda})
    violations, passed, inputs = _extension_pro_forma([extension(15)], R2.value, state, MANDATE)
    codes = {v.code for v in violations}
    assert ViolationCode.LEVERAGE_BREACH in codes
    assert inputs["pro_forma_leverage"].startswith("undefined")
    assert all(p.code != "LEVERAGE_MAX" for p in passed)


# ---------------------------------------------------------------- break-even (F-FIN-09)

BREAK_EVEN_PCT = {  # part 8, d* in percent to 6 dp: n -> (no upfront fee, 1% upfront fee)
    1: (0.883230, 1.856001), 29: (0.883230, 1.856001), 30: (0.883230, 1.856001),
    31: (1.750984, 2.706879), 59: (1.750984, 2.706879), 60: (1.750984, 2.706879),
    61: (2.603686, 3.543140), 89: (2.603686, 3.543140), 90: (2.603686, 3.543140),
    91: (3.441705, 4.365138),
}
PRINCIPAL = 10_000_000  # CNY 100,000.00


def _with_upfront(upfront_bp: int):
    fac = FAC_IF.model_copy(update={"upfront_fee_bp": upfront_bp})
    state = STATE0.model_copy(update={"facilities": [fac if f.id == "FAC-IF" else f for f in STATE0.facilities]})
    return state, MANDATE.model_copy(update={"max_apr_bp": 10_000}), fac  # the 15% APR cap would drop the facility


@pytest.mark.parametrize("n", sorted(BREAK_EVEN_PCT))
@pytest.mark.parametrize("upfront_bp", [0, 100])
def test_break_even_is_the_ledger_charge_with_the_upfront_fee_once(n, upfront_bp):
    state, mandate, fac = _with_upfront(upfront_bp)
    c, k, period = break_even_cost_share(state, mandate, n)
    interest, fee, periods = finance_invoice_charges(fac, PRINCIPAL, n)
    ledger = interest + fee + upfront_fee(fac, PRINCIPAL)
    assert (k, period) == (periods, 30)
    assert abs(c * PRINCIPAL - ledger) <= 1  # c is exact; the ledger posts each charge to the fen
    d, _ = break_even_discount(state, mandate, n)
    assert abs(float(d.value) * 100 - BREAK_EVEN_PCT[n][1 if upfront_bp else 0]) < 1e-5


def test_break_even_without_upfront_fee_is_unchanged_on_the_golden_books():
    for days, shown in ((30, 0.8832), (60, 1.751), (90, 2.6037)):
        d, _ = break_even_discount(STATE0, MANDATE, days)
        assert round(float(d.value) * 100, 4) == shown
    assert fmt_pct(break_even_discount(STATE0, MANDATE, 30)[0].value) == "0.88%"


@settings(max_examples=60, deadline=None)
@given(n=st.integers(1, 200), upfront_bp=st.integers(1, 500))
def test_property_an_upfront_fee_never_lowers_the_break_even(n, upfront_bp):
    base = break_even_discount(*_with_upfront(0)[:2], n)[0].value
    with_fee = break_even_discount(*_with_upfront(upfront_bp)[:2], n)[0].value
    assert with_fee > base
    c0 = break_even_cost_share(*_with_upfront(0)[:2], n)[0]
    c1 = break_even_cost_share(*_with_upfront(upfront_bp)[:2], n)[0]
    assert c1 - c0 == bp(upfront_bp)  # the fee enters once, at every n


# ---------------------------------------------------------------- capex reads the same pro forma


def test_capex_extension_debt_uses_the_shared_pro_forma():
    from types import SimpleNamespace

    from app.capex.evaluate import _extension_extra_receivables, _live_extension_debt
    from app.domain.models import InvoiceAdjustment

    def adj(**kw):
        return InvoiceAdjustment(id="A", commitment_id="C", obligation_id="O", counterparty_id="BUYER-1",
                                 days_delta=15, **kw)

    def live(a):
        state = STATE0.model_copy(update={"invoice_adjustments": [a]})
        return _live_extension_debt(SimpleNamespace(state=state), MANDATE)

    assert live(adj(from_issue_day=0)) == 21_000_000  # perpetual: F x 15 / 30, not 12 x F x 15 / 365
    ids = ["RI:BUYER-1:2", "RI:BUYER-1:32", "RI:BUYER-1:62"]
    assert live(adj(receivable_ids=ids)) == post(Fraction(21_000_000 * 3, 13))
    assert live(adj(from_issue_day=0, until_issue_day=100)) == post(Fraction(21_000_000 * 4, 13))  # issues 2, 32, 62, 92
    request = SimpleNamespace(extension_target_terms_days=60, extension_counterparty_id="BUYER-1")
    assert _extension_extra_receivables(request, STATE0, MANDATE) == 21_000_000
