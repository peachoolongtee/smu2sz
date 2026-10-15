"""Decision identity for every prefix family of ADR-0011 section 3."""

from __future__ import annotations

import pytest

from app.decisions import (
    alert_cure_id,
    alert_plan_id,
    approval_decision_id,
    deal_id,
    decision_id_for,
    family_of,
    offer_id_of,
)
from app.domain.models import CommitmentStatus
from tests.persistence.factories import commitment

CMT = commitment("CMT-1", CommitmentStatus.PROPOSED)  # offer OFF-1


def ident(payload: dict, key: str, approval_id: str | None = None) -> str | None:
    return decision_id_for(payload, key, [CMT], approval_id=approval_id)


def test_accept_offer_belongs_to_its_deal_whatever_its_key() -> None:
    p = {"kind": "ACCEPT_OFFER", "offer_id": "OFF-1", "offer_version": 1}
    assert ident(p, "accept-CMT-1") == "deal:OFF-1"
    assert ident(p, "accept-CMT-1", approval_id="APR-1") == "deal:OFF-1"  # an approval does not make it a separate record
    assert ident(p, "nl:s1:t3:abc:2:ACCEPT_OFFER") == "deal:OFF-1"  # a chat accept belongs to its deal


def test_reject_offer_belongs_to_its_deal_whatever_its_key() -> None:
    p = {"kind": "REJECT_OFFER", "offer_id": "OFF-1", "reason_codes": []}
    assert ident(p, "decline-OFF-1-V-1") == "deal:OFF-1"  # the owner's refusal of a request closes that negotiation
    assert ident(p, "nl:s1:t3:abc:2:REJECT_OFFER") == "deal:OFF-1"


def test_record_commitment_belongs_to_the_deal_of_its_commitment() -> None:
    assert ident({"kind": "RECORD_COMMITMENT", "commitment_id": "CMT-1"}, "rec-1", "APR-4") == "deal:OFF-1"


def test_record_commitment_of_an_unknown_commitment_falls_back_to_its_approval() -> None:
    assert ident({"kind": "RECORD_COMMITMENT", "commitment_id": "CMT-404"}, "rec-1", "APR-4") == "approval:APR-4"
    assert ident({"kind": "RECORD_COMMITMENT", "commitment_id": "CMT-404"}, "rec-1") is None


def test_negotiation_funding_legs_belong_to_the_deal_by_the_fallback_key() -> None:
    draw = {"kind": "DRAW_FACILITY"}
    assert ident(draw, "fund-OFF-1-cooperative-0") == "deal:OFF-1"
    assert ident(draw, "fund-OFF-1-hard_line-3") == "deal:OFF-1"
    assert ident(draw, "fund-OFF-X-9-hard_line-1") == "deal:OFF-X-9"  # an offer id with hyphens in it
    assert ident(draw, "fund-OFF-1-cooperative-0", approval_id="APR-2") == "deal:OFF-1"


def test_alert_cure_legs_share_one_id_with_the_state_version_in_it() -> None:
    draw = {"kind": "DRAW_FACILITY"}
    assert ident(draw, "alert:ALERT-RESERVE-34:v3:0") == "alert:ALERT-RESERVE-34:v3"
    assert ident(draw, "alert:ALERT-RESERVE-34:v3:12") == "alert:ALERT-RESERVE-34:v3"
    assert ident(draw, "alert:ALERT-RESERVE-34:v4:0") == "alert:ALERT-RESERVE-34:v4"
    assert ident(draw, "alert:ALERT-RESERVE-34:v3:0", approval_id="APR-3") == "alert:ALERT-RESERVE-34:v3"


def test_router_plan_legs_have_their_own_id() -> None:
    draw = {"kind": "SUBMIT_INVOICE_FOR_FINANCING"}
    assert ident(draw, "alert:ALERT-RESERVE-34:v3:plan:0") == "alert:ALERT-RESERVE-34:v3:plan"
    assert ident(draw, "alert:ALERT-RESERVE-34:v3:plan:1") == "alert:ALERT-RESERVE-34:v3:plan"


def test_an_alert_id_that_holds_colons_and_hyphens_still_parses() -> None:
    assert ident({"kind": "DRAW_FACILITY"}, "alert:ALERT-COVENANT-DSCR-4:v10:2") == "alert:ALERT-COVENANT-DSCR-4:v10"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("nl:sess1:t4:9f8e7d:1:DRAW_FACILITY", "nl:sess1:t4:9f8e7d"),
        ("nl:sess1:r:req-77:2:SUBMIT_INVOICE_FOR_FINANCING", "nl:sess1:r:req-77"),
        ("nl:sess1:r:req:with:colons:3:REPAY_FACILITY", "nl:sess1:r:req:with:colons"),
    ],
)
def test_chat_operations_share_the_session_and_scope(key: str, expected: str) -> None:
    assert ident({"kind": "DRAW_FACILITY"}, key) == expected


def test_two_operations_of_one_chat_turn_share_a_decision_and_two_turns_do_not() -> None:
    a = ident({"kind": "DRAW_FACILITY"}, "nl:s:t1:n:1:DRAW_FACILITY")
    b = ident({"kind": "DRAW_FACILITY"}, "nl:s:t1:n:2:SUBMIT_INVOICE_FOR_FINANCING")
    c = ident({"kind": "DRAW_FACILITY"}, "nl:s:t2:n:1:DRAW_FACILITY")
    assert a == b != c


def test_any_other_approval_is_its_own_record() -> None:
    assert ident({"kind": "APPLY_FOR_FACILITY"}, "capex:7", "APR-9") == "approval:APR-9"


def test_a_direct_operation_with_no_approval_is_activity_not_a_decision() -> None:
    assert ident({"kind": "DRAW_FACILITY"}, "my-own-key") is None
    assert ident({"kind": "RECEIVE_PAYMENT"}, "bank-feed-1") is None


def test_a_non_owner_decide_attempt_keeps_the_decision_of_the_operation() -> None:
    p = {"kind": "ACCEPT_OFFER", "offer_id": "OFF-1"}
    assert ident(p, "accept-CMT-1#decide:APR-1:AGENT") == "deal:OFF-1"
    assert ident({"kind": "DRAW_FACILITY"}, "alert:A-1:v2:0#decide:APR-1:AGENT") == "alert:A-1:v2"


def test_a_key_that_only_looks_like_a_prefix_is_not_one() -> None:
    assert ident({"kind": "DRAW_FACILITY"}, "alertx:A-1:v2:0") is None
    assert ident({"kind": "DRAW_FACILITY"}, "alert:A-1:v2:x") is None  # the leg index is a number
    assert ident({"kind": "DRAW_FACILITY"}, "nl:s1:oops") is None
    assert ident({"kind": "DRAW_FACILITY"}, "fund-OFF-1-cautious-0") is None


def test_the_id_builders_match_what_the_parser_returns() -> None:
    assert deal_id("OFF-1") == "deal:OFF-1"
    assert alert_cure_id("A-1", 3) == ident({"kind": "DRAW_FACILITY"}, "alert:A-1:v3:0")
    assert alert_plan_id("A-1", 3) == ident({"kind": "DRAW_FACILITY"}, "alert:A-1:v3:plan:0")
    assert approval_decision_id("APR-1") == "approval:APR-1"


def test_offer_id_and_family_of_an_id() -> None:
    assert offer_id_of("deal:OFF-1") == "OFF-1"
    assert offer_id_of("deal:") is None and offer_id_of("alert:A:v1") is None
    assert [family_of(i) for i in ("deal:OFF-1", "alert:A:v1", "alert:A:v1:plan", "nl:s:t1:n", "approval:APR-1", "other")] == [
        "DEAL", "FUNDING", "FUNDING", "FUNDING", "FUNDING", None,
    ]


def test_the_same_inputs_always_give_the_same_id() -> None:
    p = {"kind": "DRAW_FACILITY"}
    assert {ident(p, "alert:A-1:v3:0") for _ in range(5)} == {"alert:A-1:v3"}
