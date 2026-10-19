"""Reproduce the three security findings from the 19 Oct review of FLOW (submission build 66c31e7e).

Run from the repository root, after `uv sync --directory services/api`:

    uv run --project services/api --no-sync python flow_audit_probes.py

It builds the same in-process runtime as the sandbox (run_sandbox.py --inproc): DEMO_MODE=1, in-memory books,
LLM_MODE=cache, the golden books. Nothing leaves the machine.

  P1  The agent key can file operations as requested_by COUNTERPARTY. A forged "buyer-reported" receipt reaches
      the owner's Approvals queue as "reported by COUNTERPARTY"; approving it books cash that never arrived.
  P2  The rules reader ignores negation, scope and conditions. "We won't pay ... early" becomes a proposed
      early-payment agreement; the buyer is told "Our acceptance awaits the owner's approval"; the owner's card
      shows a clean agreement; once approved, "are we safe?" answers yes while the real gap is ¥405,000.
  P3  A non-ASCII credential header makes hmac.compare_digest raise: every authenticated route answers 500.
"""
import importlib.util
import sys
import uuid
from pathlib import Path

ROOT = Path.cwd()
spec = importlib.util.spec_from_file_location(
    "sbx", ROOT / "docs/deliverables/evidence/sandbox-2026-10-19/run_sandbox.py")
sbx = importlib.util.module_from_spec(spec)
sys.modules["sbx"] = sbx
spec.loader.exec_module(sbx)
T = sbx.InProc()


def call(method, path, role, body=None):
    s, b, _ = T.call(method, path, role, body)
    return s, b


def reset():
    call("POST", "/demo/reset", "OWNER", {})
    T.after_reset()


def nl(role, text, session):
    body = {"session_id": session, "actor": "OWNER" if role == "OWNER" else "COUNTERPARTY", "text": text}
    if role.startswith("BUYER"):
        body["counterparty_id"] = role
    return call("POST", "/nl", role, body)


def cash():
    return call("GET", "/state", "OWNER")[1]["cash"]["text"]


print("P1  agent key files a receipt as COUNTERPARTY")
reset()
op = {"kind": "RECEIVE_PAYMENT", "op_id": "op-" + uuid.uuid4().hex[:8], "idempotency_key": uuid.uuid4().hex,
      "mandate_version": 1, "requested_by": "COUNTERPARTY", "day": 0, "receivable_id": "RCV-A", "amount_fen": 42000000}
s, b = call("POST", "/operations", "AGENT", op)
print("    queued:", b["result"]["status"], "|", b["result"]["message"])
card = call("GET", "/approvals/queue", "OWNER")[1]["approvals"][0]
print("    owner's card:", card["title_text"], "| sender_unverified:", card["sender_unverified"])
before = cash()
call("POST", f"/approvals/{card['id']}", "OWNER", {"decision": "APPROVE"})
print("    cash before / after the owner approves:", before, "/", cash())

print("\nP2  'We won't pay early' is read as an early-payment offer")
reset()
s, b = nl("BUYER-1", "We won't pay the ¥420,000 invoice early at a 0.5% discount.", "b")
print("    reply sent to the buyer:", b["reply"])
card = call("GET", "/approvals/queue", "OWNER")[1]["approvals"][0]
print("    owner's card:", card["title_text"], "|", card["presentation"]["terms"])
call("POST", f"/approvals/{card['id']}", "OWNER", {"decision": "APPROVE"})
print("    owner asks 'are we safe?':", nl("OWNER", "are we safe?", "o")[1]["reply"][:160])

print("\nP3  non-ASCII credential header")
r = T.client.request("GET", "/ledger", headers={"X-Owner-Token": b"d\xe9mo"})  # latin-1 bytes, as curl sends them
print("    GET /ledger with X-Owner-Token: 'démo' ->", r.status_code)
