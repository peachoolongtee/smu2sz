"""POST /nl on the buyer channel, for the texts of the language-boundary certification that used to be read as a
discount: the buyer gets a question, and nothing is countered, committed or queued for the owner."""

from __future__ import annotations

import pytest

from tests.compiler.boundary_cases import CASES, ID_CASES, Case
from tests.nl.conftest import Chat, stored_ops, stored_verdict


def _assert_nothing_created(rt, resp: dict, ops_before: int) -> None:
    assert rt.store.commitments() == []
    assert rt.store.approvals() == []
    assert stored_ops(rt, ops_before) == []  # no ACCEPT_OFFER, no COUNTER_OFFER, no REJECT_OFFER
    assert resp["operations"] == []
    assert "Agreed" not in resp["reply"] and "Option" not in resp["reply"]


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_buyer_channel_creates_nothing(client, rt, case: Case) -> None:
    ops_before = len(rt.store.operations())
    resp = Chat(client, f"bo-{case.id}", actor="COUNTERPARTY", counterparty_id=case.sender).say(case.text)
    _assert_nothing_created(rt, resp, ops_before)
    verdict = stored_verdict(rt, resp)
    assert verdict["outcome"] == "NO_VERDICT"
    assert verdict["counters"] == [] and verdict["bound_obligations"] == []
    assert any(case.field in (v["inputs"].get("fields") or "") for v in verdict["violations"]), verdict["violations"]


@pytest.mark.parametrize(("item", "text", "sender"), ID_CASES, ids=[i[0] for i in ID_CASES])
def test_a_foreign_invoice_id_is_not_rebound_to_the_senders_own_invoice(client, rt, item: str, text: str, sender: str) -> None:
    ops_before = len(rt.store.operations())
    resp = Chat(client, f"id-{item}", actor="COUNTERPARTY", counterparty_id=sender).say(text)
    _assert_nothing_created(rt, resp, ops_before)
    verdict = stored_verdict(rt, resp)
    assert all(o["base"].get("receivable_id") != "RCV-A" for o in verdict["bound_obligations"])
