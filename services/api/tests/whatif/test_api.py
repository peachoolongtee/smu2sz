"""POST /whatif and GET /whatif/presets: strict validation, hypothetical label, nothing written."""

from __future__ import annotations

import threading
import time

import pytest

ACTUAL = {"terms_days": 60, "discount_bp": 120, "rebate_bp": 100}


def test_post_whatif_reproduces_ex01_and_is_hypothetical(client, g):
    body = client.post("/whatif", json=ACTUAL).json()
    assert body["hypothetical"] is True and "nothing is booked" in body["note"]
    assert body["outcome"] == "REJECT"
    assert body["codes"] == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH"]
    assert body["forward"]["total_fen"] == g["forward_ledger_total"]
    assert body["reserve"]["breach_day"] == 47


def test_option_a_over_http(client):
    body = client.post("/whatif", json={"terms_days": 45, "discount_bp": 85, "rebate_bp": 0,
                                        "settle_face_fen": 21_180_000}).json()
    assert body["outcome"] != "REJECT" and "AGG_CONCESSION_EXCEEDED" not in body["codes"]


def test_terms_45_means_no_extension(client):
    body = client.post("/whatif", json={"terms_days": 45, "discount_bp": 0, "rebate_bp": 0}).json()
    assert body["forward"]["total_fen"] == 0
    assert all(o["obligation_type"] != "TERMS_EXTENSION" for o in body["description"]["obligations"])


@pytest.mark.parametrize("bad", [
    {"terms_days": 29, "discount_bp": 0, "rebate_bp": 0},  # below range
    {"terms_days": 95, "discount_bp": 0, "rebate_bp": 0},  # above range
    {"terms_days": 47, "discount_bp": 0, "rebate_bp": 0},  # off the 5-day grid
    {"terms_days": 60, "discount_bp": 121, "rebate_bp": 0},  # off the 5 bp grid
    {"terms_days": 60, "discount_bp": 205, "rebate_bp": 0},  # above 2.0%
    {"terms_days": 60, "discount_bp": -5, "rebate_bp": 0},
    {"terms_days": 60, "discount_bp": 0, "rebate_bp": 205},
    {"terms_days": 60, "discount_bp": 0, "rebate_bp": 3},
    {"terms_days": 60, "discount_bp": 0, "rebate_bp": 0, "price_adjustment_bp": 105},
    {"terms_days": 60, "discount_bp": 120, "rebate_bp": 0, "settle_face_fen": 12_345},  # not whole ¥100
    {"terms_days": 60, "discount_bp": 120, "rebate_bp": 0, "settle_face_fen": 0},
    {"terms_days": 60, "discount_bp": 120, "rebate_bp": 0, "settle_face_fen": 42_010_000},  # above the invoice
    {"terms_days": "60", "discount_bp": 120, "rebate_bp": 100},  # strict: no string coercion
    {"terms_days": 60.0, "discount_bp": 120, "rebate_bp": 100},  # strict: no float
    {"terms_days": 60, "discount_bp": True, "rebate_bp": 100},  # strict: no bool
    {"terms_days": 60, "discount_bp": 120},  # missing field
    {**ACTUAL, "execute": True},  # unknown field
])
def test_invalid_params_are_422(client, bad):
    assert client.post("/whatif", json=bad).status_code == 422


def test_whatif_writes_nothing(client, rt):
    store = rt.store
    before = (len(store.operations()), len(store.commitments()), len(store.security_events()),
              store.get_state().model_dump_json(), store.get_mandate().model_dump_json(), store.verify_chain())
    for body in (ACTUAL, {"terms_days": 45, "discount_bp": 85, "rebate_bp": 0, "settle_face_fen": 21_180_000},
                 {"terms_days": 90, "discount_bp": 200, "rebate_bp": 200, "price_adjustment_bp": 100}):
        assert client.post("/whatif", json=body).status_code == 200
    client.get("/whatif/presets")
    after = (len(store.operations()), len(store.commitments()), len(store.security_events()),
             store.get_state().model_dump_json(), store.get_mandate().model_dump_json(), store.verify_chain())
    assert after == before
    assert before[0] == 0


def _join_prewarm() -> None:
    for t in threading.enumerate():
        if t.name == "whatif-prewarm":
            t.join(timeout=30)


def test_warm_latency_under_400ms(client):
    _join_prewarm()  # a background warm-up from an earlier test would compete for the GIL
    client.post("/whatif", json=ACTUAL)  # cold: fills the cache (and starts the preset warm-up)
    _join_prewarm()
    t = time.perf_counter()
    body = client.post("/whatif", json=ACTUAL).json()
    elapsed = time.perf_counter() - t
    assert body["cached"] is True
    assert elapsed < 0.4, f"warm what-if took {elapsed * 1000:.0f} ms"


def test_presets_endpoint(client):
    body = client.get("/whatif/presets").json()
    assert body["hypothetical"] is True
    actual = body["presets"]["actual"]
    assert {k: actual[k] for k in ("terms_days", "discount_bp", "rebate_bp", "price_adjustment_bp",
                                   "settle_face_fen")} == {"terms_days": 60, "discount_bp": 120, "rebate_bp": 100,
                                                           "price_adjustment_bp": 0, "settle_face_fen": None}
    assert actual["discount_display"] == "1.20%" and actual["rebate_display"] == "1.00%"
    assert body["presets"]["option_a"]["settle_face_display"] == "¥211,800.00"
    assert body["grid"]["terms_days"] == {"min": 30, "max": 90, "step": 5}
    assert body["grid"]["settle_face_fen"]["max"] == 42_000_000
    assert body["receivable_face_display"] == "¥420,000.00" and body["current_terms_days"] == 45


def test_post_carries_the_controls(client):
    body = client.post("/whatif", json=ACTUAL).json()
    c = body["controls"]
    assert c["rate_labels"]["120"] == "1.20%" and c["rate_labels"]["85"] == "0.85%"
    assert {"fen": 21_180_000, "display": "¥211,800.00"} in c["face_stops"]
    assert c["face_stops"][-1] == {"fen": 42_000_000, "display": "¥420,000.00"}
    assert set(c["presets"]) == {"actual", "option_a", "option_b", "status_quo"}
