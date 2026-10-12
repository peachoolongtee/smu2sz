"""The envelope's economics line (ticket #98 with #97's envelope items; brief E.3 "Class 3 plus economics", C.2).

Only with FEATURE_CUSTOMER_ECONOMICS on and a contribution held, and only on the class-3 package: the verdict's own forward
concession on a 12-month basis over a year's gross profit, read through the Customer overview's one margin and contribution
function (`customer_overview.year_held`, `twelve_months_of`), never a second computation. A sentence of its own after the
mandate's: it changes no class, outcome, tier, code, counter, cap or plan (property P8), and it never says profit, profitable
or worth.

Golden: ¥16,217.95 over ¥1,092,000 (¥5,460,000 projected from the books at the Demo's 20%) is 1.49%, "about 1.5%". In Chinese the
buyer keeps the name the books give it, as every other Chinese sentence does (the brief's 佛山 is a name the books do not hold).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.strategy.envelope import Economics, EnvelopeFacts, Probe, Setting, _economics_words
from tests.api.conftest import english_leaks

from .conftest import OWNER

GOLDEN_BUYER = "BUYER-1"
ECON_EN = "That is about 1.5% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit."
ECON_ZH = "约相当于我们估计Foshan Home Retail Co.订单每年为您带来的 ¥1,092,000 毛利的 1.5%。"
DEMO_NOTE_EN = "the margin is assumed for the Demo, not confirmed by you"


def _get(rt: Runtime, monkeypatch: Any, economics: bool, lang: str = "en") -> dict[str, Any]:
    from app.api.strategy_envelope import clear_cache
    from app.main import app

    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    if economics:
        monkeypatch.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")
    else:
        monkeypatch.delenv("FEATURE_CUSTOMER_ECONOMICS", raising=False)
    set_runtime(rt)
    try:
        r = TestClient(app).get(f"/buyers/{GOLDEN_BUYER}/envelope?lang={lang}", headers=OWNER)
        assert r.status_code == 200, r.text
        return dict(r.json())
    finally:
        set_runtime(None)
        clear_cache()


@pytest.fixture(scope="module")
def bodies(rt_day0: Runtime) -> dict[str, dict[str, Any]]:
    mp = pytest.MonkeyPatch()
    try:  # one sweep, worded three times (the sweep's cache is cleared only after the last read)
        from app.api.strategy_envelope import clear_cache

        clear_cache()
        out = {}
        for name, eco, lang in (("off", False, "en"), ("en", True, "en"), ("zh", True, "zh")):
            mp.setenv("FEATURE_ENVELOPE", "1")
            if eco:
                mp.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")
            else:
                mp.delenv("FEATURE_CUSTOMER_ECONOMICS", raising=False)
            from app.main import app

            set_runtime(rt_day0)
            try:
                out[name] = TestClient(app).get(f"/buyers/{GOLDEN_BUYER}/envelope?lang={lang}", headers=OWNER).json()
            finally:
                set_runtime(None)
        clear_cache()
        return out
    finally:
        mp.undo()


def test_the_class_3_package_says_its_share_of_a_years_gross_profit(bodies):
    (p,) = bodies["en"]["over_your_limits"]
    assert p["economics_sentence"] == ECON_EN and p["economics_note"] == DEMO_NOTE_EN
    (z,) = bodies["zh"]["over_your_limits"]
    assert z["economics_sentence"] == ECON_ZH and z["economics_note"] == "毛利率为演示而假设，尚未经您确认"
    assert english_leaks({"s": z["economics_sentence"], "n": z["economics_note"]}, ("Foshan Home Retail Co.",)) == []


def test_mandate_and_economics_are_two_sentences(bodies):
    (p,) = bodies["en"]["over_your_limits"]
    assert p["authority_sentence"].startswith("55-day terms at today's price: your cash floor holds")
    assert "1.5%" not in p["authority_sentence"] and "mandate" not in p["economics_sentence"]


def test_with_the_flag_off_there_is_no_economics_line(bodies):
    (p,) = bodies["off"]["over_your_limits"]
    assert p["economics_sentence"] is None and p["economics_note"] is None


def test_economics_changes_nothing_the_envelope_decides(bodies):
    """Property P8: every package, class, outcome, tier, code, counter and cost is the same with the flag on as off."""
    def decided(body: dict[str, Any]) -> list[Any]:
        keep = ("package", "outcome", "tier", "passes", "approved", "codes", "binding_codes", "forward_budget_used_fen",
                "counter_match", "plan_cost_fen", "authority", "cap_fen", "over_cap_by_fen")
        return [{k: p[k] for k in keep} for group in ("packages", "more", "over_your_limits") for p in body[group]]

    assert decided(bodies["off"]) == decided(bodies["en"])
    assert [p["economics_sentence"] for p in [*bodies["en"]["packages"], *bodies["en"]["more"]]] == [None] * 11
    for k in ("primary", "reason", "money", "levers", "zone"):
        assert bodies["off"][k] == bodies["en"][k], k


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_line_never_says_profit_gained_or_worth(bodies, lang):
    text = bodies[lang]["over_your_limits"][0]["economics_sentence"].lower()
    assert "gross profit" in text or "毛利" in text
    rest = text.replace("gross profit", "")
    assert "profit" not in rest and "worth" not in rest and "利润" not in rest, text


# ---------------------------------------------------------------- the bounds (brief C.2)


def _probe(forward: int) -> Probe:
    return Probe(setting=Setting(55), outcome="REJECT", tier="TIER_1", passes=False, liquidity_only=True,
                 codes=("AGG_CONCESSION_EXCEEDED",), binding=("AGG_CONCESSION_EXCEEDED",), forward_total_fen=forward,
                 reserve_day=None, reserve_curable=None, cure_cost_fen=None, cure_needs_owner=False, cure_cannot_run_today=False,
                 counters=(), counter_costs_fen=(), plan_cost_fen=None, recheck=None,
                 caps=(("AGG_CONCESSION_EXCEEDED", forward, 500_000),))


FACTS = EnvelopeFacts("BUYER-1", "Foshan Home Retail Co.", 0, 1, False, None, 45, 42_000_000,
                      True, (), (), (), {}, None, None, False, 0, 0.0)
YEAR = Economics(109_200_000, False, True, lambda fen: fen)


@pytest.mark.parametrize(("forward", "en", "zh"), [
    (40_000, "That is under 0.1% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit.",
     "相当于我们估计Foshan Home Retail Co.订单每年为您带来的 ¥1,092,000 毛利的低于 0.1%。"),
    (1_621_795, "That is about 1.5% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit.",
     "约相当于我们估计Foshan Home Retail Co.订单每年为您带来的 ¥1,092,000 毛利的 1.5%。"),
    (200_000_000, "That is more than all of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit.",
     "超过我们估计Foshan Home Retail Co.订单每年为您带来的 ¥1,092,000 毛利的全部。"),
    (1_100_000_000, "That is more than 10 times the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit.",
     "超过我们估计Foshan Home Retail Co.订单每年为您带来的 ¥1,092,000 毛利的 10 倍。"),
])
def test_the_share_is_said_within_its_bounds(forward, en, zh):
    assert _economics_words(FACTS, _probe(forward), YEAR, "en") == (en, None)
    assert _economics_words(FACTS, _probe(forward), YEAR, "zh") == (zh, None)


def test_the_basis_word_follows_the_margin_basis_and_no_year_says_nothing():
    contribution = Economics(109_200_000, True, False, lambda fen: fen)
    sentence, note = _economics_words(FACTS, _probe(1_621_795), contribution, "en")
    assert sentence is not None and sentence.endswith("bring you in contribution.") and note == DEMO_NOTE_EN
    assert _economics_words(FACTS, _probe(1_621_795), Economics(0, False, True, lambda fen: fen), "en") == (None, None)
    assert _economics_words(FACTS, _probe(0), YEAR, "en") == (None, None)


def test_the_flag_reads_through_the_route(rt_day0, monkeypatch):
    assert _get(rt_day0, monkeypatch, economics=True)["over_your_limits"][0]["economics_sentence"] == ECON_EN
