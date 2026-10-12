"""The customer-inputs store's reading side (map #88, brief H.4): what the owner told FLOW about a buyer or the firm.

Three things live here. The validation of a value (`parse_value`: each field takes one type and a range, anything else is
refused before it is stored). The view the strategy modules read (`CustomerInputs`: the row in force for each
(counterparty, field), built from the store; only `aggregate` and `typical_delay_days` are read in Phase 1). And the words
(provenance, field and value, in both languages through `t(lang, en, zh)`; an estimate is never worded as observed).

Context, not books: nothing here is written to `FinancialState`, a verdict, an approval, an execution or the hash chain, and
nothing a row says changes what the mandate allows.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.api.presentation import Lang, t
from app.domain.fixtures import FIXTURES
from app.domain.models import FinancialState
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.domain.ports import LedgerStore
from app.persistence.records import (
    FIRM_FIELDS,
    CustomerInputRecord,
    InputField,
    InputProvenance,
    latest_inputs,
)

GOLDEN_INPUTS = FIXTURES / "customers" / "golden_inputs.json"
DEMO_SOURCE_REF = "Demo assumption"
DEMO_ENTERED_BY = "DEMO"
MAX_TEXT = 64
MAX_DELAY_DAYS = 365

InputValue = bool | int | str


class InputRejected(ValueError):
    """A value the field does not take (wrong type or out of range); the message says why, in a sentence."""


def is_firm_field(f: InputField) -> bool:
    return f in FIRM_FIELDS


def _integer(f: InputField, value: object, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputRejected(f"{f.value} takes a whole number")
    if not low <= value <= high:
        raise InputRejected(f"{f.value} must be between {low} and {high}")
    return value


def _text(f: InputField, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputRejected(f"{f.value} takes a short piece of text")
    if len(value) > MAX_TEXT:
        raise InputRejected(f"{f.value} takes at most {MAX_TEXT} characters")
    return value.strip()


def parse_value(f: InputField, value: object) -> InputValue:
    """The value, checked for its field. Money is integer fen, rates integer bp (a margin may be negative: a loss-making
    customer), days whole numbers of days late (0 for a buyer that pays on time or early), `aggregate` a real boolean.
    Raises `InputRejected` for anything else; a string is never coerced to a number."""
    if f == InputField.ANNUAL_SALES_FEN:
        return _integer(f, value, 0, 10**15)
    if f in (InputField.MARGIN_BP, InputField.COMPANY_GROSS_MARGIN_BP):
        return _integer(f, value, -10_000, 10_000)
    if f == InputField.VAT_RATE_BP:
        return _integer(f, value, 0, 10_000)
    if f == InputField.TYPICAL_DELAY_DAYS:
        return _integer(f, value, 0, MAX_DELAY_DAYS)
    if f == InputField.AGGREGATE:
        if not isinstance(value, bool):
            raise InputRejected("aggregate takes true or false")
        return value
    return _text(f, value)  # margin_basis, classification


def value_json(value: InputValue) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def value_of(record: CustomerInputRecord) -> InputValue:
    """The stored value, decoded and checked again (a row that no longer parses is an integrity fault, not a guess)."""
    return parse_value(InputField(record.field), json.loads(record.value_json))


@dataclass(frozen=True, slots=True)
class TypicalDelay:
    """The owner's own figure for how late a buyer usually pays, with where it came from."""

    days: int
    provenance: InputProvenance
    source_ref: str


@dataclass(frozen=True)
class CustomerInputs:
    """The row in force for each (counterparty, field), as the strategy modules read them. Built by `inputs_from_store`;
    `CustomerInputs()` is an empty view (no buyer is an aggregate, no owner delay)."""

    latest: Mapping[tuple[str | None, str], CustomerInputRecord] = field(default_factory=dict)

    def aggregates(self) -> frozenset[str]:
        """Counterparties whose latest `aggregate` row is true: a name that stands for many small customers (a
        marketplace's shoppers). Excluded from per-customer statements, kept in totals."""
        return frozenset(cp for (cp, f), r in self.latest.items()
                         if cp is not None and f == InputField.AGGREGATE.value and value_of(r) is True)

    def typical_delay(self, buyer_id: str) -> TypicalDelay | None:
        row = self.latest.get((buyer_id, InputField.TYPICAL_DELAY_DAYS.value))
        if row is None:
            return None
        days = value_of(row)
        assert isinstance(days, int) and not isinstance(days, bool)
        return TypicalDelay(days=days, provenance=InputProvenance(row.provenance), source_ref=row.source_ref)

    def digest(self) -> str:
        """What the answers depend on, as a string for a cache key: the rows in force and when they were stored."""
        return json.dumps(sorted((cp or "", f, r.seq) for (cp, f), r in self.latest.items()))


def inputs_from_store(store: LedgerStore) -> CustomerInputs:
    return CustomerInputs(latest=store.latest_customer_inputs())


def inputs_from_rows(rows: list[CustomerInputRecord]) -> CustomerInputs:
    """A view over rows not (yet) in a store: the same "latest wins" the stores use."""
    return CustomerInputs(latest=latest_inputs(rows))


# ---------------------------------------------------------------- the words

_PROVENANCE: dict[InputProvenance, tuple[str, str]] = {
    InputProvenance.ACCOUNTING_HISTORY: ("from your accounts", "来自您的账目"),
    InputProvenance.INVOICE_HISTORY: ("from your invoices", "来自您的发票"),
    InputProvenance.OWNER_ENTERED: ("entered by you", "由您填写"),
    InputProvenance.ERP: ("from your ERP system", "来自您的 ERP 系统"),
    InputProvenance.DERIVED: ("worked out by FLOW from other figures", "由 FLOW 根据其他数字推算"),
    InputProvenance.ESTIMATED: ("an estimate, not a record", "估计值，不是记录"),
    InputProvenance.PROJECTED: ("projected from your books' schedule, not yet happened", "按账上排期推算，尚未发生"),
}

_LABEL: dict[InputField, tuple[str, str]] = {
    InputField.ANNUAL_SALES_FEN: ("Annual sales", "年销售额"),
    InputField.MARGIN_BP: ("Margin", "毛利率"),
    InputField.MARGIN_BASIS: ("Margin basis", "毛利率口径"),
    InputField.CLASSIFICATION: ("Classification", "客户分类"),
    InputField.TYPICAL_DELAY_DAYS: ("Usual delay in paying", "通常的延迟付款天数"),
    InputField.AGGREGATE: ("Stands for many small customers", "代表许多小客户"),
    InputField.VAT_RATE_BP: ("VAT rate", "增值税率"),
    InputField.COMPANY_GROSS_MARGIN_BP: ("Company gross margin", "公司毛利率"),
}


def provenance_words(provenance: str, lang: Lang) -> str:
    return t(lang, *_PROVENANCE[InputProvenance(provenance)])


def field_label(f: str, lang: Lang) -> str:
    return t(lang, *_LABEL[InputField(f)])


def value_words(f: str, value: InputValue, lang: Lang) -> str:
    """The value as the owner reads it: yuan for fen, a percentage for bp (ADR-0002, half-up), days, yes or no."""
    kind = InputField(f)
    if kind == InputField.ANNUAL_SALES_FEN and isinstance(value, int):
        return fmt_yuan(value)
    if kind in (InputField.MARGIN_BP, InputField.VAT_RATE_BP, InputField.COMPANY_GROSS_MARGIN_BP) and isinstance(value, int):
        return fmt_pct(bp(value))
    if kind == InputField.TYPICAL_DELAY_DAYS and isinstance(value, int):
        return t(lang, f"{value} {'day' if value == 1 else 'days'}", f"{value} 天")
    if kind == InputField.AGGREGATE:
        return t(lang, "yes", "是") if value is True else t(lang, "no", "否")
    return str(value)


def input_view(r: CustomerInputRecord, lang: Lang) -> dict[str, Any]:
    """One row for a response: the facts as stored, and the words in the language asked for."""
    value = value_of(r)
    return {
        "counterparty_id": r.counterparty_id, "field": r.field, "field_label": field_label(r.field, lang), "value": value,
        "value_display": value_words(r.field, value, lang), "provenance": r.provenance,
        "provenance_text": provenance_words(r.provenance, lang), "source_ref": r.source_ref, "entered_by": r.entered_by,
        "entered_day": r.entered_day, "state_version": r.state_version, "recorded_at": r.recorded_at, "seq": r.seq,
    }


# ---------------------------------------------------------------- the Demo's rows (fixtures/customers/golden_inputs.json)


def load_demo_inputs(path: Path | None = None) -> list[tuple[str | None, InputField, InputValue]]:
    """The fixture's rows as (counterparty id or None, field, value), each checked for its field."""
    raw = json.loads((path or GOLDEN_INPUTS).read_text(encoding="utf-8"))
    out: list[tuple[str | None, InputField, InputValue]] = []
    for row in raw["inputs"]:
        f = InputField(row["field"])
        cp = row.get("counterparty_id")
        if (cp is None) != is_firm_field(f):
            raise InputRejected(f"{f.value}: a {'firm' if is_firm_field(f) else 'buyer'} field needs "
                                f"{'no counterparty' if is_firm_field(f) else 'a counterparty'}")
        out.append((cp, f, parse_value(f, row["value"])))
    return out


def seed_demo_inputs(store: LedgerStore, state: FinancialState, path: Path | None = None) -> int:
    """Write the Demo's rows as ESTIMATED, source "Demo assumption", entered by DEMO (never OWNER_ENTERED, and never read
    from buyers.yaml). Returns how many were written. Called by the demo reset after the books are seeded."""
    known = {c.id for c in state.counterparties}
    written = 0
    for cp, f, value in load_demo_inputs(path):
        if cp is not None and cp not in known:
            raise InputRejected(f"{f.value}: there is no counterparty {cp} on the books")
        store.add_customer_input(CustomerInputRecord(
            org_id=state.org_id, counterparty_id=cp, field=f.value, value_json=value_json(value),
            provenance=InputProvenance.ESTIMATED.value, source_ref=DEMO_SOURCE_REF, entered_by=DEMO_ENTERED_BY,
            entered_day=state.as_of_day, state_version=state.state_version))
        written += 1
    return written
