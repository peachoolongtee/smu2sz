"""Three findings of the external review of the submission build (19 Oct 2026), each fixed at the route or reply:

- REV-1: POST /operations rewrote an unproven OWNER or SYSTEM claim but not COUNTERPARTY, so the agent key could file a draw or a
  receipt that the log and the approval card attributed to the buyer. The claim is now the agent's.
- REV-2: the token check compared str values; a non-ASCII header made hmac.compare_digest raise TypeError. It now compares bytes.
- REV-3: a buyer message queued for the owner (a refusal or a qualified offer can read as the plain discount) was answered
  "Our acceptance awaits the owner's approval". The reply now commits to nothing.
"""

from __future__ import annotations

from app.api.auth import is_agent, is_owner
from app.api.runtime import get_runtime
from app.operations.log import read_entries

AGENT_ONLY = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}
BUYER_ONLY = {"X-Owner-Token": "", "X-Counterparty-Key": "demo-buyer-1-key"}


def _last_entry():  # type: ignore[no-untyped-def]
    return read_entries(get_runtime().store.operations())[0][-1]


def test_a_counterparty_claim_with_the_agent_key_is_the_agent_s_draw(client) -> None:
    body = {"kind": "DRAW_FACILITY", "op_id": "rev1-draw", "idempotency_key": "rev1-draw", "mandate_version": 1,
            "requested_by": "COUNTERPARTY", "facility_id": "FAC-LINE", "amount_fen": 1_000_000}
    r = client.post("/operations", json=body, headers=AGENT_ONLY)
    assert r.status_code == 200, r.text
    e = _last_entry()
    assert e.kind == "DRAW_FACILITY" and e.op.requested_by.value == "AGENT"  # the log never names the buyer for the agent's act


def test_a_counterparty_receipt_with_the_agent_key_is_reported_by_the_agent(client) -> None:
    body = {"kind": "RECEIVE_PAYMENT", "op_id": "rev1-rcpt", "idempotency_key": "rev1-rcpt", "mandate_version": 1,
            "requested_by": "COUNTERPARTY", "receivable_id": "RCV-A", "amount_fen": 42_000_000, "bank_reference": "FAKE-1"}
    out = client.post("/operations", json=body, headers=AGENT_ONLY).json()["result"]
    assert out["status"] == "PENDING_APPROVAL"  # still only the bank feed or the owner books a receipt
    assert "reported by AGENT" in out["message"] and "COUNTERPARTY" not in out["message"]
    assert _last_entry().op.requested_by.value == "AGENT"


def test_a_non_ascii_credential_is_refused_not_raised() -> None:
    assert is_owner("dëmo-owner-token") is False and is_agent("密钥") is False
    assert is_owner("demo-owner-token") is True and is_agent("demo-agent-key") is True


def test_a_non_ascii_header_gets_the_ordinary_refusal(client) -> None:
    r = client.get("/approvals/queue", headers={"X-Owner-Token": "dëmo".encode()})  # raw bytes: the server decodes them as latin-1, non-ASCII
    assert r.status_code in (401, 403), r.text


def test_a_queued_buyer_message_is_never_called_an_acceptance(client) -> None:
    for i, text in enumerate(("We won't pay the ¥420,000 invoice early at a 0.5% discount.",
                              "我们不会以0.5%的折扣提前支付¥420,000的发票。")):
        get_runtime().reset()
        r = client.post("/nl", json={"session_id": f"rev3-{i}", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": text},
                        headers=BUYER_ONLY)
        assert r.status_code == 200, r.text
        reply = r.json()["reply"]
        assert "acceptance" not in reply.lower() and "我方接受" not in reply
        assert "nothing is agreed" in reply or "未达成任何约定" in reply
