"""What a claimed prior agreement is about, read from the stated terms figure and the buyer's quoted words (words only)."""

from __future__ import annotations

import pytest

from app.domain.claims import (
    CLAIM_NOUNS_EN,
    CLAIM_NOUNS_ZH,
    claim_kind,
    claim_kinds,
    is_claim,
    restate_not_on_record,
)
from app.domain.models import (
    BaseKind,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)


def _claim(quote: str, **kw) -> Obligation:
    return Obligation(id="C-1", type=ObligationType.CLAIMED_PRIOR_CONCESSION, counterparty_id="BUYER-1",
                      base=ObligationBase(kind=BaseKind.UNSPECIFIED), contingency=Contingency.CLAIMED_UNEVIDENCED,
                      duration=Duration(kind=DurationKind.ONE_OFF), spans=[SourceSpan(doc_id="D", start=0, end=len(quote), text=quote)],
                      confidence=0.9, **kw)


@pytest.mark.parametrize(("quote", "kw", "kind"), [
    ("the 2% rebate we agreed last month", {"rate_bp": 200}, "rebate"),
    ("As we already agreed, the 3% rebate applies", {"rate_bp": 300}, "rebate"),
    ("上个月你们已经同意的2%返利", {"rate_bp": 200}, "rebate"),
    ("you promised us 1% cashback", {"rate_bp": 100}, "rebate"),
    ("As agreed with your team, we will now pay on 60-day terms", {"target_terms_days": 60}, "terms"),
    ("the 60-day terms you agreed with us", {"target_terms_days": 60}, "terms"),
    ("之前说好的60天账期", {"target_terms_days": 60}, "terms"),
    ("the extension we agreed", {}, "terms"),
    ("you promised us a 2% early payment discount", {"rate_bp": 200}, "discount"),
    ("the 1% off we agreed", {"rate_bp": 100}, "discount"),
    ("之前同意的2%折扣", {"rate_bp": 200}, "discount"),
    ("the price cut you approved", {"rate_bp": 100}, "price"),
    ("the deal we agreed back in March", {}, "other"),
])
def test_claim_kind(quote: str, kw: dict, kind: str) -> None:
    assert claim_kind(_claim(quote, **kw)) == kind


def test_a_stated_terms_figure_decides_whatever_the_quote_says() -> None:
    assert claim_kind(_claim("the arrangement we agreed", target_terms_days=60)) == "terms"


def test_claim_kinds_lists_each_kind_once_in_a_fixed_order() -> None:
    claims = [_claim("the 60-day terms you agreed", target_terms_days=60), _claim("the 2% rebate we agreed", rate_bp=200),
              _claim("the 3% rebate we agreed", rate_bp=300)]
    assert claim_kinds(claims) == ["rebate", "terms"]
    assert claim_kinds([]) == []
    assert all(is_claim(c) for c in claims)


def test_every_noun_has_a_chinese_twin() -> None:
    assert CLAIM_NOUNS_EN.keys() == CLAIM_NOUNS_ZH.keys()


RECORD = "No rebate is on record, so none applies. We will accept early settlement on up to ¥260,000 of this invoice at 0.85%."
STAYS = "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥260,000 of this invoice at 0.85%."


@pytest.mark.parametrize(("claims", "text", "want"), [
    ([_claim("the 2% rebate we agreed last month", rate_bp=200)], RECORD, RECORD),
    ([_claim("As agreed with your team, we will now pay on 60-day terms", target_terms_days=60)], RECORD,
     RECORD.replace("No rebate", "No payment-terms agreement")),
    ([_claim("you promised us a 2% early payment discount", rate_bp=200)], RECORD, RECORD.replace("No rebate", "No discount")),
    ([_claim("the deal we agreed")], RECORD, RECORD.replace("No rebate", "No such agreement")),
    ([_claim("the 60-day terms you agreed", target_terms_days=60), _claim("the 2% rebate we agreed", rate_bp=200)], RECORD,
     RECORD.replace("No rebate", "No rebate or payment-terms agreement")),
    ([_claim("the 60-day terms you agreed", target_terms_days=60)], STAYS, STAYS.replace("no rebate", "no payment-terms agreement")),
    ([], RECORD, RECORD),
])
def test_the_not_on_record_lead_names_what_was_claimed(claims: list[Obligation], text: str, want: str) -> None:
    assert restate_not_on_record(text, claims) == want


def test_only_the_leading_clause_changes() -> None:
    option_b = "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate."
    claims = [_claim("the 60-day terms you agreed", target_terms_days=60)]
    assert restate_not_on_record(option_b, claims) == option_b
