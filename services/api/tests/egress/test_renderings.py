"""Every surface form of every golden protected value is caught (en, zh, full-width, spacing)."""

from __future__ import annotations

import pytest

from app.egress import ProtectedSet, ValueKind, normalise, renderings, scan
from tests.egress.helpers import golden_set

NOBODY = "FASTCAPITAL"  # an unknown sender: entitled to nothing


def _cases() -> list[tuple[str, int, str]]:
    out = []
    for v in golden_set().values:
        if v.kind is ValueKind.TERMS:
            continue  # terms only match next to their owner's alias; see test_guard
        for i, r in enumerate(renderings(v)):
            out.append((v.label, i, r))
    return out


CASES = _cases()


def test_the_golden_set_covers_every_required_source() -> None:
    labels = set(golden_set().labels())
    for required in (
        "mandate.min_cash", "mandate.max_aggregate_forward_concession", "mandate.max_immediate_discount",
        "mandate.min_dscr", "mandate.max_leverage", "mandate.max_apr", "mandate.tier2_single_commitment",
        "facility.FAC-LINE.limit", "facility.FAC-LINE.rate", "facility.FAC-IF.limit", "facility.FAC-IF.fee",
        "facility.FAC-IF.advance_rate", "facility.FAC-IF.all_in_rate", "facility.FAC-GGL.limit",
        "facility.FAC-LINE.covenant.FAC-LINE-DSCR", "state.cash", "debt.D-EQUIP.principal",
        "debt.D-EQUIP.monthly_service", "receivable.RCV-A.face", "receivable.RCV-A.terms",
        "recurring.BUYER-1.terms", "counterparty.BANK-1.name", "counterparty.BUYER-2.name",
        "canary.CANARY-PROMPT", "canary.CANARY-RESERVE-CODE", "canary.CANARY-RESERVE-AMOUNT",
        "canary.CANARY-COUNTERPARTY",
    ):
        assert required in labels, required
    assert len(CASES) > 400


@pytest.mark.parametrize(("label", "idx", "form"), CASES, ids=[f"{c[0]}#{c[1]}" for c in CASES])
def test_every_rendering_is_caught(label: str, idx: int, form: str) -> None:
    leaks = scan(f"As discussed, {form} is the figure.", golden_set(), recipient_id=NOBODY)
    assert label in {x.label for x in leaks}, f"{label} rendering #{idx} not caught"


@pytest.mark.parametrize("form", [
    "¥300,000.00", "¥300,000", "300,000", "300000", "30万", "30万元", "¥300k", "300k", "RMB 300,000",
    "300 thousand", "三十万元", "人民币三十万元", "３０万元", "￥３００，０００", "３００，０００元",
    "300\u2009000", "300\u202f000", "300,000.00元", "CNY 300,000", "0.3 million",
])
def test_min_cash_in_the_required_money_forms(form: str) -> None:
    leaks = scan(f"our reserve is {form}", golden_set(), recipient_id=NOBODY)
    assert "mandate.min_cash" in {x.label for x in leaks}


@pytest.mark.parametrize("form", [
    "6.4%", "6.40%", "640bp", "640 bps", "640 basis points", "0.064", "百分之六点四", "６．４％", "6.4 percent",
])
def test_line_rate_in_the_required_rate_forms(form: str) -> None:
    leaks = scan(f"the line costs {form} a year", golden_set(), recipient_id=NOBODY)
    assert "facility.FAC-LINE.rate" in {x.label for x in leaks}


@pytest.mark.parametrize("form", ["1.25x", "1.25×", "1.25 times", "1.25倍", "1.25X", "１．２５ｘ"])
def test_dscr_floor_in_the_required_ratio_forms(form: str) -> None:
    leaks = scan(f"DSCR must stay above {form}", golden_set(), recipient_id=NOBODY)
    assert "mandate.min_dscr" in {x.label for x in leaks}


@pytest.mark.parametrize(("text", "expected"), [
    ("三十万", "300000"), ("一百五十万元", "1500000"), ("四万五千", "45000"), ("三十万零五百", "300500"),
    ("百分之零点二五", "0.25%"), ("百分之十五", "15%"), ("２０２６", "2026"), ("1,500,000.00", "1500000"),
    ("¥1.5m", "1500000"), ("150k", "150000"), ("640 bps", "6.4%"), ("2.50 times", "2.50x"),
    ("3\u200b0\u200b0,000", "300000"),
])
def test_normalise_reduces_forms_to_canonical_tokens(text: str, expected: str) -> None:
    assert expected in normalise(text)


def test_renderings_include_every_form_the_spec_lists() -> None:
    ps = golden_set()
    money = set(renderings(ps.get("mandate.min_cash")))
    assert {"¥300,000.00", "¥300,000", "300,000", "300000", "30万", "30万元", "¥300k", "300k", "RMB 300,000",
            "300 thousand"} <= money
    rate = set(renderings(ps.get("facility.FAC-LINE.rate")))
    assert {"6.4%", "6.40%", "640bp", "640 bps", "0.064", "百分之六点四"} <= rate
    ratio = set(renderings(ps.get("mandate.min_dscr")))
    assert {"1.25x", "1.25×", "1.25 times"} <= ratio


def test_all_in_rate_is_caught_rounded() -> None:
    # FAC-IF: 7.8% + 0.25% per 30 days = 10.8417% a year
    for form in ("10.84%", "10.8%", "百分之十点八四"):
        leaks = scan(f"our platform charges {form}", golden_set(), recipient_id=NOBODY)
        assert "facility.FAC-IF.all_in_rate" in {x.label for x in leaks}, form


def test_a_protected_set_is_immutable_and_labels_are_unique() -> None:
    ps = golden_set()
    with pytest.raises(ValueError, match="duplicate"):
        ProtectedSet.from_values([*ps.values, ps.values[0]])
    assert "values" in repr(ps) and "300" not in repr(ps)
