"""GET /offers/{offer_id}/picture: the cash line of an offer as asked and of each reply, from the stored verdict and the books."""

from __future__ import annotations

import re

from app.api.runtime import get_runtime
from app.whatif import PRESETS, simulate

CODES = re.compile(r"DOC-|RCV-|RI:|APR-|COM-|FAC-|BUYER-|OFF-|CTR-|VER-")


def _evaluated(client):
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    view = client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    return offer["offer_id"], view


IDS = {"offer_id", "verdict_id", "counter_id"}


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
