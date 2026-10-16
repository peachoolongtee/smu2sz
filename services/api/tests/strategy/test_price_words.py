"""The price curve's sentence (read layer): a one-day stretch says "the day after", never "the 1 days after", and a run of
one-day bands (a taper: early cash also retires a small drawn balance for one day fewer each day) is one clause, not one
per day, in English and in Chinese."""

from __future__ import annotations

from app.strategy.price_curve import PriceBand, PriceCurve, price_sentence


def _band(a: int, b: int, fen: int) -> PriceBand:
    return PriceBand(from_day=a, to_day=b, value_fen=fen, value_bp=round(fen / 100), varies=False, above_guard=False)


def _curve(*bands: PriceBand) -> PriceCurve:
    return PriceCurve(amount_fen=1_000_000, day=34, bands=list(bands), flat=False, source_state_version=1)


def test_a_one_day_stretch_is_the_day_after():
    c = _curve(_band(34, 42, 17_822), _band(43, 43, 9_107), _band(44, 60, 8_911), _band(61, 154, 0))
    en = price_sentence(c, today=34, lang="en")
    assert "for the day after" in en and "1 days" not in en
    assert "随后的 1 天为 ¥91.07" in price_sentence(c, today=34, lang="zh")


def test_a_run_of_one_day_bands_is_one_clause():
    c = _curve(_band(34, 42, 17_822), _band(43, 43, 9_107), _band(44, 44, 9_058), _band(45, 45, 9_009),
               _band(46, 46, 8_960), _band(47, 60, 8_911), _band(61, 154, 0))
    en = price_sentence(c, today=34, lang="en")
    assert en == ("Cash in the next 8 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥91.07 falling day by "
                  "day to ¥89.60 (0.91%–0.90%) over the 4 days after, then ¥89.11 (0.89%) for the 14 days after; later, nothing.")
    zh = price_sentence(c, today=34, lang="zh")
    assert zh == ("未来 8 天内到账的现金，每 ¥10,000 为您节省 ¥178.22 的融资成本（1.78%），随后的 4 天从 ¥91.07 逐日降至 ¥89.60"
                  "（0.91%–0.90%），随后的 14 天为 ¥89.11（0.89%）；再之后没有。")
    assert en.count("then") == 2  # four one-day bands, one clause
