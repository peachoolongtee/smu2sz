"""GET /offers/{offer_id}/picture: the cash line of an offer as asked and of each reply, from the stored verdict and the books."""

from __future__ import annotations

import re

from app.api.runtime import get_runtime
from app.whatif import PRESETS, simulate
from tests.api.conftest import english_leaks

CODES = re.compile(r"DOC-|RCV-|RI:|APR-|COM-|FAC-|BUYER-|OFF-|CTR-|VER-")


def _evaluated(client):
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    view = client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    return offer["offer_id"], view


IDS = {"offer_id", "verdict_id", "counter_id", "key"}


def _strings(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k not in IDS:
                yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, str):
        yield x


def test_the_asked_line_is_the_verdicts_trajectory(client):
    oid, view = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    traj = view["trajectory"]
    asked = pic["asked"]
    assert min(p["closing_fen"] for p in asked["series"]) == asked["lowest_fen"] == traj["min_cash"]["fen"]
    assert asked["first_breach_day"] == traj["first_breach_day"]
    assert [p["closing_fen"] for p in asked["series"]] == [d["closing"]["fen"] for d in traj["days"] if d["day"] >= 0]
    assert pic["floor_short"] == "¥300k" and pic["horizon_days"] == 120 and asked["first_breach_when"]


def test_each_reply_is_the_cash_line_if_the_buyer_accepts_with_the_funding_within_the_limits(client):
    oid, view = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    assert [r["counter_id"] for r in pic["replies"]] == [c["id"] for c in view["counters"]] and len(pic["replies"]) == 2
    mandate = get_runtime().store.get_mandate()
    for r in pic["replies"]:
        assert r["series"] and r["note"] and r["lowest_when"] and re.fullmatch(r"[−-]?¥[\d.]+[kM]?", r["lowest_short"])
    # the preset the what-if holds for the same counter agrees with the picture's line
    rt = get_runtime()
    for r, key in zip(pic["replies"], ("option_a", "option_b"), strict=True):
        funded = simulate(rt.store.get_state(), mandate, PRESETS[key], trusted_owner_key_hex=rt.owner_key_hex, day=rt.day,
                          commitments=rt.store.commitments()).funded
        assert funded is not None
        assert min(p["closing_fen"] for p in r["series"]) == funded["min_cash"]["fen"]


def test_no_id_in_a_sentence_and_early_payment_names_the_buyer(client):
    oid, _ = _evaluated(client)
    for lang in ("en", "zh"):
        pic = client.get(f"/offers/{oid}/picture", params={"lang": lang}).json()
        ctx = pic.pop("context")  # the URL contract's selections are identifiers; its sentences are checked
        pic.pop("scenarios_href")  # an address, which carries the offer's id by design
        pic["context"] = {"back": ctx["back"] and {"label": ctx["back"]["label"]}, "irrelevant_text": ctx["irrelevant_text"]}
        hits = [s for s in _strings(pic) if CODES.search(s)]
        assert hits == []
    en = client.get(f"/offers/{oid}/picture").json()
    labels = {e["label_short"] for p in en["asked"]["series"] for e in p["events"]}
    assert "Early payment from Foshan Home Retail Co." in labels
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()
    assert zh["asked"]["label"] != en["asked"]["label"] and zh["floor_short"] == en["floor_short"]


def test_the_picture_changes_nothing(client):
    oid, view = _evaluated(client)
    rt = get_runtime()
    before = (rt.store.get_state().state_version, rt.store.operations()[-1].entry_hash if rt.store.operations() else None,
              rt.store.get_verdict(view["id"]).model_dump_json(), len(rt.store.operations()))
    for _ in range(2):
        assert client.get(f"/offers/{oid}/picture").status_code == 200
    after = (rt.store.get_state().state_version, rt.store.operations()[-1].entry_hash if rt.store.operations() else None,
             rt.store.get_verdict(view["id"]).model_dump_json(), len(rt.store.operations()))
    assert before == after


def test_an_unknown_offer_and_an_unevaluated_one(client):
    client.post("/demo/reset", json={})
    assert client.get("/offers/OFF-none/picture").status_code == 404
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    r = client.get(f"/offers/{offer['offer_id']}/picture")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "NO_VERDICT_YET"


# ---------------------------------------------------------------- paths: one entry per line on the chart, with its column's words

CLEAN = "Deduct 0.6% and we'll settle the open ¥420,000 invoice early."


def _accepted(client):
    client.post("/demo/reset", json={})
    oid = client.post("/offers", json={"documents": [{"doc_id": "t1", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0,
                                                       "text": CLEAN}], "counterparty_id": "BUYER-1"}).json()["offer"]["offer_id"]
    view = client.post(f"/offers/{oid}/evaluate", json={}).json()
    assert view["outcome"] == "ACCEPT"
    return oid, view


def _by_key(items):
    return {x["key"]: x for x in items}


def test_paths_are_the_offer_as_asked_then_each_reply_in_the_verdicts_order(client):
    oid, view = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    paths = pic["paths"]
    a, b = view["counters"]
    assert [p["key"] for p in paths] == ["asked", a["id"], b["id"]] and [p["kind"] for p in paths] == ["asked", "reply", "reply"]
    assert [p["label"] for p in paths] == ["Accept their request", "Option A", "Option B"]
    assert [p["recommended"] for p in paths] == [False, True, False]
    assert [p["needs_owner"] for p in paths] == [False, False, True]
    assert [p["sendable"] for p in paths] == [False, True, True]
    asked, opt_a, opt_b = paths
    assert (asked["tag_text"], asked["tag_tone"]) == ("Over your limit", "bad")
    assert (opt_a["tag_text"], opt_a["tag_tone"]) == ("FLOW recommends", "info")
    assert (opt_b["tag_text"], opt_b["tag_tone"]) == ("Needs your approval", "warn")
    assert asked["decides_text"] == "Cannot be accepted within your signed limits."
    assert opt_a["decides_text"] == "Within your mandate: no approval needed."
    assert opt_b["decides_text"] == "It changes your terms, so you approve it first."
    # the earlier fields are kept as they were
    assert pic["asked"]["series"] == asked["series"] and [r["series"] for r in pic["replies"]] == [opt_a["series"], opt_b["series"]]


def test_each_paths_costs_are_the_verdicts_own_displays(client):
    oid, view = _evaluated(client)
    asked, opt_a, opt_b = client.get(f"/offers/{oid}/picture").json()["paths"]
    impact = view["workspace"]["financial_impact"]
    discount = next(line for line in impact["lines"] if line["horizon"] == "IMMEDIATE")
    assert asked["cost_display"] == view["forward_concession"]["total_display"] == impact["forward_total_display"] == "¥28,326.92"
    assert asked["cost_note"] == f"over 12 months, plus {discount['amount_display']} once" == "over 12 months, plus ¥5,040.00 once"
    assert [p["cost_display"] for p in (opt_a, opt_b)] == [c["supplier_cost_display"] for c in view["counters"]]
    assert opt_a["cost_display"] == view["workspace"]["priced_response"]["supplier_cost_display"]
    assert (opt_a["cost_note"], opt_b["cost_note"]) == ("once; nothing ongoing", "the price rise pays for the longer terms")
    assert opt_a["reply_text"] == view["counters"][0]["text_when"] and opt_b["reply_text"] == view["counters"][1]["text_when"]
    assert asked["reply_text"] is None


def test_each_path_has_the_three_term_rows_with_what_it_replaces(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = client.get(f"/offers/{oid}/picture").json()["paths"]
    for p in (asked, opt_a, opt_b):
        assert [t["key"] for t in p["terms"]] == ["payment_terms", "early_payment", "rebate_or_price"]
        assert [t["label"] for t in p["terms"]] == ["Payment terms", "Early payment", "Rebate or price"]
    def rows(p):
        return [(t["value_text"], t["instead_of_text"]) for t in p["terms"]]

    assert rows(asked) == [("60 days", None), ("1.20% off ¥420,000.00", None), ("1.00% rebate", None)]
    assert rows(opt_a) == [("45 days", "instead of 60"), ("0.85% off ¥257,200.00", "instead of 1.20% off ¥420,000.00"),
                           (None, "instead of a 1.00% rebate")]  # a term the path does not carry is null, never the word "None"
    assert rows(opt_b) == [("55 days", "instead of 60"), (None, "instead of 1.20% off ¥420,000.00"),
                           ("0.30% price rise", "instead of a 1.00% rebate")]


def test_band_text_says_what_each_path_does_against_the_minimum(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = client.get(f"/offers/{oid}/picture").json()["paths"]
    assert asked["band_text"] == "Below your minimum for 15 days" and asked["first_breach_when"] == "in 47 days"
    assert opt_a["band_text"] == "The next invoice is paid 15 days sooner than if you accept their request"
    assert opt_b["band_text"] == "The next invoice is paid 5 days sooner than if you accept their request"
    assert opt_a["first_breach_when"] is None and opt_b["first_breach_when"] is None
    assert opt_a["lowest_fen"] >= 30_000_000 and opt_b["lowest_fen"] >= 30_000_000


def test_an_accepted_offer_is_one_sendable_recommended_path(client):
    oid, _ = _accepted(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    assert [p["key"] for p in pic["paths"]] == ["asked"] and pic["replies"] == []
    p = pic["paths"][0]
    assert (p["recommended"], p["sendable"], p["needs_owner"]) == (True, True, False)
    assert (p["tag_text"], p["tag_tone"]) == ("FLOW recommends", "info")
    assert p["decides_text"] == "Within your mandate: no approval needed." and p["band_text"] is None
    assert p["cost_display"] == "¥2,520.00" and p["cost_note"] == "once; nothing ongoing"
    assert [t["instead_of_text"] for t in p["terms"]] == [None, None, None]
    moments = pic["moments"]
    assert 1 <= len(moments) <= 6 and sum(m["decisive"] for m in moments) == 1
    assert all(len(m["values"]) == 1 and m["values"][0]["key"] == "asked" for m in moments)


def test_paths_and_moments_hold_no_id_and_are_said_in_both_languages(client):
    oid, _ = _evaluated(client)
    en = client.get(f"/offers/{oid}/picture").json()
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()
    assert [p["key"] for p in en["paths"]] == [p["key"] for p in zh["paths"]]
    for pic in (en, zh):
        fields = {"paths": [{k: v for k, v in p.items() if k != "series"} for p in pic["paths"]], "moments": pic["moments"]}
        assert [s for s in _strings(fields) if CODES.search(s)] == []
    for e, z in zip(en["paths"], zh["paths"], strict=True):
        assert e["label"] != z["label"] or e["kind"] == "reply"
        assert (e["tag_text"] != z["tag_text"] or e["tag_text"] is None) and e["decides_text"] != z["decides_text"]
        assert e["cost_display"] == z["cost_display"] and e["recommended"] == z["recommended"]
        assert [t["value_text"] for t in z["terms"]] and all(t["label"] != u["label"] for t, u in zip(e["terms"], z["terms"], strict=True))
    # the outflow's own name ("Operating bill") is the owner's label in the books, not a sentence of ours
    fields = {"paths": [{k: v for k, v in p.items() if k not in ("series", "reply_text")} for p in zh["paths"]],
              "moments": zh["moments"]}
    assert english_leaks(fields, ["Foshan Home Retail Co.", "Foshan", "Operating bill"]) == []


# ---------------------------------------------------------------- moments: the cursor's stops


def test_moments_are_at_most_six_ascending_with_exactly_one_decisive(client):
    oid, _ = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    moments = pic["moments"]
    days = [m["day"] for m in moments]
    assert 1 <= len(moments) <= 6 and days == sorted(set(days)) and days[0] == pic["day"] == 0
    assert [m["day"] for m in moments if m["decisive"]] == [47]
    assert days == [0, 30, 47, 60, 62, 66]
    assert moments[0]["label"] == moments[0]["title"] == "Today" and moments[2]["label"] == moments[2]["title"] == "In 47 days"
    assert all(m["text"] for m in moments)


def test_each_moments_values_are_the_paths_own_closing_cash_that_day(client):
    oid, _ = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    floor = pic["floor_fen"]
    series = {p["key"]: {r["day"]: r["closing_fen"] for r in p["series"]} for p in pic["paths"]}
    for m in pic["moments"]:
        assert [v["key"] for v in m["values"]] == [p["key"] for p in pic["paths"]]
        for v in m["values"]:
            assert v["closing_fen"] == series[v["key"]][m["day"]] and v["closing_display"]
            assert v["below_floor"] is (v["closing_fen"] < floor)
            assert v["note"] == ("Below your minimum" if v["below_floor"] else None)
    by_day = {m["day"]: _by_key(m["values"]) for m in pic["moments"]}
    assert [d for d, v in by_day.items() if v["asked"]["below_floor"]] == [47, 60]
    assert not any(v[k]["below_floor"] for v in by_day.values() for k in v if k != "asked")


def test_a_moments_text_says_what_every_path_has_once_then_what_differs_then_who_is_below(client):
    oid, view = _evaluated(client)
    opt_a = view["counters"][0]["id"]
    pic = client.get(f"/offers/{oid}/picture").json()
    text = {m["day"]: m["text"] for m in pic["moments"]}
    assert text[47] == ("On every path: Operating bill −¥100k. Option A: Receipt from Foshan Home Retail Co. ¥420k. "
                        "If you accept their request, cash is below your minimum.")
    assert text[60] == "On every path: Debt service −¥45k. If you accept their request, cash is below your minimum."
    assert text[0] == ("Option A: Credit line draw ¥150k. Option B: Credit line draw ¥90k. "
                       "Who decides: Option A: within your mandate; Option B: needs your approval.")
    assert opt_a not in " ".join(text.values())


def test_picture_days_and_the_axis_follow_the_window_of_the_moments(client):
    oid, _ = _evaluated(client)
    pic = client.get(f"/offers/{oid}/picture").json()
    # the window ends on the last moment; it runs four days past the last day anything changes (62), a month at least
    assert pic["picture_days"] == pic["moments"][-1]["day"] - pic["day"] == max(30, 62 + 4) == 66
    assert 30 <= pic["picture_days"] <= min(90, pic["horizon_days"])
    inside = [r["closing_fen"] for p in pic["paths"] for r in p["series"] if r["day"] - pic["day"] <= pic["picture_days"]]
    lo, hi = pic["axis"]["min_fen"], pic["axis"]["max_fen"]
    assert lo <= min(inside + [pic["floor_fen"]]) and hi >= max(inside)
    ticks = [t["value_fen"] for t in pic["axis"]["ticks"]]
    assert ticks[0] == lo and ticks[-1] == hi
    # nothing beyond the window sets the axis: the tallest line past it (the receipts at the end) is above the axis top
    assert max(r["closing_fen"] for p in pic["paths"] for r in p["series"]) > hi


def test_paths_and_moments_change_nothing(client):
    oid, view = _evaluated(client)
    rt = get_runtime()

    def snapshot():
        return (rt.store.get_state().state_version, len(rt.store.operations()),
                rt.store.operations()[-1].entry_hash if rt.store.operations() else None,
                rt.store.get_verdict(view["id"]).model_dump_json())

    before = snapshot()
    first = client.get(f"/offers/{oid}/picture").json()
    assert client.get(f"/offers/{oid}/picture").json() == first and snapshot() == before
    assert rt.store.get_verdict(view["id"]).id == first["verdict_id"]


# ---------------------------------------------------------------- an offer the books can no longer draw is answered, never a 500

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
UNAVAILABLE = "This offer can no longer be drawn on today's books: the days it named have passed or the invoice has changed since."


def _snapshot(client, oid, view):
    rt = get_runtime()
    ops = rt.store.operations()
    return (rt.store.get_state().state_version, len(ops), ops[-1].entry_hash if ops else None, rt.store.get_verdict(view["id"]).id)


def _assert_unavailable(client, oid, view):
    before = _snapshot(client, oid, view)
    r = client.get(f"/offers/{oid}/picture")
    assert r.status_code == 200
    pic = r.json()
    assert pic["available"] is False and pic["unavailable_text"] == UNAVAILABLE
    assert pic["paths"] == [] and pic["moments"] == [] and pic["replies"] == []
    assert pic["asked"] is None and pic["axis"] is None and pic["picture_days"] is None
    assert pic["offer_id"] == oid and pic["verdict_id"] == view["id"] and pic["floor_short"] == "¥300k" and pic["horizon_days"] == 120
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"})
    assert zh.status_code == 200 and zh.json()["available"] is False
    assert zh.json()["unavailable_text"] != UNAVAILABLE and zh.json()["unavailable_text"]
    for p in (pic, zh.json()):
        assert not CODES.search(p["unavailable_text"]) and not re.search(r"\bday \d", p["unavailable_text"])
    assert _snapshot(client, oid, view) == before


def test_an_offer_whose_days_have_passed_is_answered_as_unavailable(client):
    for day in (7, 38):
        oid, view = _evaluated(client)
        assert client.get(f"/offers/{oid}/picture").json()["available"] is True
        assert client.post("/clock/advance", json={"to_day": day}).status_code == 200
        _assert_unavailable(client, oid, view)


def test_an_offer_whose_invoice_was_part_settled_since_is_answered_as_unavailable(client):
    oid, view = _evaluated(client)
    version = client.get("/mandate").json()["mandate"]["version"]
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-1", "idempotency_key": "rc-1", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": "RCV-A", "amount_fen": 25_720_000, "bank_reference": "BANK-1"})
    assert r.json()["result"]["status"] == "EXECUTED"
    _assert_unavailable(client, oid, view)


def test_no_other_state_of_the_books_makes_the_picture_fail(client):
    oid, _ = _accepted(client)
    assert client.get(f"/offers/{oid}/picture").json()["available"] is True
    client.post("/clock/advance", json={"to_day": 34})
    assert client.get(f"/offers/{oid}/picture").status_code == 200
    oid, _ = _evaluated(client)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    assert client.get(f"/offers/{oid}/picture").status_code == 200
    client.post("/clock/advance", json={"to_day": 34})
    assert client.get(f"/offers/{oid}/picture").status_code == 200


# ---------------------------------------------------------------- the asked path's breakdown and facts (the Home deal card's words)


def test_the_asked_path_carries_the_breakdown_and_the_three_facts_on_day_zero(client):
    oid, _ = _evaluated(client)
    asked, *replies = client.get(f"/offers/{oid}/picture").json()["paths"]
    assert asked["ask_breakdown"] == [{"label": "After buyer discount", "amount_display": "¥414,960", "share_text": "99%"},
                                      {"label": "Requested discount", "amount_display": "¥5,040", "share_text": "1%"}]
    assert asked["ask_facts"] == {"invoice_value_display": "¥420,000", "requested_discount_display": "¥5,040", "requested_term_text": "60 days"}
    assert asked["cost_once_display"] == "¥5,040.00"  # the discount is the path's own posted one-off, said whole
    assert all(p["ask_breakdown"] is None and p["ask_facts"] is None for p in replies) and replies


def test_the_asked_breakdown_in_chinese_has_no_english(client):
    oid, _ = _evaluated(client)
    asked = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["paths"][0]
    assert [(r["label"], r["amount_display"], r["share_text"]) for r in asked["ask_breakdown"]] == [
        ("买方折扣后", "¥414,960", "99%"), ("买方要求的折扣", "¥5,040", "1%")]
    assert asked["ask_facts"]["requested_term_text"] == "60 天"
    assert english_leaks([asked["ask_breakdown"], asked["ask_facts"]]) == []


def test_an_ask_with_a_discount_and_no_terms_extension_has_no_requested_term(client):
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX02_EARLY_1_5"})
    asked = client.get(f"/offers/{offer}/picture").json()["paths"][0]
    assert asked["ask_facts"] == {"invoice_value_display": "¥420,000", "requested_discount_display": "¥6,300", "requested_term_text": None}
    assert [r["amount_display"] for r in asked["ask_breakdown"]] == ["¥413,700", "¥6,300"]


def test_an_ask_with_no_composable_discount_has_an_empty_breakdown_and_no_figures():
    from app.api import offer_picture

    rows, facts = offer_picture._ask_words(None, [], None, 0, "en")
    assert rows == [] and facts == {"invoice_value_display": None, "requested_discount_display": None, "requested_term_text": None}
