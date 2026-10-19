"""Chinese money units (万 = 10,000, 亿 = 100,000,000) on Arabic, Chinese and 大写 numerals, parsed by code from the quoted
fragment in exact integer fen; counts of things and company names are not money. Both readers use it: the rules grammar and
the model-reading grounding path (so Chromo's cross-check agrees when a model reads 42万 as 420,000)."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.cache import CacheBackend
from app.compiler.cross_check import DISAGREE_FIELD
from app.compiler.parsing import find_money, parse_money
from app.compiler.rules import RulesBackend, rules_offer
from app.compiler.service import cache_dir
from app.config import get_settings
from app.domain.models import CompileStatus, ObligationType, SourceDocument

from .test_cross_check import StandIn

FEN = 100


@pytest.mark.parametrize(("text", "yuan"), [
    ("42万元", 420_000), ("42万", 420_000), ("¥42万", 420_000), ("RMB 42万元", 420_000), ("42 万元", 420_000),
    ("3.5万", 35_000), ("3.5万元", 35_000), ("42.5万元", 425_000), ("1,200万元", 12_000_000), ("1.25万元", 12_500),
    ("1.2亿", 120_000_000), ("0.5亿元", 50_000_000), ("¥1.2亿", 120_000_000),
    ("四十二万元", 420_000), ("四十二万", 420_000), ("四十万零五千元", 405_000), ("一百零五万元", 1_050_000),
    ("一亿元", 100_000_000), ("三万五千元", 35_000),
    ("人民币肆拾贰万元整", 420_000), ("肆拾贰万元整", 420_000), ("叁拾伍万伍仟元整", 355_000), ("壹佰万元整", 1_000_000),
    ("壹亿贰仟万元整", 120_000_000), ("伍仟元整", 5_000), ("人民币叁仟伍佰万元", 35_000_000),
    ("3万5千元", 35_000), ("1亿2千万", 120_000_000), ("2万3千5百元", 23_500),
    ("42万元人民币", 420_000), ("¥420k", 420_000), ("420,000元", 420_000),
])
def test_the_amount_is_read_in_exact_fen(text: str, yuan: int) -> None:
    assert parse_money(text) == yuan * FEN
    assert isinstance(parse_money(text), int)


def test_every_spelling_of_one_amount_is_one_amount() -> None:
    spellings = ["42万元", "四十二万元", "人民币肆拾贰万元整", "¥420k", "420,000元", "¥420,000"]
    assert {parse_money(s) for s in spellings} == {42_000_000}
    assert {parse_money(s) for s in ["3.5万", "3万5千元", "三万五千元"]} == {3_500_000}


@pytest.mark.parametrize("text", [
    "万一出了问题", "万一", "一万步", "我们每天走一万步", "3万人参加", "五万公里", "万科", "万科地产", "万事如意", "千万别忘了",
    "一万二", "四万二", "3万5",  # colloquial and ambiguous: do not guess
])
def test_a_count_a_name_or_an_idiom_is_not_money(text: str) -> None:
    assert find_money(text) == []


def test_a_company_name_does_not_hide_the_amount_beside_it() -> None:
    assert parse_money("万科的42万元发票") == 42_000_000
    assert parse_money("万科42万元") == 42_000_000


def test_a_measure_word_does_not_hide_a_currency_marked_amount() -> None:
    assert parse_money("42万人民币") == 42_000_000 and parse_money("¥42万") == 42_000_000


def test_two_different_amounts_are_still_ambiguous() -> None:
    assert parse_money("42万元或4.2万元") is None


def _doc(text: str) -> list[SourceDocument]:
    return [SourceDocument(doc_id="zhu-1", channel="chat", sender_id="BUYER-1", received_day=0, text=text)]  # type: ignore[arg-type]


@pytest.mark.parametrize("text", [
    "我们愿意提前结清这笔42万元发票，折扣0.6%。其他不变。",
    "我们愿意提前结清这笔四十二万元发票，折扣0.6%。其他不变。",
    "我们愿意提前结清这笔人民币肆拾贰万元整发票，折扣0.6%。其他不变。",
    "We'll settle the 42万元 invoice early at 0.6%. Nothing else changes.",
    "We'll settle the ¥420k invoice early at 0.6%. Nothing else changes.",
])
def test_the_rules_grammar_reads_the_base_amount(text: str) -> None:
    ex = rules_offer(_doc(text))
    early = [o for o in ex.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    assert early and parse_money(early[0].base_amount_text) == 42_000_000
    offer = Compiler([RulesBackend()]).compile_offer(_doc(text), "BUYER-1")
    assert offer.status == CompileStatus.COMPILED
    assert [(o.base.amount_fen, o.rate_bp) for o in offer.obligations] == [(42_000_000, 60)]


def test_the_cross_check_agrees_when_the_model_reads_42_wan_as_420000() -> None:
    docs = _doc("我们愿意提前结清这笔42万元发票，折扣0.6%。其他不变。")
    model = StandIn(lambda d: rules_offer(d))
    offer = Compiler([CacheBackend(cache_dir(get_settings())), model], cross_check=True).compile_offer(docs, "BUYER-1")
    assert model.calls == 1
    assert not [a for a in offer.abstentions if a.field.startswith(DISAGREE_FIELD)]
    assert offer.status == CompileStatus.COMPILED
    assert any(o.base.amount_fen == 42_000_000 for o in offer.obligations)
