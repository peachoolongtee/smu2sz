"""The pilot journal's entry: what the owner did against an answer FLOW gave (docs/pilot/JOURNAL_SPEC.md).

A record the owner makes, appended and never edited, kept in its own store table. It is not the financial state, not an
operation and not part of the hash chain, and it carries no money field. The engine modules (`app/financial`,
`app/verifier`, `app/funding`, `app/alerts`, `app/operations`) never import this module; a test pins that.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.persistence.records import PilotJournalRecord

Answer = Literal["envelope", "worth", "curve"]
Choice = Literal["followed", "partly", "ignored", "not_applicable"]

_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ACCOUNT_SHAPED = re.compile(r"\d{12,}")  # a bank account or card number: twelve digits or more in a row


def looks_like_an_account_number(text: str) -> bool:
    """True when `text` holds twelve or more digits in a row once spaces and hyphens are ignored (how account and card
    numbers are written). A backstop for the approval step, not the control."""
    return _ACCOUNT_SHAPED.search(re.sub(r"[ \-]", "", text)) is not None


class JournalEntryIn(BaseModel):
    """The eight fields the owner's session writes. Unknown fields are refused."""

    model_config = ConfigDict(extra="forbid", strict=True)

    week: Annotated[int, Field(ge=1, le=60)]
    sme: str
    answer: Answer
    flow_said: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    snapshot_hash: str
    owner_did: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    choice: Choice
    recorded_on: str

    @field_validator("sme")
    @classmethod
    def _label(cls, v: str) -> str:
        if not _LABEL.match(v):
            raise ValueError("the SME label is 1 to 64 letters, digits, spaces, hyphens or underscores (a label, not a company name)")
        return v

    @field_validator("snapshot_hash")
    @classmethod
    def _hash(cls, v: str) -> str:
        if not _HASH.match(v):
            raise ValueError("the snapshot hash is the sha256 of the exported file: 64 lowercase hexadecimal characters")
        return v

    @field_validator("recorded_on")
    @classmethod
    def _date(cls, v: str) -> str:
        try:
            parsed = date.fromisoformat(v)
        except ValueError:
            raise ValueError("the date is written YYYY-MM-DD") from None
        if parsed.isoformat() != v:
            raise ValueError("the date is written YYYY-MM-DD")
        return v

    @field_validator("flow_said", "owner_did")
    @classmethod
    def _no_account_numbers(cls, v: str) -> str:
        if looks_like_an_account_number(v):
            raise ValueError("this looks like it holds an account or card number: leave bank identifiers out of the record")
        return v


class JournalEntry(BaseModel):
    """One stored entry as the routes show it. No money field."""

    id: str
    seq: int
    week: int
    sme: str
    answer: Answer
    flow_said: str
    snapshot_hash: str
    owner_did: str
    choice: Choice
    recorded_on: str
    state_version: int
    day: int
    recorded_at: str


def entry_from_record(rec: PilotJournalRecord) -> JournalEntry:
    return JournalEntry(
        id=f"PJ-{rec.seq:06d}", seq=rec.seq, week=rec.week, sme=rec.sme, answer=rec.answer,  # type: ignore[arg-type]
        flow_said=rec.flow_said, snapshot_hash=rec.snapshot_hash, owner_did=rec.owner_did, choice=rec.choice,  # type: ignore[arg-type]
        recorded_on=rec.recorded_on, state_version=rec.state_version, day=rec.day, recorded_at=rec.recorded_at,
    )


class PilotJournalStore(Protocol):
    """What the routes need from a store: both `LedgerStore` implementations provide it; it is not in the `LedgerStore` port."""

    def add_pilot_journal(
        self, *, week: int, sme: str, answer: str, flow_said: str, snapshot_hash: str, owner_did: str, choice: str,
        recorded_on: str, state_version: int, day: int,
    ) -> PilotJournalRecord: ...

    def pilot_journal(self) -> list[PilotJournalRecord]: ...
