"""The what-if sandbox runs the real verifier on typed, synthetic packages and reproduces the golden
verdicts. Display-only: nothing is written anywhere."""

from __future__ import annotations

import time

import pytest

from app.domain.models import ObligationType, Outcome
from app.verifier import evaluate
from app.whatif import PRESETS, WhatIfParamError, WhatIfParams, clear_cache, simulate
from app.whatif.offer import DOC_ID, build, context
from tests.verifier.conftest import compiled, declared_for

CONCESSION_CODES = {"AGG_CONCESSION_EXCEEDED", "PER_BUYER_CAP_EXCEEDED"}


def _types(r) -> list[str]:
    return [o["obligation_type"] for o in r.description["obligations"]]


# ---------------------------------------------------------------- golden reproduction


def test_buyer_offer_preset_reproduces_ex01(run, g):
    r = run(WhatIfParams(terms_days=60, discount_bp=120, rebate_bp=100))
    assert r.hypothetical is True
    assert r.outcome == "REJECT"
    assert r.codes == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert r.forward["total_fen"] == g["forward_ledger_total"] == 2_832_692
    assert r.forward["total_display"] == "¥28,326.92" and r.forward["cap_display"] == "¥5,000.00"
    assert r.forward["over_cap"] is True
    assert r.reserve["breach_day"] == 47 and r.reserve["curable"] is True
    assert r.reserve["cure_cost_fen"] == g["reserve_cure_cost_if"]
    assert r.trajectory is not None
    day47 = next(d for d in r.trajectory["days"] if d["day"] == 47)
    assert day47["closing"]["fen"] == g["cash_day47_60d_terms"] and day47["below_floor"] is True
    assert [c["label"] for c in r.counters] == ["Option A", "Option B"]  # Option B at 55 days (60 fails its re-check)


def test_buyer_offer_preset_matches_the_compiled_offer_verdict(run, state, mandate, key):
    """Same economics as the compiled EX01 text, same decision."""
    real = evaluate(compiled("EX01_PACKAGE"), state, mandate, trusted_owner_key_hex=key,
                    owner_declared=declared_for("EX01_PACKAGE")).verdict
    r = run("actual")
    assert r.outcome == real.outcome.value
    assert r.codes == list(dict.fromkeys(v.code.value for v in real.violations))
    assert r.forward["total_fen"] == real.forward_concession_total_fen
    assert [c["supplier_cost_fen"] for c in r.counters] == [c.supplier_cost_fen for c in real.counters]


def test_covenant_chips_and_break_even(run, g):
    r = run("actual")
    chips = {c["code"]: c for c in r.covenants}
    assert chips["DSCR_MIN"]["observed"] == g["dscr_after_extension"] + "x" and chips["DSCR_MIN"]["ok"]
    assert chips["LEVERAGE_MAX"]["observed"] == g["leverage_after_extension"] + "x" and chips["LEVERAGE_MAX"]["ok"]
    assert r.break_even is not None
    assert r.break_even["bp"] == g["break_even_discount_bp"] and r.break_even["display"] == "0.88%"
    assert r.break_even["discount_above"] is True  # 1.2% is dearer than financing the invoice
    assert run("option_a").break_even["discount_above"] is False  # 0.85% is below break-even


def test_option_a_is_not_rejected_for_concessions(run):
    r = run(WhatIfParams(terms_days=45, discount_bp=85, rebate_bp=0, settle_face_fen=25_720_000))
    assert not CONCESSION_CODES & set(r.codes)
    assert r.outcome != "REJECT"
    assert r.forward["total_fen"] == 0 and r.forward["over_cap"] is False
    assert r.params["effective_face_fen"] == 25_720_000 and r.params["effective_face_display"] == "¥257,200.00"


def test_option_b_nets_the_extension_with_the_price_adjustment(run):
    r = run("option_b")
    assert not CONCESSION_CODES & set(r.codes)
    # 55 days + 0.30%: extension ¥16,217.95 against the price adjustment's ¥16,380.00, net −¥162.05, floored at 0
    assert r.forward["total_fen"] == 0
    # The day-2 invoice pays on day 57 instead of 47: day 47 closes at 400,000 − 340,000 − 120,000 − 45,000 + 420,000
    # (RCV-A, day 32) − 100,000 = ¥215,000, ¥85,000 short until day 57, cured in time on the day-32 invoice: the owner
    # decides (it lengthens terms).
    assert r.outcome == "NEEDS_OWNER_APPROVAL" and r.codes == ["RESERVE_BREACH"]
    assert r.reserve["breach_day"] == 47 and r.reserve["curable"] is True


def test_the_60_day_package_fails_as_the_counter_property_says(run):
    """The 60-day package (the old Option B): day 60 closes at 215,000 − 45,000 = ¥170,000 before the day-62 receipt,
    with no admissible cure, so the verifier does not offer it."""
    r = run(WhatIfParams(terms_days=60, discount_bp=0, rebate_bp=0, price_adjustment_bp=45))
    assert r.outcome == "REJECT" and r.codes == ["RESERVE_BREACH"] and r.reserve["curable"] is False


def test_presets_are_the_verifiers_own_counters(state, mandate, key):
    """The Option A and Option B buttons move the sliders to the counters the verifier generated."""
    real = evaluate(compiled("EX01_PACKAGE"), state, mandate, trusted_owner_key_hex=key,
                    owner_declared=declared_for("EX01_PACKAGE"))
    a, b = real.verdict.counters
    (disc,) = [o for o in a.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    assert PRESETS["option_a"].discount_bp == disc.rate_bp
    assert PRESETS["option_a"].settle_face_fen == disc.base.amount_fen
    (price,) = [o for o in b.obligations if o.type == ObligationType.PRICE_ADJUSTMENT]
    (terms,) = [o for o in b.obligations if o.type == ObligationType.TERMS_EXTENSION]
    assert PRESETS["option_b"].price_adjustment_bp == price.rate_bp == 30
    assert PRESETS["option_b"].terms_days == 45 + (terms.days_delta or 0) == 55


@pytest.mark.parametrize("discount_bp", [0, 120])
def test_terms_at_current_means_no_extension(run, discount_bp):
    r = run(WhatIfParams(terms_days=45, discount_bp=discount_bp, rebate_bp=0))
    assert "TERMS_EXTENSION" not in _types(r)
    assert r.forward["total_fen"] == 0 and r.forward["total_display"] == "¥0.00"
    assert r.reserve["breach_day"] is None


def test_longer_terms_grow_the_forward_total(run):
    t60 = run(WhatIfParams(terms_days=60, discount_bp=0, rebate_bp=0)).forward["total_fen"]
    t90 = run(WhatIfParams(terms_days=90, discount_bp=0, rebate_bp=0)).forward["total_fen"]
    assert 0 < t60 < t90


def test_rebate_alone_over_the_cap(run):
    r = run(WhatIfParams(terms_days=45, discount_bp=0, rebate_bp=150))
    assert r.codes == ["AGG_CONCESSION_EXCEEDED"] and r.forward["total_fen"] == 600_000


# ---------------------------------------------------------------- the synthetic offer


def test_synthetic_offer_is_typed_with_exact_spans(state):
    ctx = context(state)
    offer, text = build(PRESETS["actual"], ctx)
    assert offer.doc_ids == [DOC_ID] and offer.compiler == "whatif-sandbox"
    assert [o.type for o in offer.obligations] == [
        ObligationType.IMMEDIATE_DISCOUNT, ObligationType.TERMS_EXTENSION, ObligationType.CONTINGENT_REBATE]
    for ob in offer.obligations:
        (sp,) = ob.spans
        assert sp.doc_id == DOC_ID and text[sp.start:sp.end] == sp.text
    disc, ext, reb = offer.obligations
    assert disc.base.receivable_id == "RCV-A" and disc.base.amount_fen == 42_000_000
    assert ext.days_delta == 15 and ext.target_terms_days == 60
    assert reb.base.amount_fen == 40_000_000  # the expected next-quarter order, counted at maximum


def test_face_above_the_invoice_is_refused(run):
    with pytest.raises(WhatIfParamError):
        run(WhatIfParams(terms_days=45, discount_bp=85, rebate_bp=0, settle_face_fen=42_010_000))


def test_no_change_package_evaluates(run):
    r = run("status_quo")
    assert r.description["obligations"] == [] and r.outcome == Outcome.ACCEPT.value


# ---------------------------------------------------------------- display rule, purity, cache


def _money_fields_have_displays(x, path="") -> list[str]:
    missing = []
    if isinstance(x, dict):
        for k, v in x.items():
            is_money = k.endswith("_fen") and isinstance(v, int) and not isinstance(v, bool)
            if is_money and k[:-4] + "_display" not in x:
                missing.append(f"{path}.{k}")
            missing += _money_fields_have_displays(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            missing += _money_fields_have_displays(v, f"{path}[{i}]")
    return missing


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_money_field_ships_a_display_string(run, preset):
    assert _money_fields_have_displays(run(preset).model_dump()) == []


def test_simulate_does_not_mutate_its_inputs(state, mandate, key):
    before = (state.model_dump_json(), mandate.model_dump_json())
    clear_cache()
    simulate(state, mandate, PRESETS["actual"], trusted_owner_key_hex=key)
    assert (state.model_dump_json(), mandate.model_dump_json()) == before


def test_cache_hits_are_fast_and_keyed_by_state(state, mandate, key):
    p = WhatIfParams(terms_days=55, discount_bp=40, rebate_bp=35)
    first = simulate(state, mandate, p, trusted_owner_key_hex=key)
    t = time.perf_counter()
    again = simulate(state, mandate, p, trusted_owner_key_hex=key)
    assert (time.perf_counter() - t) < 0.4
    assert again.cached and not first.cached and again.key == first.key
    other = state.model_copy(update={"cash_fen": state.cash_fen + 100})
    assert not simulate(other, mandate, p, trusted_owner_key_hex=key).cached


def test_equivalent_positions_share_a_cache_entry(run):
    a = run(WhatIfParams(terms_days=50, discount_bp=0, rebate_bp=0, settle_face_fen=10_000_000))
    b = run(WhatIfParams(terms_days=50, discount_bp=0, rebate_bp=0))
    assert a.key == b.key
