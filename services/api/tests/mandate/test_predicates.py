from fractions import Fraction

import pytest

from app.domain.fixtures import golden_values, load_scenario
from app.domain.models import (
    BaseKind,
    ConcessionValue,
    Contingency,
    Duration,
    DurationKind,
    ForwardConcession,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
    ViolationCode,
)
from app.domain.money import Ratio
from app.mandate import check_apr, check_predicates
from tests.covenants.builders import trajectory

STATE, MANDATE = load_scenario()
FLOOR = MANDATE.min_cash_fen  # ¥300,000
AGG_CAP = MANDATE.max_aggregate_forward_concession_fen  # ¥5,000
BUYER = "BUYER-1"
SPAN = SourceSpan(doc_id="d", start=0, end=1, text="x")


def ob(oid, contingency=Contingency.FIRM, type_=ObligationType.TERMS_EXTENSION, rate_bp=None, cp=BUYER):
    return Obligation(
        id=oid,
        type=type_,
        counterparty_id=cp,
        rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
        contingency=contingency,
        duration=Duration(kind=DurationKind.ONE_OFF),
        spans=[SPAN],
        confidence=1.0,
    )


def cv(oid, value):
    return ConcessionValue(obligation_id=oid, value_fen=value, basis="test", formula="test")


def run(obligations=(), values=(), state=STATE, mandate=MANDATE, t=None, cp=BUYER):
    return check_predicates(t or trajectory(10), list(obligations), list(values), state, mandate, cp)


def codes(vs):
    return [v.code for v in vs]


# ------------------------------------------------------------------ reserve


@pytest.mark.parametrize("closing, breach", [(FLOOR, False), (FLOOR + 1, False), (FLOOR - 1, True)])
def test_min_cash_boundary(closing, breach):
    vs = run(t=trajectory(60, closings={47: closing}))
    assert codes(vs) == ([ViolationCode.RESERVE_BREACH] if breach else [])


def test_reserve_breach_golden_day47():
    g = golden_values()
    t = trajectory(
        70,
        closings={47: g["cash_day47_60d_terms"], 48: g["cash_day47_60d_terms"], 50: 20_000_000, 62: 50_000_000},
        default_closing=g["cash_day47_60d_terms"],
    )
    # Days 0..46 must be above the floor for day 47 to be first.
    t = t.model_copy(
        update={"days": [d.model_copy(update={"closing_fen": 40_000_000}) if d.day < 47 else d for d in t.days]}
    )
    [v] = run(t=t)
    assert v.day == 47
    assert v.curable is None
    assert v.observed == "¥254,960.00" and v.limit == "¥300,000.00"
    assert v.inputs["shortfall_fen"] == str(g["reserve_shortfall_day47"])
    assert v.inputs["shortfall"] == "¥45,040.00"
    assert v.inputs["max_shortfall"] == "¥100,000.00" and v.inputs["max_shortfall_day"] == "50"
    assert v.inputs["recovery_day"] == "62"
    assert v.formula and "¥254,960.00 < ¥300,000.00" in v.formula


def test_reserve_breach_without_recovery():
    t = trajectory(20, closings={d: 1 for d in range(5, 21)})
    [v] = run(t=t)
    assert v.day == 5 and v.inputs["recovery_day"] == "none within horizon"


# ------------------------------------------------------------------ aggregate cap


@pytest.mark.parametrize("value, breach", [(AGG_CAP, False), (AGG_CAP - 1, False), (AGG_CAP + 1, True)])
def test_aggregate_cap_boundary(value, breach):
    vs = run([ob("o1")], [cv("o1", value)])
    assert codes(vs) == ([ViolationCode.AGG_CONCESSION_EXCEEDED] if breach else [])


def test_aggregate_includes_existing_concessions():
    state = STATE.model_copy(
        update={
            "forward_concessions": [
                ForwardConcession(id="fc", counterparty_id="BUYER-2", value_fen=AGG_CAP, label="prior")
            ]
        }
    )
    assert run([ob("o1")], [cv("o1", 0)], state=state) == []
    [v] = run([ob("o1")], [cv("o1", 1)], state=state)
    assert v.code == ViolationCode.AGG_CONCESSION_EXCEEDED
    assert v.inputs["existing"] == "¥5,000.00" and v.inputs["total_fen"] == str(AGG_CAP + 1)


def test_golden_package_breaches_the_cap():
    g = golden_values()
    obs = [ob("ext"), ob("rebate", Contingency.CONTINGENT, ObligationType.CONTINGENT_REBATE)]
    vals = [cv("ext", g["extension_committed_12m"]), cv("rebate", g["rebate_max"])]
    [v] = run(obs, vals)
    assert v.observed == "¥28,326.92" and v.limit == "¥5,000.00"


def test_firm_gain_netting_is_allowed():
    obs = [ob("conc"), ob("gain", Contingency.FIRM, ObligationType.PRICE_ADJUSTMENT)]
    vals = [cv("conc", AGG_CAP + 1_000), cv("gain", -1_000)]
    assert run(obs, vals) == []


def test_contingent_gain_netting_is_refused():
    obs = [ob("conc"), ob("gain", Contingency.CONTINGENT, ObligationType.PRICE_ADJUSTMENT)]
    vals = [cv("conc", AGG_CAP + 1_000), cv("gain", -1_000)]
    [v] = run(obs, vals)
    assert v.code == ViolationCode.AGG_CONCESSION_EXCEEDED
    assert v.inputs["contingent_gains_ignored"] == "−¥10.00"
    assert v.inputs["firm_gains_netted"] == "¥0.00"
    assert v.inputs["total_fen"] == str(AGG_CAP + 1_000)


def test_unevidenced_and_unmatched_gains_do_not_net():
    obs = [ob("conc"), ob("claim", Contingency.CLAIMED_UNEVIDENCED)]
    vals = [cv("conc", AGG_CAP + 1), cv("claim", -1), cv("orphan", -1)]
    assert codes(run(obs, vals)) == [ViolationCode.AGG_CONCESSION_EXCEEDED]


# ------------------------------------------------------------------ per-buyer cap

CAP_B1 = 200_000


def with_buyer_cap(cap=CAP_B1):
    return MANDATE.model_copy(update={"per_buyer_caps_fen": {BUYER: cap}})


@pytest.mark.parametrize("value, breach", [(CAP_B1, False), (CAP_B1 - 1, False), (CAP_B1 + 1, True)])
def test_per_buyer_cap_boundary(value, breach):
    vs = run([ob("o1")], [cv("o1", value)], mandate=with_buyer_cap())
    assert codes(vs) == ([ViolationCode.PER_BUYER_CAP_EXCEEDED] if breach else [])
    if breach:
        assert vs[0].inputs["counterparty_id"] == BUYER


def test_per_buyer_counts_only_that_buyers_existing_concessions():
    state = STATE.model_copy(
        update={
            "forward_concessions": [
                ForwardConcession(id="a", counterparty_id=BUYER, value_fen=CAP_B1, label="prior"),
                ForwardConcession(id="b", counterparty_id="BUYER-2", value_fen=-999_999, label="other"),
            ]
        }
    )
    mandate = with_buyer_cap().model_copy(update={"max_aggregate_forward_concession_fen": 10**9})
    assert run([ob("o1")], [cv("o1", 0)], state=state, mandate=mandate) == []
    assert codes(run([ob("o1")], [cv("o1", 1)], state=state, mandate=mandate)) == [
        ViolationCode.PER_BUYER_CAP_EXCEEDED
    ]


def test_per_buyer_cap_contingent_gain_does_not_net():
    obs = [ob("conc"), ob("gain", Contingency.CONTINGENT)]
    vals = [cv("conc", CAP_B1 + 1), cv("gain", -1)]
    assert codes(run(obs, vals, mandate=with_buyer_cap())) == [ViolationCode.PER_BUYER_CAP_EXCEEDED]
    obs_firm = [ob("conc"), ob("gain", Contingency.FIRM)]
    assert run(obs_firm, vals, mandate=with_buyer_cap()) == []


def test_no_per_buyer_cap_set_means_no_check():
    assert run([ob("o1")], [cv("o1", AGG_CAP)]) == []


# ------------------------------------------------------------------ immediate discount


@pytest.mark.parametrize("rate, breach", [(150, False), (120, False), (151, True)])
def test_immediate_discount_cap(rate, breach):
    o = ob("d", type_=ObligationType.IMMEDIATE_DISCOUNT, rate_bp=rate)
    vs = run([o], [cv("d", 0)])
    assert codes(vs) == ([ViolationCode.IMMEDIATE_DISCOUNT_EXCEEDED] if breach else [])
    if breach:
        assert vs[0].observed == "1.51%" and vs[0].limit == "1.50%" and vs[0].spans == [SPAN]


# ------------------------------------------------------------------ APR


def test_apr_cap():
    assert check_apr(Ratio.of(Fraction(1500, 10_000)), MANDATE, "at cap") is None
    v = check_apr(Ratio.of(Fraction(1501, 10_000)), MANDATE, "lender X")
    assert v is not None and v.code == ViolationCode.MAX_APR_EXCEEDED
    assert v.observed == "15.0100%" and v.limit == "15.00%"
    if_all_in = Fraction(780, 10_000) + Fraction(25, 10_000) * Fraction(365, 30)
    assert check_apr(Ratio.of(if_all_in), MANDATE, "invoice financing") is None
