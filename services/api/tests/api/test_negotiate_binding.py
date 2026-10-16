"""F07: "Send this counter" sends the counter shown. A send bound to the verdict, the counter and the books' state version the owner
read is refused (409 COUNTER_CHANGED) when any of them has moved, and nothing is proposed, accepted or funded."""

from __future__ import annotations

from typing import Any, cast

from app.api.runtime import get_runtime

EX01 = "EX01_PACKAGE"


def facts_of(rt):
    return cast(Any, rt.store).decision_facts


def _shown(client) -> tuple[str, dict]:
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    return oid, v


def _bound(v: dict, which: int = 0, **changes) -> dict:
    return {"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][which]["id"],
            "state_version": v["state_version"], **changes}


def _untouched(client, before: tuple[int, int, int]) -> None:
    ledger = client.get("/ledger").json()
    assert (ledger["chain_length"], len(ledger["commitments"]), len(facts_of(get_runtime())())) == before


def _counts(client) -> tuple[int, int, int]:
    ledger = client.get("/ledger").json()
    return ledger["chain_length"], len(ledger["commitments"]), len(facts_of(get_runtime())())


def test_a_bound_send_of_option_b_offers_only_option_b_and_records_it(client):
    oid, v = _shown(client)
    option_b = v["counters"][1]
    assert option_b["label"] == "Option B"
    r = client.post(f"/negotiate/{oid}", json=_bound(v, 1))
    assert r.status_code == 200, r.text
    n = r.json()
    assert {x["counter_id"] for x in n["rounds"]} == {option_b["id"]}
    assert n["decision_recorded"] is True
    sent = client.get(f"/decisions/{n['decision_id']}").json()["response"]["sent"]
    assert sent["chosen_counter_id"] == option_b["id"] and sent["chosen_label"] == "Option B"
    assert [c["id"] for c in sent["counters_sent"]] == [option_b["id"]]
    if n["outcome"] == "DEAL":
        assert sent["accepted_counter_id"] == option_b["id"]
        assert n["commitment"]["verdict_id"] == v["id"]


def test_a_bound_send_of_option_a_still_works_and_matches_the_unbound_numbers(client):
    oid, v = _shown(client)
    n = client.post(f"/negotiate/{oid}", json=_bound(v, 0)).json()
    assert n["outcome"] == "DEAL" and n["accepted_counter_id"] == v["counters"][0]["id"]
    assert all(o["status"] == "EXECUTED" for o in n["operations"])


def test_the_unbound_path_still_works_and_records_a_null_chosen_counter(client):
    oid, v = _shown(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    assert n.status_code == 200 and n.json()["outcome"] == "DEAL"
    sent = client.get(f"/decisions/{v['decision_id']}").json()["response"]["sent"]
    assert sent["chosen_counter_id"] is None and sent["accepted_counter_id"] == v["counters"][0]["id"]
    assert len(sent["counters_sent"]) == len(v["counters"])  # the buyer was offered every counter, as before


def test_a_stale_state_version_is_refused_and_nothing_is_proposed_accepted_or_funded(client):
    oid, v = _shown(client)
    client.post("/clock/advance", json={"to_day": 1})  # the books move
    before = _counts(client)
    r = client.post(f"/negotiate/{oid}", json=_bound(v))
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "COUNTER_CHANGED" and d["reason"] == "BOOKS_CHANGED"
    assert d["reevaluate"] is True and d["counters"] == [], "the verdict is not on the current books"
    _untouched(client, before)


def test_an_old_verdict_id_is_refused_and_the_new_guarded_counters_come_back(client):
    oid, v1 = _shown(client)
    client.post("/clock/advance", json={"to_day": 1})
    v2 = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    assert v2["id"] != v1["id"]
    before = _counts(client)
    r = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative", "verdict_id": v1["id"]})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "COUNTER_CHANGED" and d["reason"] == "VERDICT_CHANGED" and d["verdict_id"] == v2["id"]
    assert d["reevaluate"] is False and [c["label"] for c in d["counters"]] == [c["label"] for c in v2["counters"]]
    assert all("send_scope" in c and c["outbound_blocked"] is False for c in d["counters"])
    _untouched(client, before)
    assert client.post(f"/negotiate/{oid}", json=_bound(v2)).status_code == 200  # the current bundle goes through


def test_a_counter_from_another_verdict_is_refused(client):
    oid, v = _shown(client)
    before = _counts(client)
    for foreign in ("CTR-not-in-this-verdict", "CTR-000000000000"):
        r = client.post(f"/negotiate/{oid}", json=_bound(v, counter_id=foreign))
        assert r.status_code == 409 and r.json()["detail"]["reason"] == "COUNTER_NOT_IN_VERDICT"
    _untouched(client, before)


def test_one_wrong_field_is_enough_to_refuse(client):
    oid, v = _shown(client)
    before = _counts(client)
    assert client.post(f"/negotiate/{oid}", json=_bound(v, state_version=v["state_version"] + 7)).status_code == 409
    assert client.post(f"/negotiate/{oid}", json=_bound(v, verdict_id="VER-old")).status_code == 409
    _untouched(client, before)


def test_a_bound_send_after_a_restart_finds_the_verdict_in_the_store(client):
    oid, v = _shown(client)
    get_runtime().latest_verdict.clear()
    assert client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).status_code == 409  # unbound: evaluate first
    r = client.post(f"/negotiate/{oid}", json=_bound(v))
    assert r.status_code == 200 and r.json()["outcome"] == "DEAL"


def test_the_409_path_writes_no_verdict_and_no_fact(client):
    oid, v = _shown(client)
    verdicts = len(get_runtime().store.verdicts())
    client.post(f"/negotiate/{oid}", json=_bound(v, verdict_id="VER-old"))
    assert len(get_runtime().store.verdicts()) == verdicts
    kinds = [f.fact for f in facts_of(get_runtime())()]
    assert kinds == ["RECEIVED", "EVALUATED"]  # intake's and evaluate's: the refused send wrote none
