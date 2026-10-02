"""Jump the clock N days at once versus one day at a time, with term and amortising loans landing after a lead
time with an upfront fee, plus an invoice advance. Final state and logged economics must agree."""
import json

from _harness import *  # noqa: F403

FACS = [
    {"id": "FAC-TERM", "name": "Bullet term loan", "kind": "GOV_GUARANTEED_LOAN", "lender_id": "BANK-2",
     "status": "COMMITTED", "owner_approved": True, "limit_fen": 20000000, "rate_bp": 500, "upfront_fee_bp": 100,
     "lead_time_days": 2, "term_months": 12, "repayment": "BULLET"},
    {"id": "FAC-AMORT", "name": "Amortising loan", "kind": "EQUIPMENT_TERM_LOAN", "lender_id": "BANK-1",
     "status": "COMMITTED", "owner_approved": True, "limit_fen": 20000000, "rate_bp": 560, "upfront_fee_bp": 50,
     "lead_time_days": 3, "term_months": 12, "repayment": "AMORTISING"},
]


def setup():
    rt, c = fresh()
    for i, f in enumerate(FACS):
        res = op(c, OWNER, {"kind": "ADD_FACILITY", "op_id": f"add-{i}", "requested_by": "OWNER", "facility": f})
        d = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
        assert d["status"] == "EXECUTED", d
    for i, (fid, amt) in enumerate((("FAC-TERM", 5000000), ("FAC-AMORT", 6000000))):
        res = op(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": f"draw-{i}", "requested_by": "AGENT",
                            "facility_id": fid, "amount_fen": amt})
        print("  draw", fid, res["status"], res["message"][:160])
    return rt, c


def econ(rt):
    pays, landed, net = [], [], 0
    for rec in rt.store.operations():
        if rec.kind != "ADVANCE_CLOCK":
            continue
        p = json.loads(rec.payload_json)
        pays += [(x["lot_id"], x["day"], x["principal_fen"], x["interest_fen"]) for x in p.get("posted_debt_payments", [])]
        landed += p.get("settled_lot_ids", [])
        net += p.get("lots_net_fen", 0)
    return sorted(pays), sorted(landed), net


END = 400
rt, c = setup()
t = projection(rt)
advance(c, 366)
advance(c, END)
a = (snap(rt, "jump"), lots(rt), econ(rt))
rt, c = setup()
for d in range(1, END + 1):
    advance(c, d)
b = (snap(rt, "step"), lots(rt), econ(rt))
print("jump payments", a[2][0], "net", a[2][2])
print("step payments", b[2][0], "net", b[2][2])
check("final cash differs (jump vs step)", a[0]["cash"] != b[0]["cash"])
check("final lots differ", a[1] != b[1])
check("logged debt payments differ", a[2][0] != b[2][0])
check("logged landings or funding net differ", a[2][1:] != b[2][1:])
print("conservation", conservation(rt))
