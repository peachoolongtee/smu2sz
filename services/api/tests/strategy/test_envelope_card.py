"""Fewer packages on the card (ticket #98, P6; brief E.2; owner's decision 15, #89): at most three.

The verifier's own counters come first, then the answer to the buyer's ask; every other package is behind the disclosure
(`more`). The order is the verifier's and the ask's, never a ranking: nothing on the card is called recommended.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api.runtime import Runtime
from app.books import Books
from app.strategy.envelope import (
    CARD_SIZE,
    AskFacts,
    EnvelopeFacts,
    envelope_answer,
    envelope_ask,
    envelope_facts,
)

GOLDEN_BUYER = "BUYER-1"
OPTION_A = (45, 0, 85, 25_720_000, 0)
OPTION_B = (55, 30, 0, None, 0)
REBATE_COUNTER = (45, 0, 0, None, 125)  # the verifier's counter to one step past the rebate maximum
ASKED_60 = (60, 40, 5, 24_020_000, 0)


@pytest.fixture(scope="module")
def facts(rt_day0: Runtime, books_day0: Books) -> EnvelopeFacts:
    return envelope_facts(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=rt_day0.day, buyer_id=GOLDEN_BUYER,
                          trusted_owner_key_hex=rt_day0.owner_key_hex, commitments=tuple(rt_day0.store.commitments()))


def _ask(rt: Runtime, books: Books, terms: int) -> AskFacts:
    return envelope_ask(books, rt.store.get_mandate(), day=rt.day, buyer_id=GOLDEN_BUYER, trusted_owner_key_hex=rt.owner_key_hex,
                        terms=terms, commitments=tuple(rt.store.commitments()))


@pytest.fixture(scope="module")
def ask60(rt_day0: Runtime, books_day0: Books) -> AskFacts:
    return _ask(rt_day0, books_day0, 60)


def _key(p: Any) -> tuple[int, int, int, int | None, int]:
    q = p.package
    return (q.terms_days, q.price_bp, q.early_pay_bp, q.early_pay_face_fen, q.rebate_bp)


def test_without_an_ask_the_card_holds_the_verifiers_three_counters_in_the_order_of_the_asks(facts):
    a = envelope_answer(facts, "en")
    assert [_key(p) for p in a.packages] == [OPTION_A, OPTION_B, REBATE_COUNTER]  # early payment, terms, rebate
    assert all(p.counter_match and p.approved for p in a.packages)
    assert len(a.more) == 8 and {_key(p) for p in a.more}.isdisjoint({OPTION_A, OPTION_B, REBATE_COUNTER})
    assert len(a.packages) + len(a.more) == len(facts.cells) == 11  # nothing is dropped, only moved behind the disclosure


def test_with_the_ask_its_answer_keeps_the_third_place_and_the_last_counter_moves_behind_the_disclosure(facts, ask60):
    a = envelope_answer(facts, "en", ask60)
    assert [_key(p) for p in a.packages] == [OPTION_A, OPTION_B, ASKED_60]
    assert len(a.packages) == CARD_SIZE == 3
    assert a.packages[2].authority == "needs_owner" and not a.packages[2].counter_match
    assert len(a.more) == 9 and _key(a.more[0]) == REBATE_COUNTER


def test_an_ask_answered_by_a_package_already_listed_is_not_repeated(facts, rt_day0, books_day0):
    a = envelope_answer(facts, "en", _ask(rt_day0, books_day0, 55))  # 0.25% at 55 days: a grid cell of its own
    keys = [_key(p) for p in a.packages]
    assert keys[:2] == [OPTION_A, OPTION_B] and keys[2] == (55, 25, 0, None, 0) and len(set(keys)) == 3
    assert (55, 25, 0, None, 0) not in {_key(p) for p in a.more}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_nothing_is_ranked_or_called_recommended(facts, ask60, lang):
    a = envelope_answer(facts, lang, ask60)
    texts = [a.primary, a.reason, a.money, a.ask.sentence if a.ask else "",
             *[w for p in [*a.packages, *a.more, *a.over_your_limits]
               for w in (p.summary, p.authority_words or "", p.authority_sentence or "", *p.flags)]]
    for text in texts:
        low = text.lower()
        assert "recommend" not in low and "best" not in low and "推荐" not in text and "建议" not in text, text
