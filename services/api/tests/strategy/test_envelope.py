"""The Safe Deal Envelope (wayfinder map #47, Wave 3): the sweep over the real verifier, its words and its route.

The golden day-0 books are the oracle's (fixtures/strategy/envelope_day0.json, envelope_packages.json, recorded from
scripts/research/envelope_spike.py). The default grid and the zone are computed once per module; the full grid, which
takes close to a minute, is the one test with `full_grid` in its name, so `-k "not full_grid"` leaves it out.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books
from app.domain.models import ExpectedOrder, FinancialState, Mandate
from app.strategy import CandidatePackage
from app.strategy.envelope import (
    REBATE,
    TERMS_ALONE,
    TERMS_BUDGET_IGNORED,
    TERMS_WITH_PRICE,
    EnvelopeAnswer,
    EnvelopeFacts,
    EnvelopeLever,
    EnvelopePackage,
    descend,
    early_pay_lever,
    envelope,
    envelope_answer,
    envelope_facts,
    first_true,
    last_true,
    probe_packages,
    ranges_for,
)
from app.verifier.evaluate import clear_caches
from app.whatif.offer import Context, EarlyPayContext, RebateOnlyContext, build, context
from app.whatif.params import WhatIfParamError, WhatIfParams

from .conftest import OWNER

_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "strategy"
GOLDEN_BUYER = "BUYER-1"
OPTION_A = (45, 0, 85, 25_720_000, 0)  # terms, price, early-pay bp, face, rebate
OPTION_B = (55, 30, 0, None, 0)

PRIMARY_EN = ("You can live with: up to 55-day terms if the price rises 0.30%, or early payment at up to 0.85% on ¥257,200.00; "
              "a rebate up to 1.25%; not 60 days without an early payment.")
REASON_EN = ("60 days without an early payment leaves a shortfall in 47 days that no fix covers; the ¥5,000.00 budget buys no terms "
             "without a price rise.")
MONEY_EN = ("Cost to you ¥0.00 with the price rise, or ¥3,027.77 with the early payment; without a deal "
            "your current funding plan costs ¥3,113.93.")
PRIMARY_ZH = "您能接受的范围：账期最长 55 天（价格上调 0.30%），或提前付款最高 0.85%（金额 ¥257,200.00）；返利最高 1.25%；不提前付款则不能做到 60 天。"
REASON_ZH = "不提前付款的 60 天账期会在 47 天后出现无法补上的缺口；¥5,000.00 的预算无法在不加价的情况下延长账期。"
MONEY_ZH = "您的成本：加价方案 ¥0.00，或提前付款方案 ¥3,027.77；不做交易时，现行资金安排的成本为 ¥3,113.93。"

CODE_NAME = re.compile(r"\b[A-Z]{2,}(?:_[A-Z]+)+\b")  # AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, ...
DAY_N = re.compile(r"\bday \d|第 ?\d+ ?天", re.IGNORECASE)


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_DIR / name).read_text(encoding="utf-8"))
    return data


def _setting(p: EnvelopePackage) -> tuple[int, int, int, int | None, int]:
    q = p.package
    return (q.terms_days, q.price_bp, q.early_pay_bp, q.early_pay_face_fen, q.rebate_bp)


def _by_lever(a: EnvelopeAnswer) -> dict[str, EnvelopeLever]:
    return {lv.lever: lv for lv in a.levers}


def _cure(p: EnvelopePackage) -> tuple[int, bool, int | None] | None:
    b = p.reserve_breach
    return None if b is None else (b.day, b.curable, b.cure_cost_fen)


@dataclass
class Golden:
    rt: Runtime
    books: Books
    mandate: Mandate

    def facts(self, buyer: str = GOLDEN_BUYER, **kw: Any) -> EnvelopeFacts:
        return envelope_facts(self.books, self.mandate, store=self.rt.store, day=self.rt.day, buyer_id=buyer,
                              trusted_owner_key_hex=self.rt.owner_key_hex, commitments=tuple(self.rt.store.commitments()), **kw)

    def kw(self) -> dict[str, Any]:
        return {"store": self.rt.store, "day": self.rt.day, "trusted_owner_key_hex": self.rt.owner_key_hex,
                "commitments": tuple(self.rt.store.commitments())}


@pytest.fixture(scope="module")
def golden(rt_day0: Runtime, books_day0: Books) -> Golden:
    return Golden(rt_day0, books_day0, rt_day0.store.get_mandate())


@pytest.fixture(scope="module")
def cold(golden: Golden) -> tuple[EnvelopeFacts, float]:
    """The default grid on the golden books with the verifier's caches cleared, and the seconds it took."""
    clear_caches()
    started = time.perf_counter()
    facts = golden.facts()
    seconds = time.perf_counter() - started
    print(f"\nenvelope, default grid, cold: {seconds:.2f} s, {facts.evaluations} verifier runs")
    return facts, seconds


@pytest.fixture(scope="module")
def answer(cold: tuple[EnvelopeFacts, float]) -> EnvelopeAnswer:
    return envelope_answer(cold[0], "en")


@pytest.fixture(scope="module")
def zoned(golden: Golden) -> EnvelopeAnswer:
    return envelope_answer(golden.facts(zone=True), "en")


# ---------------------------------------------------------------- runtime


@pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1")
def test_default_grid_runs_cold_in_under_8_seconds(cold):
    _facts, seconds = cold
    print(f"\ndefault grid, cold: {seconds:.2f} s (limit 8 s)")
    assert seconds < 8.0, f"the default grid took {seconds:.2f} s cold"


# ---------------------------------------------------------------- the levers, pinned to the oracle


def test_terms_alone_stop_at_the_budget(answer):
    lv = _by_lever(answer)[TERMS_ALONE]
    assert lv.maximum == 45 and lv.wall == "forward budget" and lv.confirmed
    nxt = lv.next_step
    assert nxt is not None and nxt.package.terms_days == 50 and not nxt.passes
    assert nxt.binding_codes == ["AGG_CONCESSION_EXCEEDED"] and nxt.forward_budget_used_fen == 810_897


def test_terms_with_the_budget_ignored_stop_at_liquidity(answer):
    lv = _by_lever(answer)[TERMS_BUDGET_IGNORED]
    assert lv.maximum == 55 and lv.wall == "liquidity"
    assert lv.at_maximum is not None and _cure(lv.at_maximum) == (47, True, 157_036)
    assert "its funding cannot run today" in lv.at_maximum.flags
    nxt = lv.next_step
    assert nxt is not None and nxt.package.terms_days == 60
    assert _cure(nxt) == (47, False, None) and "RESERVE_BREACH" in nxt.binding_codes


def test_terms_with_the_compensating_price(answer):
    lv = _by_lever(answer)[TERMS_WITH_PRICE]
    assert lv.maximum == 55 and lv.wall == "liquidity"
    assert lv.at_maximum is not None and lv.at_maximum.package.price_bp == 25 and lv.at_maximum.approved
    assert lv.rule_price_bp == 30  # Option B's rule price, beside the smallest passing 25
    nxt = lv.next_step
    assert nxt is not None and nxt.package.terms_days == 60 and nxt.binding_codes == ["RESERVE_BREACH"]


def test_early_pay_on_the_whole_invoice(answer):
    lv = _by_lever(answer)[early_pay_lever(42_000_000)]
    assert lv.maximum == 70 and lv.face_fen == 42_000_000 and lv.wall == "plan comparison"
    assert lv.next_step is not None and lv.next_step.package.early_pay_bp == 75
    assert lv.next_step.binding_codes == ["EARLY_PAY_DEARER_THAN_PLAN"]


def test_early_pay_on_the_face_the_verifier_names(answer):
    lv = _by_lever(answer)[early_pay_lever(25_720_000)]
    assert lv.maximum == 85 and lv.face_fen == 25_720_000 and lv.wall == "break-even"
    assert lv.next_step is not None and lv.next_step.package.early_pay_bp == 90
    assert "DISCOUNT_ABOVE_BREAK_EVEN" in lv.next_step.binding_codes


def test_rebate_stops_at_the_budget(answer):
    lv = _by_lever(answer)[REBATE]
    assert lv.maximum == 125 and lv.wall == "forward budget"
    assert lv.at_maximum is not None and lv.at_maximum.forward_budget_used_fen == 500_000  # ¥5,000 exactly
    nxt = lv.next_step
    assert nxt is not None and nxt.package.rebate_bp == 130 and nxt.binding_codes == ["AGG_CONCESSION_EXCEEDED"]


def test_the_six_levers_are_the_oracles(answer):
    oracle = [m["lever"] for m in _load("envelope_day0.json")["maxima"]]
    assert [lv.lever for lv in answer.levers] == oracle
    assert all(lv.confirmed and not lv.scanned for lv in answer.levers)


# ---------------------------------------------------------------- the zone


def test_zone_is_left_out_unless_asked(answer, zoned):
    assert answer.zone == []
    assert len(zoned.zone) == 13 and [z.terms_days for z in zoned.zone] == list(range(30, 91, 5))


def test_zone_pins(zoned):
    zone = {z.terms_days: z for z in zoned.zone}
    assert zone[50].min_price_bp == 10 and zone[50].rule_price_bp == 15
    assert zone[55].min_price_bp == 25 and zone[55].rule_price_bp == 30
    assert zone[60].min_price_bp is None and not zone[60].passes_within_range
    assert zone[60].rule_price_bp == 45
    breach = zone[60].at_that_price.reserve_breach
    assert breach is not None and breach.day == 47 and not breach.curable
    assert zone[45].min_price_bp == 0 and zone[45].rule_price_bp is None  # nothing to compensate at the terms in force
    assert all(z.neighbours_confirmed for z in zoned.zone)


def test_zone_of_the_default_grid_matches_the_oracles(zoned):
    oracle = {z["terms_days"]: z for z in _load("envelope_day0.json")["zone"]}
    for z in zoned.zone:
        o = oracle[z.terms_days]
        assert z.min_price_bp == (o["min_price_adjustment"] or {}).get("bp")
        assert z.rule_price_bp == (o["price_that_nets_it_to_zero"] or {}).get("bp")
        assert z.cost_per_invoice_fen == (o["cost_per_invoice"] or {}).get("fen")


# ---------------------------------------------------------------- packages


def _asked(row: dict[str, Any]) -> CandidatePackage:
    early = row["early_pay"]
    face = None if early is None or early["face"] == "whole invoice" else early["face"]["fen"]
    return CandidatePackage(buyer_id=GOLDEN_BUYER, terms_days=row["terms_days"], price_bp=row["price_adjustment"]["bp"],
                            early_pay_bp=early["rate"]["bp"] if early else 0, early_pay_face_fen=face,
                            rebate_bp=row["rebate"]["bp"])


def test_the_ten_interaction_packages_are_reproduced_to_the_fen(golden):
    rows = _load("envelope_packages.json")["requested"]
    assert len(rows) == 10
    got = probe_packages(golden.books, golden.mandate, [_asked(r) for r in rows], day=0,
                         trusted_owner_key_hex=golden.rt.owner_key_hex)
    for row, p in zip(rows, got, strict=True):
        where = (row["terms_days"], row["price_adjustment"]["bp"], row["early_pay"], row["rebate"]["bp"])
        crumb = row["reserve_breach"]
        assert p.outcome == row["outcome"], where
        assert p.passes is row["passes"] and p.approved is row["counter_grade"], where
        assert p.codes == row["codes"] and p.binding_codes == row["binding_codes"], where
        assert p.forward_budget_used_fen == row["forward_budget_used"]["fen"], where
        expected = None if crumb is None else (crumb["day"], crumb["curable"], (crumb["cure_cost"] or {}).get("fen"))
        assert _cure(p) == expected, where


def test_the_interaction_packages_pin_the_brief_figures(golden):
    pkgs = [CandidatePackage(buyer_id=GOLDEN_BUYER, terms_days=50, rebate_bp=125),
            CandidatePackage(buyer_id=GOLDEN_BUYER, terms_days=55, price_bp=30, rebate_bp=125),
            CandidatePackage(buyer_id=GOLDEN_BUYER, terms_days=55, price_bp=30, rebate_bp=130),
            CandidatePackage(buyer_id=GOLDEN_BUYER, terms_days=55, price_bp=30, early_pay_bp=85,
                             early_pay_face_fen=25_720_000)]
    got = probe_packages(golden.books, golden.mandate, pkgs, day=0, trusted_owner_key_hex=golden.rt.owner_key_hex)
    assert [p.passes for p in got] == [False, True, False, True]
    assert [p.forward_budget_used_fen for p in got] == [1_310_897, 483_795, 503_795, 0]
    assert got[0].binding_codes == ["AGG_CONCESSION_EXCEEDED"]
    assert _cure(got[3]) == (47, True, 267_304)


def test_default_grid_packages_are_all_approved(answer):
    assert answer.packages
    for p in answer.packages:
        assert p.approved and p.passes and p.binding_codes == [], _setting(p)
    terms = {p.package.terms_days for p in answer.packages}
    assert {45, 50, 55} <= terms and max(terms) <= 55  # the terms in force, +5, +10


def test_the_verifiers_own_counters_are_among_the_approved_packages(answer):
    by = {_setting(p): p for p in answer.packages}
    for counter in (OPTION_A, OPTION_B):
        assert counter in by and by[counter].counter_match and by[counter].approved
    # the smallest passing price (0.25%) sits beside the counter's rule price (0.30%), both in the payload
    assert any(_setting(p)[:2] == (55, 25) for p in answer.packages)
    assert not by[(55, 25, 0, None, 60)].counter_match


def test_packages_say_what_needs_the_owner_in_words(answer):
    by = {_setting(p): p for p in answer.packages}
    assert by[OPTION_A].flags == [] and by[OPTION_A].outcome == "ACCEPT"
    b = by[OPTION_B]
    assert b.flags == ["needs your approval", "its funding cannot run today"]
    assert b.reserve_breach is not None and b.reserve_breach.when == "in 47 days" and b.reserve_breach.cure_cost_fen == 157_036
    deep = by[(55, 25, 85, 25_720_000, 60)]
    assert deep.outcome == "NEEDS_OWNER_APPROVAL" and _cure(deep) == (47, True, 267_304)


# ---------------------------------------------------------------- words


def test_the_golden_sentences_in_english(answer):
    assert answer.primary == PRIMARY_EN
    assert answer.reason == REASON_EN
    assert answer.money == MONEY_EN
    assert answer.refused is None and answer.hypothetical is True


def test_the_golden_sentences_in_chinese(cold):
    zh = envelope_answer(cold[0], "zh")
    assert (zh.primary, zh.reason, zh.money) == (PRIMARY_ZH, REASON_ZH, MONEY_ZH)
    assert zh.packages[3].flags == ["需要您批准", "其资金安排今天无法执行"]


LEVER_WORDS_EN = {  # maximum_display, wall_words, next_step_sentence
    "terms_alone": ("45 days", "your budget for what you give buyers", "50 days: over your limits; its funding cannot run today"),
    "terms_budget_ignored": ("55 days", "your cash floor", "60 days: over your limits"),
    "terms_with_price": ("55 days, price up 0.30%", "your cash floor", "60 days, price up 1.00%: over your limits"),
    "early_pay_whole": ("0.70% on ¥420,000.00", "the cheaper funding you already have",
                        "0.75% on ¥420,000.00: over your limits"),
    "early_pay_counter": ("0.85% on ¥257,200.00", "the break-even for paying early", "0.90% on ¥257,200.00: over your limits"),
    "rebate": ("1.25%", "your budget for what you give buyers", "1.30%: over your limits"),
}
LEVER_WORDS_ZH = {
    "terms_alone": ("45 天", "您给买家让利的预算", "50 天：超出您的底线；其资金安排今天无法执行"),
    "terms_budget_ignored": ("55 天", "您的现金底线", "60 天：超出您的底线"),
    "terms_with_price": ("55 天，加价 0.30%", "您的现金底线", "60 天，加价 1.00%：超出您的底线"),
    "early_pay_whole": ("0.70%，金额 ¥420,000.00", "您已有的更便宜的资金安排", "0.75%，金额 ¥420,000.00：超出您的底线"),
    "early_pay_counter": ("0.85%，金额 ¥257,200.00", "提前付款的盈亏平衡点", "0.90%，金额 ¥257,200.00：超出您的底线"),
    "rebate": ("1.25%", "您给买家让利的预算", "1.30%：超出您的底线"),
}
SUMMARIES_EN = [
    "45-day terms · rebate 1.25%",
    "45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%",
    "45-day terms · early payment 0.70% · rebate 1.25%",
    "50-day terms · price up 0.10% · rebate 0.55%",
    "50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%",
    "50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%",
    "55-day terms · price up 0.25% · rebate 0.60%",
    "55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%",
    "55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%",
    "45-day terms · early payment 0.85% on ¥257,200.00",
    "55-day terms · price up 0.30%",
]


def test_the_lever_table_comes_worded_by_the_server_in_english(answer):
    assert {lv.key: (lv.maximum_display, lv.wall_words, lv.next_step_sentence) for lv in answer.levers} == LEVER_WORDS_EN
    assert [p.summary for p in answer.packages] == SUMMARIES_EN


def test_the_lever_table_comes_worded_by_the_server_in_chinese(cold):
    zh = envelope_answer(cold[0], "zh")
    assert {lv.key: (lv.maximum_display, lv.wall_words, lv.next_step_sentence) for lv in zh.levers} == LEVER_WORDS_ZH
    assert zh.packages[6].summary == "55 天账期 · 加价 0.25% · 返利 0.60%"
    assert zh.packages[1].summary == "45 天账期 · 提前付款 0.85%，金额 ¥257,200.00 · 返利 1.25%"


def test_the_zone_rows_say_the_lowest_price_in_words(zoned):
    words = {z.terms_days: z.lowest_price_words for z in zoned.zone}
    assert [words[d] for d in (30, 35, 40, 45)] == ["no price rise needed"] * 4
    assert words[50] == "0.10%" and words[55] == "0.25%"
    assert [z.terms_words for z in zoned.zone][:2] == ["30 days", "35 days"]
    assert [words[d] for d in range(60, 91, 5)] == ["none works"] * 7


def test_the_zone_rows_say_the_lowest_price_in_chinese(golden):
    zh = {z.terms_days: z.lowest_price_words for z in envelope_answer(golden.facts(zone=True), "zh").zone}
    assert [z.terms_words for z in envelope_answer(golden.facts(zone=True), "zh").zone][:2] == ["30 天", "35 天"]
    assert zh[30] == zh[45] == "无需加价" and zh[50] == "0.10%" and zh[60] == "没有可行的价格"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_server_strings_use_business_words(golden, lang):
    a = envelope_answer(golden.facts(zone=True), lang)
    texts = [*[w for lv in a.levers for w in (lv.maximum_display, lv.wall_words or "", lv.next_step_sentence)],
             *[p.summary for p in a.packages], *[z.lowest_price_words for z in a.zone], *[z.at_that_price.summary for z in a.zone]]
    for text in texts:
        assert text and not DAY_N.search(text), text
        assert not CODE_NAME.search(text), text
        for engine_word in ("verdict", "trajectory", "basis", "fen", "offer them", "give them", "cure", "standing plan",
                            "price step", "approved"):
            assert engine_word not in text.lower(), text


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_sentences_use_business_words(cold, lang):
    a = envelope_answer(cold[0], lang)
    for text in (a.primary, a.reason, a.money, *[f for p in a.packages for f in p.flags],
                 *[lv.label for lv in a.levers], *[lv.wall_text or "" for lv in a.levers]):
        assert "offer them" not in text and "give them" not in text, text
        assert not DAY_N.search(text), text
        assert not CODE_NAME.search(text), text
        for engine_word in ("verdict", "trajectory", "basis", "fen", "cure", "standing plan", "price step"):
            assert engine_word not in text.lower(), text


def test_the_primary_uses_the_rule_price_and_keeps_the_smallest_in_the_payload(answer):
    assert "0.30%" in answer.primary and "0.25%" not in answer.primary
    assert _by_lever(answer)[TERMS_WITH_PRICE].at_maximum.package.price_bp == 25  # type: ignore[union-attr]


# ---------------------------------------------------------------- a buyer with nothing to value


def test_a_buyer_with_no_lever_is_refused_in_one_sentence(golden):
    for lang, sentence in (
        ("en", "FLOW has no terms, payment or rebate lever to value for Dongguan Office Supplies Ltd. yet."),
        ("zh", "FLOW 目前没有可为Dongguan Office Supplies Ltd.估值的账期、付款或返利杠杆。"),
    ):
        a = envelope(golden.books, golden.mandate, buyer_id="BUYER-2", lang=lang, **golden.kw())
        assert a.refused == sentence
        assert (a.packages, a.levers, a.zone, a.primary, a.reason, a.money) == ([], [], [], "", "", "")
        assert a.evaluations == 0 and a.buyer_name == "Dongguan Office Supplies Ltd."


def test_the_builder_refuses_with_the_same_sentence(golden):
    with pytest.raises(WhatIfParamError, match="FLOW has no terms, payment or rebate lever to value for Dongguan Office Supplies"):
        context(golden.books.state, 0, "BUYER-2")


def test_the_default_context_is_unchanged_and_a_buyer_id_finds_the_same_rows(golden):
    state = golden.books.state
    default = context(state)
    assert isinstance(default, Context) and default.counterparty_id == GOLDEN_BUYER
    assert context(state, 0, GOLDEN_BUYER) == default and context(state, buyer_id=GOLDEN_BUYER) == default


def test_a_buyer_with_an_open_invoice_and_no_recurring_invoice_gets_the_early_pay_levers_only(golden):
    state: FinancialState = golden.books.state.model_copy(update={"recurring_invoices": []})
    ctx = context(state, 0, GOLDEN_BUYER)
    assert isinstance(ctx, EarlyPayContext) and ctx.receivable.id == "RCV-A"
    offer, _ = build(WhatIfParams(terms_days=60, discount_bp=70, rebate_bp=100, price_adjustment_bp=30), ctx)
    assert [o.type.value for o in offer.obligations] == ["IMMEDIATE_DISCOUNT"]  # no terms, rebate or price clause
    a = envelope(replace(golden.books, state=state), golden.mandate, buyer_id=GOLDEN_BUYER, **golden.kw())
    by = _by_lever(a)
    assert by[TERMS_ALONE].unavailable == "no recurring invoice to extend" and by[TERMS_ALONE].maximum is None
    assert by[REBATE].unavailable is not None
    # without the recurring invoices the standing breach is deeper and no early payment fits: the engine's answer
    assert by[early_pay_lever(42_000_000)].maximum == 0 and by[early_pay_lever(42_000_000)].wall == "liquidity"
    assert a.packages and all(p.package.terms_days == a.packages[0].package.terms_days for p in a.packages)
    assert a.refused is None and a.reason == "There is no recurring invoice to extend, so only an early payment can be priced."


# ---------------------------------------------------------------- the searches, on their own


def test_a_neighbour_that_disagrees_sends_the_search_to_a_full_scan():
    values = list(range(0, 50, 5))
    # 15 fails but 20 passes: the search lands on 10, finds a passing value one step past it and scans the lever whole
    found = last_true(values, lambda v: v <= 10 or v == 20)
    assert found.value == 20 and found.scanned and not found.confirmed
    # 15 passes but 20 fails: the search lands on 25, finds a passing value two steps before it and scans
    smallest = first_true(values, lambda v: v >= 25 or v == 15)
    assert smallest.value == 15 and smallest.scanned and not smallest.confirmed


def _at_most(bound: int) -> Callable[[int], bool]:
    return lambda v: v <= bound


def _at_least(bound: int) -> Callable[[int], bool]:
    return lambda v: v >= bound


def test_the_searches_agree_with_a_scan_when_the_lever_is_monotone():
    values = list(range(0, 205, 5))
    for boundary in (0, 5, 70, 125, 200):
        ok = _at_most(boundary)
        scan = max(v for v in values if ok(v))
        for kw in ({}, {"gallop": True}, {"hint": boundary}, {"hint": 100}):
            f = last_true(values, ok, **kw)
            assert (f.value, f.confirmed) == (scan, True), (boundary, kw)
        assert descend(values, ok, 150).value == scan
        up = _at_least(boundary)
        for hint in (None, boundary, 95):
            g = first_true(values, up, hint=hint)
            assert (g.value, g.confirmed) == (boundary, True), (boundary, hint)
    assert last_true(values, lambda v: False).value is None
    assert first_true(values, lambda v: False).value is None


# ---------------------------------------------------------------- the day-34 books


def test_day_34_books_no_extension_passes_without_a_price_rise(rt_day34, books_day34):
    g = Golden(rt_day34, books_day34, rt_day34.store.get_mandate())
    started = time.perf_counter()
    facts = g.facts()
    a = envelope_answer(facts, "en")
    print(f"\nenvelope, day-34 books: {time.perf_counter() - started:.2f} s, {facts.evaluations} verifier runs")
    by = _by_lever(a)
    # the engine's figures: the credit line has ¥13.80 left, cash sits on the ¥300,000 floor (headroom ¥0) and the
    # trajectory breaches on day 42, so nothing can be added without the owner; RCV-A is two days past due
    line = next(f for f in books_day34.state.facilities if f.id == "FAC-LINE")
    assert line.limit_fen - line.drawn_fen == 1_380
    assert books_day34.state.cash_fen == g.mandate.min_cash_fen
    assert a.refused is None and a.source_state_version == books_day34.state.state_version
    # no longer terms pass on their own: the ¥5,000 budget stops them at 50 days (¥7,485.21 against ¥5,000.00)
    assert by[TERMS_ALONE].maximum == 45 and by[TERMS_ALONE].wall == "forward budget"
    assert by[TERMS_ALONE].next_step is not None and by[TERMS_ALONE].next_step.forward_budget_used_fen == 748_521
    # with a price rise the engine does pass them (the verifier judges the offer's own effect, not the standing breach)
    assert by[TERMS_WITH_PRICE].maximum == 80
    assert a.primary.startswith("You can live with: up to 80-day terms if the price rises 0.95%")
    # the early-pay face is the earliest invoice not yet past due, RI:BUYER-1:2 (¥420,000 due day 47), not the overdue RCV-A
    assert context(books_day34.state, 34, GOLDEN_BUYER).receivable.id == "RI:BUYER-1:2"
    assert context(books_day34.state, 34).receivable.id == "RCV-A"  # the default rule is untouched
    early = by[early_pay_lever(42_000_000)]
    assert early.maximum == 40 and early.wall == "plan comparison" and early.face_fen == 42_000_000
    assert early.next_step is not None and early.next_step.package.early_pay_bp == 45
    assert early.next_step.binding_codes == ["EARLY_PAY_DEARER_THAN_PLAN"]
    with_early = [p for p in a.packages if p.package.early_pay_bp == 40]
    assert with_early and all(p.approved and p.package.early_pay_face_fen is None for p in with_early)
    assert "early payment at up to 0.40% on ¥420,000.00" in a.primary
    # the overdue invoice is why the standing position needs the owner, and the reason says so
    assert facts.past_due == ((16_280_000, 2),)
    assert a.reason.startswith("The ¥162,800.00 still owed by Foshan Home Retail Co. is 2 days past due, so any deal "
                               "with Foshan Home Retail Co. needs your approval; the ¥5,000.00 budget buys no terms")
    zh = envelope_answer(facts, "zh")
    assert zh.reason.startswith("Foshan Home Retail Co. 欠款 ¥162,800.00 已逾期 2 天，因此与其做任何交易都需要您批准；")
    assert a.money == "Without a deal your current funding plan costs ¥1,706.10."
    assert all(p.approved for p in a.packages) and not CODE_NAME.search(a.primary + a.reason + a.money)
    assert not DAY_N.search(a.primary + a.reason + a.money)


# ---------------------------------------------------------------- the route


@pytest.fixture
def api(rt_day0, monkeypatch):
    from app.api.strategy_envelope import clear_cache
    from app.main import app

    monkeypatch.delenv("FEATURE_ENVELOPE", raising=False)
    clear_cache()
    set_runtime(rt_day0)
    yield TestClient(app)
    set_runtime(None)
    clear_cache()


def test_route_is_403_with_the_flag_off(api):
    r = api.get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_route_needs_the_owner(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope").status_code == 401


def test_route_404_for_an_unknown_buyer(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    r = api.get("/buyers/NOBODY/envelope", headers=OWNER)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "BUYER_NOT_FOUND"


def test_route_refuses_a_buyer_with_no_lever_with_200(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    body = api.get("/buyers/BUYER-2/envelope?lang=zh", headers=OWNER).json()
    assert body["refused"].startswith("FLOW 目前没有可为Dongguan Office Supplies Ltd.估值")
    assert body["packages"] == [] and body["levers"] == [] and body["zone"] == []
    assert body["hypothetical"] is True and body["day"] == 0


def test_route_rejects_a_bad_query(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=2", headers=OWNER).status_code == 422
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?lang=fr", headers=OWNER).status_code == 422


def test_route_reads_the_zone_from_the_query_string(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    r = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=1", headers=OWNER)
    assert r.status_code == 200 and len(r.json()["zone"]) == 13
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=0", headers=OWNER).json()["zone"] == []
    assert api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=2", headers=OWNER).status_code == 422


def test_route_answers_in_both_languages_from_one_sweep(api, monkeypatch, rt_day0):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    first = api.get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER)
    assert first.status_code == 200
    en = first.json()
    assert (en["primary"], en["reason"], en["money"]) == (PRIMARY_EN, REASON_EN, MONEY_EN)
    assert en["state_version"] == rt_day0.store.get_state().state_version and en["day"] == 0
    assert en["hypothetical"] is True and en["zone"] == [] and en["refused"] is None
    assert en["computed_in_seconds"] > 0 and en["evaluations"] > 0
    pkg = next(p for p in en["packages"] if p["package"]["terms_days"] == 55 and p["package"]["price_bp"] == 30)
    assert pkg["package"]["price_display"] == "0.30%" and pkg["forward_budget_used_display"] == "¥0.00"
    assert pkg["reserve_breach"]["cure_cost_display"] == "¥1,570.36" and pkg["counter_match"] is True
    lever = next(lv for lv in en["levers"] if lv["lever"] == TERMS_WITH_PRICE)
    assert lever["rule_price_display"] == "0.30%" and lever["at_maximum"]["package"]["price_display"] == "0.25%"
    from app.api import strategy_envelope as route

    sweeps: list[int] = []
    real = route.envelope_facts
    monkeypatch.setattr(route, "envelope_facts", lambda *a, **k: sweeps.append(1) or real(*a, **k))
    zh = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?lang=zh", headers=OWNER).json()  # the cached sweep, worded again
    assert sweeps == [] and zh["evaluations"] == en["evaluations"]  # no second sweep: counts, not wall-clock
    assert (zh["primary"], zh["reason"], zh["money"]) == (PRIMARY_ZH, REASON_ZH, MONEY_ZH)


def test_route_cache_holds_32_sweeps():
    from app.api import strategy_envelope as route

    route.clear_cache()
    facts = EnvelopeFacts("B", "B", 0, 1, True, None, 0, 0, False, (), (), (), {}, None, None, False, 0, 0.0)
    for i in range(40):
        route._cache.put(str(i), facts)
    assert len(route._cache) == 32 and route._cache.get("0") is None and route._cache.get("39") is facts
    route.clear_cache()


# ---------------------------------------------------------------- the full grid against the oracle


def test_full_grid_reproduces_the_oracles_thirty_packages(golden):
    oracle = _load("envelope_day0.json")
    clear_caches()
    started = time.perf_counter()
    a = envelope(golden.books, golden.mandate, buyer_id=GOLDEN_BUYER, zone=True, full_grid=True, **golden.kw())
    print(f"\nenvelope, full grid and zone, cold: {time.perf_counter() - started:.2f} s, {a.evaluations} verifier runs")
    mine = {(p.package.terms_days, p.package.price_bp, p.package.early_pay_bp, p.package.early_pay_face_fen,
             p.package.rebate_bp): p for p in a.packages}
    assert len(oracle["packages"]) == 30
    for row in oracle["packages"]:
        early = row["early_pay"]
        key = (row["terms_days"], row["price_adjustment"]["bp"], early["rate"]["bp"] if early else 0,
               None if early is None or early["face"] == "whole invoice" else early["face"]["fen"], row["rebate"]["bp"])
        p = mine.get(key)
        assert p is not None, key
        crumb = row["reserve_breach"]
        assert (p.outcome, p.passes, p.approved) == (row["outcome"], row["passes"], row["counter_grade"]), key
        assert p.codes == row["codes"] and p.binding_codes == row["binding_codes"], key
        assert p.forward_budget_used_fen == row["forward_budget_used"]["fen"], key
        assert _cure(p) == (None if crumb is None else (crumb["day"], crumb["curable"], (crumb["cure_cost"] or {}).get("fen"))), key
    # the maxima and the zone too
    for m in oracle["maxima"]:
        lv = _by_lever(a)[m["lever"]]
        assert lv.maximum == m["value"] and lv.confirmed == m["neighbours_confirmed"], m["lever"]
        if m["next_step"] is not None:
            assert lv.next_step is not None
            assert lv.next_step.binding_codes == m["next_step"]["binding_codes"], m["lever"]
            assert lv.next_step.forward_budget_used_fen == m["next_step"]["forward_budget_used"]["fen"], m["lever"]
    zone = {z.terms_days: z for z in a.zone}
    for o in oracle["zone"]:
        z = zone[o["terms_days"]]
        assert z.min_price_bp == (o["min_price_adjustment"] or {}).get("bp"), o["terms_days"]
        assert z.rule_price_bp == (o["price_that_nets_it_to_zero"] or {}).get("bp"), o["terms_days"]
        assert _setting(z.at_that_price)[1] == o["at_that_price"]["price_adjustment"]["bp"]
    # a failing row is listed but never approved; the approved ones are the grid's passing packages
    assert any(not p.approved for p in a.packages) and any(p.approved for p in a.packages)


# ---------------------------------------------------------------- books off the levers' grids


def _with_terms(golden: Golden, days: int) -> Books:
    other = [r.model_copy(update={"terms_days": days}) if r.counterparty_id == GOLDEN_BUYER else r
             for r in golden.books.state.recurring_invoices]
    return replace(golden.books, state=golden.books.state.model_copy(update={"recurring_invoices": other}))


def test_terms_in_force_off_the_five_day_grid_do_not_crash(golden):
    books = _with_terms(golden, 32)
    facts = envelope_facts(books, golden.mandate, buyer_id=GOLDEN_BUYER, zone=True, **golden.kw())
    a = envelope_answer(facts, "en")
    assert a.refused is None and a.packages and facts.current_terms == 32
    # the terms in force are a point of their own in the range, and the packages at them are carried
    assert 32 in [z.terms_days for z in a.zone] and a.zone[0].terms_days == 30
    assert any(p.package.terms_days == 32 for p in a.packages)
    assert all(p.package.terms_days >= 32 for p in a.packages)
    assert a.primary.startswith("You can live with: ") and envelope_answer(facts, "zh").primary.startswith("您能接受的范围：")
    json.loads(a.model_dump_json())


def _terms_range(golden: Golden, days: int | None) -> tuple[int, ...]:
    books = golden.books if days is None else _with_terms(golden, days)
    ctx = context(books.state, golden.rt.day, GOLDEN_BUYER)
    assert isinstance(ctx, Context)
    return ranges_for(ctx, golden.mandate).terms


def test_the_terms_range_runs_two_steps_past_the_terms_in_force(golden):
    grid = tuple(range(30, 91, 5))
    assert _terms_range(golden, None) == grid  # the golden buyer's 60 days: the range tops out where the sandbox's does
    assert _terms_range(golden, 85) == grid + (95,)
    assert _terms_range(golden, 90) == grid + (95, 100)
    assert _terms_range(golden, 100) == grid + (95, 100, 105, 110)
    assert _terms_range(golden, 88) == tuple(sorted(grid + (88, 95)))  # off the grid: the terms in force are a point of their own
    assert _terms_range(golden, 32)[:3] == (30, 32, 35) and _terms_range(golden, 32)[-1] == 90


def test_the_builder_takes_the_steps_past_the_sandbox_top_as_terms_extensions(golden):
    books = _with_terms(golden, 90)
    ctx = context(books.state, golden.rt.day, GOLDEN_BUYER)
    assert isinstance(ctx, Context)
    for days in (95, 100):
        with pytest.raises(ValueError):
            WhatIfParams(terms_days=days, discount_bp=0, rebate_bp=0)  # the sandbox still refuses them
        offer, _ = build(WhatIfParams.model_construct(terms_days=days, discount_bp=0, rebate_bp=0, price_adjustment_bp=0,
                                                      settle_face_fen=None), ctx, golden.rt.day)
        ext = next(o for o in offer.obligations if o.type.value == "TERMS_EXTENSION")
        assert ext.days_delta == days - 90 and ext.target_terms_days == days


def test_a_buyer_on_90_day_terms_is_scanned_to_100_and_the_zone_has_the_rows(golden):
    books = _with_terms(golden, 90)
    facts = envelope_facts(books, golden.mandate, buyer_id=GOLDEN_BUYER, zone=True, **golden.kw())
    a = envelope_answer(facts, "en")
    assert a.refused is None and facts.current_terms == 90
    assert [z.terms_days for z in a.zone][-3:] == [90, 95, 100]
    levers = _by_lever(a)
    alone = levers[TERMS_ALONE]  # the budget still stops the bare extension, now with a next step to show for it
    assert alone.maximum == 90 and alone.wall == "forward budget" and alone.next_step is not None
    assert alone.next_step.package.terms_days == 95 and not alone.next_step.passes
    for name in (TERMS_BUDGET_IGNORED, TERMS_WITH_PRICE):  # liquidity and the price let both new steps through: the range's top
        assert levers[name].maximum == 100 and levers[name].wall is None and levers[name].next_step is None
    assert "up to 100-day terms (the most FLOW checks) if the price rises 0.25%" in a.primary
    assert "no longer payment terms" not in a.primary
    assert "账期最长 100 天（FLOW 检查的上限；价格上调 0.25%）" in envelope_answer(facts, "zh").primary
    assert any(p.package.terms_days in (95, 100) for p in a.packages)
    json.loads(a.model_dump_json())


def test_a_counter_outside_the_levers_ranges_is_listed_not_probed(golden, monkeypatch):
    from app.strategy import envelope as module

    base = envelope_facts(golden.books, golden.mandate, buyer_id=GOLDEN_BUYER, **golden.kw())
    assert base.unlisted_counters == () and envelope_answer(base).unlisted_counters == []
    # a mandate whose early-payment ceiling (0.60%) is below the counters the verifier names (0.85%): the verifier keeps
    # to the mandate it is given, so the ranges are narrowed here and the verifier still runs on the golden one
    capped = golden.mandate.model_copy(update={"max_immediate_discount_bp": 60})
    narrowed = module.ranges_for
    monkeypatch.setattr(module, "ranges_for", lambda ctx, _mandate: narrowed(ctx, capped))
    facts = envelope_facts(golden.books, golden.mandate, buyer_id=GOLDEN_BUYER, **golden.kw())
    assert facts.unlisted_counters, "the verifier's counter above the cap must be listed"
    assert all(c.discount > 60 for c in facts.unlisted_counters)
    assert all(c.probe.setting.discount <= 60 for c in facts.cells) and facts.evaluations > 0
    assert all(c.discount <= 60 for c in facts.counter_costs_fen)
    en, zh = envelope_answer(facts, "en"), envelope_answer(facts, "zh")
    assert len(en.unlisted_counters) == len(facts.unlisted_counters)
    assert all("not listed" in x and "FLOW's own counter (" in x for x in en.unlisted_counters)
    assert all("未列出" in x for x in zh.unlisted_counters)


# ---------------------------------------------------------------- a buyer with an expected order and nothing else


ORDER_250K = ExpectedOrder(counterparty_id="BUYER-2", label="next quarter", start_day=92, end_day=182, amount_fen=25_000_000)


@pytest.fixture(scope="module")
def rebate_only_books(books_day0: Books) -> Books:
    """The golden books plus BUYER-2's ¥250,000 expected order (H37's, stated in the offer and not on the golden books)."""
    state = books_day0.state.model_copy(update={"expected_orders": [*books_day0.state.expected_orders, ORDER_250K]})
    return replace(books_day0, state=state)


@pytest.fixture(scope="module")
def rebate_only(golden: Golden, rebate_only_books: Books) -> EnvelopeFacts:
    return envelope_facts(rebate_only_books, golden.mandate, buyer_id="BUYER-2", **golden.kw())


def test_a_rebate_only_buyer_has_the_rebate_lever_and_no_other(golden, rebate_only_books, rebate_only):
    from app.strategy.envelope import open_context, ranges_for

    ctx = open_context(rebate_only_books.state, 0, "BUYER-2")
    assert isinstance(ctx, RebateOnlyContext)
    r = ranges_for(ctx, golden.mandate)
    assert (r.terms, r.price, r.discount, r.face_max_fen) == ((), (0,), (0,), 0) and r.rebate[0] == 0 and r.rebate[-1] == 200
    a = envelope_answer(rebate_only, "en")
    assert rebate_only.rebate_only and a.refused is None and rebate_only.receivable_face_fen == 0
    by = _by_lever(a)
    assert [lv.key for lv in a.levers][:3] == ["terms_alone", "terms_budget_ignored", "terms_with_price"]
    for name in (TERMS_ALONE, TERMS_BUDGET_IGNORED, TERMS_WITH_PRICE):
        assert by[name].unavailable == "no recurring invoice to extend" and by[name].maximum is None
    early = next(lv for lv in a.levers if lv.key == "early_pay_whole")
    assert early.unavailable == "no open invoice to pay early" and early.maximum is None and early.label == "Early payment"
    assert by[REBATE].unavailable is None and by[REBATE].maximum == 200 and by[REBATE].maximum_display == "2.00%"


def test_the_rebate_only_sentences(rebate_only):
    en, zh = envelope_answer(rebate_only, "en"), envelope_answer(rebate_only, "zh")
    assert en.primary == "You can live with: a rebate up to 2.00% on the expected order; no terms or early payment to value yet."
    assert zh.primary == "您能接受的范围：对预期订单的返利最高 2.00%；暂无可估值的账期或提前付款。"
    assert en.reason.startswith("There is no recurring invoice to extend and no open invoice to pay early, so only the rebate")
    assert en.money.startswith("The rebate at that most counts ¥5,000.00 against your budget for what you give buyers; ") and "your current funding plan costs" in en.money
    assert zh.money.startswith("按上述上限，返利会占用") and zh.reason.endswith("。")
    assert [(p.package.rebate_bp, p.approved) for p in en.packages] == [(200, True)]
    assert en.packages[0].package.early_pay_bp == 0 and en.packages[0].package.price_bp == 0


def test_the_rebate_only_route_answers_with_the_flag_on(rebate_only_books, monkeypatch):
    from app.api.strategy_envelope import clear_cache
    from app.main import app

    from .conftest import _runtime

    rt = _runtime()
    rt.store.put_state(rebate_only_books.state)
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    clear_cache()
    set_runtime(rt)
    try:
        body = TestClient(app).get("/buyers/BUYER-2/envelope", headers=OWNER)
        assert body.status_code == 200, body.text
        j = body.json()
        assert j["refused"] is None and j["primary"].startswith("You can live with: a rebate up to 2.00%")
        assert [lv["unavailable"] for lv in j["levers"] if lv["unavailable"]] == [
            "no recurring invoice to extend", "no recurring invoice to extend", "no recurring invoice to extend",
            "no open invoice to pay early"]
    finally:
        set_runtime(None)
        clear_cache()


# ---------------------------------------------------------------- the zone cached apart (map #58, follow-up of ticket #78)


def test_the_zone_table_alone_equals_the_rows_of_a_sweep_with_the_zone(golden, zoned):
    from app.strategy.envelope import envelope_zone

    z = envelope_zone(golden.books, golden.mandate, day=golden.rt.day, buyer_id=GOLDEN_BUYER,
                      trusted_owner_key_hex=golden.rt.owner_key_hex, commitments=tuple(golden.rt.store.commitments()))
    assert len(z.rows) == 13 and z.evaluations > 0
    assert envelope_answer(replace(golden.facts(), zone=z.rows), "en").zone == zoned.zone


def test_route_reads_the_zone_after_a_read_without_it_without_a_second_sweep(api, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    from app.api import strategy_envelope as route

    route.clear_cache()
    plain = api.get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER).json()
    sweeps: list[int] = []
    zones: list[int] = []
    real_sweep, real_zone = route.envelope_facts, route.envelope_zone
    monkeypatch.setattr(route, "envelope_facts", lambda *a, **k: sweeps.append(1) or real_sweep(*a, **k))
    monkeypatch.setattr(route, "envelope_zone", lambda *a, **k: zones.append(1) or real_zone(*a, **k))
    both = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=1", headers=OWNER).json()
    again = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=1", headers=OWNER).json()
    assert sweeps == [] and zones == [1], "the sweep is cached; the table is computed once, and then cached too"
    assert plain["zone"] == [] and len(both["zone"]) == 13 and both["zone"] == again["zone"]
    assert {k: v for k, v in both.items() if k not in ("zone", "evaluations", "computed_in_seconds")} == {
        k: v for k, v in plain.items() if k not in ("zone", "evaluations", "computed_in_seconds")}
    assert both["evaluations"] > plain["evaluations"]
    route.clear_cache()
