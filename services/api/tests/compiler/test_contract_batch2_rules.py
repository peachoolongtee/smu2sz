"""Code rules added after the second Chinese contract test set. Every string here is synthetic: written for the test,
not copied from a contract."""

from __future__ import annotations

import pytest

from app.compiler.contract_parsing import parse_date

# ---------------------------------------------------------------- slash and dot dates


@pytest.mark.parametrize("text, iso", [
    ("签订日期：2026/5/24", "2026-05-24"), ("2026.03.05", "2026-03-05"), ("2026/3/5", "2026-03-05"),
    ("生效日期：2025.11.04。", "2025-11-04"), ("于2026/12/31前", "2026-12-31"), ("2026.03.05.", "2026-03-05"),
])
def test_slash_and_dot_dates_with_a_four_digit_year_are_read(text, iso):
    assert parse_date(text).value == iso


@pytest.mark.parametrize("text", ["5/24", "3.5", "2026.5", "金额1,234.00元", "单价3.14159元", "12026/3/5", "2026/3/5/7",
                                  "2026/03.05", "V12026.03.05"])
def test_no_date_without_a_four_digit_year_and_one_separator(text):
    assert parse_date(text).value is None
    assert not parse_date(text).conflict


@pytest.mark.parametrize("text", ["2026/2/30", "2026.13.01", "2026/4/31"])
def test_a_slash_or_dot_date_that_does_not_exist_is_not_a_date(text):
    p = parse_date(text)
    assert p.value is None and p.conflict


def test_two_different_slash_dates_are_a_conflict():
    assert parse_date("2026.3.5至2027.3.4").conflict
