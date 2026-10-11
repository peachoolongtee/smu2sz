"""Axis ticks for the cash pictures: the server rounds and labels them, so a browser never formats a tick."""

from __future__ import annotations

import pytest

from app.api.presentation import axis_ticks, fmt_short, series_axes, series_axis
from tests.api.test_time_semantics import _act, _walk


def _label(v):
    return "¥0" if v == 0 else fmt_short(v)


@pytest.mark.parametrize(("lo", "hi"), [
    (-10_500_000, 80_500_000), (30_000_000, 30_000_000), (0, 100_000), (-5, 5), (4_500_000, 70_000_000), (-120_000_000, -1_000_000),
    (29_999_999, 30_000_001), (12_345_678, 98_765_432), (-50_000_000, 150_000_000),
])
def test_ticks_are_ascending_round_and_cover_the_range(lo, hi):
    ticks = axis_ticks(lo, hi)
    values = [t["value_fen"] for t in ticks]
    assert 3 <= len(ticks) <= 7 and values == sorted(set(values))
    assert values[0] <= lo and values[-1] >= hi
    assert all(t["label"] == _label(t["value_fen"]) for t in ticks)
    assert all(v % 100_000 == 0 for v in values)
    if lo <= 0 <= hi:
        assert 0 in values and ticks[values.index(0)]["label"] == "¥0"


def test_the_step_is_the_smallest_that_fits_in_seven_and_the_domain_is_tight():
    # day 0 on the demo books: -¥105k to ¥805k. A ¥100k step needs 11 ticks; ¥200k fits in 7
    ticks = axis_ticks(-10_500_000, 80_500_000)
    assert [t["value_fen"] for t in ticks] == [-20_000_000, 0, 20_000_000, 40_000_000, 60_000_000, 80_000_000, 100_000_000]
    assert [t["label"] for t in ticks][:3] == ["−¥200k", "¥0", "¥200k"]
    # a step that already fits does not grow: ¥300k to ¥700k at a ¥100k step is 5 ticks
    assert [t["value_fen"] for t in axis_ticks(30_000_000, 70_000_000)] == [30_000_000, 40_000_000, 50_000_000, 60_000_000, 70_000_000]


def test_a_window_keeps_only_the_days_the_picture_shows():
    series = [{"day": d, "closing_fen": 10_000_000 if d < 10 else 90_000_000} for d in range(40)]
    near, far = series_axis([series], None, 5), series_axis([series], None, 30)
    assert near["max_fen"] < far["max_fen"] and near["max_fen"] >= 10_000_000
    assert set(series_axes([series], None, (30, 60, 30))) == {"30", "60"}


def _check(axis, *series, window=None):
    assert axis is not None
    ticks = axis["ticks"]
    values = [t["value_fen"] for t in ticks]
    assert 3 <= len(ticks) <= 7 and values == sorted(values)
    assert axis["min_fen"] == values[0] and axis["max_fen"] == values[-1]
    first = min(p["day"] for s in series if s for p in s)
    points = [p["closing_fen"] for s in series if s for p in s if window is None or p["day"] - first <= window]
    assert values[0] <= min(points) and values[-1] >= max(points)
    assert all(t["label"] == _label(t["value_fen"]) for t in ticks)


def test_the_home_the_router_and_the_picture_carry_an_axis_that_covers_their_series(client):
    client.post("/demo/reset", json={})
    home = client.get("/home").json()["cash"]
    assert home["picture_days"] == 36
    _check(home["axis"], home["series"], home["plan_series"], window=36)
    assert home["axis"]["min_fen"] <= home["floor_fen"] <= home["axis"]["max_fen"]
    # day 0: -¥105k to ¥805k at a ¥200k step, topping out at ¥1,000k
    assert [t["value_fen"] for t in home["axis"]["ticks"]] == [-20_000_000, 0, 20_000_000, 40_000_000, 60_000_000, 80_000_000, 100_000_000]
    assert set(home["axes"]) == {"30", "36", "60", "120"} and home["axes"]["36"] == home["axis"]
    for days, axis in home["axes"].items():
        _check(axis, home["series"], home["plan_series"], window=int(days))
    plan = client.post("/router/plan").json()
    rows = [r["series"] for r in plan["comparison"]]
    _check(plan["series_axis"], *rows)
    assert set(plan["series_axes"]) == {"30", "60", "120"}
    for days, axis in plan["series_axes"].items():
        _check(axis, *rows, window=int(days))
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    pic = client.get(f"/offers/{offer['offer_id']}/picture").json()
    _check(pic["axis"], pic["asked"]["series"], *(r["series"] for r in pic["replies"]), window=60)


def test_the_queue_carries_an_axis_for_a_pending_funding_request_and_none_otherwise(client):
    _walk(client, receipt="half")
    _act(client)
    (row,) = [r for r in client.get("/approvals/queue").json()["approvals"] if r["status"] == "PENDING"]
    p = row["presentation"]
    _check(p["series_axis"], p["series_if_declined"], p["series_if_approved"], window=60)
    client.post(f"/approvals/{row['id']}", json={"decision": "REJECT"})
    assert all(r["presentation"]["series_axis"] is None for r in client.get("/approvals/queue").json()["approvals"])
