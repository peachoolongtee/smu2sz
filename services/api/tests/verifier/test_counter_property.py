"""The counter property (curable reading, decided 3 Oct): every counter a verdict offers, re-evaluated as an offer on
the same books it was built from (as the commit hook re-evaluates a commitment, `app.api.runtime.Runtime.reverify`),
gives ACCEPT or NEEDS_OWNER_APPROVAL, never REJECT, with no covenant breach and no MAX_APR_EXCEEDED; every
RESERVE_BREACH it shows is curable by an admissible committed plan, and a cure flagged "cannot run today" only
finances invoices issued (and, if already on the books, open and confirmed) by the first day of the shortfall.

Checked over every golden offer, the what-if presets and varied books (the world builder of
tests/funding/test_planner_executor_agree.py). The re-check and the rule here are built independently of the
verifier's own (`app.verifier.evaluate.counter_recheck`, `app.verifier.counters.infeasibility`)."""

from __future__ import annotations

import os
from dataclasses import replace
from types import SimpleNamespace

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
    FundingAction,
    FundingActionKind,
    Mandate,
    ObligationType,
    Outcome,
    Verdict,
)
from app.domain.money import bp, post
from app.verifier import evaluate, evaluate_verdict
from app.verifier.counters import late_legs
from app.whatif import PRESETS, WhatIfParamError, WhatIfParams
from app.whatif.offer import build as build_whatif
from app.whatif.offer import context as whatif_context
from tests.funding.test_planner_executor_agree import World, worlds
from tests.funding.test_planner_executor_agree import build as build_world
from tests.verifier.conftest import bundle

PASSING = {Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL}
FORBIDDEN = {"DSCR_BREACH", "LEVERAGE_BREACH", "CLEAN_DOWN_BREACH", "MAX_APR_EXCEEDED"}
GOLDEN = list(load_offers())


def as_offer(c: CounterProposal, day: int) -> CompiledOffer:
    """The counter's obligations as an offer, as `Runtime.reverify` builds one from a commitment."""
    return CompiledOffer(offer_id=f"REVERIFY-{c.id}", counterparty_id=c.obligations[0].counterparty_id,
                         doc_ids=sorted({sp.doc_id for o in c.obligations for sp in o.spans}), received_day=day,
                         status=CompileStatus.COMPILED, obligations=list(c.obligations), compiler="whatif-reverify",
                         prompt_version="reverify-v1")


def _issue_day(state: FinancialState, rid: str) -> int | None:
    r = next((x for x in state.receivables if x.id == rid), None)
    if r is not None:
        return r.issue_day if r.status == "OPEN" and r.confirmed else None
    return int(rid.rsplit(":", 1)[1]) if rid.startswith("RI:") else None


def assert_property(v: Verdict, state: FinancialState, mandate: Mandate, key: str, day: int = 0) -> None:
    for c in v.counters:
        r = evaluate_verdict(as_offer(c, day), state, mandate, trusted_owner_key_hex=key, day=day)
        got = [x.code.value for x in r.violations]
        assert r.outcome in PASSING, (v.offer_id, c.label, r.outcome, got)
        assert not FORBIDDEN & set(got), (v.offer_id, c.label, got)
        for x in r.violations:
            if x.code.value != "RESERVE_BREACH":
                continue
            assert x.curable and r.plan is not None and r.plan.admissible, (v.offer_id, c.label, x.cure_note)
            if not r.plan.executable_now:
                for a in r.plan.actions:
                    if a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
                        issue = _issue_day(state, a.receivable_id)
                        assert issue is not None and issue <= (x.day or 0), (v.offer_id, c.label, a.receivable_id)


@pytest.mark.parametrize("offer_id", GOLDEN)
def test_every_golden_counter_passes_its_own_recheck(offer_id, state, mandate, key):
    assert_property(bundle(offer_id).verdict, state, mandate, key)


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_whatif_preset_counter_passes_its_own_recheck(preset, state, mandate, key):
    offer, _ = build_whatif(PRESETS[preset], whatif_context(state))
    v = evaluate(offer, state, mandate, trusted_owner_key_hex=key, plans="committed").verdict
    assert_property(v, state, mandate, key)


def test_the_golden_counter_sets(g):
    """Option A is unchanged everywhere it was offered; EX01 adds the 55-day Option B; EX06 offers none."""
    got = {k: [c.label for c in bundle(k).verdict.counters] for k in GOLDEN}
    assert {k: v for k, v in got.items() if v} == {
        "EX01_PACKAGE": ["Option A", "Option B"], "EX01B_REWORDED": ["Option A", "Option B"],
        "EX02_EARLY_1_5": ["Option A"], "EX03_AS_USUAL": ["Option A"], "EX04_CLAIMED_REBATE": ["Option A"]}
    assert {bundle(k).verdict.counters[0].supplier_cost_fen for k in got if got[k]} == {g["counter_a_total"]}


@pytest.mark.parametrize("offer_id", ["EX01_PACKAGE", "EX01B_REWORDED"])
def test_ex01_offers_option_b_at_55_days(offer_id):
    """EX01 on the golden books (cash ¥400,000, reserve ¥300,000, RCV-A ¥420,000 due day 32, payroll ¥340,000 day 12,
    supplier ¥120,000 day 20, the equipment loan's ¥45,000 on days 30, 60, ..., the operating bill ¥100,000 day 47,
    and BUYER-1's ¥420,000 invoice issued day 2 on 45-day terms, paid day 47).

    Without the counter, day 47 closes at 400,000 − 340,000 − 120,000 − 45,000 + 420,000 − 100,000 + 420,000 =
    ¥635,000. With longer terms the day-2 invoice pays later, so day 47 closes at 635,000 − 420,000 = ¥215,000:
    ¥85,000 below the reserve.
    - 60 days (paid day 62): the day-60 payment also falls first, 215,000 − 45,000 = ¥170,000 (¥130,000 short to day
      61). The re-check finds no admissible cure on sources able to carry a permanent need: not offered.
    - 55 days (paid day 57, before the day-60 payment): ¥85,000 short on days 47-56. The re-check cures it with an
      advance of ¥88,113.93 (the router's figure) on the invoice issued day 32 (RI:BUYER-1:32, issued before the day-47
      shortfall, so the "cannot run today" cure can run in time), held 52 days and billed as 2 × 30-day periods:
      88,113.93 × 7.8% × 60/365 = 1,129.79 + 88,113.93 × 0.25% × 2 = 440.57 = ¥1,570.36. Re-check outcome
      NEEDS_OWNER_APPROVAL (it lengthens terms): offered.
    - Price step for +10 days: per invoice 420,000 × 10/365 × 10.8417% (FAC-IF all-in, 7.8% + 0.25% × 365/30) =
      ¥1,247.53 → smallest whole-5bp rate 0.30% (420,000 × 0.30% = ¥1,260.00; 0.25% gives ¥1,050.00). Over the 13
      invoices of the window: extension 13 × 1,247.5342 = 16,217.945 → ¥16,217.95; price 13 × 1,260 = ¥16,380.00;
      net −¥162.05, so supplier cost and forward value are 0.
    Counter A is unchanged (its face rounded to ¥10,000 since R-10): ¥260,000 at 0.85%, discount ¥2,210.00 + line 147,210.00 × 6.4% × 32/365 = ¥825.99 =
    ¥3,035.99."""
    v = bundle(offer_id).verdict
    assert v.outcome == Outcome.REJECT
    assert [x.code.value for x in v.violations] == [
        "AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    a, b = v.counters
    (disc,) = a.obligations
    assert (disc.base.amount_fen, disc.rate_bp, a.supplier_cost_fen) == (26_000_000, 85, 303_599)
    assert post(bp(85) * 26_000_000) + 82_599 == 303_599
    terms, price = b.obligations
    assert (b.label, terms.days_delta, price.rate_bp, price.base.amount_fen) == ("Option B", 10, 30, 42_000_000)
    assert b.text == "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate."
    assert "per-invoice funding cost ¥1,247.53: 0.30% → ¥1,260.00 per invoice" in b.formula
    assert "extension ¥16,217.95 + price adjustment −¥16,380.00 = −¥162.05" in b.formula
    assert b.supplier_cost_fen == b.forward_value_fen == 0
    assert post(bp(30) * 42_000_000) == 126_000 and 1_621_795 - 13 * 126_000 == -16_205
    assert round(88_113.93 * 0.078 * 60 / 365, 2) == 1_129.79 and round(88_113.93 * 0.0025 * 2, 2) == 440.57
    assert "The offered 60-day terms fail their own re-check; 55 days is the longest that passes." in b.rationale
    assert ("Price-adjustment counter at 55 days, not 60: 60-day terms cannot be funded from committed sources: the "
            "shortfall of ¥85,000.00 on day 47 has no cure.") in v.summary
    assert ("Option B passes its own re-check: its terms leave a shortfall of ¥85,000.00 on day 47, funded by the "
            "plan: committed plan: ¥1,570.36 (cannot run today).") in v.summary


def test_a_cure_that_cannot_run_by_the_shortfall_day_does_not_count(state):
    """The "cannot run today" rule: an advance on an invoice issued after the first day of the shortfall cannot
    have landed by then; one issued on or before it can. An advance on an issued invoice runs today."""
    def plan(rid: str) -> SimpleNamespace:
        return SimpleNamespace(executable_now=False, actions=[FundingAction(
            kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF", day=0, amount_fen=1, receivable_id=rid)])
    assert late_legs(plan("RI:BUYER-1:32"), state, 47) == []
    assert late_legs(plan("RI:BUYER-1:32"), state, 32) == []
    assert late_legs(plan("RI:BUYER-1:62"), state, 47) == ["RI:BUYER-1:62 is issued on day 62"]
    assert late_legs(SimpleNamespace(executable_now=True, actions=[]), state, 0) == []


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
