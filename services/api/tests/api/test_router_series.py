"""POST /router/plan: each comparison row carries the cash line of the plan if it ran (the shape of GET /home's `cash.plan_series`)."""

from __future__ import annotations

import time

from app.api import decide


def _rows(client, lang="en"):
    return {r["key"]: r for r in client.post("/router/plan", params={"lang": lang}).json()["comparison"]}


def test_the_recommended_row_draws_the_line_the_home_draws(client):
    client.post("/demo/reset", json={})
    rows = _rows(client)
    home = client.get("/home").json()["cash"]["plan_series"]
    for point in home:  # the home's receipt events also say what they rest on (ticket #116) and its points carry `when` and `display`; the router's rows do not
        point.pop("when"), point.pop("display")
        for event in point["events"]:
            event.pop("basis", None), event.pop("basis_text", None)
    assert rows["router_optimum"]["role"] == "recommended" and rows["router_optimum"]["series"] == home
    assert rows["router_optimum"]["series_note"] is None
    assert set(rows["router_optimum"]["series"][0]) >= {"day", "closing_fen", "closing_display", "events", "net_fen", "net_display", "net_short"}


def test_a_plan_that_leaves_a_gap_bottoms_out_at_the_reserve_less_its_uncovered_amount(client):
    client.post("/demo/reset", json={})
    floor = client.get("/mandate").json()["mandate"]["min_cash_fen"]
    row = _rows(client)["line_only"]
    assert row["status"] == "insufficient" and row["shortfall_fen"] > 0
    assert min(p["closing_fen"] for p in row["series"]) == floor - row["shortfall_fen"]
    alternative = _rows(client)["full_discount"]
    assert alternative["series"] and alternative["series"][0]["day"] == 0


def test_a_row_that_cannot_be_projected_says_why_in_both_languages(client):
    client.post("/demo/reset", json={})
    en, zh = _rows(client)["line_guaranteed_loan"], _rows(client, "zh")["line_guaranteed_loan"]
    assert en["series"] is None and zh["series"] is None
    assert en["series_note"] == "Cash cannot be projected for this option." and zh["series_note"] == "无法为此方案预测现金。"


def test_the_series_stay_within_one_and_a_half_times_the_plan_read(client, monkeypatch):
    client.post("/demo/reset", json={})

    def best(n=5):
        out = []
        for _ in range(n):
            t0 = time.perf_counter()
            client.post("/router/plan")
            out.append(time.perf_counter() - t0)
        return min(out)

    with_series = best()
    monkeypatch.setattr(decide, "_add_series", lambda *a, **k: None)
    without = best()
    print(f"router/plan: {without * 1000:.0f} ms without series, {with_series * 1000:.0f} ms with")
    assert with_series < without * 1.5
