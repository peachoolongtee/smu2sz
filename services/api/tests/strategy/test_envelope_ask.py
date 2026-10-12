"""The envelope answers the buyer's ask (ticket #98, P4; brief E.2 and E.3): `compensate(T)` for the asked terms.

The smallest approved price at T with the rule price beside it; when no price works, the smallest early payment of the open
invoice that lets T through (the face searched at the smallest rate only, where it is monotone), then the smallest price with
it, then the largest rate at that face; each result probed whole and re-checked. Golden day 0: 55 days needs 0.25% (0.30%
pays for it in full); no price makes 60 days work, ¥240,200 paid now plus 0.40% does (r3:21-23, r3 section 1).
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books
from app.strategy import envelope as module
from app.strategy.envelope import AskFacts, EnvelopeFacts, ask_answer, envelope_ask, envelope_facts
from app.verifier.evaluate import clear_caches
from tests.api.conftest import english_leaks

from .conftest import OWNER

GOLDEN_BUYER = "BUYER-1"
NAMES = ("Foshan Home Retail Co.",)

PRICE_WORKS_EN = ("55 days works if the price rises at least 0.25%; at 0.30% the price rise pays for the longer terms in full. "
                  "Either needs your approval.")
PRICE_WORKS_ZH = "价格至少上调 0.25%，即可接受 55 天账期；上调 0.30% 时，加价可完全抵消延长账期的成本。两者都需要您批准。"
NO_PRICE_EN = ("No price rise makes 60 days work: the longer terms leave your cash short in 47 days. 60 days works only if "
               "¥240,200 of the open ¥420,000.00 invoice is paid now and the price rises 0.40%; that needs your approval.")
NO_PRICE_ZH = ("任何加价都无法让 60 天账期可行：账期延长会让您的现金在 47 天后不足。只有在 ¥420,000.00 的未结发票中先支付 ¥240,200，"
               "并加价 0.40% 时，60 天才可行；这需要您批准。")


def _ask(rt: Runtime, books: Books, terms: int) -> AskFacts:
    return envelope_ask(books, rt.store.get_mandate(), day=rt.day, buyer_id=GOLDEN_BUYER, trusted_owner_key_hex=rt.owner_key_hex,
                        terms=terms, commitments=tuple(rt.store.commitments()))


@pytest.fixture(scope="module")
def facts(rt_day0: Runtime, books_day0: Books) -> EnvelopeFacts:
    return envelope_facts(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=rt_day0.day, buyer_id=GOLDEN_BUYER,
                          trusted_owner_key_hex=rt_day0.owner_key_hex, commitments=tuple(rt_day0.store.commitments()))


@pytest.fixture(scope="module")
def ask55(rt_day0: Runtime, books_day0: Books) -> tuple[AskFacts, float]:
    clear_caches()
    started = time.perf_counter()
    a = _ask(rt_day0, books_day0, 55)
    return a, time.perf_counter() - started


@pytest.fixture(scope="module")
def ask60(rt_day0: Runtime, books_day0: Books) -> AskFacts:
    return _ask(rt_day0, books_day0, 60)


def _key(p: Any) -> tuple[int, int, int, int | None, int]:
    return (p.terms, p.price, p.discount, p.face, p.rebate)


# ---------------------------------------------------------------- a price works


def test_55_days_works_with_the_smallest_price_and_the_rule_price_beside_it(ask55):
    a, _ = ask55
    assert a.price_only is not None and _key(a.price_only.setting) == (55, 25, 0, None, 0) and a.price_only.approved
    assert a.rule_price_bp == 30 and a.at_rule is not None and _key(a.at_rule.setting) == (55, 30, 0, None, 0)
    assert a.at_rule.approved and a.with_early is None and a.at_top is None and a.confirmed and a.refusal == ""


def test_the_price_works_sentence_in_both_languages(facts, ask55):
    a, _ = ask55
    en, zh = ask_answer(facts, a, "en"), ask_answer(facts, a, "zh")
    assert en.sentence == PRICE_WORKS_EN and zh.sentence == PRICE_WORKS_ZH
    assert en.price_works and en.smallest_price is not None and en.rule_price is not None and en.with_early_payment is None
    assert en.smallest_price.authority == en.rule_price.authority == "needs_owner"
    assert en.terms_words == "55 days" and zh.terms_words == "55 天" and en.refused is None


def test_the_price_only_answer_costs_a_handful_of_verifier_runs(ask55):
    a, _ = ask55
    assert a.evaluations <= 9, a.evaluations  # the first_true over 21 prices, the rule price's whole probe


@pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1")
def test_the_price_only_answer_runs_cold_in_about_two_seconds(ask55):
    _, seconds = ask55
    assert seconds < 2.0, f"the price-only ask took {seconds:.2f} s cold"


# ---------------------------------------------------------------- no price works


def test_no_price_makes_60_days_work_and_the_smallest_early_payment_does(ask60):
    a = ask60
    assert a.price_only is None and a.at_top is not None and _key(a.at_top.setting) == (60, 100, 0, None, 0)
    assert a.at_top.reserve_day == 47 and a.at_top.reserve_curable is False
    w = a.with_early
    assert w is not None and _key(w.setting) == (60, 40, 5, 24_020_000, 0) and w.approved
    assert w.outcome == "NEEDS_OWNER_APPROVAL" and w.forward_total_fen == 248_692
    assert (w.reserve_day, w.reserve_curable, w.cure_cost_fen) == (47, True, 293_919)  # "its funding cannot run today"
    assert 25 <= a.evaluations <= 32, a.evaluations  # about 25 to 30 with the fallback (brief E.2)


def test_the_no_price_sentence_in_both_languages(facts, ask60):
    en, zh = ask_answer(facts, ask60, "en"), ask_answer(facts, ask60, "zh")
    assert en.sentence == NO_PRICE_EN and zh.sentence == NO_PRICE_ZH
    assert not en.price_works and en.with_early_payment is not None and en.early_face_fen == 24_020_000
    assert en.with_early_payment.authority == "needs_owner"
    assert english_leaks({"sentence": zh.sentence, "summary": zh.with_early_payment.summary if zh.with_early_payment else ""},
                         NAMES) == []


def test_one_hundred_yuan_less_paid_now_does_not_work(rt_day0, books_day0):
    """The smallest face is a boundary the verifier agrees with: ¥240,100 at the same price leaves the day-47 shortfall."""
    ctx = module.open_context(books_day0.state, 0, GOLDEN_BUYER)
    v = module._Verifier(books_day0, rt_day0.store.get_mandate(), rt_day0.owner_key_hex, 0, (), ctx,
                         module.ranges_for(ctx, rt_day0.store.get_mandate()))
    below = v.quick(module.Setting(60, price=40, discount=5, face=24_010_000))
    assert not below.approved and "RESERVE_BREACH" in below.codes


def test_the_face_is_searched_only_at_the_smallest_rate(rt_day0, books_day0, monkeypatch):
    """The face is not monotone at a high rate (at 0.85% 60 days passes only from ¥244,000 to ¥286,000, r3 section 2), so it
    is never bisected there: every face tried at another rate is the face the search settled on."""
    seen: list[module.Setting] = []
    real = module._Verifier.quick

    def spy(self: Any, s: module.Setting) -> Any:
        seen.append(s)
        return real(self, s)

    monkeypatch.setattr(module._Verifier, "quick", spy)
    a = _ask(rt_day0, books_day0, 60)
    assert a.with_early is not None
    chosen = a.with_early.setting.face
    with_face = [s for s in seen if s.discount > 0]
    assert with_face and all(s.discount == 5 or s.face == chosen for s in with_face)
    assert len({s.face for s in with_face if s.discount == 5}) > 5  # the face really was searched


# ---------------------------------------------------------------- nothing to search


def test_an_ask_at_the_terms_in_force_works_at_todays_price(facts, rt_day0, books_day0):
    a = _ask(rt_day0, books_day0, 45)
    assert a.price_only is not None and a.price_only.setting.price == 0 and a.evaluations <= 2
    assert ask_answer(facts, a, "en").sentence == "45 days works at today's price. FLOW may send it on its own."
    assert ask_answer(facts, a, "zh").sentence == "按现价即可接受 45 天账期。FLOW 可以自行发送。"


def test_an_ask_off_the_grid_is_refused_in_a_sentence(facts, rt_day0, books_day0):
    for terms in (52, 95):
        a = _ask(rt_day0, books_day0, terms)
        assert a.refusal == "out_of_range" and a.evaluations == 0
        en, zh = ask_answer(facts, a, "en"), ask_answer(facts, a, "zh")
        assert en.refused == en.sentence == f"{terms} days is outside the payment terms FLOW checks."
        assert zh.refused == f"{terms} 天不在 FLOW 检查的账期范围内。"


def test_nothing_works_is_said_when_no_early_payment_lets_the_terms_through(facts):
    top = module.Probe(setting=module.Setting(60, price=100), outcome="REJECT", tier="TIER_1", passes=False, liquidity_only=False,
                       codes=("RESERVE_BREACH",), binding=("RESERVE_BREACH",), forward_total_fen=0, reserve_day=47,
                       reserve_curable=False, cure_cost_fen=None, cure_needs_owner=False, cure_cannot_run_today=False,
                       counters=(), counter_costs_fen=(), plan_cost_fen=None, recheck=None)
    a = AskFacts(60, 45, 42_000_000, None, 45, None, top, None, True, 16, 1.0)
    assert ask_answer(facts, a, "en").sentence == (
        "No price rise makes 60 days work: the longer terms leave your cash short in 47 days. Nothing within the ranges FLOW "
        "checks makes 60 days work on today's books.")
    assert ask_answer(facts, a, "zh").sentence == (
        "任何加价都无法让 60 天账期可行：账期延长会让您的现金在 47 天后不足。按今天的账面，在 FLOW 检查的范围内，没有方案能让 60 天账期可行。")


# ---------------------------------------------------------------- the route


@pytest.fixture
def api(rt_day0, monkeypatch):
    from app.api.strategy_envelope import clear_cache
    from app.main import app

    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    clear_cache()
    set_runtime(rt_day0)
    yield TestClient(app)
    set_runtime(None)
    clear_cache()


def test_route_answers_the_ask_and_caches_it_apart(api, monkeypatch):
    from app.api import strategy_envelope as route

    plain = api.get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER).json()
    assert plain["ask"] is None
    asks: list[int] = []
    sweeps: list[int] = []
    real_ask, real_sweep = route.envelope_ask, route.envelope_facts
    monkeypatch.setattr(route, "envelope_ask", lambda *a, **k: asks.append(1) or real_ask(*a, **k))
    monkeypatch.setattr(route, "envelope_facts", lambda *a, **k: sweeps.append(1) or real_sweep(*a, **k))
    en = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?ask=60", headers=OWNER).json()
    zh = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?ask=60&lang=zh", headers=OWNER).json()
    assert sweeps == [] and asks == [1], "the sweep is cached; the ask is computed once, then cached apart"
    assert en["ask"]["sentence"] == NO_PRICE_EN and zh["ask"]["sentence"] == NO_PRICE_ZH
    assert en["ask"]["early_face_display"] == "¥240,200.00" and en["ask"]["with_early_payment"]["package"]["price_bp"] == 40
    assert en["evaluations"] == plain["evaluations"] + en["ask"]["evaluations"]
    # the ask's answer takes its place on the card (P6); every other field is the plain read's
    assert en["packages"][2]["package"]["terms_days"] == 60 and en["packages"][:2] == plain["packages"][:2]
    moved = ("ask", "evaluations", "computed_in_seconds", "packages", "more")
    assert {k: v for k, v in en.items() if k not in moved} == {k: v for k, v in plain.items() if k not in moved}


def test_route_rejects_an_ask_outside_the_query_range(api):
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?ask=0", headers=OWNER).status_code == 422
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?ask=abc", headers=OWNER).status_code == 422


def test_route_asks_nothing_of_a_buyer_with_no_lever(api):
    body = api.get("/buyers/BUYER-2/envelope?ask=60", headers=OWNER).json()
    assert body["refused"] is not None and body["ask"] is None


# ---------------------------------------------------------------- refused (brief E.3)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_ask_never_says_upfront_and_the_budget_has_one_chinese_name(facts, ask60, lang):
    """"60 days with 20% upfront" is false on these books and not representable (no deposit obligation exists): the
    answer names the part of the open invoice paid now, never a share upfront. The budget is 让利 everywhere, never 让步."""
    a = module.envelope_answer(facts, lang, ask60)
    texts = [a.primary, a.reason, a.money, a.ask.sentence if a.ask else "",
             *[w for p in [*a.packages, *a.more, *a.over_your_limits]
               for w in (p.summary, p.authority_sentence or "", *p.flags)],
             *[w for lv in a.levers for w in (lv.wall_text or "", lv.wall_words or "", lv.next_step_sentence)]]
    for text in texts:
        assert "upfront" not in text.lower() and "20%" not in text and "预付" not in text and "定金" not in text, text
        assert "让步" not in text, text


def test_the_two_wall_tables_name_the_budget_alike():
    assert module._WALL_TEXT["forward budget"][1] == module._WALL_WORDS["forward budget"][1] == "您给买家让利的预算"
