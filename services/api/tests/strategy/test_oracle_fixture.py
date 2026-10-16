"""The recorded output of the research spikes (fixtures/strategy/*.json) is the differential oracle of map #47.
These tests pin its headline figures, so a re-recording that moves one is noticed. Nothing in the app reads the files."""

import json
from pathlib import Path
from typing import Any

import pytest

_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "strategy"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_DIR / name).read_text(encoding="utf-8"))
    return data


def _one(items: list[dict[str, Any]], **where: Any) -> dict[str, Any]:
    hits = [i for i in items if all(i.get(k) == v for k, v in where.items())]
    assert len(hits) == 1, (where, len(hits))
    return hits[0]


def _fen(a: dict[str, Any]) -> int:
    return int(a["fen"])


def _bp(r: dict[str, Any]) -> int:
    return int(r["bp"])


@pytest.fixture(scope="module")
def envelope() -> dict[str, Any]:
    return _load("envelope_day0.json")


@pytest.fixture(scope="module")
def collections() -> dict[str, Any]:
    return _load("collections_both.json")


@pytest.fixture(scope="module")
def portfolio() -> dict[str, Any]:
    return _load("portfolio_default.json")


def test_every_file_carries_its_meta():
    for name in ("envelope_day0.json", "collections_both.json", "portfolio_default.json"):
        meta = _load(name)["_meta"]
        assert set(meta) == {"command", "branch", "base_commit", "recorded"}
        assert "FLOW_RESEARCH_SPIKES=1" in meta["command"]


def test_envelope_levers(envelope):
    maxima = {m["lever"]: m for m in envelope["maxima"]}
    alone = maxima["Terms (days), alone"]
    assert alone["value"] == 45 and alone["wall"] == "forward budget"
    over = alone["next_step"]
    assert over["terms_days"] == 50 and over["passes"] is False
    assert "AGG_CONCESSION_EXCEEDED" in over["codes"]
    assert maxima["Terms (days), budget ignored"]["value"] == 55
    assert maxima["Early pay on ¥420,000.00"]["value"] == 70
    assert maxima["Early pay on ¥260,000.00"]["value"] == 85
    assert maxima["Rebate on the expected order"]["value"] == 125
    early = maxima["Early pay on ¥260,000.00"]["at_largest"]["early_pay"]
    assert _fen(early["face"]) == 26_000_000 and early["rate"]["display"] == "0.85%"
    assert maxima["Early pay on ¥420,000.00"]["at_largest"]["early_pay"]["face"] == "whole invoice"


def test_envelope_zone(envelope):
    zone = {z["terms_days"]: z for z in envelope["zone"]}
    assert zone[55]["min_price_adjustment"] == {"bp": 25, "display": "0.25%"}
    assert zone[55]["price_that_nets_it_to_zero"] == {"bp": 30, "display": "0.30%"}
    assert _bp(zone[50]["min_price_adjustment"]) == 10
    assert zone[60]["passes_within_range"] is False and zone[60]["min_price_adjustment"] is None
    breach = zone[60]["at_that_price"]["reserve_breach"]
    assert breach["day"] == 47 and breach["curable"] is False


def test_envelope_package_cure_cost(envelope):
    # the grid pairs 55 days with its smallest passing price (25 bp); no 30 bp package is recorded
    pkg = _one(
        envelope["packages"],
        terms_days=55,
        price_adjustment={"bp": 25, "display": "0.25%"},
        early_pay={"rate": {"bp": 85, "display": "0.85%"}, "face": {"fen": 26_000_000, "display": "¥260,000.00"}},
    )
    assert pkg["passes"] is True and pkg["outcome"] == "NEEDS_OWNER_APPROVAL"
    assert pkg["reserve_breach"]["day"] == 47
    assert pkg["reserve_breach"]["cure_cost"] == {"fen": 262_356, "display": "¥2,623.56"}


def _book(collections: dict[str, Any], label: str) -> dict[str, Any]:
    return _one(collections["books"], books=label)


def _ranked(book: dict[str, Any], receivable: str) -> dict[str, Any]:
    return _one(book["ranking"], receivable=receivable)


def _ceiling(row: dict[str, Any], face_fen: int) -> dict[str, Any]:
    return next(e for e in row["early_pay"] if _fen(e["face"]) == face_fen)


def test_collections_day_34(collections):
    book = _book(collections, "day 34")
    rcv = _ranked(book, "RCV-A")
    assert _fen(rcv["marginal_value"]) == 136_426 and rcv["marginal_value"]["display"] == "¥1,364.26"
    assert _fen(rcv["effects"][0]["saving"]) == 136_426
    assert rcv["effects"][0]["after"]["need"] == {"fen": 4_000_000, "display": "¥40,000.00"}
    assert "¥40,000.00" in rcv["sentence"]

    ri2 = _ranked(book, "RI:BUYER-1:2")
    assert _fen(ri2["marginal_value"]) == 170_220
    assert _bp(_ceiling(ri2, 20_000_000)["largest_rate"]) == 80
    assert _bp(_ceiling(ri2, 42_000_000)["largest_rate"]) == 40
    shortfall_face = _ceiling(ri2, 20_000_000)
    assert shortfall_face["next_rate_dearer_by"] == {"fen": 168, "display": "¥1.68"}
    assert next(s for s in shortfall_face["sweep"] if _bp(s["rate"]) == 40)["c1_less_c0"]["display"] == "−¥899.92"

    ri32 = _ranked(book, "RI:BUYER-1:32")
    five_earlier = _one(ri32["effects"], receipt_day=72)
    assert _fen(five_earlier["saving"]) == -6_150


def test_collections_day_0(collections):
    book = _book(collections, "day 0")
    rcv = _ranked(book, "RCV-A")
    by_breach = _one(rcv["effects"], receipt_day=12)
    assert _fen(by_breach["saving"]) == 311_393
    assert _bp(_ceiling(rcv, 42_000_000)["largest_rate"]) == 70


def _segments(book: dict[str, Any]) -> list[tuple[int, int, int]]:
    segs: list[list[int]] = []
    for p in book["cash_price_curve"]["points"]:
        worth = _fen(p["worth"])
        if segs and segs[-1][2] == worth:
            segs[-1][1] = p["arrival_day"]
        else:
            segs.append([p["arrival_day"], p["arrival_day"], worth])
    return [(a, b, w) for a, b, w in segs]


def test_collections_price_curve(collections):
    for label in ("day 0", "day 34"):
        assert _fen(_book(collections, label)["cash_price_curve"]["amount"]) == 1_000_000
    day0 = _segments(_book(collections, "day 0"))
    assert day0[1] == (1, 30, 8_911)
    assert day0[2][0] == 31 and day0[2][2] == 0
    day34 = _segments(_book(collections, "day 34"))
    assert day34[0] == (34, 42, 17_822)
    # days 43 to 46 also retire the line's ¥2,790 draw (R-10 rounding) one day sooner each (2,790 × 6.4% × n/365 per ¥10,000
    # of cash on top of one invoice-financing period, 89.11): 91.07, 90.58, 90.09, 89.60, then 89.11 to day 60
    assert day34[1:6] == [(43, 43, 9_107), (44, 44, 9_058), (45, 45, 9_009), (46, 46, 8_960), (47, 60, 8_911)]
    assert day34[6][0] == 61 and day34[6][2] == 0


def test_portfolio_default(portfolio):
    best = portfolio["ranked"][0]
    assert best["rank"] == 1
    assert _fen(best["posted_cost"]) == 303_599
    assert _fen(best["funding_cost"]) == 82_599
    assert portfolio["counts"]["feasible"] == 9
    greedy = portfolio["greedy_evaluate_many"]
    assert greedy["rank_in_enumeration"] == 7 and greedy["feasible_portfolios"] == 9
    assert _fen(greedy["cost_for_ranking"]) == 611_393
    assert _fen(greedy["best_cost_for_ranking"]) == 303_599


@pytest.fixture(scope="module")
def packages() -> list[dict[str, Any]]:
    """The ten recorded evaluations (the deep dive's nine packages; package 8 at price 95 and at price 100), in order."""
    recorded: list[dict[str, Any]] = _load("envelope_packages.json")["requested"]
    assert len(recorded) == 10
    return recorded


def _package_at(recorded: list[dict[str, Any]], index: int, terms: int, price: int, rebate: int = 0) -> dict[str, Any]:
    p = recorded[index]
    assert (p["terms_days"], _bp(p["price_adjustment"]), _bp(p["rebate"])) == (terms, price, rebate)
    return p


def test_package_1_terms_50_with_rebate_fails(packages):
    p = _package_at(packages, 0, 50, 0, 125)
    assert p["passes"] is False and p["binding_codes"] == ["AGG_CONCESSION_EXCEEDED"]
    assert _fen(p["forward_budget_used"]) == 1_310_897


def test_package_2_terms_55_price_30_passes_at_no_budget(packages):
    p = _package_at(packages, 1, 55, 30)
    assert p["passes"] is True and p["binding_codes"] == [] and p["early_pay"] is None
    assert _fen(p["forward_budget_used"]) == 0


def test_package_3_and_4_rebate_edge(packages):
    three = _package_at(packages, 2, 55, 30, 125)
    assert three["passes"] is True and three["binding_codes"] == []
    assert _fen(three["forward_budget_used"]) == 483_795
    four = _package_at(packages, 3, 55, 30, 130)
    assert four["passes"] is False and four["binding_codes"] == ["AGG_CONCESSION_EXCEEDED"]
    assert _fen(four["forward_budget_used"]) == 503_795


def test_package_5_early_pay_cure(packages):
    p = _package_at(packages, 4, 55, 30)
    assert p["passes"] is True and p["binding_codes"] == []
    assert (_bp(p["early_pay"]["rate"]), _fen(p["early_pay"]["face"])) == (85, 25_720_000)
    assert _fen(p["forward_budget_used"]) == 0
    assert _fen(p["reserve_breach"]["cure_cost"]) == 267_304


def test_package_6_terms_60_passes(packages):
    p = _package_at(packages, 5, 60, 45)
    assert p["passes"] is True and p["binding_codes"] == []
    assert _fen(p["forward_budget_used"]) == 0
    assert _fen(p["reserve_breach"]["cure_cost"]) == 267_304


def test_package_7_terms_80_passes_with_larger_cure(packages):
    p = _package_at(packages, 6, 80, 95)
    assert p["passes"] is True and p["binding_codes"] == []
    assert p["outcome"] == "NEEDS_OWNER_APPROVAL"
    assert _fen(p["reserve_breach"]["cure_cost"]) == 400_957
    # recorded, not in the deep dive's list: the forward budget this package uses
    assert _fen(p["forward_budget_used"]) == 489_281


def test_package_8_terms_85_fails_at_price_95_and_100(packages):
    # the deep dive's 10,271.78 is the figure at price 100; at price 95 the recorded figure is 13,001.78
    at_95 = _package_at(packages, 7, 85, 95)
    assert at_95["passes"] is False
    assert at_95["binding_codes"] == ["AGG_CONCESSION_EXCEEDED", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert _fen(at_95["forward_budget_used"]) == 1_300_178
    at_100 = _package_at(packages, 8, 85, 100)
    assert at_100["passes"] is False
    assert at_100["binding_codes"] == ["AGG_CONCESSION_EXCEEDED", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert _fen(at_100["forward_budget_used"]) == 1_027_178
    assert _fen(at_100["reserve_breach"]["cure_cost"]) == 400_957


def test_package_9_ex01_as_asked_fails(packages):
    p = _package_at(packages, 9, 60, 0, 100)
    assert p["passes"] is False
    assert (_bp(p["early_pay"]["rate"]), p["early_pay"]["face"]) == (120, "whole invoice")
    assert p["binding_codes"] == ["AGG_CONCESSION_EXCEEDED", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert _fen(p["forward_budget_used"]) == 2_832_692
    assert _fen(p["reserve_breach"]["cure_cost"]) == 240_667
