"""Axis ticks for the cash pictures: the server rounds and labels them, so a browser never formats a tick."""

from __future__ import annotations

import pytest

from app.api.presentation import axis_ticks, fmt_short
from tests.api.test_time_semantics import _act, _walk


@pytest.mark.parametrize(("lo", "hi"), [
    (-10_500_000, 40_000_000), (30_000_000, 30_000_000), (0, 100_000), (-5, 5), (4_500_000, 70_000_000), (-120_000_000, -1_000_000),
    (29_999_999, 30_000_001), (12_345_678, 98_765_432),
])
def test_ticks_are_ascending_round_and_cover_the_range(lo, hi):
    ticks = axis_ticks(lo, hi)
    values = [t["value_fen"] for t in ticks]
    assert 3 <= len(ticks) <= 5 and values == sorted(set(values))
    assert values[0] <= lo and values[-1] >= hi
    assert all(t["label"] == fmt_short(t["value_fen"]) for t in ticks)
    assert all(v % 100_000 == 0 for v in values)
    if lo < 0 < hi or lo <= 0 <= hi:
        assert 0 in values


def _check(axis, *series):
    assert axis is not None
    ticks = axis["ticks"]
    values = [t["value_fen"] for t in ticks]
    assert 3 <= len(ticks) <= 5 and values == sorted(values)
    assert axis["min_fen"] == values[0] and axis["max_fen"] == values[-1]
    points = [p["closing_fen"] for s in series if s for p in s]
    assert values[0] <= min(points) and values[-1] >= max(points)
    assert all(t["label"] == fmt_short(t["value_fen"]) for t in ticks)


def test_the_home_the_router_and_the_picture_carry_an_axis_that_covers_their_series(client):
    client.post("/demo/reset", json={})
    home = client.get("/home").json()["cash"]
    _check(home["axis"], home["series"], home["plan_series"])
    assert home["axis"]["min_fen"] <= home["floor_fen"] <= home["axis"]["max_fen"]
    plan = client.post("/router/plan").json()
    _check(plan["series_axis"], *(r["series"] for r in plan["comparison"]))
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    pic = client.get(f"/offers/{offer['offer_id']}/picture").json()
    _check(pic["axis"], pic["asked"]["series"], *(r["series"] for r in pic["replies"]))


def test_the_queue_carries_an_axis_for_a_pending_funding_request_and_none_otherwise(client):
    _walk(client, receipt="half")
    _act(client)
    (row,) = [r for r in client.get("/approvals/queue").json()["approvals"] if r["status"] == "PENDING"]
    p = row["presentation"]
    _check(p["series_axis"], p["series_if_declined"], p["series_if_approved"])
    client.post(f"/approvals/{row['id']}", json={"decision": "REJECT"})
    assert all(r["presentation"]["series_axis"] is None for r in client.get("/approvals/queue").json()["approvals"])
