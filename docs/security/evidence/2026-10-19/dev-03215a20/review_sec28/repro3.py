import os, sys, json
API = r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api"
sys.path.insert(0, API)
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime, get_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.domain.models import Tier
from app.operations import executor as X
from app.nl import reset_sessions
from tests.nl.conftest import build_app

REAL_TIER, REAL_CHECK = X.Executor._tier, X.Executor._check_mandate
FUNDING = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
CFG = {"tier2": set(), "refuse": set(), "leg": None, "seen": {}}

def _match(op, which):
    k = op.kind
    if k not in CFG[which]: return False
    if CFG["leg"] is not None and k in FUNDING:
        return op.op_id.endswith(f"-{CFG['leg']}")
    return True

def tier(self, ctx):
    t = REAL_TIER(self, ctx)
    return Tier.TIER_2 if _match(ctx.op, "tier2") else t
def check(self, ctx):
    if _match(ctx.op, "refuse"):
        raise X._refuse(X.Code.MAX_APR_EXCEEDED, "forced refusal for the review")
    return REAL_CHECK(self, ctx)
X.Executor._tier, X.Executor._check_mandate = tier, check

def fresh():
    CFG.update(tier2=set(), refuse=set(), leg=None)
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    return rt, TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})

def shown(c):
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    return oid

def neg(name, lang="en", profile="cooperative", tier2=(), refuse=(), leg=None):
    rt, c = fresh(); oid = shown(c)
    CFG.update(tier2=set(tier2), refuse=set(refuse), leg=leg)
    r = c.post(f"/negotiate/{oid}?lang={lang}", json={"buyer_profile": profile}); n = r.json()
    CFG.update(tier2=set(), refuse=set())
    d = c.get(f"/decisions/{n.get('decision_id')}?lang={lang}").json() if n.get("decision_id") else {}
    print(f"\n=== NEG {name} lang={lang} {profile} http={r.status_code}")
    for k in ("outcome", "accept_status", "funding_status", "message", "message_when"): print(f"  {k}: {n.get(k)}")
    print("  ops:", [(o['kind'], o['status']) for o in n.get("operations", [])])
    print("  execution.summary_text:", (n.get("execution") or {}).get("summary_text"))
    print("  record.state_text:", d.get("state_text"), "| agreement:", (d.get("agreement") or {}).get("status_text"))
    print("  record.waiting_for:", (d.get("waiting_for") or {}).get("text"))

# ---- chat
def chat(name, lang="en", mode="business", first="Evaluate EX01", tier2=(), refuse=(), leg=None, confirm=None):
    rt, c = fresh()
    params = {"mode": mode} if mode else {}
    def say(text, sid):
        r = c.post("/nl", params=params, json={"session_id": sid, "actor": "OWNER", "text": text, "lang": lang})
        return r.json()
    sid = f"s-{name}-{lang}-{mode}"
    a = say(first, sid)
    CFG.update(tier2=set(tier2), refuse=set(refuse), leg=leg)
    b = say(confirm or ("go ahead" if lang == "en" else "好，执行"), sid)
    CFG.update(tier2=set(), refuse=set())
    print(f"\n=== CHAT {name} lang={lang} mode={mode} first={first!r}")
    print("  awaiting after first:", a.get("awaiting_confirmation"))
    print("  reply:", b.get("reply"))
    print("  ops:", [(o['kind'], o['status']) for o in b.get("operations", [])])

for mode in ("business", None):
    for lang in ("en", "zh"):
        pa = "Can I pay everyone?" if lang == "en" else "我能付清所有账单吗"
        chat("fund-2nd-refused", lang, mode, first="fund the gap", refuse=("SUBMIT_INVOICE_FOR_FINANCING",))
        chat("fund-1st-tier2", lang, mode, first="fund the gap", tier2=("DRAW_FACILITY",))
        chat("payall-1st-tier2", lang, mode, first=pa, tier2=("DRAW_FACILITY",))
        chat("payall-2nd-refused", lang, mode, first=pa, refuse=("SUBMIT_INVOICE_FOR_FINANCING",))
