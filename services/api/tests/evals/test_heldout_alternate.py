"""The offers and intent suites can be pointed at an alternate held-out directory (--heldout), and an
item whose outcome is `unlabelled` is scored on its obligations but left out of verdict agreement."""

from __future__ import annotations

import pytest

from app.nl.models import Intent
from evals.common import HELDOUT, ROOT, InProcApi, heldout_path
from evals.suites import intent, offers

HELDOUT2 = "fixtures/heldout2"


def metric(res, key):
    return next(m for m in res.metrics if m.key == key)


def test_heldout_path_accepts_none_a_directory_or_a_file():
    assert heldout_path(None, "offers.yaml") == HELDOUT / "offers.yaml"
    assert heldout_path(HELDOUT2, "offers.yaml") == ROOT / HELDOUT2 / "offers.yaml"
    assert heldout_path(ROOT / HELDOUT2 / "intents.yaml", "offers.yaml") == ROOT / HELDOUT2 / "intents.yaml"
    with pytest.raises(FileNotFoundError):
        heldout_path("fixtures/no-such-heldout", "offers.yaml")


def test_heldout2_offers_are_labelled_with_the_required_mix():
    items, pairs = offers.load(HELDOUT2)
    ids = {i["id"] for i in items}
    assert len(items) >= 40 and len(ids) == len(items)
    assert not ids & {i["id"] for i in offers.load()[0]}
    for it in items:
        assert "outcome" in it["expect"] and ("booked" in it["expect"] or it["expect"].get("abstain"))
    zh = [i for i in items if any("一" <= c <= "鿿" for c in i.get("text", "") + str(i.get("documents")))]
    assert len(zh) >= 12
    assert sum(bool(i["expect"].get("abstain")) for i in items) >= 8
    assert sum(i["kind"] == "security" for i in items) >= 4
    assert sum(p["relation"] == "same" for p in pairs) >= 6
    assert sum(p["relation"] == "different" for p in pairs) >= 4
    assert all(p["a"] in ids and p["b"] in ids for p in pairs)


def test_unlabelled_outcomes_are_left_out_of_verdict_agreement():
    res = offers.run(only=["H2A02_WECHAT_ZH_080", "H2N02_60D_ONE_INVOICE"], heldout=HELDOUT2)
    assert res.error is None
    rows = {r["id"]: r for r in res.details["rows"]}
    assert not rows["H2N02_60D_ONE_INVOICE"]["labelled"] and rows["H2N02_60D_ONE_INVOICE"]["outcome_ok"]
    assert res.details["counts"]["unlabelled_outcome"] == 1
    assert metric(res, "verdict_agreement").display.split(" ")[0].endswith("/1")
    assert res.details["source"].replace("\\", "/").endswith("heldout2/offers.yaml")


def test_heldout2_intents_run_through_the_alternate_file():
    items = intent.load(HELDOUT2)
    assert len(items) >= 40 and all(Intent(i["intent"]) for i in items)
    assert sum(bool(i.get("ambiguous")) for i in items) >= 6
    res = intent.run(only=["H2I-S01", "H2I-V01"], api=InProcApi(), heldout=HELDOUT2)
    assert res.error is None and len(res.details["rows"]) == 2
