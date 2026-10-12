"""The envelope's sentences one by one (ticket #98, the review's fixes): each zh twin pinned with its English, on synthetic probes and
facts, so no sweep runs. Covers the class-2 sentences for a Tier-1 package that needs the owner (its funding cannot run today, or only
the owner may approve its fix), what a class-2 package needs the owner for, the per-buyer class-3 sentence, the ask's sentences
(a wall other than the cash floor, the rule price as the smallest, two packages that differ in class, a buyer with no recurring
invoice), and the route keeping the envelope when the ask alone fails.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.strategy.envelope import (
    NO_RECURRING,
    AskFacts,
    EnvelopeFacts,
    Probe,
    Setting,
    _ask_sentence,
    _authority_sentence,
    authority_of,
)
from tests.api.conftest import english_leaks

NAME = "Foshan Home Retail Co."
FACTS = EnvelopeFacts("BUYER-1", NAME, 0, 1, False, None, 45, 42_000_000, True, (), (), (), {}, None, None, False, 0, 0.0)


def _p(setting: Setting, **kw: Any) -> Probe:
    base: dict[str, Any] = {"setting": setting, "outcome": "ACCEPT", "tier": "TIER_1", "passes": True, "liquidity_only": True,
                            "codes": (), "binding": (), "forward_total_fen": 0, "reserve_day": None, "reserve_curable": None,
                            "cure_cost_fen": None, "cure_needs_owner": False, "cure_cannot_run_today": False, "counters": (),
                            "counter_costs_fen": (), "plan_cost_fen": None, "recheck": None}
    return Probe(**{**base, **kw})


def _both(p: Probe) -> tuple[str | None, str | None]:
    a = authority_of(p)
    return _authority_sentence(FACTS, p, a, "en"), _authority_sentence(FACTS, p, a, "zh")


def _no_leak(zh: str | None) -> None:
    assert zh is not None and english_leaks({"s": zh}, (NAME,)) == []


EARLY = Setting(45, discount=85, face=25_720_000)


def test_a_tier_1_package_whose_funding_cannot_run_today():
    en, zh = _both(_p(EARLY, cure_cannot_run_today=True))
    assert en == ("45-day terms with early payment of 0.85% on ¥257,200.00: within your limits and your cash floor holds, but its "
                  "funding cannot run today. It needs your approval.")
    assert zh == "45 天账期并提前付款 0.85%（金额 ¥257,200.00）：在您的底线内，现金底线也守得住，但其资金安排今天无法执行，需要您批准。"
    _no_leak(zh)


def test_a_tier_1_package_whose_fix_only_the_owner_may_approve():
    en, zh = _both(_p(EARLY, cure_needs_owner=True))
    assert en == ("45-day terms with early payment of 0.85% on ¥257,200.00: within your limits, but the funding that keeps your cash "
                  "floor needs your approval.")
    assert zh == "45 天账期并提前付款 0.85%（金额 ¥257,200.00）：在您的底线内，但守住现金底线的资金安排需要您批准。"
    _no_leak(zh)


@pytest.mark.parametrize(("setting", "en", "zh"), [
    (Setting(45, price=10), "a price change", "调整价格"),
    (Setting(45, discount=85, face=25_720_000), "this early payment", "这笔提前付款"),
])
def test_what_a_class_2_package_needs_the_owner_for(setting, en, zh):
    p = _p(setting, outcome="NEEDS_OWNER_APPROVAL", tier="TIER_2")
    s_en, s_zh = _both(p)
    assert s_en is not None and f"FLOW cannot agree {en} on its own" in s_en
    assert s_zh is not None and f"FLOW 不能自行同意{zh}，需要您批准。" in s_zh
    _no_leak(s_zh)


def test_the_class_3_sentence_for_a_per_buyer_cap():
    p = _p(Setting(55), outcome="REJECT", passes=False, caps=(("PER_BUYER_CAP_EXCEEDED", 1_621_795, 300_000),))
    en, zh = _both(p)
    assert en == ("55-day terms at today's price: your cash floor holds, but it uses ¥16,217.95 of your ¥3,000.00 limit for Foshan Home "
                  "Retail Co.. FLOW will not send it under the limits you signed; only you can decide, and raising the limit means signing "
                  "a new mandate.")
    assert zh == ("按现价给 55 天账期：现金底线守得住，但会占用您对Foshan Home Retail Co.的上限中的 ¥16,217.95（上限为 ¥3,000.00）。"
                  "在您签署的授权范围内，FLOW 不会发送此方案；只有您能决定，提高上限需要签署新的授权。")
    _no_leak(zh)


def _ask(**kw: Any) -> AskFacts:
    base: dict[str, Any] = {"terms_days": 55, "current_terms": 45, "receivable_face_fen": 42_000_000, "price_only": None,
                            "rule_price_bp": None, "at_rule": None, "at_top": None, "with_early": None, "confirmed": True,
                            "evaluations": 3, "seconds": 0.1}
    return AskFacts(**{**base, **kw})


def _say(ask: AskFacts) -> tuple[str, str]:
    return _ask_sentence(FACTS, ask, "en"), _ask_sentence(FACTS, ask, "zh")


OWNER = {"outcome": "NEEDS_OWNER_APPROVAL", "tier": "TIER_2"}


def test_the_rule_price_is_the_smallest_price():
    en, zh = _say(_ask(price_only=_p(Setting(55, price=30), **OWNER), rule_price_bp=30))
    assert en == "55 days works if the price rises 0.30%; at that price the price rise pays for the longer terms in full. It needs your approval."
    assert zh == "价格上调 0.30%，即可接受 55 天账期；该加价可完全抵消延长账期的成本。这需要您批准。"
    _no_leak(zh)


def test_two_packages_that_differ_in_class_are_each_named():
    ask = _ask(price_only=_p(Setting(55, price=25), **OWNER), rule_price_bp=30, at_rule=_p(Setting(55, price=30)))
    en, zh = _say(ask)
    assert en.endswith("pays for the longer terms in full. At 0.25%: within your limits; needs your approval; at 0.30%: FLOW may do this "
                       "on its own.")
    assert zh.endswith("加价可完全抵消延长账期的成本。加价 0.25%：在您的底线内；需要您批准；加价 0.30%：FLOW 可以自行处理。")
    _no_leak(zh)


def test_no_price_works_against_a_wall_other_than_the_cash_floor():
    top = _p(Setting(60, price=100), outcome="REJECT", passes=False, liquidity_only=False, codes=("DSCR_BREACH",), binding=("DSCR_BREACH",))
    en, zh = _say(_ask(terms_days=60, at_top=top))
    assert en == ("No price rise makes 60 days work: the longer terms run into your loan covenants. Nothing within the ranges FLOW "
                  "checks makes 60 days work on today's books.")
    assert zh == "任何加价都无法让 60 天账期可行：账期延长会碰到您的贷款契约。按今天的账面，在 FLOW 检查的范围内，没有方案能让 60 天账期可行。"
    _no_leak(zh)


def test_a_buyer_with_no_recurring_invoice_is_refused_the_ask():
    en, zh = _say(_ask(terms_days=60, refusal=NO_RECURRING))
    assert en == "FLOW cannot value 60-day terms for Foshan Home Retail Co.: there is no recurring invoice to extend."
    assert zh == "FLOW 无法为Foshan Home Retail Co.估值 60 天账期：没有可延长的定期发票。"
    _no_leak(zh)


def test_an_ask_that_fails_keeps_the_envelope(rt_day0, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import strategy_envelope as route
    from app.api.runtime import set_runtime
    from app.main import app

    from .conftest import OWNER as HEADERS

    def broken(*a: Any, **k: Any) -> AskFacts:
        raise ValueError("a package off the levers' grids")

    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    monkeypatch.setattr(route, "envelope_ask", broken)
    route.clear_cache()
    set_runtime(rt_day0)
    try:
        body = TestClient(app).get("/buyers/BUYER-1/envelope?ask=60", headers=HEADERS).json()
    finally:
        set_runtime(None)
        route.clear_cache()
    assert body["refused"] is None and body["packages"] and body["primary"].startswith("At today's price:")
    assert body["ask"]["refused"] == "60 days is outside the payment terms FLOW checks." and body["ask"]["price_works"] is False
