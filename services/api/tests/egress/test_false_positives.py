"""No false positives: legitimate counters, a buyer's own invoice, dates, day counts and round numbers."""

from __future__ import annotations

import pytest

from app.egress import (
    OWNER_ID,
    AllowedValue,
    Category,
    PrivateValue,
    ProtectedSet,
    allowed_for_counter,
    assert_no_leak,
    guard,
    scan,
)
from tests.counterparties.builders import OPTION_A_TEXT, OPTION_B_TEXT, option_a, option_b
from tests.egress.helpers import golden_set

OPTION_A_ZH = "账期维持45天，不设返利。我方接受本发票不超过¥211,900的部分以0.85%的折扣提前结算。"
OPTION_B_ZH = "接受60天账期，今后发票价格上调0.45%，不设返利。按¥420,000的发票计，每张发票¥1,890。"
OPTION_B_EXPLAINED = (
    OPTION_B_TEXT + " 0.45% of ¥420,000 is ¥1,890 per invoice, so 60-day terms cost you nothing extra."
)
PER_INVOICE = AllowedValue.money(189_000)  # ¥1,890: Option B's own per-invoice price adjustment


@pytest.mark.parametrize("text", [OPTION_A_TEXT, OPTION_A_ZH])
def test_option_a_counter_passes_to_buyer_1(text: str) -> None:
    allow = allowed_for_counter(option_a())
    assert scan(text, golden_set(), recipient_id="BUYER-1", allow=allow) == []
    result = guard(text, golden_set(), recipient_id="BUYER-1", allow=allow, day=0)
    assert result.ok and result.text_out == text and result.security_event is None


@pytest.mark.parametrize("text", [OPTION_B_TEXT, OPTION_B_ZH, OPTION_B_EXPLAINED])
def test_option_b_counter_passes_to_buyer_1(text: str) -> None:
    allow = [*allowed_for_counter(option_b()), PER_INVOICE]
    assert_no_leak([text], golden_set(), "BUYER-1", allow)
    assert guard(text, golden_set(), recipient_id="BUYER-1", allow=allow, day=0).ok


def test_the_counters_own_values_are_what_the_allow_list_carries() -> None:
    allow = set(allowed_for_counter(option_a()))
    assert AllowedValue.rate_bp(85) in allow and AllowedValue.money(21_190_000) in allow
    assert AllowedValue.rate_bp(45) in set(allowed_for_counter(option_b()))


@pytest.mark.parametrize("text", [
    "Your invoice RCV-A for ¥420,000.00 is due on day 32.",
    "Invoice RCV-A (¥420,000) remains open.",
    "发票RCV-A金额42万元，第32天到期。",
    "early settlement of invoice RCV-A (¥420,000.00) on day 2 at a 0.85% discount",
    "We can settle your 420k invoice early.",
])
def test_a_buyers_own_invoice_is_allowed_to_that_buyer(text: str) -> None:
    allow = [AllowedValue.rate_bp(85)]
    assert scan(text, golden_set(), recipient_id="BUYER-1", allow=allow) == []


def test_the_same_invoice_amount_leaks_to_another_buyer() -> None:
    leaks = scan("Foshan's invoice is ¥420,000.", golden_set(), recipient_id="BUYER-2")
    assert "receivable.RCV-A.face" in {x.label for x in leaks}


BENIGN = [
    "Round 3 of 3. This is our final round.",
    "Payment is due on day 47.",
    "Invoice dated 2026-10-01, due 2026-11-15.",
    "We deliver 52 shipments a year across 12 invoices.",
    "Please pay within 30 days, or 45 days at the latest.",
    "Our Q4 2026 plan covers 120 days.",
    "Meeting at 10:30 on 1 October 2026.",
    "An order of 100 units, 3 rounds, 2 options.",
    "2026年10月1日，第3轮，账期45天，net 45。",
    "We accept 60-day terms and a 365-day horizon.",
    "Thank you. Kind regards, Accounts team.",
    "第一轮：我方统一按45天账期结算。",
    "Terms move from 45 to 60 days from 1 November 2026.",
]


@pytest.mark.parametrize("recipient", ["BUYER-1", "BUYER-2", "FASTCAPITAL"])
def test_dates_day_counts_and_round_numbers_are_never_protected(recipient: str) -> None:
    assert_no_leak(BENIGN, golden_set(), recipient)


def test_years_and_small_amounts_need_a_currency_marker() -> None:
    ps = ProtectedSet.from_values([
        PrivateValue.money("test.year_like", 202_600),  # ¥2,026
        PrivateValue.money("test.small", 60_000),  # ¥600
    ])
    assert scan("Plan for 2026 with 600 units.", ps, recipient_id="BUYER-1") == []
    assert {x.label for x in scan("It is ¥2,026 and 600元.", ps, recipient_id="BUYER-1")} == {
        "test.year_like", "test.small"}


def test_identifiers_are_not_amounts() -> None:
    assert scan("Ticket abc300000 and ref INV-300000.", golden_set(), recipient_id="BUYER-1") == []


def test_owner_sees_mandate_values_but_not_reservations_or_canaries() -> None:
    reservation = PrivateValue.rate_bp("reservation.X.min_discount", 80, category=Category.RESERVATION,
                                       owner_visible=False)
    ps = ProtectedSet.from_values([*golden_set().values, reservation])
    text = "Minimum cash is ¥300,000 and the line is ¥150,000 at 6.4%."
    assert scan(text, ps, recipient_id=OWNER_ID) == []
    leaks = scan("The buyer's floor is 0.80%. Marker TLX-KESTREL-7Q3Z-PROMPT.", ps, recipient_id=OWNER_ID)
    assert {x.label for x in leaks} == {"reservation.X.min_discount", "canary.CANARY-PROMPT"}


def test_a_lender_may_see_its_own_facility_terms_only() -> None:
    text = "Your line of ¥150,000 at 6.4% keeps a DSCR covenant of 1.25x and leverage of 2.5x."
    assert scan(text, golden_set(), recipient_id="BANK-1") == []
    leaks = {x.label for x in scan(text, golden_set(), recipient_id="BANK-2")}
    assert {"facility.FAC-LINE.limit", "facility.FAC-LINE.rate", "mandate.min_dscr"} <= leaks
    assert "mandate.max_leverage" in leaks


def test_an_allowed_value_suppresses_only_that_value() -> None:
    text = "We accept 0.85% on up to ¥211,900; our floor is ¥300,000."
    allow = allowed_for_counter(option_a())
    assert {x.label for x in scan(text, golden_set(), recipient_id="BUYER-1", allow=allow)} == {"mandate.min_cash"}
