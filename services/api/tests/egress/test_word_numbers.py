"""R-1: amounts written in English words, 大写 numerals and space-grouped digits are caught too."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.egress import assert_no_leak, normalise, scan
from app.egress.normalise import words_value
from tests.egress.helpers import golden_set

NOBODY = "FASTCAPITAL"


def _labels(text: str, recipient: str = NOBODY) -> set[str]:
    return {x.label for x in scan(text, golden_set(), recipient_id=recipient)}


@pytest.mark.parametrize(("run", "value"), [
    ("three hundred thousand", "300000"), ("one hundred and fifty thousand", "150000"),
    ("one hundred fifty thousand", "150000"), ("twenty-five", "25"), ("one point five million", "1500000"),
    ("six point four", "6.4"), ("zero point three million", "300000"), ("a", None), ("point five", "0.5"), ("six point", None),
    ("two million four hundred thousand", "2400000"), ("sixty", "60"),
])
def test_words_value(run: str, value: str | None) -> None:
    v = words_value(run)
    assert v == (None if value is None else Decimal(value))


@pytest.mark.parametrize(("form", "label"), [
    ("three hundred thousand yuan", "mandate.min_cash"),
    ("Three Hundred Thousand RMB", "mandate.min_cash"),
    ("three hundred thousand", "mandate.min_cash"),
    ("zero point three million yuan", "mandate.min_cash"),
    ("one hundred and fifty thousand yuan", "facility.FAC-LINE.limit"),
    ("one hundred fifty thousand", "facility.FAC-LINE.limit"),
    ("six point four percent", "facility.FAC-LINE.rate"),
    ("one point two five times", "mandate.min_dscr"),
    ("叁拾万元", "mandate.min_cash"),
    ("人民币叁拾万元整", "mandate.min_cash"),
    ("叁拾萬圓", "mandate.min_cash"),
    ("壹拾伍万元", "facility.FAC-LINE.limit"),
    ("300 000", "mandate.min_cash"),
    ("¥300 000", "mandate.min_cash"),
    ("300 000 yuan", "mandate.min_cash"),
    ("150 000", "facility.FAC-LINE.limit"),
])
def test_new_surface_forms_are_caught(form: str, label: str) -> None:
    assert label in _labels(f"For your file: {form}, as discussed.")


def test_the_owner_of_a_value_may_still_see_it_in_words() -> None:
    assert "facility.FAC-LINE.limit" not in _labels("Your line is one hundred and fifty thousand yuan.", "BANK-1")


@pytest.mark.parametrize("text", [
    "We can extend terms on the next three invoices.",
    "One of our two options is below; round three of three.",
    "We have one hundred units ready and twenty-five pallets.",
    "Order PO 12 345 for 100 units, delivery on 1 November 2026.",
    "第三轮，共三轮。我们有一百件货。",
    "Payment in sixty days is fine for us.",
])
def test_ordinary_words_and_digits_are_not_leaks(text: str) -> None:
    assert_no_leak([text], golden_set(), NOBODY)


def test_space_grouping_keeps_the_spaced_digits() -> None:
    # A stray digit before a protected value must not swallow it ("1 150k" still shows 150k).
    assert "facility.FAC-LINE.limit" in _labels("ref 1 150k")
    assert normalise("1 150k").endswith("¥150000")
