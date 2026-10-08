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
    assert maxima["Early pay on ¥257,200.00"]["value"] == 85
    assert maxima["Rebate on the expected order"]["value"] == 125
    early = maxima["Early pay on ¥257,200.00"]["at_largest"]["early_pay"]
    assert _fen(early["face"]) == 25_720_000 and early["rate"]["display"] == "0.85%"
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
        early_pay={"rate": {"bp": 85, "display": "0.85%"}, "face": {"fen": 25_720_000, "display": "¥257,200.00"}},
    )
    assert pkg["passes"] is True and pkg["outcome"] == "NEEDS_OWNER_APPROVAL"
    assert pkg["reserve_breach"]["day"] == 47
    assert pkg["reserve_breach"]["cure_cost"] == {"fen": 267_304, "display": "¥2,673.04"}


def _book(collections: dict[str, Any], label: str) -> dict[str, Any]:
    return _one(collections["books"], books=label)


def _ranked(book: dict[str, Any], receivable: str) -> dict[str, Any]:
    return _one(book["ranking"], receivable=receivable)


def _ceiling(row: dict[str, Any], face_fen: int) -> dict[str, Any]:
    return next(e for e in row["early_pay"] if _fen(e["face"]) == face_fen)


def test_collections_day_34(collections):
    book = _book(collections, "day 34")
    rcv = _ranked(book, "RCV-A")
    assert _fen(rcv["marginal_value"]) == 137_461 and rcv["marginal_value"]["display"] == "¥1,374.61"
    assert _fen(rcv["effects"][0]["saving"]) == 137_461
    assert rcv["effects"][0]["after"]["need"] == {"fen": 3_720_000, "display": "¥37,200.00"}
    assert "¥37,200.00" in rcv["sentence"]

    ri2 = _ranked(book, "RI:BUYER-1:2")
    assert _fen(ri2["marginal_value"]) == 170_610
    assert _bp(_ceiling(ri2, 20_000_000)["largest_rate"]) == 80
    assert _bp(_ceiling(ri2, 42_000_000)["largest_rate"]) == 40
    shortfall_face = _ceiling(ri2, 20_000_000)
    assert shortfall_face["next_rate_dearer_by"] == {"fen": 2_420, "display": "¥24.20"}
    assert next(s for s in shortfall_face["sweep"] if _bp(s["rate"]) == 40)["c1_less_c0"]["display"] == "−¥888.28"

    ri32 = _ranked(book, "RI:BUYER-1:32")
    five_earlier = _one(ri32["effects"], receipt_day=72)
    assert _fen(five_earlier["saving"]) == -7_609


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
    assert day34[1] == (43, 60, 8_912)
    assert day34[2][0] == 61 and day34[2][2] == 0


def test_portfolio_default(portfolio):
    best = portfolio["ranked"][0]
    assert best["rank"] == 1
    assert _fen(best["posted_cost"]) == 302_777
    assert _fen(best["funding_cost"]) == 84_157
    assert portfolio["counts"]["feasible"] == 9
    greedy = portfolio["greedy_evaluate_many"]
    assert greedy["rank_in_enumeration"] == 7 and greedy["feasible_portfolios"] == 9
    assert _fen(greedy["cost_for_ranking"]) == 611_393
    assert _fen(greedy["best_cost_for_ranking"]) == 302_777
