from fractions import Fraction

import pytest
from hypothesis import given, strategies as st

from app.domain.money import (Ratio, bp, fmt_yuan, gross_up_face, post, round_half_up, simple_interest, yuan)


def test_half_up_both_signs():
    assert round_half_up(Fraction(5, 2)) == 3
    assert round_half_up(Fraction(-5, 2)) == -3
    assert round_half_up(Fraction(249, 100)) == 2


def test_line_interest_fixture():
    assert post(simple_interest(yuan(150000), bp(640), 32)) == yuan("841.64")


def test_gross_up_face():
    assert gross_up_face(yuan(210000), bp(120)) == yuan("212550.61")


def test_yuan_rejects_sub_fen():
    with pytest.raises(ValueError):
        yuan("0.001")


def test_fmt():
    assert fmt_yuan(yuan("26455.62")) == "¥26,455.62"
    assert fmt_yuan(-4504000) == "−¥45,040.00"


def test_ratio_text():
    assert Ratio.of(Fraction(9_000_000, 4_687_130)).text == "1.92"


@given(st.integers(min_value=-10**12, max_value=10**12), st.integers(min_value=1, max_value=10**6))
def test_post_is_nearest(n, d):
    x = Fraction(n, d)
    assert abs(Fraction(post(x)) - x) <= Fraction(1, 2)
