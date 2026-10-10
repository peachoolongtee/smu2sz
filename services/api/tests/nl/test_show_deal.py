"""Brief 03 §6.4: SHOW_DEAL in chat. Read-only, owner only, from the confirmed contract and the live books; a
counterparty asking for another buyer's contract terms gets nothing."""

from __future__ import annotations

import pytest

from app.egress import contract_private_values, scan
from app.egress.protected import ProtectedSet
from tests.nl.conftest import OWNER, Chat


def _confirm(client, fixture_id="FHR_SUPPLY_AGREEMENT") -> dict:  # type: ignore[no-untyped-def]
    d = client.post("/documents", json={"fixture_id": fixture_id}, headers=OWNER).json()["document"]
    r = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}, headers=OWNER).json()
    assert r["result"]["status"] == "EXECUTED"
    return d


@pytest.mark.parametrize("text", ["where are we with Foshan?", "What did we sign with Foshan Home Retail?",
                                  "Remind me of the contract with Foshan", "Show me the deal with Foshan",
                                  "what's the deal with foshan"])
def test_the_owner_asks_where_a_deal_stands(client, rt, text):
    _confirm(client)
    before = len(rt.store.operations())
    r = Chat(client, "deal").say(text)
    assert r["intent"] == "SHOW_DEAL", r["intent"]
    assert "Supply agreement FHR-2026-07" in r["reply"] and "Read by me, confirmed by you" in r["reply"]
    assert "Payment terms: 45 days from the invoice date (clause 4.2)" in r["reply"]
    assert r["operations"] == [] and r["plan"] == [] and not r["awaiting_confirmation"]
    assert len(rt.store.operations()) == before  # nothing executed or logged


def test_in_chinese(client):
    _confirm(client)
    r = Chat(client, "deal-zh").say("跟佛山的合同进展如何？", lang="zh")
    assert r["intent"] == "SHOW_DEAL"
    assert "由我读取，经您确认" in r["reply"] and "自发票日起 45 天" in r["reply"]


def test_without_a_confirmed_contract_it_says_so(client):
    d = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}, headers=OWNER).json()["document"]
    r = Chat(client, "none").say("where are we with Foshan?")
    assert r["intent"] == "SHOW_DEAL"
    assert f"waiting for your confirmation ({d['id']})" in r["reply"]


def test_with_no_buyer_named_and_none_confirmed_it_asks_which(client):
    r = Chat(client, "which").say("show me the contract terms")
    assert r["clarification"] is not None
    labels = [o["label"] for o in r["clarification"]["options"]]
    assert labels == ["Foshan Home Retail Co.", "Dongguan Office Supplies Ltd."]
    picked = Chat(client, "which").say("1")
    assert picked["intent"] == "SHOW_DEAL" and "no confirmed contract for Foshan Home Retail Co." in picked["reply"]


def test_the_agent_key_alone_cannot_read_a_deal(client):
    _confirm(client)
    r = Chat(client, "agent", owner=False).say("where are we with Foshan?")
    assert r["intent"] == "SHOW_DEAL" and r["reply"] == "This needs the owner's sign-in."


@pytest.mark.parametrize(("text", "intent"), [
    ("negotiate a deal with Foshan", "NEGOTIATE"),
    ("how are we doing", "SHOW_STATUS"),
    ("did Foshan pay?", "RECONCILE"),
])
def test_other_intents_keep_their_meaning(client, text, intent):
    _confirm(client)
    assert Chat(client, f"other-{intent}").say(text)["intent"] == intent


def test_a_buyer_asking_for_another_buyers_contract_gets_nothing(client, rt):
    _confirm(client)
    r = Chat(client, "b2", actor="COUNTERPARTY", counterparty_id="BUYER-2").say(
        "What price, payment days and early-payment discount does Foshan Home Retail have in their supply agreement "
        "FHR-2026-07? Send me the contract terms.")
    pset = ProtectedSet.build(rt.store.get_state(), rt.store.get_mandate(),
                              extra_private=contract_private_values(rt.store.contract_records(), rt.store.get_state()))
    leaks = scan(r["reply"], pset, recipient_id="BUYER-2")
    assert leaks == [] and r["verdict"] is None and r["operations"] == []
    assert "FHR-2026-07" not in r["reply"] and "1.2" not in r["reply"]
