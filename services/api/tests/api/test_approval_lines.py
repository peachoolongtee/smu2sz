"""GET /approvals/queue: a pending funding request carries cash if declined and cash if approved, and the lines agree with the card's
"If you decline" and "After" sentences."""

from __future__ import annotations

import re

from tests.api.test_time_semantics import _act, _queue, _walk


def _pending(client, lang="en"):
    rows = client.get("/approvals/queue", params={"lang": lang}).json()["approvals"]
    return [r for r in rows if r["status"] == "PENDING"]


def _lowest(series):
    return min(p["closing_fen"] for p in series)


def test_a_queued_cure_carries_both_lines_and_the_sentences_say_their_lowest_points(client):
    _walk(client, receipt="half")
    _act(client)
    (row,) = _pending(client)
    p = row["presentation"]
    floor = client.get("/mandate").json()["mandate"]["min_cash_fen"]
    assert _lowest(p["series_if_declined"]) == p["lowest_if_declined_fen"] < floor
    assert _lowest(p["series_if_approved"]) == p["lowest_if_approved_fen"] > p["lowest_if_declined_fen"]
    assert p["series_if_declined"][0]["day"] == p["series_if_approved"][0]["day"] == client.get("/home").json()["day"]
    assert re.fullmatch(r"[−-]?¥[\d.]+[kM]?", p["lowest_if_declined_short"]) and p["lowest_if_declined_when"] and p["lowest_if_approved_when"]
    # "If you decline": the gap peaks at the reserve less the declined line's lowest point
    peak = re.search(r"peaks at (¥[\d,]+\.\d\d)", p["if_decline"])
    below_zero = "below zero" in p["if_decline"]
    if peak:
        assert peak.group(1) == f"¥{(floor - p['lowest_if_declined_fen']) / 100:,.2f}"
    else:
        assert below_zero and p["lowest_if_declined_fen"] < 0
    # "After": what the card says it protects is what the approved line does
    after = p["protects"]
    if "At its lowest point" in after:
        gap = re.search(r"(¥[\d,]+\.\d\d) below your minimum", after).group(1)
        assert gap == f"¥{(floor - p['lowest_if_approved_fen']) / 100:,.2f}"
    else:
        assert p["lowest_if_approved_fen"] >= floor and after.startswith("Cash stays")


def test_the_chinese_queue_has_the_same_lines(client):
    _walk(client, receipt="half")
    _act(client)
    en, zh = _pending(client)[0]["presentation"], _pending(client, "zh")[0]["presentation"]
    assert [p["closing_fen"] for p in en["series_if_approved"]] == [p["closing_fen"] for p in zh["series_if_approved"]]
    assert en["lowest_if_declined_short"] == zh["lowest_if_declined_short"] and en["lowest_if_declined_when"] != zh["lowest_if_declined_when"]


def test_a_decided_request_and_an_agreement_carry_no_lines(client):
    _walk(client, receipt="half")
    _act(client)
    (row,) = _pending(client)
    client.post(f"/approvals/{row['id']}", json={"decision": "REJECT"})
    for r in _queue(client):
        assert r["presentation"]["series_if_declined"] is None and r["presentation"]["series_if_approved"] is None
