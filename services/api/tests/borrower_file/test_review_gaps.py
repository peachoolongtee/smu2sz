"""Review gap G5: the borrower file's "as of" date is the generation day, and its forward months start there."""

from __future__ import annotations

from datetime import date, timedelta

from app.borrower_file import build
from tests.borrower_file.test_build import _store

GGL = {"facility_id": "FAC-GGL", "amount_fen": 36_000_000, "use_of_proceeds": "Working capital for payroll"}


def section(bf, key):
    return next(s for s in bf.sections if s.key == key)


def test_a_file_generated_on_day_34_is_dated_day_34_not_day_0():
    store, _ = _store()
    state = store.get_state()
    assert state.as_of == "2026-10-01"
    expected = (date(2026, 10, 1) + timedelta(days=34)).isoformat()
    bf = build(store, day=34, **GGL)
    row = next(r for r in section(bf, "summary").rows if r.label.startswith("Data as of"))
    assert "generation day 34" in row.label and "day 0" not in row.label
    assert row.figures[0].text == expected
    assert bf.provenance.as_of == expected and bf.provenance.generated_day == 34
    gen = next(r for r in section(bf, "provenance").rows if r.label == "Generated on")
    assert expected in gen.figures[0].text and state.as_of not in gen.figures[0].text


def test_a_file_generated_on_day_0_keeps_the_books_date():
    store, _ = _store()
    bf = build(store, day=0, **GGL)
    row = next(r for r in section(bf, "summary").rows if r.label.startswith("Data as of"))
    assert row.figures[0].text == "2026-10-01" and bf.provenance.as_of == "2026-10-01"


def test_month_1_starts_on_the_generation_day_everywhere_in_the_file():
    store, _ = _store()
    bf = build(store, day=34, **GGL)
    assert section(bf, "trajectory_12m").rows[0].label == "Month 1 (days 35–64)"
    summary = [r for r in section(bf, "summary").rows if r.label.startswith("Month 1")]
    assert [r.label for r in summary] == ["Month 1 (days 35–64) DSCR · leverage (before the facility)"]
    for key in ("forecast", "headroom"):
        sec = next((s for s in bf.sections if s.key == key), None)
        if sec is not None:
            assert not any(r.label.startswith("Month 1 (days 1–") for r in sec.rows)
    # the same table generated on day 0 starts at day 1: the label moves with the generation day
    assert section(build(store, day=0, **GGL), "trajectory_12m").rows[0].label == "Month 1 (days 1–30)"
