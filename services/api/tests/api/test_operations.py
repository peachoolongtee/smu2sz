import subprocess
import sys
from pathlib import Path

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}  # the agent channel, no owner credential


def op(kind, **kw):
    return {"kind": kind, "op_id": kw.pop("op_id", f"op-{kind}"), "idempotency_key": kw.pop("key", f"k-{kind}"),
            "mandate_version": 1, "requested_by": kw.pop("by", "AGENT"), **kw}


def test_committed_line_draw_executes_tier1(client):
    r = client.post("/operations", json=op("DRAW_FACILITY", facility_id="FAC-LINE", amount_fen=15_000_000), headers=AGENT).json()["result"]
    assert r["status"] == "EXECUTED" and r["tier"] == "TIER_1"
    assert client.get("/state").json()["cash"]["text"] == "¥550,000.00"


def test_unauthenticated_owner_claim_cannot_add_a_lender(client):
    fac = client.get("/state").json()["state"]["facilities"][0]
    fac = {k: v for k, v in fac.items() if not k.endswith("_display")}
    fac["covenants"] = []
    fac = {**fac, "id": "FAC-FASTCAPITAL", "lender_id": "FASTCAPITAL", "name": "FastCapital"}
    r = client.post("/operations", json=op("ADD_FACILITY", by="OWNER", facility=fac), headers=AGENT).json()["result"]
    assert r["status"] == "REFUSED"
    ids = [f["id"] for f in client.get("/state").json()["state"]["facilities"]]
    assert "FAC-FASTCAPITAL" not in ids


def test_tier3_refused_even_for_authenticated_owner(client):
    r = client.post("/operations", json=op("SIGN_PERSONAL_GUARANTEE", by="OWNER", facility_id="FAC-LINE"),
                    headers=OWNER).json()["result"]
    assert r["status"] == "REFUSED" and r["tier"] == "TIER_3"


def test_tier2_needs_owner_token_to_approve(client):
    r = client.post("/operations", json=op("APPLY_FOR_FACILITY", facility_id="FAC-GGL", amount_fen=20_000_000), headers=AGENT).json()["result"]
    assert r["status"] == "PENDING_APPROVAL" and r["approval_id"]
    denied = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}, headers=AGENT).json()["result"]
    assert denied["status"] == "REFUSED"
    ok = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert ok["status"] == "EXECUTED"


def test_replayed_idempotency_key_is_duplicate_and_evidence_verifies(client, tmp_path):
    body = op("DRAW_FACILITY", facility_id="FAC-LINE", amount_fen=1_000_000)
    client.post("/operations", json=body, headers=AGENT)
    assert client.post("/operations", json=body, headers=AGENT).json()["result"]["status"] == "DUPLICATE"
    f = tmp_path / "ev.jsonl"
    f.write_text(client.get("/evidence").text)
    script = Path(__file__).resolve().parents[4] / "scripts" / "verify_evidence.py"
    out = subprocess.run([sys.executable, str(script), str(f)], capture_output=True, text=True, check=False)
    assert out.returncode == 0 and "2 operations" in out.stdout, out.stdout


def test_reads_and_reset_require_the_owner_token(client):
    for path in ("/state", "/mandate", "/ledger", "/audit", "/evidence", "/trajectory"):
        assert client.get(path, headers={"X-Owner-Token": ""}).status_code == 401, path
    assert client.post("/demo/reset", headers={"X-Owner-Token": "wrong"}).status_code == 401
    assert client.post("/operations", json=op("DRAW_FACILITY", facility_id="FAC-LINE", amount_fen=1),
                       headers={"X-Owner-Token": ""}).status_code == 401


def test_fail_closed_without_configured_credentials(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.delenv("OWNER_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_KEY", raising=False)
    assert client.get("/state").status_code == 503  # the published demo token is not accepted
    monkeypatch.setenv("OWNER_TOKEN", "s3cret-owner")
    assert client.get("/state", headers={"X-Owner-Token": "s3cret-owner"}).status_code == 200
