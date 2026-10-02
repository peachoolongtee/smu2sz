"""Audit findings A13: F5 (an equipment file keeps the purchase money as cash), the EBITDA label and F7 (the
forward table is rolling and never raises)."""

from __future__ import annotations

import re

from app.borrower_file import build
from app.domain.models import FacilityKind
from tests.borrower_file.test_build import _store

ETL = {"facility_id": "FAC-ETL", "amount_fen": 60_000_000, "use_of_proceeds": "Purchase of production equipment"}
GGL = {"facility_id": "FAC-GGL", "amount_fen": 36_000_000, "use_of_proceeds": "Working capital for payroll"}


def section(bf, key):
    return next(s for s in bf.sections if s.key == key)


def month_cash(bf, month: int) -> int:
    return section(bf, "trajectory_12m").rows[month - 1].figures[0].fen


def test_f5_equipment_file_deducts_the_purchase_by_default():
    # FAC-ETL lands 14 days after the request, so the defaulted spend day is day 14 and the ¥600,000 leaves cash
    # on day 14: month-2 cash (day 60) is ¥661,855.38, not ¥1,261,855.38 (the audit's omitted-spend figure).
    store, _ = _store()
    default = build(store, day=0, **ETL)
    explicit = build(store, day=0, spend_day=14, **ETL)
    kept = build(store, day=0, **{**ETL, "use_of_proceeds": "Working capital"}, spend_day=None)
    # a working-capital file on an equipment loan is still an equipment purpose: the facility is purpose-bound
    assert month_cash(default, 2) == month_cash(explicit, 2) == month_cash(kept, 2) == 66_185_538
    assert next(f for f in store.get_state().facilities if f.id == "FAC-ETL").kind == FacilityKind.EQUIPMENT_TERM_LOAN
    # (the audit's ¥1,261,855.38 was this figure plus the ¥600,000 that was never deducted)
    # a working-capital file on a non-equipment facility is left alone: no purchase is invented
    ggl = month_cash(build(store, day=0, **GGL), 2)
    assert ggl == month_cash(build(store, day=0, **GGL, spend_day=None), 2)


def test_f5_the_defaulted_spend_day_is_stated_in_the_file():
    store, _ = _store()
    bf = build(store, day=0, **ETL)
    proceeds = section(bf, "proceeds")
    row = next(r for r in proceeds.rows if r.label.startswith("Proceeds spent on"))
    assert "assumed" in row.label and row.figures[0].text == "day 14"
    assert any("no spend day was given" in n and "day 14" in n for n in proceeds.notes)
    given = build(store, day=0, spend_day=20, **ETL)
    row = next(r for r in section(given, "proceeds").rows if r.label.startswith("Proceeds spent on"))
    assert row.label == "Proceeds spent on" and row.figures[0].text == "day 20"


def test_a_non_equipment_file_without_a_spend_day_has_no_assumption():
    store, _ = _store()
    bf = build(store, day=0, **GGL)
    assert all(not r.label.startswith("Proceeds spent on") for r in section(bf, "proceeds").rows)


def test_ebitda_is_labelled_as_the_owners_figure_never_as_operating_cash_flow():
    store, _ = _store()
    bf = build(store, day=0, **ETL)
    labels = [r.label for s in bf.sections for r in s.rows]
    assert any("EBITDA (owner's figure)" in label for label in labels)
    assert not any("operating cash flow" in label.lower() for label in labels)
    assert not any("operating cash flow" in label.lower() for s in bf.sections for label in s.notes)


def _day_spans(sec):
    return [tuple(int(x) for x in re.search(r"days (\d+)–(\d+)", r.label).groups()) for r in sec.rows]


def test_f7_a_file_on_day_34_starts_at_day_34_and_covers_360_days():
    # Month k covers days 34 + 30(k−1) + 1 .. 34 + 30k: day 35 .. day 394, twelve 30-day months, no closed day.
    store, _ = _store()
    bf = build(store, day=34, **GGL)
    for key in ("trajectory_12m", "covenant_headroom"):
        spans = _day_spans(section(bf, key))
        assert spans[0] == (35, 64) and spans[-1] == (365, 394) and len(spans) == 12
        assert all(b - a == 29 for a, b in spans)
    weeks = _day_spans(section(bf, "forecast_13w"))
    assert weeks[0] == (35, 41) and weeks[-1] == (119, 125)
    assert min(a for a, _ in weeks + _day_spans(section(bf, "trajectory_12m"))) > 34  # nothing before today
    assert bf.generated_day == 34


def test_f7_a_file_generated_on_day_361_or_later_does_not_raise():
    store, _ = _store()
    for day in (360, 361, 400, 730):
        bf = build(store, day=day, **GGL)
        assert _day_spans(section(bf, "trajectory_12m"))[-1] == (day + 331, day + 360)
        assert any(r.label.startswith("Lowest projected cash") for r in section(bf, "proceeds").rows)
