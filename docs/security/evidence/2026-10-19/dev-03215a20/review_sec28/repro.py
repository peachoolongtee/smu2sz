import os, sys, json
API = r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api"
sys.path.insert(0, API)
os.environ.setdefault("DEMO_MODE", "1"); os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.domain.models import OperationResult, OperationStatus, Tier
from app.operations.executor import Executor
from app.nl import reset_sessions
from tests.nl.conftest import build_app

REAL = Executor.execute
FUNDING = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
QUEUED = "Queued for owner approval (APR-TEST): rate 18.00% a year is above the 12.00% limit."
REFUSED = "Refused: the facility has no headroom for this amount."

def force(status_for, leg=None):
    seen = [0]
    def execute(self, op):
        want = status_for.get(op.kind)
        if op.kind in FUNDING:
            i = seen[0]; seen[0] += 1
            if leg is not None and i != leg: want = None
        if want is None: return REAL(self, op)
        q = want == OperationStatus.PENDING_APPROVAL
        return OperationResult(op_id=op.op_id, kind=op.kind, status=want, tier=Tier.TIER_2, message=QUEUED if q else REFUSED,
                               approval_id="APR-TEST" if q else None)
    Executor.execute = execute

def fresh():
    Executor.execute = REAL
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    return rt, TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})

def shown(c):
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    return oid

def neg_case(name, status_for, lang="en", profile="cooperative", leg=None):
    rt, c = fresh()
    oid = shown(c)
    force(status_for, leg)
    r = c.post(f"/negotiate/{oid}?lang={lang}", json={"buyer_profile": profile})
    n = r.json()
    Executor.execute = REAL
    d = c.get(f"/decisions/{n.get('decision_id')}?lang={lang}").json() if n.get("decision_id") else {}
    print(f"\n=== NEGOTIATE {name} lang={lang} profile={profile} http={r.status_code}")
    for k in ("outcome", "accept_status", "funding_status", "message", "message_when"):
        print(f"  {k}: {n.get(k)}")
    print("  legs:", [(l['kind'], l['status']) for l in n.get("funding_legs", [])])
    print("  ops:", [(o['kind'], o['status']) for o in n.get("operations", [])])
    print("  execution.summary_text:", (n.get("execution") or {}).get("summary_text"))
    print("  commitment.status:", (n.get("commitment") or {}).get("status"))
    print("  record.state_text:", d.get("state_text"), "| agreement:", (d.get("agreement") or {}).get("status"), (d.get("agreement") or {}).get("status_text"))
    print("  record.waiting_for:", (d.get("waiting_for") or {}).get("text"))
    print("  record.execution.summary_text:", (d.get("execution") or {}).get("summary_text"))

for lang in ("en", "zh"):
    neg_case("baseline", {}, lang)
    neg_case("legs queued", {k: OperationStatus.PENDING_APPROVAL for k in FUNDING}, lang)
    neg_case("legs refused", {k: OperationStatus.REFUSED for k in FUNDING}, lang)
    neg_case("accept queued", {"ACCEPT_OFFER": OperationStatus.PENDING_APPROVAL}, lang)
    neg_case("accept refused", {"ACCEPT_OFFER": OperationStatus.REFUSED}, lang)
    neg_case("nodeal legs queued", {k: OperationStatus.PENDING_APPROVAL for k in FUNDING}, lang, "hard_line")
    neg_case("nodeal leg0 refused", {k: OperationStatus.REFUSED for k in FUNDING}, lang, "hard_line", leg=0)
    neg_case("nodeal baseline", {}, lang, "hard_line")
