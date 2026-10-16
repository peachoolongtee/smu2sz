"""Security Lead probes against int/capex-buy-side (throwaway; not part of the repo)."""
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
AGENT = {"X-Agent-Key": "demo-agent-key"}
ROOT = Path(os.environ["WT_ROOT"])
FIX = (ROOT / "fixtures/capex/gzpm-2026-114-equipment-purchase.md").read_text(encoding="utf-8")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app
    yield TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})
    set_runtime(None)


def rt():
    from app.api.runtime import get_runtime
    return get_runtime()


def capex_flows():
    return [(f.id, f.day, f.amount_fen) for f in rt().store.get_state().flows if f.kind.value == "CAPEX"]


def upload_text(client, text, cp="EVILVENDOR"):
    r = client.post("/documents", json={"kind": "CAPEX_CONTRACT", "counterparty_id": cp, "filename": "c.md",
                                        "content_base64": base64.b64encode(text.encode()).decode()})
    assert r.status_code == 200, r.text
    d = r.json()["document"]
    c = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    assert c.status_code == 200, c.text
    return d


def test_p1_early_discount_over_100pct_books_an_inflow(client):
    text = FIX.replace("a discount of 2% of that payment", "a discount of 150% of that payment")
    d = upload_text(client, text)
    rec = rt().store.get_contract_record(d["id"])
    print("STATUS", rec.contract.status, [(t.field.value, t.rate_bp) for t in rec.contract.terms if t.rate_bp])
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    eps = ev.get("early_pay_schedule")
    print("EARLY", eps and [(p["day"], p["amount_fen"]) for p in eps["payments"]])
    r = client.post(f"/capex/contracts/{d['id']}/commit",
                    json={"timeline": TIMELINE, "schedule_hash": eps["schedule_hash"], "take_early_pay": True}).json()
    card = next(a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == r["approval_id"])
    print("CARD", card["presentation"].get("headline"), "|", card["presentation"].get("what"))
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    print("RESULT", out["status"], out.get("message"))
    print("FLOWS", capex_flows())
    assert any(a > 0 for _, _, a in capex_flows())


def test_p2_retention_over_100pct_payment_terms_only(client):
    from app.capex.schedule import Timeline, derive_schedule
    from app.domain.models import CompiledContract, CompileStatus, ContractField as F, ContractTerm, PaymentBasis, PriceUnit, SourceSpan

    sp = SourceSpan(doc_id="D", start=0, end=1, text="x")
    terms = [ContractTerm(field=F.PRICE, span=sp, amount_fen=60_000_000, unit=PriceUnit.LUMP_SUM),
             ContractTerm(field=F.PAYMENT_TERMS, span=sp, days=30, basis=PaymentBasis.DELIVERY),
             ContractTerm(field=F.RETENTION, span=SourceSpan(doc_id="D", start=2, end=3, text="12 months after acceptance"),
                          rate_bp=15000, months=12)]
    c = CompiledContract(doc_id="D", status=CompileStatus.COMPILED, terms=terms, compiler="x", prompt_version="x")
    r = derive_schedule(c, Timeline(**TIMELINE), anchor_iso="2026-10-01", today=0)
    print("DERIVED", r.derivable, r.reasons, r.schedule and [(p.day, p.amount_fen, p.kind) for p in r.schedule.payments])
    assert r.derivable and any(p.amount_fen < 0 for p in r.schedule.payments)


def test_p2b_retention_over_100pct_through_reader(client):
    text = FIX.replace("4.1 30% of the Contract Price is payable on signing of this Contract.\n\n", "") \
              .replace("4.2 60% of the Contract Price is payable within forty-five (45) days after delivery of the Equipment.",
                       "4.2 The Buyer shall pay the Contract Price within thirty (30) days after delivery of the Equipment.") \
              .replace("retain 10% of the Contract Price", "retain 150% of the Contract Price")
    d = upload_text(client, text)
    rec = rt().store.get_contract_record(d["id"])
    print("STATUS", rec.contract.status, [(t.field.value, t.rate_bp, t.days, t.basis) for t in rec.contract.terms])
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    s = ev["schedule"]
    print("SCHED", s.get("derivable"), s.get("reasons"), s.get("schedule") and [(p["day"], p["amount_fen"]) for p in s["schedule"]["payments"]])


def test_p3_same_contract_twice_double_books(client):
    hs = []
    for _ in range(2):
        d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
        client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
        ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
        r = client.post(f"/capex/contracts/{d['id']}/commit",
                        json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()
        out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
        hs.append((d["id"], d["doc_hash"][:12], out["status"]))
    print("TWICE", hs, len(capex_flows()), sum(a for _, _, a in capex_flows()))
    assert len(capex_flows()) == 6


def test_p4_agent_queues_its_own_timeline(client):
    """The agent picks a different (valid) timeline; the owner sees the same card wording."""
    from app.capex.schedule import Timeline, derive_schedule
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    st = rt().store.get_state()
    rec = rt().store.get_contract_record(d["id"])
    tl = {"signing_day": 20, "delivery_day": 21, "acceptance_day": 22}
    s = derive_schedule(rec.contract, Timeline(**tl), anchor_iso=st.as_of, today=st.as_of_day).schedule
    agent = TestClient(__import__("app.main", fromlist=["app"]).app, headers=AGENT)
    body = {"kind": "COMMIT_PURCHASE", "op_id": "agent-tl", "idempotency_key": "agent-tl", "mandate_version": 1,
            "requested_by": "AGENT", "document_id": d["id"], "doc_hash": d["doc_hash"], "schedule_hash": s.schedule_hash,
            "amount_fen": s.price_fen, **tl}
    r = agent.post("/operations", json=body).json()["result"]
    card = next(a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == r["approval_id"])
    print("AGENTCARD", card["summary_rows"], card["terms_rows"], card["subject"], card["reason"])
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    print("AGENTRESULT", out["status"], capex_flows())


def test_p5_vendor_name_from_contract_text(client):
    text = FIX.replace("Guangzhou Precision Machinery Co., Ltd.", "Lingnan Homeware Manufacturing Co., Ltd.", 1)
    d = upload_text(client, text, cp="V2")
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    r = client.post(f"/capex/contracts/{d['id']}/commit",
                    json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()
    client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"})
    print("REGISTERED", [(c.id, c.name, c.role, c.known) for c in rt().store.get_state().counterparties if c.id == "V2"])


def _commit_via_409(client, doc_id, early=False):
    r = client.post(f"/capex/contracts/{doc_id}/commit", json={"timeline": TIMELINE, "schedule_hash": "0" * 64,
                                                              "take_early_pay": early})
    print("FIRST", r.status_code, r.json().get("detail", r.json()).get("code") if isinstance(r.json(), dict) else r.text)
    h = r.json()["detail"]["schedule_hash"]
    r = client.post(f"/capex/contracts/{doc_id}/commit", json={"timeline": TIMELINE, "schedule_hash": h,
                                                              "take_early_pay": early}).json()
    print("SCHEDULE", [(p["day"], p["amount_fen"]) for p in r["schedule"]["payments"]])
    card = next(a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == r["approval_id"])
    print("CARD", card["presentation"].get("headline"), "|", card["presentation"].get("what"))
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    print("RESULT", out["status"], out.get("message"))
    print("FLOWS", capex_flows())


def test_p6_retention_inflow_end_to_end(client):
    text = FIX.replace("4.1 30% of the Contract Price is payable on signing of this Contract.\n\n", "") \
              .replace("4.2 60% of the Contract Price is payable within forty-five (45) days after delivery of the Equipment.",
                       "4.2 The Buyer shall pay the Contract Price within thirty (30) days after delivery of the Equipment.") \
              .replace("retain 10% of the Contract Price", "retain 150% of the Contract Price")
    d = upload_text(client, text)
    cash0 = rt().store.get_state().cash_fen
    _commit_via_409(client, d["id"])
    h = client.get("/home")
    print("HOME", h.status_code)


def test_p7_early_discount_inflow_end_to_end(client):
    text = FIX.replace("a discount of 2% of that payment", "a discount of 150% of that payment")
    d = upload_text(client, text)
    _commit_via_409(client, d["id"], early=True)
