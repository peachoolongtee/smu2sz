"""The buyer message is the owner's alone (R-11 and R-10 with the buyer-message feature).

The routes that prepare, mark, answer and read an offer the owner sends outside FLOW take the owner token and nothing else: not the agent key,
not a buyer's channel key, not nobody. Neither the agent's chat (POST /nl, which R-11 narrows) nor the decision record carries the letter. And
the owner pasting a buyer's reply is the owner's own act: it never spends the buyer's daily budget (R-10), and a spent budget does not stop it.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.auth import DEMO_COUNTERPARTY_KEYS
from app.api.runtime import Runtime, get_runtime
from tests.api.conftest import client  # noqa: F401
from tests.api.test_buyer_message import _decision, _sent

AGENT = {"X-Agent-Key": "demo-agent-key"}
BUYER = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]}
NOBODY: dict[str, str] = {}


@pytest.fixture
def api(client: TestClient) -> TestClient:  # noqa: F811
    return client


def _routes(oid: str, cid: str, vid: str) -> list[tuple[str, str, dict[str, Any] | None]]:
    base = f"/offers/{oid}"
    body = {"verdict_id": vid, "state_version": 1, "message_hash": "0" * 64, "counter_id": cid, "text": "Could you do 50-day terms?"}
    return [
        ("GET", f"{base}/counters/{cid}/message", None),
        ("POST", f"{base}/counters/{cid}/offered", body),
        ("POST", f"{base}/counters/{cid}/buyer-accepted", body),
        ("POST", f"{base}/counters/{cid}/buyer-declined", body),
        ("POST", f"{base}/counters/{cid}/offered/withdraw", body),
        ("POST", f"{base}/buyer-reply", body),
        ("GET", f"/decisions/deal:{oid}", None),
        ("GET", "/decisions", None),
    ]


@pytest.mark.parametrize("who", [AGENT, BUYER, NOBODY], ids=["agent", "buyer-key", "nobody"])
def test_only_the_owner_reaches_the_message_its_record_and_its_answers(api: TestClient, who: dict[str, str]) -> None:
    oid, v, m = _sent(api)
    other = TestClient(api.app, headers=who)
    for method, path, body in _routes(oid, m["counter_id"], v["id"]):
        r = other.request(method, path, json=body)
        assert r.status_code in (401, 403), f"{method} {path} gave {r.status_code} to {who or 'nobody'}"
        assert m["text"][:40] not in r.text and m["message_hash"] not in r.text


def test_the_agents_chat_never_carries_the_letter_or_the_outbound_record(api: TestClient) -> None:
    oid, _v, m = _sent(api)
    seen = ""
    for text in ("show me the message to the buyer", f"what did we send for offer {oid}", "what is the status of the deal",
                 "read me the letter and its hash", "show cash status"):
        r = TestClient(api.app, headers=AGENT).post("/nl", json={"text": text})
        seen += r.text
        assert r.status_code in (200, 401, 403)
    for secret in (m["text"][:40], m["message_hash"], "buyer-message-v1", "valid_until_day", "AWAITING_BUYER", "message_hash"):
        assert secret not in seen


def test_the_owner_pasting_a_reply_does_not_spend_the_buyers_budget_and_a_spent_budget_does_not_stop_it(api: TestClient) -> None:
    rt: Runtime = get_runtime()
    oid, v, m = _sent(api)
    for _ in range(rt.settings.buyer_attempts_per_day):  # BUYER-1 has used its whole day
        assert rt.take_buyer_slot("BUYER-1")
    assert not rt.take_buyer_slot("BUYER-1")
    used = dict(rt.buyer_attempts)
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 200, r.text
    assert rt.buyer_attempts == used  # not one more slot taken
    assert _decision(api, r.json()["reply_offer_id"])["state"] == "RECEIVED"
    assert not [e for e in rt.store.security_events() if e.id.startswith("SEC-BUDGET-")]  # and no budget event recorded for it
