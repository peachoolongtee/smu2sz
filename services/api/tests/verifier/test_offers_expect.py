"""Every `expect` block in fixtures/offers/offers.yaml (except the owner requests EX11 and EX12, which
are not offers) is a required verdict. EX09 is a term sheet and EX08 is concurrent: both have their
own entry points and are checked here too."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_offers, load_scenario
from app.domain.models import Outcome, ViolationCode
from app.verifier import evaluate_many, evaluate_term_sheet
from tests.verifier.conftest import bundle, codes, compiled, compiled_term_sheet

OFFERS = load_offers()
SINGLE = [k for k, o in OFFERS.items()
          if o.get("kind") is None and "concurrent_with" not in o["expect"]]
EXACT_CODES = {"EX10_FASTCAPITAL", "SEC_DEMO_FASTCAPITAL", "EX01_PACKAGE", "EX01B_REWORDED", "EX04_CLAIMED_REBATE",
               "EX07_CONFLICT"}


def expect(offer_id: str) -> dict:
    e = OFFERS[offer_id]["expect"]
    return OFFERS[e["same_as"]]["expect"] if "same_as" in e else e


def test_every_offer_example_is_covered():
    covered = set(SINGLE) | {"EX08A_JOINT_BUYER1", "EX08B_JOINT_BUYER2", "EX09_TERM_SHEET_PG"}
    assert covered == set(OFFERS) - {"EX11_CAPEX", "EX12_GOAL"}


@pytest.mark.parametrize("offer_id", SINGLE)
def test_outcome(offer_id):
    assert bundle(offer_id).verdict.outcome.value == expect(offer_id)["outcome"]


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if "codes" in expect(k)])
def test_codes(offer_id):
    got = codes(bundle(offer_id).verdict.violations)
    want = expect(offer_id)["codes"]
    if offer_id in EXACT_CODES:
        assert got == want
    else:
        assert set(want) <= set(got)


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if "obligations" in expect(k)])
def test_obligation_types(offer_id):
    b = bundle(offer_id)
    assert sorted(o.type.value for o in b.bound_obligations) == sorted(expect(offer_id)["obligations"])


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if "forward_concession_total_fen" in expect(k)])
def test_forward_concession_total(offer_id):
    assert bundle(offer_id).verdict.forward_concession_total_fen == expect(offer_id)["forward_concession_total_fen"]


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if expect(k).get("booked") == 0])
def test_nothing_booked(offer_id):
    b = bundle(offer_id)
    assert b.bound_obligations == []
    assert b.verdict.forward_concession_total_fen == 0
    assert all(cv.value_fen == 0 for cv in b.verdict.concession_values)


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if "counters" in expect(k)])
def test_counter_labels(offer_id):
    assert [c.label for c in bundle(offer_id).verdict.counters] == expect(offer_id)["counters"]


@pytest.mark.parametrize("offer_id", [k for k in SINGLE if "reserve_breach_day" in expect(k)])
def test_reserve_breach_day(offer_id):
    rb = [v for v in bundle(offer_id).verdict.violations if v.code == ViolationCode.RESERVE_BREACH]
    assert [v.day for v in rb] == [expect(offer_id)["reserve_breach_day"]]


def test_ex02_counter_rate_and_face_cap():
    e = expect("EX02_EARLY_1_5")
    (a,) = bundle("EX02_EARLY_1_5").verdict.counters
    (ob,) = a.obligations
    assert ob.rate_bp == e["counter_rate_bp"] and ob.base.amount_fen == e["counter_face_cap_fen"]


def test_ex02_plan_comparison():
    e = expect("EX02_EARLY_1_5")
    rows = {r.key: r for r in bundle("EX02_EARLY_1_5").comparison}
    assert rows["line_partial_early_pay"].cost_fen == e["line_plus_partial_fen"]
    selected = [r for r in rows.values() if r.result.value == "SELECTED"]
    assert [r.cost_fen for r in selected] == [e["router_best_fen"]]


def test_ex03_unresolved_reference():
    b = bundle("EX03_AS_USUAL")
    refs = [n for n in b.notes if n.field == "unresolved_reference"]
    assert refs and not refs[0].material and not refs[0].resolved
    assert expect("EX03_AS_USUAL")["unresolved"] == ["as usual"]


def test_ex05_funding_saved():
    b = bundle("EX05_CONSOLIDATE")
    ext = next(o for o in b.bound_obligations if o.type.value == "TERMS_EXTENSION")
    cv = next(cv for cv in b.verdict.concession_values if cv.obligation_id == ext.id)
    assert -cv.value_fen == expect("EX05_CONSOLIDATE")["funding_saved_12m_fen"]


def test_ex07_clarification():
    v = bundle("EX07_CONFLICT").verdict
    assert expect("EX07_CONFLICT")["clarification"] is True
    assert "Clarification requested" in v.summary
    assert v.violations[0].inputs["clarification"] == "requested"


def test_ex08_concurrent(state, mandate, key):
    a, b = evaluate_many([compiled("EX08A_JOINT_BUYER1"), compiled("EX08B_JOINT_BUYER2")], state, mandate,
                         trusted_owner_key_hex=key)
    ea, eb = expect("EX08A_JOINT_BUYER1"), expect("EX08B_JOINT_BUYER2")
    assert a.verdict.outcome.value == ea["outcome"]
    assert b.verdict.outcome.value == eb["outcome"]
    assert codes(b.verdict.violations) == eb["codes"]


def test_ex09_term_sheet(state, mandate):
    e = expect("EX09_TERM_SHEET_PG")
    v = evaluate_term_sheet(compiled_term_sheet("EX09_TERM_SHEET_PG"), state, mandate)
    assert v.outcome.value == e["outcome"]
    assert codes(v.violations) == e["codes"]
    ts = compiled_term_sheet("EX09_TERM_SHEET_PG")
    assert ts.all_in_rate_bp == e["all_in_rate_bp"]


@pytest.mark.parametrize("offer_id", ["EX10_FASTCAPITAL", "SEC_DEMO_FASTCAPITAL"])
def test_security_offers_add_nothing(offer_id, state):
    b = bundle(offer_id)
    e = expect(offer_id)
    assert e["facilities_added"] == 0 and e["booked"] == 0
    assert b.verdict.outcome == Outcome.REJECT
    assert b.trajectory is None and b.plan_committed is None and b.verdict.plan is None
    assert b.verdict.counters == []
    assert state == load_scenario()[0]  # the input state is never modified
    assert not [f for f in state.facilities if "FAST" in f.lender_id.upper()]
