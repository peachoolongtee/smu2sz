"""The scenario comparator routes (ticket #100; brief D.1 to D.5): GET /offers/{id}/compare and GET /decisions/{id}/compare.

Five kinds of row in the brief's order and a 30-day late overlay through `scenario_paid_late`, no probabilities. The Demo rows of D.5
are pinned on the golden books with EX01 evaluated (they match the brief's table to the fen on today's books), and the overlay's
current-books row is G.3's (−¥250,000, 65 days below the minimum, ¥550,000, no admissible plan).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
NAMES = ("Foshan Home Retail Co.", "Buyer early-payment offer")


def _runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    return rt


def _clear() -> None:
    from app.api.strategy_compare import clear_cache
    from app.strategy import exposure

    clear_cache()
    exposure.clear_cache()


@pytest.fixture(scope="module")
def reads() -> Iterator[dict[str, Any]]:
    """EX01 evaluated on the golden books, compared once per (language, delay, economics flag)."""
    from app.main import app

    mp = pytest.MonkeyPatch()
    mp.setenv("FEATURE_EXPOSURE", "1")
    mp.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")
    rt = _runtime()
    set_runtime(rt)
    _clear()
    try:
        c = TestClient(app)
        oid = c.post("/offers", json=EX01, headers=OWNER).json()["offer"]["offer_id"]
        c.post(f"/offers/{oid}/evaluate", json=EX01, headers=OWNER)
        out: dict[str, Any] = {"oid": oid}
        for name, query in (("en", ""), ("zh", "?lang=zh"), ("late", "?late=30"), ("late_zh", "?late=30&lang=zh")):
            r = c.get(f"/offers/{oid}/compare{query}", headers=OWNER)
            assert r.status_code == 200, r.text
            out[name] = r.json()
        out["decision"] = c.get(f"/decisions/deal:{oid}/compare", headers=OWNER).json()
        mp.delenv("FEATURE_CUSTOMER_ECONOMICS")
        out["no_econ"] = c.get(f"/offers/{oid}/compare", headers=OWNER).json()
        yield out
    finally:
        mp.undo()
        set_runtime(None)
        _clear()


def _rows(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["kind"] if r["kind"] != "reply" else r["label"]: r for r in body["rows"]}


# ---------------------------------------------------------------- the shape


def test_the_rows_come_in_the_briefs_order(reads):
    body = reads["en"]
    assert [r["kind"] for r in body["rows"]] == ["current", "asked", "reply", "reply", "customer_loss"]
    assert [r["label"] for r in body["rows"]] == ["Your books as they stand", "As they asked", "Option A", "Option B",
                                                  "If Foshan stops buying"]
    assert all(r["available"] for r in body["rows"]) and body["hypothetical"] is True and body["late"] == 0


def test_each_row_says_its_assumption(reads):
    rows = _rows(reads["en"])
    assert rows["current"]["assumption_text"] == "Your books as they stand: Foshan keeps buying on today's terms."
    assert rows["asked"]["assumption_text"] == "If you accept Foshan's request as asked."
    assert rows["Option A"]["assumption_text"] == "If Foshan accepts Option A."
    assert rows["customer_loss"]["assumption_text"] == (
        "Scenario assumes Foshan stops buying from you after today; the ¥420,000 already invoiced (due in 32 days) is still paid. "
        "This is not a prediction.")
    zh = _rows(reads["zh"])
    assert zh["current"]["assumption_text"] == "您账面的现状：Foshan Home Retail Co.按今天的条款继续采购。"
    assert zh["asked"]["assumption_text"] == "如果您按对方要求接受Foshan Home Retail Co.的请求。"
    assert zh["方案 A"]["assumption_text"] == "如果Foshan Home Retail Co.接受方案 A。"


def test_the_decision_read_compares_the_same_offer(reads):
    keep = ("key", "funding_cost_fen", "lowest_cash_fen", "need_fen")
    assert [{k: r.get(k) for k in keep} for r in reads["decision"]["rows"]] == [{k: r.get(k) for k in keep} for r in reads["en"]["rows"]]
    assert reads["decision"]["decision_id"] == f"deal:{reads['oid']}"


# ---------------------------------------------------------------- the Demo rows (brief D.5)


def test_the_demo_rows_as_pinned(reads):
    rows = _rows(reads["en"])
    cur, asked, a, b, loss = (rows[k] for k in ("current", "asked", "Option A", "Option B", "customer_loss"))
    # verdicts: packages only
    assert cur["outcome"] is None and loss["outcome"] is None and cur["codes"] is None
    assert asked["outcome"] == "REJECT" and asked["codes"] == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH",
                                                               "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert (a["outcome"], a["required_tier"], a["codes"]) == ("ACCEPT", "TIER_1", [])
    assert b["outcome"] == "NEEDS_OWNER_APPROVAL" and b["codes"] == ["RESERVE_BREACH"]
    # the forward concession (budget ¥5,000) and the immediate discount, each its own figure
    assert [r["concession_forward_fen"] for r in (cur, asked, a, b, loss)] == [None, 2_832_692, 0, 0, None]
    assert [r["immediate_discount_fen"] for r in (cur, asked, a, b, loss)] == [None, 504_000, 218_620, 0, None]
    # the router's selected plan, never the verdict's cure
    assert [r["funding_cost_fen"] for r in (cur, asked, a, b)] == [311_393, 146_805, 84_157, 370_646]
    assert loss["funding_cost_fen"] is None and loss["plan_flags"]["admissible"] is False
    assert loss["plan_flags"]["words"] == ["no committed plan covers it"]
    # lowest cash, unfunded, and its day (31 Oct = day 30, 30 Nov = day 60)
    assert [(r["lowest_cash_fen"], r["lowest_day"]) for r in (cur, asked, a, b, loss)] == [
        (-10_500_000, 30), (16_496_000, 60), (15_001_380, 30), (-10_500_000, 30), (-10_500_000, 30)]
    assert loss["breach_days"] == 94
    # the further payment FLOW could still cover alone (S1, R-TODAY), each row's own
    assert [r["capacity"]["spare_fen"] for r in (cur, asked, a, b, loss)] == [8_100_000, 1_400_000, 0, 6_200_000, None]


def test_the_customer_loss_figures_each_once(reads):
    loss = _rows(reads["en"])["customer_loss"]["loss"]
    assert (loss["receipts_before_fen"], loss["receipts_kept_fen"], loss["receipts_removed_fen"]) == (168_000_000, 42_000_000,
                                                                                                       126_000_000)
    assert loss["billings_removed_year_fen"] == 546_000_000 and loss["gross_profit_foregone_fen"] == 109_200_000
    assert loss["gross_profit_estimated"] is True and loss["horizon_days"] == 120
    assert loss["receipts_text"] == "¥1,260,000 of receipts removed within the next 120 days; ¥420,000 still arrives."
    assert loss["costs_text"] == ("Costs that would also stop are not modelled; the economic loss is the gross-profit figure, "
                                  "not the cash figure.")
    assert loss["loss_text"] == ("About ¥5,460,000 a year of billings and about ¥1,092,000 a year of gross profit foregone "
                                 "(estimated).")


def test_the_marginal_impact_is_against_the_books_as_they_stand(reads):
    rows = _rows(reads["en"])
    assert rows["current"]["marginal_impact"]["posted_cost_delta_fen"] == 0
    assert rows["asked"]["marginal_impact"]["posted_cost_delta_fen"] == 146_805 - 311_393
    assert rows["Option A"]["marginal_impact"]["before_cost_fen"] == 311_393


# ---------------------------------------------------------------- the late overlay


def test_the_late_overlay_reads_every_row_paid_30_days_late(reads):
    rows = _rows(reads["late"])
    cur = rows["current"]
    assert (cur["lowest_cash_fen"], cur["lowest_day"], cur["breach_days"], cur["need_fen"]) == (-25_000_000, 60, 65, 55_000_000)
    assert cur["funding_cost_fen"] is None and cur["plan_flags"]["admissible"] is False  # G.3: no admissible committed plan
    assert all(r["late_days"] == 30 for r in reads["late"]["rows"])
    assert all(r["late_assumption_text"].startswith("If Foshan Home Retail Co. paid every invoice 30 days late (a test, not a forecast).")
               for r in reads["late"]["rows"])
    assert all(r["capacity"]["note"] == "Read on your books without the late payment." for r in reads["late"]["rows"])
    assert reads["late"]["late_assumption_text"] == cur["late_assumption_text"]


# ---------------------------------------------------------------- economics as context


def test_the_economics_context_is_labelled_and_only_with_the_flag(reads):
    asked = _rows(reads["en"])["asked"]["contribution_context"]
    assert asked["label"] == "Context, not a reason to say yes" and asked["contribution_fen"] == 109_200_000
    assert asked["share_sentence"] == "That is about 2.6% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit."
    assert asked["note"] == "the margin is assumed for the Demo, not confirmed by you"
    assert _rows(reads["en"])["Option A"]["contribution_context"]["share_sentence"] is None  # no forward concession to share
    off = _rows(reads["no_econ"])
    assert all(r["contribution_context"] is None for r in off.values())
    assert off["customer_loss"]["loss"]["gross_profit_foregone_fen"] is None and off["customer_loss"]["loss"]["loss_text"] is None


def test_economics_changes_no_row_figure(reads):
    keep = ("outcome", "required_tier", "codes", "concession_forward_fen", "immediate_discount_fen", "funding_cost_fen", "need_fen",
            "lowest_cash_fen", "breach_days", "plan_flags")
    assert [{k: r.get(k) for k in keep} for r in reads["en"]["rows"]] == [{k: r.get(k) for k in keep} for r in reads["no_econ"]["rows"]]


# ---------------------------------------------------------------- refused (brief D.4)


PROBABILITY = re.compile(r"probab|likel|chance|expected value|odds|walks|weighted|可能性|概率|期望值", re.IGNORECASE)


@pytest.mark.parametrize("name", ["en", "zh", "late", "late_zh"])
def test_no_probability_no_walking_buyer_and_nothing_summed(reads, name):
    body = reads[name]
    # the note states the refusal itself ("never weighted, never added across rows"); every other sentence is scanned
    texts = [*[v for r in body["rows"] for k, v in r.items() if k.endswith("_text") and isinstance(v, str)],
             *[r["loss"][k] for r in body["rows"] if r.get("loss") for k in ("receipts_text", "costs_text", "loss_text") if r["loss"][k]]]
    for text in texts:
        assert not PROBABILITY.search(text), text
    for r in body["rows"]:
        assert not any(k in r for k in ("total_cost_fen", "expected_fen", "weight", "probability"))
        if r.get("concession_forward_fen") and r.get("funding_cost_fen"):  # shown apart, never added
            assert all(v != r["concession_forward_fen"] + r["funding_cost_fen"] for v in r.values() if isinstance(v, int))


@pytest.mark.parametrize("name", ["zh", "late_zh"])
def test_no_english_left_in_chinese(reads, name):
    body = reads[name]
    texts = {"note": body["note"], "late": body["late_assumption_text"],
             "rows": [{k: v for k, v in r.items() if (k.endswith("_text") or k in ("label",)) and isinstance(v, str)}
                      for r in body["rows"]],
             "loss": [{k: v for k, v in r["loss"].items() if k.endswith("_text") and v} for r in body["rows"] if r.get("loss")],
             "flags": [r["plan_flags"]["words"] for r in body["rows"]]}
    assert english_leaks(texts, NAMES) == []


# ---------------------------------------------------------------- the route's edges, the cache and the cost


@pytest.fixture
def api(monkeypatch) -> Iterator[tuple[TestClient, Runtime]]:
    from app.main import app

    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    rt = _runtime()
    set_runtime(rt)
    _clear()
    yield TestClient(app), rt
    set_runtime(None)
    _clear()


def test_route_is_403_with_the_flag_off(api):
    c, _ = api
    r = c.get("/offers/NOPE/compare", headers=OWNER)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_route_needs_the_owner_and_an_evaluated_offer(api, monkeypatch):
    c, _ = api
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    assert c.get("/offers/NOPE/compare").status_code == 401
    assert c.get("/offers/NOPE/compare", headers=OWNER).json()["detail"]["code"] == "OFFER_NOT_FOUND"
    assert c.get("/decisions/funding:x/compare", headers=OWNER).json()["detail"]["code"] == "DECISION_NOT_FOUND"
    oid = c.post("/offers", json=EX01, headers=OWNER).json()["offer"]["offer_id"]
    r = c.get(f"/offers/{oid}/compare", headers=OWNER)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "NO_VERDICT_YET"


def test_only_0_and_30_days_are_offered(api, monkeypatch):
    c, _ = api
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    oid = c.post("/offers", json=EX01, headers=OWNER).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json=EX01, headers=OWNER)
    bad = c.get(f"/offers/{oid}/compare?late=15", headers=OWNER)  # the 15-day row waits (owner's decision 11)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "BAD_LATE"


def test_route_caches_the_comparison(api, monkeypatch):
    from app.strategy import comparator

    c, _ = api
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    oid = c.post("/offers", json=EX01, headers=OWNER).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json=EX01, headers=OWNER)
    runs: list[int] = []
    real = comparator._compute
    monkeypatch.setattr(comparator, "_compute", lambda *a, **k: runs.append(1) or real(*a, **k))
    first = c.get(f"/offers/{oid}/compare", headers=OWNER).json()
    again = c.get(f"/offers/{oid}/compare", headers=OWNER).json()
    assert runs == [1] and first["rows"] == again["rows"]
    c.get(f"/offers/{oid}/compare?late=30", headers=OWNER)
    assert runs == [1, 1]  # the delay is part of the key


@pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1")
def test_the_full_read_is_under_three_seconds_cold(api, monkeypatch):
    c, _ = api
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    oid = c.post("/offers", json=EX01, headers=OWNER).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json=EX01, headers=OWNER)
    _clear()
    body = c.get(f"/offers/{oid}/compare", headers=OWNER).json()
    assert body["computed_in_seconds"] < 3, body["computed_in_seconds"]
