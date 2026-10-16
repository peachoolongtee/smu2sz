"""Security Lead re-certification probes against 8911fb21 (throwaway; not part of the repo)."""
import base64
import os
from pathlib import Path

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}
OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
ROOT = Path(os.environ["WT_ROOT"])
FIX = (ROOT / "fixtures/capex/gzpm-2026-114-equipment-purchase.md").read_text(encoding="utf-8")
SME = "Lingnan Homeware Manufacturing Co., Ltd."
SELLER = "Guangzhou Precision Machinery Co., Ltd."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app
    yield TestClient(app, headers=OWNER)
    set_runtime(None)


def rt():
    from app.api.runtime import get_runtime
    return get_runtime()


def capex_flows():
    return [(f.id, f.day, f.amount_fen) for f in rt().store.get_state().flows if f.kind.value == "CAPEX"]


def upload(client, text, cp):
    r = client.post("/documents", json={"kind": "CAPEX_CONTRACT", "counterparty_id": cp, "filename": "c.md",
                                        "content_base64": base64.b64encode(text.encode()).decode()})
    assert r.status_code == 200, r.text
    d = r.json()["document"]
    assert client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).status_code == 200
    return d


def commit(client, doc_id, early=False):
    ev = client.post(f"/capex/contracts/{doc_id}/evaluate", json={"timeline": TIMELINE})
    if ev.status_code != 200:
        return ("EVAL", ev.status_code, ev.text[:200])
    ev = ev.json()
    s = (ev.get("early_pay_schedule") if early else ev["schedule"].get("schedule"))
    if not s:
        return ("NO_SCHEDULE", ev["schedule"].get("reasons"))
    r = client.post(f"/capex/contracts/{doc_id}/commit", json={"timeline": TIMELINE, "schedule_hash": s["schedule_hash"],
                                                                "take_early_pay": early})
    if r.status_code != 200:
        return ("COMMIT", r.status_code, r.text[:250])
    j = r.json()
    out = client.post(f"/approvals/{j['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    return (out["status"], [v["code"] for v in out.get("violations", [])], out.get("message", "")[:200])


def test_v1_near_duplicate_under_another_vendor_id(client):
    a = upload(client, FIX, "VEND-A")
    b = upload(client, FIX.replace("Contract No. GZPM-2026-114", "Contract No. GZPM-2026-114 "), "VEND-B")  # one space
    print("V1", commit(client, a["id"]), commit(client, b["id"]), "flows", len(capex_flows()), sum(x[2] for x in capex_flows()))


def test_v1b_near_duplicate_same_vendor_new_reference(client):
    a = upload(client, FIX, "VEND-A")
    b = upload(client, FIX.replace("GZPM-2026-114", "GZPM-2026-114A"), "VEND-A")
    print("V1B", commit(client, a["id"]), commit(client, b["id"]), "flows", len(capex_flows()))


def test_v2_own_name_with_punctuation_variant(client):
    text = FIX.replace(SELLER, "Lingnan Homeware Manufacturing Co. Ltd", 1)
    d = upload(client, text, "V2")
    print("V2", commit(client, d["id"]), [(c.id, c.name) for c in rt().store.get_state().counterparties if c.id == "V2"])


def test_v3_own_name_with_buyer_party_changed(client):
    text = FIX.replace(SME, "Lingnan Homeware (Shunde) Co., Ltd.", 1).replace(SELLER, SME, 1)
    d = upload(client, text, "V3")
    print("V3", commit(client, d["id"]), [(c.id, c.name) for c in rt().store.get_state().counterparties if c.id == "V3"])


def test_v4_agent_claims_owner_on_operations(client):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    s = ev["schedule"]["schedule"]
    body = {"kind": "COMMIT_PURCHASE", "op_id": "ag", "idempotency_key": "ag", "mandate_version": 1, "requested_by": "OWNER",
            "document_id": d["id"], "doc_hash": d["doc_hash"], "schedule_hash": s["schedule_hash"], "amount_fen": s["price_fen"], **TIMELINE}
    r = TestClient(__import__("app.main", fromlist=["app"]).app, headers=AGENT).post("/operations", json=body).json()["result"]
    sec = [e.kind.value for e in rt().store.security_events()][-2:]
    print("V4", r["status"], [v["code"] for v in r["violations"]], r.get("approval_id"), "sec", sec,
          "queue", [a.id for a in rt().store.approvals() if a.status.value == "PENDING"])


def test_v5_discount_just_below_100(client):
    d = upload(client, FIX.replace("a discount of 2% of that payment", "a discount of 99.99% of that payment"), "V5")
    res = commit(client, d["id"], early=True)
    print("V5", res, capex_flows())


def test_v6_shares_over_100(client):
    d = upload(client, FIX.replace("4.1 30% of the Contract Price", "4.1 70% of the Contract Price"), "V6")
    print("V6", commit(client, d["id"]), capex_flows())


def test_v7_card_shows_schedule(client):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    r = client.post(f"/capex/contracts/{d['id']}/commit", json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()
    card = next(a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == r["approval_id"])
    print("V7", {k: card.get(k) for k in ("summary_rows", "terms_rows", "schedule_rows", "purchase") if card.get(k)})


def _vendor_case(client, seller_text, cp, buyer_text=None):
    text = FIX.replace(SELLER, seller_text, 1)
    if buyer_text is not None:
        text = text.replace(SME, buyer_text, 1)
    d = upload(client, text, cp)
    return commit(client, d["id"])[:2], [(c.id, c.name) for c in rt().store.get_state().counterparties if c.id == cp]


def test_v8_capex4_variants(client):
    cases = {
        "punct": ("Lingnan Homeware Manufacturing Co. Ltd", None),
        "buyer_changed": (SME, "Lingnan Homeware (Shunde) Co., Ltd."),
        "fullwidth": ("Ｌｉｎｇｎａｎ Ｈｏｍｅｗａｒｅ Ｍａｎｕｆａｃｔｕｒｉｎｇ Ｃｏ．， Ｌｔｄ．", "Someone Else Co., Ltd."),
        "limited": ("LINGNAN HOMEWARE MANUFACTURING LIMITED", "Someone Else Co., Ltd."),
        "cyrillic_a": ("Lingnаn Homeware Manufacturing Co., Ltd.", "Someone Else Co., Ltd."),
        "legit_similar": ("Lingnan Homeware Trading Co., Ltd.", None),
        "legit_other": ("Shenzhen Tooling Co., Ltd.", None),
    }
    for i, (k, (seller, buyer)) in enumerate(cases.items()):
        print("V8", k, _vendor_case(client, seller, f"VX{i}", buyer))


def test_v9_poison_own_name_with_a_confirmed_contract(client):
    # a confirmed capex contract whose BUYER party is the real vendor's name: does the real vendor then count as "own business"?
    poison = FIX.replace(SME, SELLER, 1).replace(SELLER, "Other Seller Co., Ltd.", 1)
    p = upload(client, poison, "VPOISON")
    real = upload(client, FIX, "VREAL")
    print("V9", commit(client, real["id"])[:2])


def test_v10_buyer_changed_correct_order(client):
    text = FIX.replace(SME, "Lingnan Homeware (Shunde) Co., Ltd.", 1).replace(SELLER, "LINGNAN  HOMEWARE MANUFACTURING CO LTD", 1)
    d = upload(client, text, "V10")
    rec = rt().store.get_contract_record(d["id"])
    print("V10 parties", [(t.field.value, t.text) for t in rec.contract.terms if t.field.value.startswith("PARTY")])
    print("V10", commit(client, d["id"]), [(c.id, c.name) for c in rt().store.get_state().counterparties if c.id == "V10"])


def test_v9b_poison_message(client):
    poison = FIX.replace(SELLER, "Other Seller Co., Ltd.", 1).replace(SME, SELLER, 1)
    p = upload(client, poison, "VPOISON")
    rec = rt().store.get_contract_record(p["id"])
    print("V9B poison parties", [(t.field.value, t.text) for t in rec.contract.terms if t.field.value.startswith("PARTY")])
    real = upload(client, FIX, "VREAL")
    print("V9B", commit(client, real["id"]))
