"""The offer picture's moments: the whole list the cursor visits, pinned against the kernel's own trajectories."""

from __future__ import annotations

from typing import Any

from app.api import offer_picture
from app.api.decisions import latest_verdict_for
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import Mode
from app.domain.money import fmt_yuan
from app.financial import project
from app.funding import plan
from tests.api.test_offer_picture import _accepted, _evaluated

KINDS = {"today", "invoice_due", "paths_part", "lowest", "reserve_cross", "end"}


def _kernel(oid: str) -> tuple[dict[str, Any], int, int]:
    """The trajectories the route draws, read through the same `project` calls: the offer as asked and each counter with its funding."""
    rt = get_runtime()
    verdict = latest_verdict_for(rt, oid)
    assert verdict is not None
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, [c for c in rt.store.commitments() if c.offer_id != oid])
    floor = mandate.min_cash_fen
    out: dict[str, Any] = {"asked": project(books.state, books.with_(verdict.bound_obligations), [], Mode.CONSERVATIVE,
                                            mandate.horizon_days, floor)}
    for c in verdict.counters:
        funding = plan(books.state, books.with_(c.obligations), mandate)
        actions = list(funding.actions) if funding.admissible else []
        out[c.id] = project(books.state, books.with_(c.obligations), actions, Mode.CONSERVATIVE, mandate.horizon_days, floor)
    return out, max(rt.day, state.as_of_day), floor


def _closing(traj: Any) -> dict[int, int]:
    return {d.day: d.closing_fen for d in traj.days}


def test_the_parting_day_is_the_first_day_two_paths_differ_in_the_kernels_trajectories(client):
    oid, _ = _evaluated(client)
    trajs, today, _ = _kernel(oid)
    closings = {k: _closing(t) for k, t in trajs.items()}
    first = next(d for d in sorted(closings["asked"]) if d >= today and len({c[d] for c in closings.values()}) > 1)
    moments = client.get(f"/offers/{oid}/picture").json()["moments"]
    assert [m["day"] for m in moments if "paths_part" in m["kinds"]] == [first]


def test_each_lowest_point_is_the_trajectorys_min_cash_day(client):
    oid, _ = _evaluated(client)
    trajs, _, _ = _kernel(oid)
    pic = client.get(f"/offers/{oid}/picture").json()
    by_day = {m["day"]: m for m in pic["moments"]}
    for key, traj in trajs.items():
        assert traj.min_cash_day in by_day and "lowest" in by_day[traj.min_cash_day]["kinds"]
        assert next(p for p in pic["paths"] if p["key"] == key)["lowest_fen"] == traj.min_cash_fen
    # the two replies share a lowest day: one moment, not two
    assert sum("lowest" in m["kinds"] for m in pic["moments"]) == len({t.min_cash_day for t in trajs.values()}) == 2


def test_every_reserve_crossing_is_a_moment_with_the_two_sides_of_the_floor(client):
    oid, _ = _evaluated(client)
    trajs, today, floor = _kernel(oid)
    pic = client.get(f"/offers/{oid}/picture").json()
    closings = {k: _closing(t) for k, t in trajs.items()}
    crossings = {d: {(c[d - 1] < floor, c[d] < floor) for c in closings.values() if d - 1 in c and (c[d - 1] < floor) != (c[d] < floor)}
                 for d in sorted(closings["asked"]) if d > today}
    crossings = {d: sides for d, sides in crossings.items() if sides}
    assert sorted(crossings) == [47, 62]
    by_day = {m["day"]: m for m in pic["moments"]}
    for d, sides in crossings.items():
        assert "reserve_cross" in by_day[d]["kinds"]
        key = "asked"
        assert (closings[key][d - 1] < floor) != (closings[key][d] < floor)
        assert by_day[d]["word"] == ("Below the reserve" if (False, True) in sides else "Back above the reserve")
    assert [m["day"] for m in pic["moments"] if "reserve_cross" in m["kinds"]] == [47, 62]


def test_the_list_is_ascending_at_most_six_with_one_decisive_and_every_word_in_both_languages(client):
    oid, _ = _evaluated(client)
    en = client.get(f"/offers/{oid}/picture").json()["moments"]
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["moments"]
    days = [m["day"] for m in en]
    assert days == sorted(set(days)) and len(days) <= 6 and sum(m["decisive"] for m in en) == 1 and days == [m["day"] for m in zh]
    assert [m["kind"] for m in en] == ["today", "lowest", "reserve_cross", "lowest", "reserve_cross", "end"]
    assert all(m["kind"] in KINDS and m["kind"] == m["kinds"][0] for m in en)
    assert [m["word"] for m in en] == ["Today", "Lowest, Option A and Option B", "Below the reserve", "Lowest, as asked",
                                           "Back above the reserve", "Day 66"]
    assert [m["word"] for m in zh] == ["今天", "最低点，方案 A、方案 B", "低于储备", "最低点，按对方要求", "回到储备之上", "第 66 天"]
    assert next(m for m in en if m["decisive"])["day"] == 47
    assert en[0]["kinds"] == ["today", "paths_part"] and en[2]["kinds"] == ["reserve_cross", "invoice_due"]
    assert [m["day"] for m in en if "invoice_due" in m["kinds"]] == [47] and en[-1]["kinds"] == ["end"]


def test_each_value_carries_the_short_figure_the_tone_and_its_difference_from_the_offer_as_asked(client):
    oid, _ = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    for m in pic["moments"]:
        values = {v["key"]: v for v in m["values"]}
        asked = values["asked"]
        assert (asked["vs_asked_fen"], asked["vs_asked_short"], asked["vs_asked_tone"]) == (None, None, None)
        for v in m["values"]:
            assert v["tone"] == ("bad" if v["below_floor"] else "neutral") and v["closing_short"]
            if v["key"] != "asked":
                assert v["vs_asked_fen"] == v["closing_fen"] - asked["closing_fen"]
                assert v["vs_asked_tone"] == ("ok" if v["vs_asked_fen"] > 0 else "bad" if v["vs_asked_fen"] < 0 else "neutral")
    first = {v["key"]: v for v in pic["moments"][0]["values"]}
    a, b = pic["paths"][1]["key"], pic["paths"][2]["key"]
    assert (first[a]["vs_asked_short"], first[b]["vs_asked_short"], first[a]["closing_short"]) == ("+¥150k", "+¥90k", "¥550k")
    second = {v["key"]: v for v in pic["moments"][1]["values"]}
    assert second[a]["vs_asked_short"] == second[b]["vs_asked_short"] == "−¥10k" and second[a]["vs_asked_tone"] == "bad"
    decisive = {v["key"]: v for v in next(m for m in pic["moments"] if m["decisive"])["values"]}
    assert (decisive["asked"]["tone"], decisive["asked"]["closing_short"]) == ("bad", "¥210k") and decisive[a]["vs_asked_short"] == "+¥422k"


def test_the_signed_short_form_has_an_explicit_sign(client):
    assert offer_picture._signed_short(9_000_000) == "+¥90k" and offer_picture._signed_short(-1_000_000) == "−¥10k"
    assert offer_picture._signed_short(0) == "¥0" and offer_picture._signed_short(5_000) == "+¥50.00"


def test_the_parting_moment_names_who_decides_for_each_reply(client):
    oid, _ = _evaluated(client)
    en = client.get(f"/offers/{oid}/picture").json()["moments"]
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["moments"]
    assert en[0]["text"].endswith("Who decides: Option A: FLOW can send it; Option B: needs your approval.")
    assert zh[0]["text"].endswith("由谁决定：方案 A：FLOW 可以直接发送；方案 B：需要您批准。")
    assert not any("Who decides" in m["text"] for m in en[1:])
    # the Business voice is 您, never 你
    assert "你" not in str(zh) and "你" not in str(client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["paths"])


def test_what_moved_cash_on_a_day_is_each_paths_events_in_words_with_their_amounts(client):
    oid, _ = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    keys = [p["key"] for p in pic["paths"]]
    a, b = keys[1], keys[2]
    by_day = {m["day"]: m["events_text"] for m in pic["moments"]}
    assert all(list(m["events_text"]) == keys for m in pic["moments"])
    assert by_day[0] == {"asked": [], a: ["Credit line draw ¥149,986.20"], b: ["Credit line draw ¥90,000.00"]}
    assert by_day[47]["asked"] == ["Operating bill −¥100,000.00"]
    assert by_day[47][a] == ["Receipt from Foshan Home Retail Co. ¥420,000.00", "Operating bill −¥100,000.00"]
    assert by_day[62] == {"asked": ["Receipt from Foshan Home Retail Co. ¥420,000.00"], a: [], b: []}
    assert by_day[66] == {"asked": [], a: [], b: []}
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["moments"]
    assert zh[0]["events_text"][a] != by_day[0][a] and "¥149,986.20" in zh[0]["events_text"][a][0]


def test_an_accepted_offer_walks_today_its_lowest_point_and_the_end(client):
    oid, _ = _accepted(client)
    moments = client.get(f"/offers/{oid}/picture").json()["moments"]
    assert moments[0]["kind"] == "today" and moments[-1]["kind"] == "end" and sum(m["decisive"] for m in moments) == 1
    assert not any("paths_part" in m["kinds"] for m in moments)
    assert all(m["text"] and "Who decides" not in m["text"] for m in moments)


# ---------------------------------------------------------------- the cap of six keeps the priority order


def _row(day: int, closing: int) -> dict[str, Any]:
    return {"day": day, "closing_fen": closing, "closing_display": f"¥{closing}", "events": []}


def _path(key: str, kind: str, series: list[dict[str, Any]]) -> dict[str, Any]:
    return {"key": key, "kind": kind, "label": key, "recommended": False, "series": series,
            "authority_text": "FLOW can send it" if kind == "reply" else "x"}


def test_when_more_than_six_days_qualify_the_cap_keeps_today_the_parting_the_asked_lowest_the_first_crossing_and_the_end():
    floor = 100
    # the offer as asked swings across the reserve every other day; the reply rises away from it on day 3
    asked = [_row(d, 50 if d % 2 else 150) for d in range(40)]
    asked[25] = _row(25, 10)  # its lowest point
    reply = [_row(d, r["closing_fen"] + (0 if d < 3 else 5)) for d, r in enumerate(asked)]
    moments, window = offer_picture._moments([_path("asked", "asked", asked), _path("r", "reply", reply)], 0, floor, 120, 20, "en")
    days = [m["day"] for m in moments]
    by_day = {m["day"]: m for m in moments}
    # kept in order: today (0), the parting (3), the asked path's lowest (25), the first crossing (1), the end of the rows (39), then the
    # rest by day: the crossing on day 2 before the invoice falling due on day 20
    assert days == [0, 1, 2, 3, 25, 39] and window == 39  # the window ends on the end moment, not past the last row
    assert by_day[3]["kinds"][0] == "paths_part" and "lowest" in by_day[25]["kinds"] and by_day[39]["kinds"][-1] == "end"
    assert by_day[1]["kinds"] == ["reserve_cross"] and by_day[1]["decisive"] is True and sum(m["decisive"] for m in moments) == 1
    assert 20 not in days


def test_a_day_where_one_path_goes_below_the_reserve_and_another_comes_back_is_said_so():
    floor = 100
    asked = [_row(d, 150 if d < 2 else 50) for d in range(6)]  # goes below on day 2
    reply = [_row(d, 50 if d < 2 else 150) for d in range(6)]  # is back above on day 2
    moments, _ = offer_picture._moments([_path("asked", "asked", asked), _path("r", "reply", reply)], 0, floor, 120, None, "en")
    day2 = next(m for m in moments if m["day"] == 2)
    assert day2["kind"] == "reserve_cross" and day2["word"] == "Paths cross the reserve"
    zh, _ = offer_picture._moments([_path("asked", "asked", asked), _path("r", "reply", reply)], 0, floor, 120, None, "zh")
    assert next(m for m in zh if m["day"] == 2)["word"] == "路径穿过储备"


def test_events_text_follows_the_trajectorys_own_events_day_by_day(client):
    oid, _ = _evaluated(client)
    trajs, _, _ = _kernel(oid)
    pic = client.get(f"/offers/{oid}/picture").json()
    for m in pic["moments"]:
        for key, traj in trajs.items():
            events = next((d.events for d in traj.days if d.day == m["day"]), [])
            shown = m["events_text"][key]
            assert len(shown) == len(events)
            assert [s.rsplit(" ", 1)[1] for s in shown] == [fmt_yuan(e.amount_fen) for e in events]


def test_a_lowest_point_names_its_path_only_when_more_than_one_is_listed():
    floor = 100
    asked = [_row(d, 300 - d if d < 4 else 400) for d in range(8)]  # lowest on day 3
    reply = [_row(d, 300 - 2 * d if d < 6 else 400) for d in range(8)]  # lowest on day 5
    paths = [_path("asked", "asked", asked), _path("r", "reply", reply)]
    moments, _ = offer_picture._moments(paths, 0, floor, 120, None, "en")
    assert {m["day"]: m["word"] for m in moments if "lowest" in m["kinds"]} == {3: "Lowest, as asked", 5: "Lowest, r"}
    same = [_path("asked", "asked", asked), _path("r", "reply", asked)]
    only, _ = offer_picture._moments(same, 0, floor, 120, None, "en")
    assert [m["word"] for m in only if "lowest" in m["kinds"]] == ["Lowest point"]
