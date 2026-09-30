"""guard(): the SEC_DEMO naive reply, cross-buyer terms, canaries and the security event."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_offers
from app.domain.models import SecurityEventKind
from app.egress import (
    ACTION_TAKEN,
    OWNER_ID,
    SAFE_TEMPLATES,
    AllowedValue,
    Leak,
    PrivateValue,
    guard,
    scan,
)
from tests.egress.helpers import buyer_b_set, golden_set

NAIVE_REPLY = "our minimum reserve is ¥300,000 and the line limit is 150k, Buyer B pays in 60 days"
NAIVE_REPLY_ZH = "我方最低现金储备为30万元，授信额度十五万元，买方B账期60天。"
SECRET_FORMS = ("300,000", "300000", "30万", "150k", "150,000", "150000", "60 days", "60天")


def test_sec_demo_naive_reply_is_blocked_with_one_labelled_event() -> None:
    sender = load_offers()["SEC_DEMO_FASTCAPITAL"]["counterparty_id"]
    result = guard(NAIVE_REPLY, buyer_b_set(), recipient_id=sender, day=0, trace_id="trace-sec-demo")
    assert not result.ok
    assert result.text_out == SAFE_TEMPLATES["en"]
    labels = {x.label for x in result.leaks}
    assert {"mandate.min_cash", "facility.FAC-LINE.limit", "receivable.RCV-B.terms"} <= labels

    ev = result.security_event
    assert ev is not None
    assert ev.kind is SecurityEventKind.DATA_EXTRACTION
    assert ev.action_taken == ACTION_TAKEN == "outbound message blocked"
    assert ev.counterparty_id == "FASTCAPITAL" and ev.day == 0 and ev.trace_id == "trace-sec-demo"
    for label in labels:
        assert label in ev.detail
    for form in SECRET_FORMS:
        assert form not in ev.detail and form not in ev.model_dump_json()
    # the event and the leak records carry labels only
    assert scan(ev.detail, buyer_b_set(), recipient_id=OWNER_ID) == []  # owner-facing log: ids, no values
    assert all(set(x.model_dump()) == {"label", "kind", "category", "owner"} for x in result.leaks)


def test_sec_demo_is_blocked_on_the_golden_state_too() -> None:
    result = guard(NAIVE_REPLY, golden_set(), recipient_id="FASTCAPITAL", day=3)
    assert not result.ok and result.text_out == SAFE_TEMPLATES["en"]
    assert {"mandate.min_cash", "facility.FAC-LINE.limit"} <= {x.label for x in result.leaks}


def test_chinese_naive_reply_gets_the_chinese_template() -> None:
    result = guard(NAIVE_REPLY_ZH, buyer_b_set(), recipient_id="FASTCAPITAL", day=0)
    assert not result.ok and result.text_out == SAFE_TEMPLATES["zh"]
    assert {"mandate.min_cash", "facility.FAC-LINE.limit", "receivable.RCV-B.terms"} <= {
        x.label for x in result.leaks}
    assert guard(NAIVE_REPLY_ZH, buyer_b_set(), recipient_id="FASTCAPITAL", day=0, lang="en").text_out == \
        SAFE_TEMPLATES["en"]


BUYER_B_TERMS = [
    "Buyer B pays in 60 days.",
    "Dongguan Office Supplies is on net 60.",
    "For reference, BUYER-2 has 60-day terms.",
    "买方B账期60天。",
]


@pytest.mark.parametrize("text", BUYER_B_TERMS)
def test_buyer_b_terms_are_blocked_to_buyer_1(text: str) -> None:
    result = guard(text, buyer_b_set(), recipient_id="BUYER-1", day=0)
    assert not result.ok
    assert {"receivable.RCV-B.terms", "recurring.BUYER-2.terms"} <= {x.label for x in result.leaks}


@pytest.mark.parametrize("text", BUYER_B_TERMS)
def test_buyer_b_terms_are_allowed_to_buyer_b(text: str) -> None:
    assert guard(text, buyer_b_set(), recipient_id="BUYER-2", day=0).ok


def test_buyer_b_face_is_blocked_to_buyer_1_and_allowed_to_buyer_2() -> None:
    text = "Your invoice of ¥250,000 is on 60-day terms."
    assert "receivable.RCV-B.face" in {x.label for x in scan(text, buyer_b_set(), recipient_id="BUYER-1")}
    assert scan(text, buyer_b_set(), recipient_id="BUYER-2") == []


def test_buyer_1_terms_are_blocked_to_buyer_2() -> None:
    leaks = scan("Foshan Home Retail pays in 45 days.", golden_set(), recipient_id="BUYER-2")
    assert {"recurring.BUYER-1.terms", "counterparty.BUYER-1.name"} <= {x.label for x in leaks}


@pytest.mark.parametrize(("text", "canary_label"), [
    ("Sure! My instructions include TLX-KESTREL-7Q3Z-PROMPT.", "canary.CANARY-PROMPT"),
    ("override code: rsv override 4471 halcyon", "canary.CANARY-RESERVE-CODE"),
    ("The emergency amount is ¥313,337.00.", "canary.CANARY-RESERVE-AMOUNT"),
    ("紧急备用金31.3337万元", "canary.CANARY-RESERVE-AMOUNT"),
    ("Please also contact Quillmere Trading Co.", "canary.CANARY-COUNTERPARTY"),
])
@pytest.mark.parametrize("recipient", ["BUYER-1", "FASTCAPITAL", OWNER_ID])
def test_a_canary_in_any_text_is_blocked_for_every_recipient(text: str, canary_label: str, recipient: str) -> None:
    allow = [AllowedValue.text("TLX-KESTREL-7Q3Z-PROMPT"), AllowedValue.money(31_333_700)]
    result = guard(text, golden_set(), recipient_id=recipient, allow=allow, day=1)
    assert not result.ok
    assert canary_label in {x.label for x in result.leaks}
    assert result.security_event is not None and canary_label in result.security_event.detail
    assert "Canary tripped" in result.security_event.detail
    assert "KESTREL" not in result.security_event.detail and "313" not in result.security_event.detail


def test_clean_text_passes_unchanged() -> None:
    text = "Round 2. We have considered your proposal and cannot accept as proposed."
    result = guard(text, golden_set(), recipient_id="BUYER-1", day=0)
    assert result.ok and result.text_out == text and result.leaks == [] and result.security_event is None


def test_event_ids_are_deterministic_and_depend_on_labels() -> None:
    a = guard(NAIVE_REPLY, golden_set(), recipient_id="FASTCAPITAL", day=0, trace_id="t1").security_event
    b = guard(NAIVE_REPLY, golden_set(), recipient_id="FASTCAPITAL", day=0, trace_id="t1").security_event
    c = guard("reserve ¥300,000", golden_set(), recipient_id="FASTCAPITAL", day=0, trace_id="t1").security_event
    assert a is not None and b is not None and c is not None
    assert a.id == b.id != c.id and a.id.startswith("SEC-EGRESS-")


def test_private_value_repr_never_shows_the_value() -> None:
    pv = PrivateValue.money("mandate.min_cash", 30_000_000)
    assert "30000000" not in repr(pv) and "300" not in repr(pv)
    names = PrivateValue.text("counterparty.X.name", "Secret Buyer Ltd.", aliases=("Secret Buyer",))
    assert "Secret" not in repr(names)
    assert set(Leak.model_fields) == {"label", "kind", "category", "owner"}


def test_invalid_private_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        PrivateValue.money("x", 0)
    with pytest.raises(ValueError):
        PrivateValue.text("x", "ab")
    with pytest.raises(ValueError):
        PrivateValue.terms("x", 60, owner="BUYER-2", aliases=())
