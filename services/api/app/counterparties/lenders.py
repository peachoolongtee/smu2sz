"""Mock lenders for the golden_sme funding menu (fixtures/counterparties/lenders.yaml).

The registry is fixture-only: there is no way to add a lender at runtime, and any other lender id
(e.g. FASTCAPITAL) raises `UnknownLender`. Decisions are pure functions of their inputs:

- screening on the application day: an amount above the limit, or a missing borrower file where
  one is required, is DECLINED at once as an incomplete or ineligible application;
- a COMMITTED facility is APPROVED on the application day;
- otherwise the application is PENDING until `day + decision_lead_days`, then APPROVED or
  DECLINED by the credit rules (e.g. the equipment loan needs a pro-forma DSCR >= 1.25x).

A lender decision says nothing about cash: an APPROVED facility still enters the funding menu
only through an owner-originated change (INVARIANTS 3, 4).
"""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field

from app.counterparties.errors import UnknownFacility, UnknownLender
from app.domain.fixtures import FIXTURES
from app.domain.models import Contract, SourceDocument
from app.domain.money import Ratio, bp, fmt_yuan, ratio_from_bp

LENDERS_YAML: Path = FIXTURES / "counterparties" / "lenders.yaml"


class LenderFacilityRules(Contract):
    facility_id: str
    committed: bool
    decision_lead_days: int = Field(ge=0)
    max_amount_fen: int = Field(ge=0)
    requires_borrower_file: bool
    min_pro_forma_dscr_bp: int | None = None
    term_sheet: str


class OfferedTermSheet(Contract):
    """A term sheet a lender sends that is not on the funding menu. It can only be compiled."""

    term_sheet_id: str
    text: str


class LenderRecord(Contract):
    lender_id: str
    name: str
    facilities: list[LenderFacilityRules]
    offered_term_sheets: list[OfferedTermSheet] = Field(default_factory=list)


class LenderDecisionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"


class LenderDecision(Contract):
    application_id: str
    lender_id: str
    facility_id: str
    amount_fen: int
    borrower_file_present: bool
    pro_forma_dscr: Ratio | None = None
    applied_day: int
    decision_day: int  # when the lender decides (or decided)
    as_of_day: int  # the day this view of the application was taken
    status: LenderDecisionStatus
    reason: str


@lru_cache
def load_lenders(path: Path = LENDERS_YAML) -> dict[str, LenderRecord]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    records = [LenderRecord.model_validate_json(json.dumps(r)) for r in raw["lenders"]]
    out = {r.lender_id: r for r in records}
    if len(out) != len(records):
        raise ValueError("duplicate lender id")
    ids = [f.facility_id for r in records for f in r.facilities] + [
        t.term_sheet_id for r in records for t in r.offered_term_sheets
    ]
    if len(set(ids)) != len(ids):
        raise ValueError("a facility or term sheet belongs to more than one lender")
    return out


def known_lender_ids() -> list[str]:
    return sorted(load_lenders())


class MockLender:
    """One lender from the fixture registry."""

    def __init__(self, lender_id: str) -> None:
        record = load_lenders().get(lender_id)
        if record is None:
            raise UnknownLender(lender_id)
        self._record = record
        self._rules = {f.facility_id: f for f in record.facilities}
        self._sheets = {t.term_sheet_id: t for t in record.offered_term_sheets}

    @property
    def lender_id(self) -> str:
        return self._record.lender_id

    @property
    def name(self) -> str:
        return self._record.name

    @property
    def facility_ids(self) -> list[str]:
        return list(self._rules)

    def rules(self, facility_id: str) -> LenderFacilityRules:
        try:
            return self._rules[facility_id]
        except KeyError:
            raise UnknownFacility(f"{facility_id} is not a facility of {self.lender_id}") from None

    def apply(
        self,
        facility_id: str,
        amount_fen: int,
        borrower_file_present: bool,
        day: int,
        *,
        pro_forma_dscr: Ratio | None = None,
        current_day: int | None = None,
    ) -> LenderDecision:
        """An application made on `day`, as it stands on `current_day` (default: `day`)."""
        rules = self.rules(facility_id)
        if amount_fen <= 0:
            raise ValueError("amount must be positive")
        as_of = day if current_day is None else current_day
        if as_of < day:
            raise ValueError("current_day is before the application day")

        decision_day = day + (0 if rules.committed else rules.decision_lead_days)
        status, reason = LenderDecisionStatus.APPROVED, ""
        if amount_fen > rules.max_amount_fen:
            status, decision_day = LenderDecisionStatus.DECLINED, day
            reason = f"declined: {fmt_yuan(amount_fen)} exceeds the facility limit of {fmt_yuan(rules.max_amount_fen)}"
        elif rules.requires_borrower_file and not borrower_file_present:
            status, decision_day = LenderDecisionStatus.DECLINED, day
            reason = "declined: incomplete application, borrower file required"
        elif rules.committed:
            reason = "approved: facility already committed; available within its limit"
        elif as_of < decision_day:
            status = LenderDecisionStatus.PENDING
            reason = f"under review: decision due on day {decision_day}"
        elif rules.min_pro_forma_dscr_bp is not None and pro_forma_dscr is None:
            status = LenderDecisionStatus.DECLINED
            reason = "declined: pro-forma DSCR not provided"
        elif rules.min_pro_forma_dscr_bp is not None and pro_forma_dscr is not None and (
            pro_forma_dscr.value < bp(rules.min_pro_forma_dscr_bp)
        ):
            minimum = ratio_from_bp(rules.min_pro_forma_dscr_bp).text
            status = LenderDecisionStatus.DECLINED
            reason = f"declined: pro-forma DSCR {pro_forma_dscr.text}x is below the {minimum}x minimum"
        else:
            reason = f"approved on day {decision_day}"

        return LenderDecision(
            application_id=f"APP-{facility_id}-D{day}-{amount_fen}",
            lender_id=self.lender_id,
            facility_id=facility_id,
            amount_fen=amount_fen,
            borrower_file_present=borrower_file_present,
            pro_forma_dscr=pro_forma_dscr,
            applied_day=day,
            decision_day=decision_day,
            as_of_day=as_of,
            status=status,
            reason=reason,
        )

    def status(self, decision: LenderDecision, current_day: int) -> LenderDecision:
        """The same application viewed on a later day."""
        if decision.lender_id != self.lender_id:
            raise UnknownFacility(f"{decision.application_id} was not made to {self.lender_id}")
        return self.apply(
            decision.facility_id,
            decision.amount_fen,
            decision.borrower_file_present,
            decision.applied_day,
            pro_forma_dscr=decision.pro_forma_dscr,
            current_day=current_day,
        )

    def term_sheet_text(self, facility_id: str) -> str:
        """Canned term sheet for a menu facility or an offered (off-menu) term sheet."""
        if facility_id in self._sheets:
            return self._sheets[facility_id].text
        return self.rules(facility_id).term_sheet

    def term_sheet_document(
        self, facility_id: str, received_day: int = 0, doc_id: str | None = None
    ) -> SourceDocument:
        """The term sheet as an untrusted inbound document for the compiler."""
        return SourceDocument(
            doc_id=doc_id or f"TS-{facility_id}",
            channel="term_sheet",
            sender_id=self.lender_id,
            received_day=received_day,
            text=self.term_sheet_text(facility_id),
        )


def lender_for(facility_id: str) -> MockLender:
    """The mock lender behind a facility or offered term sheet id."""
    for record in load_lenders().values():
        if facility_id in {f.facility_id for f in record.facilities} | {
            t.term_sheet_id for t in record.offered_term_sheets
        }:
            return MockLender(record.lender_id)
    raise UnknownFacility(facility_id)


def term_sheet_text(facility_id: str) -> str:
    return lender_for(facility_id).term_sheet_text(facility_id)
