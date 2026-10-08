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
from app.strategy import PriceCurve, money_line, price_curve, price_sentence
from tests.strategy.conftest import OWNER

pc = importlib.import_module("app.strategy.price_curve")  # `app.strategy.price_curve` the attribute is the function

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


def test_no_arrival_day_is_computed_twice(rt_day34: Runtime, books_day34: Books, monkeypatch: pytest.MonkeyPatch):
    seen: list[int] = []
    real = pc.scenario_inflow

    def spy(books: Books, amount: int, on_day: int) -> Any:
        seen.append(on_day)
        return real(books, amount, on_day)

    monkeypatch.setattr(pc, "scenario_inflow", spy)
    price_curve(books_day34, rt_day34.store.get_mandate(), store=rt_day34.store, day=34)
    shifted = [d for i, d in enumerate(seen) if i % 2 == 0]  # each evaluation reads the d + 30 copy first
    assert len(shifted) == len(set(shifted)) and 40 < len(seen) < 120


def test_a_band_the_budget_cannot_settle_is_marked_varies_with_the_smaller_value(
        rt_day34: Runtime, books_day34: Books, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pc, "MAX_EXTRA_EVALUATIONS", 0)
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
    assert en == "Cash arriving within the next 30 days is worth 0.89% to you; after that, nothing."
    assert "0.89%" in en and "nothing" in en
    zh = price_sentence(curve0, today=0, lang="zh")
    assert zh == "未来 30 天内到账的现金对你价值 0.89%；之后则没有。"
    assert money_line(curve0, "en") == en and money_line(curve0, "zh") == zh


def test_the_day34_sentence_has_two_bands(curve34: PriceCurve):
    en = price_sentence(curve34, today=34, lang="en")
    assert en == ("Cash arriving within the next 8 days is worth 1.78% to you, then 0.89% if it arrives within the "
                  "next 26 days; after that, nothing.")
    zh = price_sentence(curve34, today=34, lang="zh")
    assert zh == "未来 8 天内到账的现金对你价值 1.78%，未来 26 天内到账的为 0.89%；之后则没有。"


def test_a_band_ending_today_or_tomorrow_is_said_as_such():
    def one(last: int) -> PriceCurve:
        return PriceCurve(day=5, flat=False, source_state_version=1, bands=[
            pc.PriceBand(from_day=5, to_day=last, value_fen=8911, value_bp=89),
            pc.PriceBand(from_day=last + 1, to_day=125, value_fen=0, value_bp=0)])

    assert price_sentence(one(5), today=5, lang="en") == "Cash arriving today is worth 0.89% to you; after that, nothing."
    assert price_sentence(one(6), today=5, lang="en") == "Cash arriving by tomorrow is worth 0.89% to you; after that, nothing."
    assert price_sentence(one(6), today=5, lang="zh") == "最迟明天到账的现金对你价值 0.89%；之后则没有。"


def test_the_sentences_use_business_words_only(curve0: PriceCurve, curve34: PriceCurve):
    flat = PriceCurve(day=0, flat=True, source_state_version=1, bands=[pc.PriceBand(from_day=0, to_day=120, value_fen=0, value_bp=0)])
    for curve, today in ((curve0, 0), (curve34, 34), (flat, 0)):
        for text in (price_sentence(curve, today=today, lang="en"), money_line(curve, "en")):
            assert not _DAY_N.search(text), text
            assert not any(w in text.lower() for w in _FORBIDDEN), text
        zh = price_sentence(curve, today=today, lang="zh")
        assert not re.search(r"第 ?\d+ ?天|day", zh), zh
