"""The counter property: every counter a verdict offers, re-evaluated as an offer on the same books it was built
from (as the commit hook re-evaluates a commitment, `app.api.runtime.Runtime.reverify`), gives ACCEPT or
NEEDS_OWNER_APPROVAL, never REJECT, and carries no RESERVE_BREACH (curable or not) and no covenant breach.

Checked over every golden offer, the what-if presets and varied books (the world builder of
tests/funding/test_planner_executor_agree.py). The re-check here is built independently of the verifier's own."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
from hypothesis import HealthCheck, assume, event, given, settings
from hypothesis import strategies as st

from app.domain.fixtures import load_offers
from app.domain.models import (
    CompiledOffer,
    CompileStatus,
    CounterProposal,
    Duration,
    DurationKind,
    FinancialState,
    Mandate,
    ObligationType,
    Outcome,
    Verdict,
)
from app.domain.money import bp, post
from app.verifier import evaluate, evaluate_verdict
from app.whatif import PRESETS, WhatIfParamError, WhatIfParams
from app.whatif.offer import build as build_whatif
from app.whatif.offer import context as whatif_context
from tests.funding.test_planner_executor_agree import World, worlds
from tests.funding.test_planner_executor_agree import build as build_world
from tests.verifier.conftest import bundle, compiled, declared_for

PASSING = {Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL}
FORBIDDEN = {"RESERVE_BREACH", "DSCR_BREACH", "LEVERAGE_BREACH", "CLEAN_DOWN_BREACH"}
GOLDEN = list(load_offers())


def as_offer(c: CounterProposal, day: int) -> CompiledOffer:
    """The counter's obligations as an offer, as `Runtime.reverify` builds one from a commitment."""
    return CompiledOffer(offer_id=f"REVERIFY-{c.id}", counterparty_id=c.obligations[0].counterparty_id,
                         doc_ids=sorted({sp.doc_id for o in c.obligations for sp in o.spans}), received_day=day,
                         status=CompileStatus.COMPILED, obligations=list(c.obligations), compiler="whatif-reverify",
                         prompt_version="reverify-v1")


def assert_property(v: Verdict, state: FinancialState, mandate: Mandate, key: str, day: int = 0) -> None:
    for c in v.counters:
        r = evaluate_verdict(as_offer(c, day), state, mandate, trusted_owner_key_hex=key, day=day)
        got = [x.code.value for x in r.violations]
        assert r.outcome in PASSING, (v.offer_id, c.label, r.outcome, got)
        assert not FORBIDDEN & set(got), (v.offer_id, c.label, got)


@pytest.mark.parametrize("offer_id", GOLDEN)
def test_every_golden_counter_passes_its_own_recheck(offer_id, state, mandate, key):
    assert_property(bundle(offer_id).verdict, state, mandate, key)


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_whatif_preset_counter_passes_its_own_recheck(preset, state, mandate, key):
    offer, _ = build_whatif(PRESETS[preset], whatif_context(state))
    v = evaluate(offer, state, mandate, trusted_owner_key_hex=key, plans="committed").verdict
    assert_property(v, state, mandate, key)


def test_the_golden_counters_that_remain(g):
    """Option A is unchanged everywhere it was offered; EX06 offers none (tests/verifier/test_golden_verdicts.py)."""
    got = {k: [c.label for c in bundle(k).verdict.counters] for k in GOLDEN}
    assert {k: v for k, v in got.items() if v} == {k: ["Option A"] for k in (
        "EX01_PACKAGE", "EX01B_REWORDED", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX04_CLAIMED_REBATE")}
    assert {bundle(k).verdict.counters[0].supplier_cost_fen for k in got if got[k]} == {g["counter_a_total"]}


def test_ex01_offers_option_a_only(g):
    """EX01 on the golden books (cash ¥400,000, reserve ¥300,000, RCV-A ¥420,000 due day 32, payroll ¥340,000 day 12,
    supplier ¥120,000 day 20, the equipment loan's ¥45,000 on days 30, 60, ..., the operating bill ¥100,000 day 47,
    and BUYER-1's ¥420,000 invoice issued day 2 on 45-day terms, paid day 47).

    Without the counter, day 47 closes at 400,000 − 340,000 − 120,000 − 45,000 + 420,000 − 100,000 + 420,000 =
    ¥635,000. Any of the price-adjustment counter's terms (60, then 55 and 50 days) moves the day-2 invoice to day 62,
    57 or 52, so day 47 closes at 635,000 − 420,000 = ¥215,000: ¥85,000 below the reserve, and below the no-counter
    day, with no new funding. Under 60 days the day-60 payment also falls before the receipt: 215,000 − 45,000 =
    ¥170,000, ¥130,000 below. The price adjustment (0.45% at 60 days) only changes invoices received after day 47.
    So no price-adjustment counter is offered and the verdict says why; Counter A is unchanged: ¥257,200 at 0.85%,
    discount 257,200 × 0.85% = ¥2,186.20 + line 149,986.20 × 6.4% × 32/365 = ¥841.57 = ¥3,027.77."""
    v = bundle("EX01_PACKAGE").verdict
    assert v.outcome == Outcome.REJECT
    assert [x.code.value for x in v.violations] == [
        "AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    (a,) = v.counters
    (disc,) = a.obligations
    assert (disc.base.amount_fen, disc.rate_bp, a.supplier_cost_fen) == (25_720_000, 85, 302_777)
    assert post(bp(85) * 25_720_000) + 84_157 == 302_777
    assert (40_000_000 - 34_000_000 - 12_000_000 - 4_500_000 + 42_000_000 - 10_000_000) == 21_500_000
    assert 30_000_000 - 21_500_000 == 8_500_000 and 30_000_000 - (21_500_000 - 4_500_000) == 13_000_000
    assert ("No price-adjustment counter: 60-day terms would take cash below the reserve with no new funding: a "
            "shortfall of ¥85,000.00 on day 47 (at most ¥130,000.00, day 60); 55- or 50-day terms would take cash "
            "below the reserve with no new funding: a shortfall of ¥85,000.00 on day 47.") in v.summary


def test_the_longest_shorter_terms_that_pass_are_offered(state, mandate, key):
    """Without the day-47 bill, 60-day terms still fail and 55 days pass, so Option B is offered at 55 days.

    Day 32 closes at 400,000 − 340,000 − 120,000 − 45,000 + 420,000 = ¥315,000 and stays there to day 60. At 60 days
    the day-2 invoice pays on day 62, after the loan's day-60 ¥45,000: day 60 closes at ¥270,000, ¥30,000 below the
    reserve. At 55 days it pays on day 57, before it. The price step is re-sized for +10 days: per invoice
    420,000 × 10/365 × 10.8417% (the committed marginal all-in rate, 7.8% + 0.25% × 365/30) = ¥1,247.53; the smallest
    whole-5bp rate covering it is 0.30% (420,000 × 0.30% = ¥1,260.00; 0.25% gives ¥1,050.00). Over the 13 invoices
    of the window: 13 × 1,247.5342 = 16,217.945 → ¥16,217.95 (the extension's value, rounded once) against
    13 × 1,260 = ¥16,380.00, a net gain of ¥162.05, so the supplier cost and forward value are 0."""
    s = state.model_copy(update={"flows": [f for f in state.flows if f.id != "F-BILL47"]})
    v = evaluate(compiled("EX01_PACKAGE"), s, mandate, trusted_owner_key_hex=key,
                 owner_declared=declared_for("EX01_PACKAGE")).verdict
    b = next(c for c in v.counters if any(o.type == ObligationType.PRICE_ADJUSTMENT for o in c.obligations))
    terms, price = b.obligations
    assert terms.days_delta == 10 and price.rate_bp == 30
    assert b.text == "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate."
    assert "per-invoice funding cost ¥1,247.53: 0.30% → ¥1,260.00 per invoice" in b.formula
    assert "extension ¥16,217.95 + price adjustment −¥16,380.00 = −¥162.05" in b.formula
    assert b.supplier_cost_fen == b.forward_value_fen == 0
    assert "Funded on current books with these terms by the router's committed plan (" in b.formula
    assert "The offered 60-day terms fail their own re-check; 55 days is the longest that passes." in b.rationale
    assert_property(v, s, mandate, key)


# ---------------------------------------------------------------- varied books

EXAMPLES = int(os.environ.get("COUNTER_EXAMPLES", "30"))
PROPS = settings(max_examples=EXAMPLES, deadline=None,
                 suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much])


@st.composite
def packages(draw: st.DrawFn) -> tuple[WhatIfParams, bool]:
    """A typed buyer package for the world's buyer (the what-if builder, so it binds on any books) and whether its
    terms extension is bounded to three invoices (the bounded-extension counters) instead of perpetual."""
    params = WhatIfParams(terms_days=draw(st.sampled_from([45, 50, 60, 75, 90])),
                          discount_bp=draw(st.sampled_from([0, 85, 120, 150])),
                          rebate_bp=draw(st.sampled_from([0, 0, 100])))
    return params, draw(st.booleans())


def typed_offer(params: WhatIfParams, bounded: bool, state: FinancialState, day: int) -> CompiledOffer:
    offer, _ = build_whatif(params, whatif_context(state, day), day)
    if not bounded or not any(o.type == ObligationType.TERMS_EXTENSION for o in offer.obligations):
        return offer
    obs = [o.model_copy(update={"duration": Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3)})
           if o.type == ObligationType.TERMS_EXTENSION else o
           for o in offer.obligations if o.type != ObligationType.IMMEDIATE_DISCOUNT]
    return offer.model_copy(update={"obligations": obs})


@PROPS
@given(w=worlds(), pkg=packages())
def test_counters_pass_their_own_recheck_on_varied_books(w: World, pkg: tuple[WhatIfParams, bool]) -> None:
    if w.recurring is None:  # the packages are the buyer's: it needs a recurring invoice
        w = replace(w, recurring=(42_000_000, 2, 45))
    rt = build_world(w)
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    try:
        offer = typed_offer(*pkg, state, rt.day)
    except WhatIfParamError:  # the world has no open receivable for the buyer by now
        assume(False)
    v = evaluate(offer, state, mandate, trusted_owner_key_hex=rt.owner_key_hex, day=rt.day, plans="committed").verdict
    event(f"{v.outcome.value} with {len(v.counters)} counter(s)")
    for c in v.counters:
        event("offered: " + "+".join(sorted({o.type.value for o in c.obligations})))
    for note in v.summary.split(". "):
        if note.startswith("No ") and " counter" in note:
            event("not offered: " + note.split(" counter")[0].removeprefix("No "))
    assert_property(v, state, mandate, rt.owner_key_hex, rt.day)
