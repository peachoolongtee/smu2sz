"""Borrower-file contracts. Strict and frozen; every figure carries its evidence label."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.domain.models import Contract, Day, Fen
from app.domain.money import Ratio

TITLE_EN = "Borrower file (micro-enterprise loan format)"
TITLE_ZH = "借款资料 (小微企业贷款格式)"
LENDER_NOTE = ("Designed to be consumable by a digital SME lender. The lender is mocked; no lender "
               "branding or application form is reproduced.")
LENDER_NOTE_ZH = "为数字化小微企业贷款机构的读取而设计。贷款机构为模拟对象。"
STATUS_NOTE = "Prepared, not sent. The owner reviews and submits it (Tier 2); the agent never applies."
STATUS_NOTE_ZH = "已生成，未发送。由企业主审阅并提交 (二级审批)；代理不会代为申请。"


class Evidence(StrEnum):
    OBSERVED = "OBSERVED"  # read from the verified ledger / fixture state or the operations log
    PROJECTED = "PROJECTED"  # computed by the engine in conservative mode (pro forma where stated)
    OWNER_ESTIMATE = "OWNER_ESTIMATE"  # entered by the owner; never relied on by the projections


EVIDENCE_TEXT = {
    Evidence.OBSERVED: ("Observed", "实际记录", "read from the verified ledger state or the operations log"),
    Evidence.PROJECTED: ("Projected", "预测", "engine projection, conservative mode"),
    Evidence.OWNER_ESTIMATE: ("Owner estimate", "企业主估计", "entered by the owner; not relied on"),
}


class Figure(Contract):
    """One stated value. `text` is display-ready (money formatted on the server)."""

    text: str
    evidence: Evidence
    fen: Fen | None = None
    ratio: Ratio | None = None
    formula: str | None = None
    source: str = ""  # e.g. "state.cash_fen", "trajectory day 30", "op seq 3"


class Row(Contract):
    label: str
    figures: list[Figure] = Field(min_length=1)
    note: str = ""

    @property
    def evidence(self) -> str:
        kinds = list(dict.fromkeys(f.evidence.value for f in self.figures))
        return kinds[0] if len(kinds) == 1 else "/".join(kinds)

    @property
    def value(self) -> str:
        return " · ".join(f.text for f in self.figures)


class Section(Contract):
    key: str
    title_en: str
    title_zh: str
    columns: list[str] = Field(default_factory=list)  # for tables: one per figure in each row
    rows: list[Row]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aligned(self) -> Section:
        if self.columns and any(len(r.figures) != len(self.columns) for r in self.rows):
            raise ValueError(f"section {self.key}: every row needs one figure per column")
        return self


class Provenance(Contract):
    org_id: str
    as_of: str
    state_version: int
    mandate_version: int
    chain_head_hash: str | None
    chain_length: int
    chain_valid: bool
    generated_day: Day
    basis: Literal["CONSERVATIVE"] = "CONSERVATIVE"
    calc: str = "app.financial.project (integer fen, ADR-0002)"


class BorrowerFile(Contract):
    file_id: str
    title_en: str = TITLE_EN
    title_zh: str = TITLE_ZH
    status: Literal["PREPARED_NOT_SENT"] = "PREPARED_NOT_SENT"
    lender_mocked: Literal[True] = True
    lender_note: str = LENDER_NOTE
    facility_id: str
    amount_fen: Fen
    use_of_proceeds: str
    generated_day: Day
    sections: list[Section]
    provenance: Provenance
