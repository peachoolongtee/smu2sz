"""Projection versus reality: project on day d, then let exactly the projected buyer receipts happen, one day at a
time, and compare each day's actual closing cash with the projected closing. The scenario's day-25 event adds a
¥200,000 payroll on day 42 that a day-0 projection cannot know; differences of exactly that are expected."""
from _harness import *  # noqa: F403

PAYROLL_M2 = -20000000

TERM = {"id": "FAC-TERM", "name": "Bullet term loan", "kind": "GOV_GUARANTEED_LOAN", "lender_id": "BANK-2",
        "status": "COMMITTED", "owner_approved": True, "limit_fen": 20000000, "rate_bp": 500, "upfront_fee_bp": 100,
        "lead_time_days": 2, "term_months": 1, "repayment": "BULLET", "counts_in_debt_service": False}


def add(c, f):
    res = op(c, OWNER, {"kind": "ADD_FACILITY", "op_id": f"add-{f['id']}", "requested_by": "OWNER", "facility": f})
    c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})


def run(label, prepare, until=60):
    rt, c = fresh()
    prepare(rt, c)
    t = projection(rt)
    diffs = live(c, rt, t, until, tag=label)
    unexplained = [(d, w, g) for d, w, g in diffs if not (d >= 42 and g - w == PAYROLL_M2)]
    print(f"[{label}] days with a difference not explained by the day-42 payroll: {len(unexplained)}")
    for d, w, g in unexplained[:5]:
        print(f"    day {d}: projected {fmt_yuan(w)} actual {fmt_yuan(g)} (diff {fmt_yuan(g - w)})")
    print("    conservation:", conservation(rt), "| lots:", lots(rt))
    return unexplained


def nothing(rt, c):
    pass


def finance_a(rt, c):
    op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "f", "requested_by": "AGENT",
                  "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33600000})


def finance_ri2_day3(rt, c):
    advance(c, 3)
    op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "f2", "requested_by": "OWNER",
                  "facility_id": "FAC-IF", "receivable_id": "RI:BUYER-1:2", "advance_fen": 33600000})


def term_loan(rt, c):
    add(c, TERM)
    r = op(c, OWNER, {"kind": "DRAW_FACILITY", "op_id": "d", "requested_by": "OWNER", "facility_id": "FAC-TERM",
                      "amount_fen": 5000000})
    print("    term draw:", r["status"], r["message"][:100])


bad = {}
for label, prep in (("nothing", nothing), ("finance RCV-A day 0", finance_a),
                    ("finance RI:2 day 3", finance_ri2_day3), ("bullet term loan", term_loan)):
    bad[label] = run(label.replace(" ", "_"), prep)
for k, v in bad.items():
    check(f"projection != reality: {k}", bool(v))
