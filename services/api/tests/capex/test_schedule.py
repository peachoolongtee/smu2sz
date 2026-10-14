"""ADR-0013, phase 2: a capex contract's payment schedule is derived by code from the reading and the owner's timeline, sums
to the price exactly, and is not derivable (with a reason) whenever a material value cannot be established."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.capex.schedule import Timeline, classify, derive_schedule, events_in, offset_days, schedule_hash
from app.compiler import Compiler
from app.compiler.contract import contract_document
from app.compiler.rules import RulesBackend
from app.domain.fixtures import capex_contract_fixture_bytes
from app.domain.models import CompiledContract, DocumentKind

ANCHOR = "2026-10-01"
HEAD = ("Contract No. T-1. This Contract is made on 8 October 2026 between Alpha Machines Co., Ltd. (the \"Seller\") and "
        "Beta Works Co., Ltd. (the \"Buyer\").\n\n")


def read(text: str) -> CompiledContract:
    doc = contract_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-T")
    return Compiler([RulesBackend()]).compile_contract(doc, DocumentKind.CAPEX_CONTRACT)


def fixture() -> CompiledContract:
    return read(capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8"))


def derive(c: CompiledContract, today: int = 0, **timeline: int):  # type: ignore[no-untyped-def]
    return derive_schedule(c, Timeline(**timeline), anchor_iso=ANCHOR, today=today)


# ---------------------------------------------------------------- the demo contract


def test_the_demo_contract_gives_three_payments_that_sum_to_the_price():
    r = derive(fixture(), delivery_day=60, acceptance_day=80)
    assert r.derivable and r.reasons == []
    s = r.schedule
    assert s is not None and s.price_fen == 60_000_000
    assert [(p.day, p.amount_fen, p.kind, p.event, p.offset_days) for p in s.payments] == [
        (7, 18_000_000, "MILESTONE", "SIGNING", 0),       # the contract's own signing date, 8 Oct 2026 = day 7
        (105, 36_000_000, "MILESTONE", "DELIVERY", 45),   # delivery day 60 + "within forty-five (45) days after"
        (440, 6_000_000, "RETENTION", "ACCEPTANCE", 360),  # acceptance day 80 + 12 months of 30 days
    ]
    assert sum(p.amount_fen for p in s.payments) == s.price_fen
    assert [p.owner_dated for p in s.payments] == [False, True, True]
    assert [p.clause for p in s.payments] == ["4.1", "4.2", "4.3"]
    assert any("not added on top of a milestone" in a for a in s.assumptions)  # clause 4.2 also reads as payment terms


def test_the_demo_contract_early_payment_is_priced_as_an_annual_return():
    s = derive(fixture(), delivery_day=60, acceptance_day=80).schedule
    assert s is not None and s.early_pay is not None
    e = s.early_pay
    assert (e.payment_n, e.rate_bp, e.window_days, e.pay_by_day, e.due_day, e.days_earlier) == (2, 200, 5, 65, 105, 40)
    assert (e.discount_fen, e.pay_early_fen) == (720_000, 35_280_000)
    assert e.implied_annual_rate is not None
    assert e.implied_annual_rate.value == Fraction(720_000, 35_280_000) * Fraction(365, 40)  # 18.62% a year, exactly


def test_the_owner_must_date_the_events_the_contract_cannot():
    r = derive(fixture())
    assert not r.derivable and r.needs == ["delivery_day", "acceptance_day"]
    assert r.reasons == ["Give the delivery day and the acceptance day to date the payments that wait for them."]


def test_the_owners_signing_day_wins_over_the_contracts_date():
    s = derive(fixture(), signing_day=20, delivery_day=60, acceptance_day=80).schedule
    assert s is not None and s.payments[0].day == 20 and s.payments[0].owner_dated


def test_a_payment_before_today_is_not_derivable():
    r = derive(fixture(), today=10, delivery_day=60, acceptance_day=80)  # signing (day 7) is already past
    assert not r.derivable and "before today (day 10)" in r.reasons[0]


def test_a_timeline_out_of_order_is_not_derivable():
    r = derive(fixture(), delivery_day=60, acceptance_day=50)
    assert not r.derivable and r.reasons == ["Your timeline has acceptance (day 50) is before delivery (day 60)."]


def test_the_hash_binds_days_and_amounts():
    a = derive(fixture(), delivery_day=60, acceptance_day=80).schedule
    b = derive(fixture(), delivery_day=60, acceptance_day=80).schedule
    c = derive(fixture(), delivery_day=61, acceptance_day=80).schedule
    assert a is not None and b is not None and c is not None
    assert a.schedule_hash == b.schedule_hash != c.schedule_hash
    assert a.schedule_hash == schedule_hash(a.price_fen, a.payments)


# ---------------------------------------------------------------- shares, retention, rounding


def test_shares_that_do_not_add_up_are_not_derivable():
    c = read(HEAD + "The Contract Price is RMB 100,000.\n\n30% of the Contract Price is payable on signing of this Contract."
             "\n\n60% of the Contract Price is payable upon delivery of the Equipment.\n\nThe Buyer shall retain 5% of the "
             "Contract Price as retention for six (6) months after acceptance.\n")
    r = derive(c, delivery_day=30, acceptance_day=40)
    assert not r.derivable and r.reasons == ["The milestones and the retention add up to 95.00% of the price, not 100%."]


def test_milestones_of_100_percent_keep_the_retention_undeferred():
    c = read(HEAD + "The Contract Price is RMB 100,000.\n\n40% of the Contract Price is payable on signing of this Contract."
             "\n\n60% of the Contract Price is payable upon delivery of the Equipment.\n\nThe Buyer shall retain 5% of the "
             "Contract Price as retention for six (6) months after acceptance.\n")
    s = derive(c, delivery_day=30, acceptance_day=40).schedule
    assert s is not None
    assert [(p.day, p.amount_fen, p.kind) for p in s.payments] == [(7, 4_000_000, "MILESTONE"), (30, 6_000_000, "MILESTONE")]
    assert any("retention is not deferred" in a for a in s.assumptions)


def test_rounding_happens_once_per_payment_and_the_last_payment_carries_the_remainder():
    c = read(HEAD + "The Contract Price is RMB 1,000,000.01.\n\n33.33% of the Contract Price is payable on signing of this "
             "Contract.\n\n33.33% of the Contract Price is payable upon delivery of the Equipment.\n\n33.34% of the Contract "
             "Price is payable upon acceptance of the Equipment.\n")
    s = derive(c, delivery_day=30, acceptance_day=40).schedule
    assert s is not None and s.price_fen == 100_000_001
    a = [p.amount_fen for p in s.payments]
    assert a[0] == a[1] == 33_330_000  # 100,000,001 × 33.33% = 33,330,000.33, half-up once
    assert sum(a) == 100_000_001 and a[2] == 100_000_001 - 2 * 33_330_000


def test_payment_terms_alone_date_the_price_and_hold_back_the_retention():
    c = read(HEAD + "The Contract Price is RMB 100,000.\n\nThe Contract Price is payable thirty (30) days after delivery."
             "\n\nThe Buyer shall retain 5% of the Contract Price as retention for six (6) months after acceptance.\n")
    s = derive(c, delivery_day=30, acceptance_day=40).schedule
    assert s is not None
    assert [(p.day, p.amount_fen, p.kind, p.event) for p in s.payments] == [
        (60, 9_500_000, "PAYMENT_TERMS", "DELIVERY"), (220, 500_000, "RETENTION", "ACCEPTANCE")]


def test_payment_terms_from_the_month_end_count_from_the_next_multiple_of_30_days():
    c = read(HEAD + "The Contract Price is RMB 100,000.\n\nThe Contract Price is payable thirty (30) days after the end of "
             "the month of the invoice.\n")
    s = derive(c, delivery_day=30, invoice_day=45).schedule
    assert s is not None and [(p.day, p.amount_fen) for p in s.payments] == [(90, 10_000_000)]


def test_a_retention_without_a_period_needs_the_owners_release_day():
    text = (HEAD + "The Contract Price is RMB 100,000.\n\n90% of the Contract Price is payable upon delivery of the "
            "Equipment.\n\nThe Buyer shall retain 10% of the Contract Price until the end of the warranty period.\n")
    r = derive(read(text), delivery_day=30)
    assert not r.derivable and r.needs == ["retention_release_day"]
    s = derive(read(text), delivery_day=30, retention_release_day=400).schedule
    assert s is not None and [(p.day, p.amount_fen, p.kind) for p in s.payments] == [
        (30, 9_000_000, "MILESTONE"), (400, 1_000_000, "RETENTION")]


# ---------------------------------------------------------------- what is not derivable


@pytest.mark.parametrize(("clause", "why"), [
    ("100% of the Contract Price is payable upon completion of the works.", "names no event"),
    ("100% of the Contract Price is payable upon delivery and acceptance of the Equipment.", "which one the payment"),
])
def test_a_trigger_the_code_cannot_date_is_not_derivable(clause, why):
    r = derive(read(HEAD + "The Contract Price is RMB 100,000.\n\n" + clause + "\n"), delivery_day=30, acceptance_day=40)
    assert not r.derivable and why in r.reasons[0]


def test_a_price_per_unit_or_a_reading_without_a_price_is_not_derivable():
    per_unit = read(HEAD + "The Unit price is RMB 1,000.\n\n100% of the Contract Price is payable upon delivery of the "
                    "Equipment.\n")
    assert "not one lump sum" in derive(per_unit, delivery_day=30).reasons[0]
    no_price = read(HEAD + "100% of the Contract Price is payable upon delivery of the Equipment.\n")
    assert no_price.status.value == "ABSTAINED"
    assert "complete reading" in derive(no_price, delivery_day=30).reasons[0]


def test_an_early_payment_the_code_cannot_attach_is_reported_not_priced():
    c = read(HEAD + "The Contract Price is RMB 100,000.\n\n50% of the Contract Price is payable upon delivery of the "
             "Equipment.\n\n50% of the Contract Price is payable within thirty (30) days after delivery of the Equipment."
             "\n\nIf the Buyer pays early, within five (5) days of delivery, the Seller grants a discount of 1%.\n")
    s = derive(c, delivery_day=30).schedule
    assert s is not None and s.early_pay is None
    assert s.early_pay_note is not None and "more than one payment" in s.early_pay_note


# ---------------------------------------------------------------- the classifier


@pytest.mark.parametrize(("text", "expected"), [
    ("on signing of this Contract", ("SIGNING", 0)),
    ("within forty-five (45) days after delivery of the Equipment", ("DELIVERY", 45)),
    ("within ten (10) business days after acceptance", ("ACCEPTANCE", 10)),  # business days counted as calendar days
    ("within two (2) months of commissioning", ("ACCEPTANCE", 60)),
    ("upon receipt of the Seller's invoice", ("INVOICE", 0)),
    ("30 days after the date of this Contract", ("SIGNING", 30)),
])
def test_triggers_are_classified_with_their_offsets(text, expected):
    assert classify(text) == expected


def test_a_time_before_an_event_or_two_periods_is_refused():
    from app.capex.schedule import _Unclear

    with pytest.raises(_Unclear):
        offset_days("ten (10) days before delivery")
    with pytest.raises(_Unclear):
        offset_days("30 days or 2 months after delivery")
    assert events_in("the Buyer pays the delivery payment early") == ["DELIVERY"]
