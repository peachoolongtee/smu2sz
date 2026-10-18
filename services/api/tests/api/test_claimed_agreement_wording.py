"""The Chinese twins of the counter's "not on record" clauses (owner's QA report, 18 Oct: a claimed terms agreement was answered "No rebate
is on record"). The clause names what was claimed: a rebate, a payment-terms agreement, a discount, a price agreement, or "such agreement"."""

from __future__ import annotations

import pytest

from app.api.engine_zh import translate
from tests.api.conftest import english_leaks

SETTLE_EN = "We will accept early settlement on up to ¥260,000 of this invoice at 0.85%, paid on or before day 2."


@pytest.mark.parametrize(("en", "zh"), [
    ("No rebate is on record, so none applies", "记录中没有返利，因此不适用"),
    ("No payment-terms agreement is on record, so none applies", "记录中没有账期协议，因此不适用"),
    ("No discount is on record, so none applies", "记录中没有折扣，因此不适用"),
    ("No price agreement is on record, so none applies", "记录中没有价格协议，因此不适用"),
    ("No such agreement is on record, so none applies", "记录中没有此类协议，因此不适用"),
    ("No rebate or payment-terms agreement is on record, so none applies", "记录中没有返利或账期协议，因此不适用"),
    ("Terms stay at 45 days, no rebate", "账期保持 45 天，无返利"),
    ("Terms stay at 45 days, no payment-terms agreement", "账期保持 45 天，无账期协议"),
])
def test_every_not_on_record_clause_has_its_chinese_twin(en: str, zh: str) -> None:
    assert translate(en) == zh
    assert english_leaks({"s": translate(en + ". " + SETTLE_EN)}) == []
