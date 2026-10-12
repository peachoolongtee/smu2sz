"""The envelope's three classes of authority (ticket #98 with #97's envelope items, P1; brief E.1 and E.3).

Every package carries one class, read from the verifier's own fields and never computed: FLOW may do it alone, it is within the
signed limits and needs the owner, or it is financially safe but over a cap the owner signed (only a new signed mandate moves
it). The `terms_budget_ignored` maximum is listed as the one class-3 package, in its own group, with the cap it breaks and by
how much. Pinned on the golden day-0 books in both languages.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books
from app.strategy.envelope import EnvelopeFacts, Probe, Setting, authority_of, envelope_answer, envelope_facts
from tests.api.conftest import english_leaks

from .conftest import OWNER

GOLDEN_BUYER = "BUYER-1"
OPTION_A = (45, 0, 85, 25_720_000, 0)
OPTION_B = (55, 30, 0, None, 0)

CLASS_2_EN = ("55-day terms with a 0.30% price rise: within your limits and your cash floor holds, but FLOW cannot agree "
              "longer terms on its own. It needs your approval.")
CLASS_2_ZH = "55 天账期并加价 0.30%：在您的底线内，现金底线也守得住，但 FLOW 不能自行同意延长账期，需要您批准。"
CLASS_3_EN = ("55-day terms at today's price: your cash floor holds, but it uses ¥16,217.95 of your ¥5,000.00 budget for what "
              "you give buyers. FLOW will not send it under the limits you signed; only you can decide, and raising the limit "
              "means signing a new mandate.")
CLASS_3_ZH = ("按现价给 55 天账期：现金底线守得住，但会占用您给买家让利预算中的 ¥16,217.95（预算为 ¥5,000.00）。在您签署的授权"
              "范围内，FLOW 不会发送此方案；只有您能决定，提高上限需要签署新的授权。")
NAMES = ("Foshan Home Retail Co.",)


@pytest.fixture(scope="module")
def facts(rt_day0: Runtime, books_day0: Books) -> EnvelopeFacts:
    return envelope_facts(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=rt_day0.day, buyer_id=GOLDEN_BUYER,
                          trusted_owner_key_hex=rt_day0.owner_key_hex, commitments=tuple(rt_day0.store.commitments()))


def _key(p: Any) -> tuple[int, int, int, int | None, int]:
    q = p.package
    return (q.terms_days, q.price_bp, q.early_pay_bp, q.early_pay_face_fen, q.rebate_bp)


def _all(a: Any) -> list[Any]:
    return [*a.packages, *a.more]


def test_every_package_has_exactly_one_of_the_three_classes(facts):
    a = envelope_answer(facts, "en")
    classes = {_key(p): p.authority for p in _all(a)}
    assert set(classes.values()) <= {"flow_may", "needs_owner"}
    # Option A, an early payment on a named invoice, is the one package of eleven FLOW may send alone (r3:101)
    assert classes[OPTION_A] == "flow_may"
    assert [k for k, c in classes.items() if c == "flow_may"] == [OPTION_A]
    assert len(classes) == 11 and list(classes.values()).count("needs_owner") == 10


def test_option_a_says_flow_may_and_option_b_says_needs_your_approval(facts):
    en = {_key(p): p for p in _all(envelope_answer(facts, "en"))}
    zh = {_key(p): p for p in _all(envelope_answer(facts, "zh"))}
    assert en[OPTION_A].authority_words == "FLOW may do this on its own" and en[OPTION_A].authority_sentence is None
    assert zh[OPTION_A].authority_words == "FLOW 可以自行处理"
    assert en[OPTION_B].authority_words == "within your limits; needs your approval"
    assert en[OPTION_B].authority_sentence == CLASS_2_EN
    assert zh[OPTION_B].authority_sentence == CLASS_2_ZH and zh[OPTION_B].authority_words == "在您的底线内；需要您批准"


def test_a_class_2_package_without_longer_terms_names_what_needs_the_owner(facts):
    en = {_key(p): p for p in _all(envelope_answer(facts, "en"))}
    rebate = en[(45, 0, 0, None, 125)]
    assert rebate.authority == "needs_owner"
    assert rebate.authority_sentence == ("45-day terms with a 1.25% rebate: within your limits and your cash floor holds, but FLOW "
                                         "cannot agree a rebate on its own. It needs your approval.")
    deep = en[(55, 25, 85, 25_720_000, 60)]
    assert deep.authority_sentence is not None and deep.authority_sentence.startswith(
        "55-day terms with a 0.25% price rise, early payment of 0.85% on ¥257,200.00 and a 0.60% rebate: ")


def test_the_budget_ignored_maximum_is_the_one_class_3_package_with_its_cap(facts):
    a = envelope_answer(facts, "en")
    assert len(a.over_your_limits) == 1
    p = a.over_your_limits[0]
    assert _key(p) == (55, 0, 0, None, 0) and p.authority == "over_your_limits" and p.outcome == "REJECT"
    assert (p.cap_fen, p.cap_used_fen, p.over_cap_by_fen) == (500_000, 1_621_795, 1_121_795)
    assert p.reserve_breach is not None and (p.reserve_breach.day, p.reserve_breach.curable, p.reserve_breach.cure_cost_fen) == (
        47, True, 157_036)
    assert p.authority_words == "over a limit you signed" and p.authority_sentence == CLASS_3_EN
    assert all(_key(q) != _key(p) for q in _all(a))  # its own group: never among the packages within your limits


def test_the_class_3_package_in_chinese(facts):
    zh = envelope_answer(facts, "zh")
    p = zh.over_your_limits[0]
    assert p.authority_sentence == CLASS_3_ZH and p.authority_words == "超出您签署的上限"
    texts = {"words": p.authority_words, "sentence": p.authority_sentence,
             "class2": [q.authority_sentence for q in _all(zh) if q.authority_sentence]}
    assert english_leaks(texts, NAMES) == []


def test_the_lever_table_carries_the_class_on_its_packages(facts):
    a = envelope_answer(facts, "en")
    by = {lv.key: lv for lv in a.levers}
    assert by["terms_budget_ignored"].at_maximum is not None
    assert by["terms_budget_ignored"].at_maximum.authority == "over_your_limits"
    assert by["terms_alone"].next_step is not None and by["terms_alone"].next_step.authority == "over_your_limits"
    assert by["terms_budget_ignored"].next_step is not None and by["terms_budget_ignored"].next_step.authority is None  # no fix


# ---------------------------------------------------------------- the derivation, on its own


def _probe(**kw: Any) -> Probe:
    base: dict[str, Any] = {"setting": Setting(45), "outcome": "ACCEPT", "tier": "TIER_1", "passes": True, "liquidity_only": True,
                            "codes": (), "binding": (), "forward_total_fen": 0, "reserve_day": None, "reserve_curable": None,
                            "cure_cost_fen": None, "cure_needs_owner": False, "cure_cannot_run_today": False, "counters": (),
                            "counter_costs_fen": (), "plan_cost_fen": None, "recheck": None}
    return Probe(**{**base, **kw})


def test_the_three_classes_are_derived_from_the_verifiers_fields_and_never_overlap():
    assert authority_of(_probe()) == "flow_may"
    assert authority_of(_probe(outcome="NEEDS_OWNER_APPROVAL", tier="TIER_2")) == "needs_owner"
    assert authority_of(_probe(cure_needs_owner=True)) == "needs_owner"
    # FLOW could agree it, but the fix behind it cannot run today: not FLOW's alone
    assert authority_of(_probe(cure_cannot_run_today=True)) == "needs_owner"
    over = _probe(outcome="REJECT", passes=False, caps=(("AGG_CONCESSION_EXCEEDED", 1_621_795, 500_000),))
    assert authority_of(over) == "over_your_limits"
    # not financially safe, or refused for something other than a cap: no class at all
    assert authority_of(_probe(outcome="REJECT", passes=False, liquidity_only=False)) is None
    assert authority_of(_probe(outcome="REJECT", passes=False, caps=())) is None
    # passes but fails its own re-check: neither within the limits nor over them
    assert authority_of(_probe(recheck="cannot be funded in time")) is None


# ---------------------------------------------------------------- the route


def test_route_carries_the_class_3_group_with_its_displays(rt_day0, monkeypatch):
    from app.api.strategy_envelope import clear_cache
    from app.main import app

    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    clear_cache()
    set_runtime(rt_day0)
    try:
        body = TestClient(app).get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER).json()
    finally:
        set_runtime(None)
        clear_cache()
    (p,) = body["over_your_limits"]
    assert (p["cap_display"], p["cap_used_display"], p["over_cap_by_display"]) == ("¥5,000.00", "¥16,217.95", "¥11,217.95")
    assert p["authority"] == "over_your_limits" and p["authority_sentence"] == CLASS_3_EN
    assert all(q["authority"] in ("flow_may", "needs_owner") for q in [*body["packages"], *body["more"]])
