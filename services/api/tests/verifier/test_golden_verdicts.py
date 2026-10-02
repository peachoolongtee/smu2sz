"""Exact golden values (fixtures/golden/golden_values.json) through the whole verdict."""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.domain.models import FacilityKind, ObligationType, Outcome, Tier, ViolationCode
from app.domain.money import fmt_yuan
from app.financial import finance_invoice_charges
from app.verifier import CALC_VERSION, evaluate, evaluate_term_sheet
from tests.verifier.conftest import bundle, codes, compiled, compiled_term_sheet, declared_for

EX01 = ("EX01_PACKAGE", "EX01B_REWORDED")


def _by_type(b, t: ObligationType):
    ob = next(o for o in b.bound_obligations if o.type == t)
    return ob, next(cv for cv in b.verdict.concession_values if cv.obligation_id == ob.id)


def _reserve(v):
    return next(x for x in v.violations if x.code == ViolationCode.RESERVE_BREACH)


# ---------------------------------------------------------------- EX01 / EX01B


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_reject_codes_and_forward_ledger(offer_id, g):
    v = bundle(offer_id).verdict
    assert v.outcome == Outcome.REJECT
    # 1.2% early settlement is above the 0.88% break-even, which is why Option A is priced at 0.85%.
    assert codes(v.violations) == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert v.forward_concession_total_fen == g["forward_ledger_total"]
    agg = v.violations[0]
    assert agg.inputs["total_fen"] == str(g["forward_ledger_total"])
    assert agg.limit == "¥5,000.00" and agg.observed == "¥28,326.92"
    assert v.calc_version == CALC_VERSION == "tl-v2.0"
    assert v.required_tier == Tier.TIER_1
    assert all(x.formula and x.inputs for x in v.violations)


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_concession_values(offer_id, g):
    b = bundle(offer_id)
    ext, ext_v = _by_type(b, ObligationType.TERMS_EXTENSION)
    assert ext.days_delta == 15
    assert ext_v.value_fen == g["extension_committed_12m"]
    assert ext_v.per_invoice_fen == g["extension_committed_per_invoice"]
    assert "13 invoices" in ext_v.formula  # the window holds 13 invoices (issue days 2, 32, ..., 362)
    _, rebate_v = _by_type(b, ObligationType.CONTINGENT_REBATE)
    assert rebate_v.value_fen == g["rebate_max"]
    disc, disc_v = _by_type(b, ObligationType.IMMEDIATE_DISCOUNT)
    assert disc.base.receivable_id == "RCV-A" and disc.effective_day == 2 and disc_v.value_fen == 0


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_reserve_breach_day_47_curable(offer_id, g, state):
    b = bundle(offer_id)
    rb = _reserve(b.verdict)
    assert rb.day == 47 and rb.curable is True
    # 354,960 on day 20 − the existing loan's 45,000 on day 30 − the 100,000 bill = 209,960 on day 47; the deepest is
    # day 60, after the next 45,000 payment: 164,960, short 135,040 (compute_golden.py reserve_shortfall_max)
    assert rb.observed == "¥209,960.00"
    assert int(rb.inputs["shortfall_fen"]) == g["reserve_shortfall_day47"]
    assert rb.inputs["max_shortfall"] == "¥135,040.00" and rb.inputs["max_shortfall_day"] == "60"
    assert g["reserve_shortfall_max"] == 13_504_000
    assert b.trajectory is not None and b.trajectory.days[47].closing_fen == g["cash_day47_60d_terms"]
    assert b.trajectory.days[20].closing_fen == g["cash_day20"]
    # The cure uses only sources able to carry a permanent need: invoice financing, never the line.
    assert b.cure_plan is not None and b.cure_plan.admissible
    kinds = {f.kind for f in state.facilities for a in b.cure_plan.actions if a.facility_id == f.id}
    assert kinds == {FacilityKind.INVOICE_FINANCING}
    (adv,) = b.cure_plan.actions
    assert adv.amount_fen == g["reserve_shortfall_max"]  # the deepest shortfall (day 60), not day 47's
    # requested day 0 (ADR-0003), lands day 5 against the day-2 invoice, repaid day 62: 57 days = 2 periods:
    # 135,040 × 7.8% × 60/365 = 1,731.47 + 135,040 × 0.25% × 2 = 675.20 -> 2,406.67
    fac = next(f for f in state.facilities if f.id == "FAC-IF")
    interest, fee, periods = finance_invoice_charges(fac, g["reserve_shortfall_max"], 62 - 5)
    assert periods == 2
    assert rb.cure_cost_fen == b.cure_plan.total_cost_fen == interest + fee == g["reserve_cure_cost_if"] == 240_667
    assert "Invoice financing" in (rb.cure_note or "")
    assert rb.inputs["structural_cost_per_invoice"] == "¥1,871.30"  # extension_committed_per_invoice
    assert b.verdict.plan == b.cure_plan


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_covenants_hold_pro_forma(offer_id, g):
    b = bundle(offer_id)
    passed = {p.code: p for p in b.passed_checks}
    assert passed["DSCR_MIN"].observed == f"{g['dscr_after_extension']}x"
    assert passed["LEVERAGE_MAX"].observed == f"{g['leverage_after_extension']}x"
    assert passed["DSCR_MIN"].limit == "≥ 1.25x" and passed["LEVERAGE_MAX"].limit == "≤ 2.50x"
    assert passed["CLEAN_DOWN"].code == "CLEAN_DOWN"
    assert passed["DSCR_MIN"].inputs["extra_receivables"] == fmt_yuan(g["extension_extra_receivables"])
    assert passed["DSCR_MIN"].inputs["extra_monthly_debt_service"] == fmt_yuan(g["extension_monthly_service"])
    rb = _reserve(b.verdict)
    assert rb.inputs["covenant_pro_forma_dscr"] == "1.92x"
    assert rb.inputs["covenant_pro_forma_leverage"] == "1.72x"
    assert "DSCR_MIN 1.92x" in b.verdict.summary and "LEVERAGE_MAX 1.72x" in b.verdict.summary
    assert "MAX_APR" in passed  # 1.2% for 30 days ≈ 14.78% a year, inside the 15% maximum


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_counter_a(offer_id, g):
    a = bundle(offer_id).verdict.counters[0]
    assert a.label == "Option A"
    assert a.supplier_cost_fen == g["counter_a_total"]
    (ob,) = a.obligations
    assert ob.type == ObligationType.IMMEDIATE_DISCOUNT and ob.rate_bp == 85
    assert ob.base.amount_fen == g["counter_a_face"] == 25_720_000
    assert ob.base.receivable_id == "RCV-A" and ob.effective_day == 2
    assert a.text == ("Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥257,200 "
                      "of this invoice at 0.85%.")
    assert "¥2,186.20" in a.formula and "¥841.57" in a.formula  # counter_a_discount + the router plan's funding cost
    assert "0.8832%" in a.formula and "¥257,186.08" in a.formula
    assert all(sp.text == a.text[sp.start:sp.end] for sp in ob.spans)


@pytest.mark.parametrize("offer_id", EX01)
def test_ex01_counter_b(offer_id, g):
    b = bundle(offer_id).verdict.counters[1]
    assert b.label == "Option B"
    terms, price = b.obligations
    assert terms.type == ObligationType.TERMS_EXTENSION and terms.days_delta == 15
    assert price.type == ObligationType.PRICE_ADJUSTMENT and price.rate_bp == 45
    assert price.base.amount_fen == 42_000_000 and price.contingency.value == "FIRM"
    assert b.text == "60-day terms accepted with a 0.45% price adjustment on future invoices, no rebate."
    assert f"¥{g['counter_b_price_adj_per_invoice'] // 100:,}.00 per invoice" in b.formula
    assert "¥1,871.30" in b.formula
    assert b.supplier_cost_fen == 0 and g["counter_b_net_12m"] < 0  # the price adjustment more than covers the cost


def _normalise(x: Any, ids: set[str]) -> Any:
    if isinstance(x, dict):
        return {k: _normalise(v, ids) for k, v in x.items()
                if k not in {"id", "offer_id", "obligation_id", "spans", "doc_id", "confidence"}}
    if isinstance(x, list):
        return [_normalise(v, ids) for v in x]
    if isinstance(x, str):
        for i in ids:
            x = x.replace(i, "<id>")
        return x
    return x


def test_ex01_wording_invariance():
    a, b = bundle("EX01_PACKAGE").verdict, bundle("EX01B_REWORDED").verdict
    ids = {a.id, b.id, a.offer_id, b.offer_id}
    assert _normalise(a.model_dump(mode="json"), ids) == _normalise(b.model_dump(mode="json"), ids)
    assert a.id != b.id


def test_ex01_evaluates_under_two_seconds(state, mandate, key):
    offer = compiled("EX01_PACKAGE")
    t0 = time.perf_counter()
    evaluate(offer, state, mandate, trusted_owner_key_hex=key, owner_declared=declared_for("EX01_PACKAGE"))
    assert time.perf_counter() - t0 < 2.0


# ---------------------------------------------------------------- EX02 / EX03


@pytest.mark.parametrize("offer_id", ["EX02_EARLY_1_5", "EX03_AS_USUAL"])
def test_early_pay_offers_counter_at_85bp(offer_id, g):
    b = bundle(offer_id)
    v = b.verdict
    assert v.outcome == Outcome.COUNTER
    # 1.5% is above the 0.88% break-even, and 1.5% for 30 days ≈ 18.53% a year is above the 15% APR cap
    assert codes(v.violations) == ["DISCOUNT_ABOVE_BREAK_EVEN", "MAX_APR_EXCEEDED", "EARLY_PAY_DEARER_THAN_PLAN"]
    apr = v.violations[0]
    assert apr.inputs["days_early"] == "30"
    assert apr.inputs["line_plus_partial_at_offered_rate"].endswith(
        f"¥{g['example2_line_plus_partial_1_5pct'] // 100:,}.{g['example2_line_plus_partial_1_5pct'] % 100:02d}")
    assert apr.inputs["router_optimum"].endswith("¥3,113.93")
    (a,) = v.counters
    assert a.obligations[0].rate_bp == 85 and a.obligations[0].base.amount_fen == g["counter_a_face"]
    assert a.supplier_cost_fen == g["counter_a_total"]
    assert a.text == "We will accept early settlement on up to ¥257,200 of this invoice at 0.85%. Nothing else changes."
    assert len(b.bound_obligations) == 1 and v.forward_concession_total_fen == 0


def test_ex03_books_nothing_for_as_usual():
    b = bundle("EX03_AS_USUAL")
    assert [o.type for o in b.bound_obligations] == [ObligationType.IMMEDIATE_DISCOUNT]
    assert "Unresolved reference flagged" in b.verdict.summary


# ---------------------------------------------------------------- EX04 / EX05 / EX06


def test_ex04_rejects_claim_and_counters_without_the_rebate():
    b = bundle("EX04_CLAIMED_REBATE")
    v = b.verdict
    assert v.outcome == Outcome.REJECT and codes(v.violations) == ["UNEVIDENCED_PRIOR_CONCESSION"]
    assert v.violations[0].spans[0].text == "the 2% rebate we agreed last month"
    assert [e.kind.value for e in b.security_events] == ["UNEVIDENCED_CLAIM"]
    (c,) = v.counters
    assert not [o for o in c.obligations if o.type in (ObligationType.CONTINGENT_REBATE,
                                                        ObligationType.PRICE_ADJUSTMENT)]
    assert "2%" not in c.text and c.text.startswith("No rebate is on record")


def test_ex05_accepts_net_firm_gain(g):
    b = bundle("EX05_CONSOLIDATE")
    v = b.verdict
    assert v.outcome == Outcome.NEEDS_OWNER_APPROVAL and v.violations == []
    assert v.required_tier == Tier.TIER_2  # a shorter term is a gain, but only early pay is accepted at Tier 1
    op, op_v = _by_type(b, ObligationType.OPERATIONAL_CONCESSION)
    assert op.amount_fen == 15_000 and op.base.events_per_year == 52 and op_v.value_fen == 780_000
    ext, ext_v = _by_type(b, ObligationType.TERMS_EXTENSION)
    assert ext.days_delta == -15 and ext_v.value_fen == g["extension_shortening_gain_12m"] == -g["extension_committed_12m"]
    assert v.forward_concession_total_fen == 0  # a net FIRM gain adds nothing to the ledger


def test_ex06_bounded_extension(g):
    v = bundle("EX06_THREE_INVOICES").verdict
    assert v.outcome == Outcome.REJECT and "AGG_CONCESSION_EXCEEDED" in codes(v.violations)
    assert v.forward_concession_total_fen == 561_390 == 3 * g["extension_committed_per_invoice"]
    a, b = v.counters
    assert a.text == "We can extend terms by 15 days on the next two invoices."
    assert a.supplier_cost_fen == 2 * g["extension_committed_per_invoice"]
    assert a.obligations[0].duration.invoices == 2
    assert b.text == "We can extend terms by 15 days on the next three invoices if the 0.50% credit is firm on each of them."
    credit = b.obligations[1]
    assert credit.contingency.value == "FIRM" and credit.duration.invoices == 3 and credit.rate_bp == 50


# ---------------------------------------------------------------- EX09 term sheet


def test_ex09_term_sheet_shows_all_in_rate(state, mandate, key):
    v = evaluate_term_sheet(compiled_term_sheet("EX09_TERM_SHEET_PG"), state, mandate, trusted_owner_key_hex=key)
    assert v.outcome == Outcome.REJECT and v.required_tier == Tier.TIER_3
    (pg,) = v.violations
    assert pg.code == ViolationCode.TIER3_PERSONAL_GUARANTEE
    assert pg.observed == "5.90%" and pg.inputs["headline_rate"] == "3.90%"
    assert "5.90% all-in, not 3.90%" in pg.message and "All-in 5.90%" in v.summary
    assert pg.spans and pg.spans[0].text.endswith("personal guarantee")
    assert v.counters == [] and v.calc_version == "tl-v2.0"
