"""Wave 2 of map #47: the cash price curve, pinned to the collections spike's recorded oracle
(fixtures/strategy/collections_both.json) as integer fen, with its sentence in both languages and its route."""

from __future__ import annotations

import dataclasses
import importlib
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books
from app.funding.rates import break_even_cost_share
from app.funding.search import GRID_STEP_FEN
from app.strategy import PriceCurve, money_line, price_sentence
from app.strategy.price_curve import price_curve
from tests.strategy.conftest import OWNER

pc = importlib.import_module("app.strategy.price_curve")  # the package exports no `price_curve`: the attribute is the submodule

_ORACLE = Path(__file__).resolve().parents[4] / "fixtures" / "strategy" / "collections_both.json"
_DAY_N = re.compile(r"\bday \d")
_FORBIDDEN = ("rate", "charged", "interest")


def _oracle(which: int) -> dict[int, int]:
    books = json.loads(_ORACLE.read_text(encoding="utf-8"))["books"]
    book = next(b for b in books if b["books"] == f"day {which}")
    return {p["arrival_day"]: int(p["worth"]["fen"]) for p in book["cash_price_curve"]["points"]}


def _spans(curve: PriceCurve) -> list[tuple[int, int, int]]:
    return [(b.from_day, b.to_day, b.value_fen) for b in curve.bands]


def _value_on(curve: PriceCurve, d: int) -> int:
    return next(b.value_fen for b in curve.bands if b.from_day <= d <= b.to_day)


@pytest.fixture(scope="module")
def curve0(rt_day0: Runtime, books_day0: Books) -> PriceCurve:
    return price_curve(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=0)


@pytest.fixture(scope="module")
def curve34(rt_day34: Runtime, books_day34: Books) -> PriceCurve:
    return price_curve(books_day34, rt_day34.store.get_mandate(), store=rt_day34.store, day=34)


# ---------------------------------------------------------------- the bands


def test_day0_bands_are_the_briefs_pins(curve0: PriceCurve):
    assert curve0.amount_fen == GRID_STEP_FEN == 1_000_000 and curve0.window_days == 30
    assert curve0.hypothetical is True and curve0.flat is False
    assert _spans(curve0) == [(0, 0, 0), (1, 30, 8911), (31, 120, 0)]
    assert [b.value_bp for b in curve0.bands] == [0, 89, 0]


def test_day34_bands_are_the_briefs_pins(curve34: PriceCurve):
    assert _spans(curve34) == [(34, 42, 17822), (43, 60, 8912), (61, 154, 0)]
    assert [b.value_bp for b in curve34.bands] == [178, 89, 0]


@pytest.mark.parametrize("which", [0, 34])
def test_every_oracle_point_falls_in_a_band_with_its_value(which: int, curve0: PriceCurve, curve34: PriceCurve):
    curve = curve0 if which == 0 else curve34
    assert not any(b.varies for b in curve.bands)
    for d, fen in _oracle(which).items():
        assert _value_on(curve, d) == fen, d


@pytest.mark.parametrize("which", [0, 34])
def test_the_bands_tile_the_horizon_without_a_gap_or_a_repeat(which: int, curve0: PriceCurve, curve34: PriceCurve):
    curve = curve0 if which == 0 else curve34
    assert curve.bands[0].from_day == curve.day == which
    for a, b in zip(curve.bands, curve.bands[1:], strict=False):
        assert b.from_day == a.to_day + 1
        assert (a.value_fen, a.varies) != (b.value_fen, b.varies)  # equal neighbours are merged
    assert curve.bands[-1].to_day == which + 120


def test_the_value_never_exceeds_the_cost_of_funds(rt_day0: Runtime, books_day0: Books, rt_day34: Runtime,
                                                    books_day34: Books, curve0: PriceCurve, curve34: PriceCurve):
    one, _, _ = break_even_cost_share(books_day0.state, rt_day0.store.get_mandate(), 30)
    assert round(one * GRID_STEP_FEN) == 8911
    assert max(b.value_fen for b in curve0.bands) <= round(one * GRID_STEP_FEN)
    # invoice financing bills whole periods: the oracle's own day-34 point (¥178.22) is two periods, and no more
    two, _, _ = break_even_cost_share(books_day34.state, rt_day34.store.get_mandate(), 60)
    assert max(b.value_fen for b in curve34.bands) <= round(two * GRID_STEP_FEN) == 17822
    assert all(b.value_fen <= 8912 for b in curve34.bands if b.from_day >= 43)


def test_a_value_above_the_cost_of_funds_is_a_runtime_error(rt_day0: Runtime, books_day0: Books, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pc, "_ceiling_fen", lambda *_: 100)
    with pytest.raises(RuntimeError, match="above the cost of funds"):
        price_curve(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=0)


def test_no_arrival_day_is_planned_twice(rt_day34: Runtime, books_day34: Books, monkeypatch: pytest.MonkeyPatch):
    seen: list[int] = []
    real = pc.scenario_inflow

    def spy(books: Books, amount: int, on_day: int) -> Any:
        seen.append(on_day)
        return real(books, amount, on_day)

    monkeypatch.setattr(pc, "scenario_inflow", spy)
    price_curve(books_day34, rt_day34.store.get_mandate(), store=rt_day34.store, day=34)
    # a value is the difference of two arrival days' plan costs and every arrival day is planned once: the two legs of
    # neighbouring days share their costs, and the events cut the days so that the bisection stays short
    assert len(seen) == len(set(seen)) and 8 < len(seen) < 40


def test_a_band_the_budget_cannot_settle_is_marked_varies_with_the_smaller_value(
        rt_day34: Runtime, books_day34: Books, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pc, "MAX_EXTRA_EVALUATIONS", 0)
    monkeypatch.setattr(pc, "_sample_days", lambda _b, _m, _s, day, last: [day, last])  # no event cuts: nothing to settle with
    curve = price_curve(books_day34, rt_day34.store.get_mandate(), store=rt_day34.store, day=34)
    varying = [b for b in curve.bands if b.varies]
    assert varying and all(b.value_fen == 0 for b in varying)  # the smaller of 8912 and 0


def test_a_state_with_no_breach_is_flat(rt_day0: Runtime, books_day0: Books):
    rich = dataclasses.replace(books_day0, state=books_day0.state.model_copy(update={"cash_fen": 100_000_000}))
    curve = price_curve(rich, rt_day0.store.get_mandate(), store=rt_day0.store, day=0)
    assert curve.flat is True
    assert all(b.value_fen == 0 and b.value_bp == 0 and not b.varies for b in curve.bands)
    assert price_sentence(curve, today=0, lang="en") == "Earlier cash saves you nothing today."
    assert money_line(curve, "en") == "Earlier cash saves you nothing today."
    assert "现金" in price_sentence(curve, today=0, lang="zh")


def test_the_runtime_of_the_day0_curve(rt_day0: Runtime, books_day0: Books, capsys: pytest.CaptureFixture[str]):
    price_curve(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=0)  # warm
    t0 = time.perf_counter()
    price_curve(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=0)
    seconds = time.perf_counter() - t0
    with capsys.disabled():
        print(f"\nprice curve, day 0, warm: {seconds:.2f} s")
    assert seconds < 5


# ---------------------------------------------------------------- the sentence


def test_the_day0_sentence(curve0: PriceCurve):
    en = price_sentence(curve0, today=0, lang="en")
    assert en == ("Cash in the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); "
                  "after that, earlier cash saves nothing.")
    zh = price_sentence(curve0, today=0, lang="zh")
    assert zh == "未来 30 天内到账的现金，每 ¥10,000 为您节省 ¥89.11 的融资成本（0.89%）；之后更早到账也不再节省。"
    assert money_line(curve0, "en") == en and money_line(curve0, "zh") == zh


def test_the_day34_sentence_has_two_bands(curve34: PriceCurve):
    en = price_sentence(curve34, today=34, lang="en")
    assert en == ("Cash in the next 8 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥89.12 (0.89%) "
                  "for the 18 days after; later, nothing.")
    zh = price_sentence(curve34, today=34, lang="zh")
    assert zh == ("未来 8 天内到账的现金，每 ¥10,000 为您节省 ¥178.22 的融资成本（1.78%），随后的 18 天为 ¥89.12（0.89%）；"
                  "再之后没有。")


def test_a_band_ending_today_or_tomorrow_is_said_as_such():
    def one(last: int) -> PriceCurve:
        return PriceCurve(day=5, flat=False, source_state_version=1, bands=[
            pc.PriceBand(from_day=5, to_day=last, value_fen=8911, value_bp=89),
            pc.PriceBand(from_day=last + 1, to_day=125, value_fen=0, value_bp=0)])

    tail = "saves you ¥89.11 of funding cost per ¥10,000 (0.89%); after that, earlier cash saves nothing."
    assert price_sentence(one(5), today=5, lang="en") == f"Cash arriving today {tail}"
    assert price_sentence(one(6), today=5, lang="en") == f"Cash arriving by tomorrow {tail}"
    assert price_sentence(one(6), today=5, lang="zh") == "最迟明天到账的现金，每 ¥10,000 为您节省 ¥89.11 的融资成本（0.89%）；之后更早到账也不再节省。"


def test_two_live_bands_with_a_gap_say_how_far_the_later_one_reaches():
    curve = PriceCurve(day=0, flat=False, source_state_version=1, bands=[
        pc.PriceBand(from_day=0, to_day=10, value_fen=17822, value_bp=178),
        pc.PriceBand(from_day=11, to_day=15, value_fen=0, value_bp=0),
        pc.PriceBand(from_day=16, to_day=40, value_fen=8912, value_bp=89),
        pc.PriceBand(from_day=41, to_day=120, value_fen=0, value_bp=0)])
    assert price_sentence(curve, today=0, lang="en") == (
        "Cash in the next 10 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥89.12 (0.89%) "
        "in the next 40 days; later, nothing.")


def test_a_step_between_two_samples_is_found_at_the_event_day_in_few_reads():
    read: list[int] = []

    def cost(x: int) -> int:
        read.append(x)
        return 0 if x < 31 else 900

    runs = pc._settle(12, 77, cost, [13, 20, 21, 30, 31, 32, 47, 60], lambda: False)
    by_day = {d: r.costs for r in runs for d in range(r.first, r.last + 1)}
    assert sorted(by_day) == list(range(12, 77))  # the runs tile the span
    assert all(by_day[d] == ((0,) if d < 31 else (900,)) for d in by_day)
    assert len(set(read)) <= 8  # the ends and the event days halved down to the step, not a bisection of 65 days


def test_event_days_are_the_flows_receipts_and_debt_payments(books_day0: Books):
    events = pc._event_days(books_day0, 0, 150)
    state = books_day0.state
    assert {f.day for f in state.flows} <= events
    assert {r.due_day for r in state.receivables if r.status == "OPEN"} <= events
    assert {ri_issue + ri.terms_days for ri in state.recurring_invoices for ri_issue in (ri.next_issue_day,)} <= events
    assert {30, 60, 90, 120} & events  # the existing loan's monthly payment


def test_the_sentences_use_business_words_only(curve0: PriceCurve, curve34: PriceCurve):
    flat = PriceCurve(day=0, flat=True, source_state_version=1, bands=[pc.PriceBand(from_day=0, to_day=120, value_fen=0, value_bp=0)])
    for curve, today in ((curve0, 0), (curve34, 34), (flat, 0)):
        for text in (price_sentence(curve, today=today, lang="en"), money_line(curve, "en")):
            assert not _DAY_N.search(text), text
            assert not any(w in text.lower() for w in _FORBIDDEN), text
        zh = price_sentence(curve, today=today, lang="zh")
        assert not re.search(r"第 ?\d+ ?天|day", zh), zh


# ---------------------------------------------------------------- the route


@pytest.fixture
def client(rt_day0: Runtime):
    set_runtime(rt_day0)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def test_the_route_is_403_with_the_flag_off(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FEATURE_PRICE_CURVE", raising=False)
    r = client.get("/cash/price-curve", headers=OWNER)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_the_route_needs_the_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_PRICE_CURVE", "1")
    assert client.get("/cash/price-curve").status_code in (401, 403)


def test_the_route_answers_the_curve_with_display_strings(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_PRICE_CURVE", "1")
    r = client.get("/cash/price-curve", headers=OWNER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hypothetical"] is True and body["flat"] is False
    assert body["day"] == 0 and body["amount_fen"] == 1_000_000 and body["amount_display"] == "¥10,000.00"
    assert body["state_version"] == body["source_state_version"] and body["computed_in_seconds"] >= 0
    assert body["sentence"] == ("Cash in the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); "
                                "after that, earlier cash saves nothing.")
    first, second, third = body["bands"]
    assert first["value_display"] == "¥0.00" and first["from_when"] == "today" and first["to_when"] == "today"
    assert second["value_fen"] == 8911 and second["value_display"] == "¥89.11" and second["value_pct"] == "0.89%"
    assert (second["from_when"], second["to_when"]) == ("tomorrow", "in 30 days")
    assert third["value_display"] == "¥0.00" and third["from_when"] == "in 31 days"
    assert not _DAY_N.search(json.dumps(body))


def test_the_route_speaks_chinese_and_serves_the_second_call_from_its_cache(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_PRICE_CURVE", "1")
    zh = client.get("/cash/price-curve?lang=zh", headers=OWNER).json()
    assert zh["sentence"] == "未来 30 天内到账的现金，每 ¥10,000 为您节省 ¥89.11 的融资成本（0.89%）；之后更早到账也不再节省。"
    assert zh["bands"][1]["to_when"] == "30 天后"
    t0 = time.perf_counter()
    again = client.get("/cash/price-curve", headers=OWNER)
    assert again.status_code == 200 and time.perf_counter() - t0 < 1.0
    assert client.get("/cash/price-curve?lang=fr", headers=OWNER).status_code == 422


def test_the_package_exports_the_module_not_the_function():
    import types

    from app import strategy

    assert isinstance(strategy.price_curve, types.ModuleType) and "price_curve" not in strategy.__all__
    assert strategy.price_curve.price_curve is price_curve
