"""`Verdict.bound_obligations` (what was verified) and `CounterProposal.forward_value_fen` (what a
commitment on a counter books), on the worked examples."""

from __future__ import annotations

import pytest

from app.domain.models import Contingency, ObligationType, Outcome
from app.financial import value_concessions
from app.funding import marginal_cost
from app.verifier import evaluate
from app.verifier.counters import counters
from tests.verifier.conftest import bundle, compiled

T = ObligationType


@pytest.mark.parametrize("offer_id", ["EX01_PACKAGE", "EX01B_REWORDED", "EX02_EARLY_1_5", "EX05_CONSOLIDATE",
                                      "EX06_THREE_INVOICES"])
def test_verdict_carries_exactly_the_verified_bound_obligations(offer_id):
    b = bundle(offer_id)
    v = b.verdict
    assert v.bound_obligations == b.bound_obligations
    assert [cv.obligation_id for cv in v.concession_values] == [o.id for o in v.bound_obligations]
    # Only a contingent gain (counted as zero, e.g. EX06's loyalty credit) may keep an open base.
    assert all(o.unresolved == [] or (o.type == T.PRICE_ADJUSTMENT and o.contingency != Contingency.FIRM)
               for o in v.bound_obligations)
    assert all(o.contingency != Contingency.CLAIMED_UNEVIDENCED for o in v.bound_obligations)


def test_bound_obligations_are_bound_not_raw():
    v = bundle("EX01_PACKAGE").verdict
    raw = {o.type: o for o in compiled("EX01_PACKAGE").obligations}
    bound = {o.type: o for o in v.bound_obligations}
    assert raw[T.TERMS_EXTENSION].days_delta is None and bound[T.TERMS_EXTENSION].days_delta == 15
    assert raw[T.CONTINGENT_REBATE].base.amount_fen is None and bound[T.CONTINGENT_REBATE].base.amount_fen == 40_000_000
    assert raw[T.IMMEDIATE_DISCOUNT].base.receivable_id is None
    assert bound[T.IMMEDIATE_DISCOUNT].base.receivable_id == "RCV-A"


@pytest.mark.parametrize("offer_id", ["EX04_CLAIMED_REBATE", "EX07_CONFLICT", "EX10_FASTCAPITAL",
                                      "SEC_DEMO_FASTCAPITAL"])
def test_nothing_is_bound_when_nothing_was_verified(offer_id):
    assert bundle(offer_id).verdict.bound_obligations == []


def test_ex05_without_declared_costs_binds_nothing(state, mandate, key):
    v = evaluate(compiled("EX05_CONSOLIDATE"), state, mandate, trusted_owner_key_hex=key).verdict
    assert v.outcome == Outcome.NO_VERDICT and v.bound_obligations == []


def _values(obs, state, mandate):
    rate, _ = marginal_cost(state, mandate)
    return [cv.value_fen for cv in value_concessions(obs, state, rate, "test", mandate.forward_concession_horizon_days)]


@pytest.mark.parametrize("offer_id", ["EX01_PACKAGE", "EX01B_REWORDED"])
def test_ex01_counter_forward_values(offer_id, g, state, mandate):
    a, b = bundle(offer_id).verdict.counters
    # Option A: an immediate discount is not a forward concession; its cost is immediate.
    assert a.forward_value_fen == 0 and a.supplier_cost_fen == g["counter_a_total"]
    # Option B (55 days + 0.30%; 60 days fails its own re-check, tests/verifier/test_counter_property.py): the
    # extension net of the FIRM price adjustment on the same 13 invoices of the window. Extension: 13 × 420,000 ×
    # 10/365 × 10.8417% = 16,217.945 → ¥16,217.95; price: 13 × 420,000 × 0.30% = ¥16,380.00; net −¥162.05, floored at 0.
    ext_v, price_v = _values(b.obligations, state, mandate)
    assert (ext_v, price_v) == (1_621_795, -1_638_000)
    assert ext_v + price_v == -16_205
    assert b.forward_value_fen == max(0, ext_v + price_v) == 0


def test_ex02_counter_books_no_forward_value(g):
    (a,) = bundle("EX02_EARLY_1_5").verdict.counters
    assert a.forward_value_fen == 0 and a.supplier_cost_fen == g["counter_a_total"]


def test_ex06_bounded_counters_are_valued_but_not_offered(g, state, mandate):
    """Both bounded-extension counters are still valued as before; neither is offered, because each fails its own
    re-check on these books (a +15-day extension of the day-2 invoice leaves day 47 ¥85,000 below the reserve, with
    no admissible cure)."""
    b = bundle("EX06_THREE_INVOICES")
    assert b.verdict.counters == []
    a, firm = counters(compiled("EX06_THREE_INVOICES"), b.verdict, state, mandate, bound=b.bound_obligations)
    assert a.forward_value_fen == 2 * g["extension_committed_per_invoice"] == a.supplier_cost_fen
    net = sum(_values(firm.obligations, state, mandate))
    assert firm.forward_value_fen == max(0, net) == firm.supplier_cost_fen
    assert all(o.contingency == Contingency.FIRM for o in firm.obligations)


def test_counters_fit_the_cap_with_their_forward_value(mandate):
    for offer_id in ("EX01_PACKAGE", "EX02_EARLY_1_5", "EX06_THREE_INVOICES"):
        for c in bundle(offer_id).verdict.counters:
            assert 0 <= c.forward_value_fen <= mandate.max_aggregate_forward_concession_fen, (offer_id, c.label)
