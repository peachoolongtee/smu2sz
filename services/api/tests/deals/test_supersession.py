"""A later confirmed buyer contract replaces the earlier one openly (ticket #103): the earlier record says which one replaced
it, the later says what it replaces, both in the owner's words in either language, and the superseded record never feeds the
deal summary."""

from __future__ import annotations

import re

from tests.api.test_deals import _confirm_text, _demo_text


def _post(client, text):  # type: ignore[no-untyped-def]
    return client.post("/documents", json={"kind": "BUYER_CONTRACT", "counterparty_id": "BUYER-1", "text": text}).json()["document"]


def _confirm_two(client):  # type: ignore[no-untyped-def]
    first = _post(client, _demo_text())
    assert client.post(f"/documents/{first['id']}/confirm", json={"doc_hash": first["doc_hash"]}).status_code == 200
    client.post("/clock/advance", json={"to_day": 3})
    second = _post(client, _demo_text().replace("RMB 420,000 (four hundred and twenty thousand yuan)", "RMB 400,000"))
    assert client.post(f"/documents/{second['id']}/confirm", json={"doc_hash": second["doc_hash"]}).status_code == 200
    return first["id"], second["id"]


def test_the_later_confirmation_says_what_it_replaces_and_the_earlier_what_replaced_it(client):
    first, second = _confirm_two(client)
    old, new = (client.get(f"/documents/{i}").json()["document"] for i in (first, second))
    assert (old["replaces"], old["superseded_by"], old["replaces_text"]) == (None, second, None)
    assert (new["replaces"], new["superseded_by"], new["superseded_by_text"]) == (first, None, None)
    assert new["replaces_text"] == "Replaces the contract you confirmed 3 days ago"
    assert old["superseded_by_text"] == "Replaced by a contract you confirmed today"
    zh_old, zh_new = (client.get(f"/documents/{i}", params={"lang": "zh"}).json()["document"] for i in (first, second))
    assert zh_new["replaces_text"] == "取代您3 天前确认的合同" and zh_old["superseded_by_text"] == "已被您今天确认的合同取代"
    for text in (new["replaces_text"], old["superseded_by_text"], zh_new["replaces_text"], zh_old["superseded_by_text"]):
        assert not re.search(r"DOC-|\d{6}", text)
    assert not re.search(r"[A-Za-z]{2,}", zh_new["replaces_text"] + zh_old["superseded_by_text"])
    listed = {d["id"]: d for d in client.get("/documents").json()["documents"]}
    assert listed[first]["superseded_by"] == second and listed[second]["replaces"] == first


def test_the_deal_summary_reads_only_the_contract_in_force_and_says_it_replaced_one(client):
    first, second = _confirm_two(client)
    deal = client.get("/deals/BUYER-1").json()["deal"]
    assert deal["contract"]["record_id"] == second
    assert deal["contract"]["replaces"] == first
    assert deal["contract"]["replaces_text"] == "Replaces the contract you confirmed 3 days ago"
    assert any(t["field"] == "PRICE" and "400,000" in t["value_display"] for t in deal["contract_terms"])
    zh = client.get("/deals/BUYER-1", params={"lang": "zh"}).json()["deal"]
    assert zh["contract"]["replaces_text"] == "取代您3 天前确认的合同"


def test_a_first_contract_replaces_nothing_and_another_buyers_contract_is_not_replaced(client):
    _confirm_text(client, _demo_text())
    other = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    assert other["replaces"] is None and other["superseded_by"] is None
    deal = client.get("/deals/BUYER-1").json()["deal"]
    assert deal["contract"]["replaces"] is None and deal["contract"]["replaces_text"] is None
