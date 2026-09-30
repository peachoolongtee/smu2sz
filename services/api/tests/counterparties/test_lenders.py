from __future__ import annotations

import pytest

from app.counterparties import (
    LenderDecisionStatus,
    MockLender,
    UnknownFacility,
    UnknownLender,
    known_lender_ids,
    lender_for,
    term_sheet_text,
)
from app.domain.fixtures import golden_values, load_offers, load_scenario
from app.domain.models import FacilityKind
from app.domain.money import Ratio

PENDING, APPROVED, DECLINED = (
    LenderDecisionStatus.PENDING,
    LenderDecisionStatus.APPROVED,
    LenderDecisionStatus.DECLINED,
)


def test_registry_covers_every_lender_facility_in_golden_sme() -> None:
    state, _ = load_scenario()
    assert known_lender_ids() == ["BANK-1", "BANK-2", "LESSOR-1", "PLATFORM-1"]
    menu = [
        f for f in state.facilities if f.kind not in (FacilityKind.BUYER_EARLY_PAY, FacilityKind.EQUITY)
    ]
    for f in menu:
        lender = lender_for(f.id)
        assert lender.lender_id == f.lender_id
        rules = lender.rules(f.id)
        assert rules.max_amount_fen == f.limit_fen
        assert rules.committed == (f.status.value == "COMMITTED")
        if not rules.committed:
            assert rules.decision_lead_days == f.lead_time_days


def test_ggl_is_pending_before_day_21_and_approved_after_with_a_borrower_file() -> None:
    bank2 = MockLender("BANK-2")
    app = bank2.apply("FAC-GGL", 36_000_000, borrower_file_present=True, day=0)
    assert app.status is PENDING and app.decision_day == 21
    assert "day 21" in app.reason
    for day in (0, 1, 12, 20):
        assert bank2.status(app, day).status is PENDING
    for day in (21, 22, 60):
        later = bank2.status(app, day)
        assert later.status is APPROVED and later.as_of_day == day
    assert bank2.apply("FAC-GGL", 36_000_000, True, 0, current_day=21).status is APPROVED


def test_ggl_is_declined_without_a_borrower_file() -> None:
    bank2 = MockLender("BANK-2")
    app = bank2.apply("FAC-GGL", 36_000_000, borrower_file_present=False, day=0)
    assert app.status is DECLINED and "borrower file" in app.reason
    assert bank2.status(app, 21).status is DECLINED
    assert bank2.status(app, 30).status is DECLINED


def test_application_over_the_limit_is_declined() -> None:
    d = MockLender("BANK-2").apply("FAC-GGL", 50_000_001, True, 0)
    assert d.status is DECLINED and "exceeds the facility limit" in d.reason


def test_equipment_loan_needs_pro_forma_dscr_of_1_25() -> None:
    capex = golden_values()["capex"]
    bank1 = MockLender("BANK-1")

    def dscr(text: str) -> Ratio:
        whole, frac = text.split(".")
        return Ratio(num=int(whole) * 100 + int(frac), den=100)

    weak = bank1.apply("FAC-ETL", 60_000_000, True, 0, pro_forma_dscr=dscr(capex["loan_18m"]["dscr_m1_3"]))
    strong = bank1.apply("FAC-ETL", 60_000_000, True, 0, pro_forma_dscr=dscr(capex["loan_36m"]["dscr_m1_3"]))
    assert weak.status is PENDING and strong.status is PENDING
    assert bank1.status(weak, 14).status is DECLINED
    assert "1.13x" in bank1.status(weak, 14).reason and "1.25x" in bank1.status(weak, 14).reason
    assert bank1.status(strong, 14).status is APPROVED
    edge = bank1.apply("FAC-ETL", 60_000_000, True, 0, pro_forma_dscr=Ratio(num=5, den=4), current_day=14)
    assert edge.status is APPROVED
    missing = bank1.apply("FAC-ETL", 60_000_000, True, 0, current_day=14)
    assert missing.status is DECLINED and "not provided" in missing.reason
    assert bank1.apply("FAC-ETL", 60_000_000, False, 0).status is DECLINED


def test_committed_facility_is_approved_on_the_day() -> None:
    d = MockLender("BANK-1").apply("FAC-LINE", 15_000_000, False, 5)
    assert d.status is APPROVED and d.decision_day == 5
    assert MockLender("PLATFORM-1").apply("FAC-IF", 21_000_000, False, 0).status is APPROVED


def test_lease_decides_after_10_days() -> None:
    lessor = MockLender("LESSOR-1")
    app = lessor.apply("FAC-LEASE", 60_000_000, False, 3)
    assert app.status is PENDING and app.decision_day == 13
    assert lessor.status(app, 13).status is APPROVED


def test_decisions_are_deterministic() -> None:
    a = MockLender("BANK-2").apply("FAC-GGL", 36_000_000, True, 0, current_day=25)
    b = MockLender("BANK-2").apply("FAC-GGL", 36_000_000, True, 0, current_day=25)
    assert a == b and a.application_id == "APP-FAC-GGL-D0-36000000"


def test_unknown_lender_raises() -> None:
    with pytest.raises(UnknownLender):
        MockLender("FASTCAPITAL")
    with pytest.raises(KeyError):
        MockLender("FASTCAPITAL")


def test_unknown_or_foreign_facility_raises() -> None:
    with pytest.raises(UnknownFacility):
        MockLender("BANK-2").apply("FAC-LINE", 1, True, 0)
    with pytest.raises(UnknownFacility):
        lender_for("FAC-FASTCAPITAL")
    with pytest.raises(UnknownFacility):
        MockLender("BANK-1").apply("TS-BANK1-WCL-PG", 30_000_000, True, 0)


def test_bad_inputs_raise() -> None:
    with pytest.raises(ValueError):
        MockLender("BANK-2").apply("FAC-GGL", 0, True, 0)
    with pytest.raises(ValueError):
        MockLender("BANK-2").apply("FAC-GGL", 1, True, 5, current_day=4)


def test_example9_term_sheet_with_a_personal_guarantee_clause() -> None:
    text = term_sheet_text("TS-BANK1-WCL-PG")
    expected = load_offers()["EX09_TERM_SHEET_PG"]["documents"][0]["text"]
    assert text == expected
    assert "personal guarantee" in text
    doc = MockLender("BANK-1").term_sheet_document("TS-BANK1-WCL-PG", doc_id="EX09-ts")
    assert doc.channel == "term_sheet" and doc.sender_id == "BANK-1" and doc.text == expected


def test_menu_term_sheets_state_their_limits() -> None:
    state, _ = load_scenario()
    for f in state.facilities:
        if f.kind in (FacilityKind.BUYER_EARLY_PAY, FacilityKind.EQUITY) or f.limit_fen == 0:
            continue
        text = term_sheet_text(f.id)
        assert f"¥{f.limit_fen // 100:,}" in text, f.id
        assert "personal guarantee" not in text.lower() or f.personal_guarantee
