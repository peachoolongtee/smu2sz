"""Randomised multi-month differential run: owner funding ops, partial and late receipts, clock steps.

After the random operations of a day, the conservative projection `t` on current books is taken; then exactly what
`t` says happens today is made to happen (its buyer receipts by the bank feed, its assumed line repayment and its
repayment of orphaned advance remainders by the owner) and the day is closed. The actual cash at the start of the
next day must equal t's closing for today (ADR-0010: "closing days then projecting gives the suffix"). Days on which
t repays an overdue financed invoice's advance without the receipt (the documented recourse convention) are skipped.
Every step also checks: lots sum to drawn, a FINANCED invoice has exactly one live lot equal to its advance, no live
lot names an OPEN invoice, settled <= face, the chain verifies, and the projection runs.

usage: p03_fuzz.py [seed] [days] [scenario]
"""
import random
import sys

from _harness import *  # noqa
from app.financial import EngineError

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 120
scenario = sys.argv[3] if len(sys.argv) > 3 else "golden_sme"
rng = random.Random(seed)
P_FIN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
P_RX = float(sys.argv[5]) if len(sys.argv) > 5 else 0.2
rt, c = fresh()
if scenario != "golden_sme":
    rt.reset(scenario)
n = 0
problems: list[str] = []


def key(tag):
    global n
    n += 1
    return f"{tag}-{seed}-{n}"


def try_op(headers, body):
    code, res = opj(c, headers, body)
    return res if code == 200 else {"status": f"HTTP{code}", "message": str(res)[:200]}


EXTRA = []  # owner-added facilities (argv[6] == "extra"): an amortising loan, a bullet term loan, a line with a lead time
if len(sys.argv) > 6 and sys.argv[6] == "extra":
    base = dict(owner_approved=True, status="COMMITTED", lender_id="BANK-1", fee_bp_per_advance=0, drawn_fen=0,
                counts_in_leverage=True, counts_in_debt_service=True, covenants=[])
    for fac in (
        dict(id="FAC-TL", name="Term loan", kind="EQUIPMENT_TERM_LOAN", limit_fen=20_000_000, rate_bp=600,
             upfront_fee_bp=100, lead_time_days=2, term_months=6, repayment="AMORTISING"),
        dict(id="FAC-BT", name="Bullet term", kind="GOV_GUARANTEED_LOAN", limit_fen=20_000_000, rate_bp=500,
             upfront_fee_bp=50, lead_time_days=1, term_months=2, repayment="BULLET"),
        dict(id="FAC-L2", name="Second line", kind="CREDIT_LINE", limit_fen=10_000_000, rate_bp=700,
             upfront_fee_bp=20, lead_time_days=2, term_months=None, repayment="BULLET"),
    ):
        r = try_op(OWNER, {"kind": "ADD_FACILITY", "op_id": key("add"), "requested_by": "OWNER",
                           "facility": {**base, **fac}})
        d = c.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
        print("added", fac["id"], d["status"], d["message"][:100])
        EXTRA.append(fac["id"])


def invariants(label):
    s = rt.store.get_state()
    for p in conservation(rt):
        problems.append(f"day {rt.day} {label}: {p}")
    live = [x for x in s.lots if x.remaining_fen > 0]
    for r in s.receivables:
        mine = [x for x in live if x.receivable_id == r.id]
        if r.status == "FINANCED":
            if len(mine) != 1:
                problems.append(f"day {rt.day} {label}: FINANCED {r.id} has {len(mine)} live lots")
            elif mine[0].remaining_fen != r.advance_fen:
                problems.append(f"day {rt.day} {label}: {r.id} advance_fen {r.advance_fen} != lot {mine[0].remaining_fen}")
        if r.status == "OPEN" and mine:
            problems.append(f"day {rt.day} {label}: OPEN {r.id} still named by live lot(s) {[x.id for x in mine]}")
    if not rt.store.verify_chain():
        problems.append(f"day {rt.day} {label}: chain broken")


def random_ops():
    s = rt.store.get_state()
    d = rt.day
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    iff = next(f for f in s.facilities if f.id == "FAC-IF")
    if rng.random() < 0.25 and line.limit_fen > line.drawn_fen:
        amt = rng.randint(1, (line.limit_fen - line.drawn_fen) // 100) * 100
        r = try_op(OWNER, {"kind": "DRAW_FACILITY", "op_id": key("draw"), "requested_by": "OWNER",
                           "facility_id": "FAC-LINE", "amount_fen": amt})
        print(f"  d{d} draw {amt}: {r['status']} {r['message'][:120]}")
    for fid in EXTRA:
        f = next(x for x in s.facilities if x.id == fid)
        if rng.random() < 0.12 and f.limit_fen > f.drawn_fen:
            amt = rng.randint(1, (f.limit_fen - f.drawn_fen) // 10000) * 100
            r = try_op(OWNER, {"kind": "DRAW_FACILITY", "op_id": key("xdraw"), "requested_by": "OWNER",
                               "facility_id": fid, "amount_fen": amt})
            print(f"  d{d} draw {fid} {amt}: {r['status']} {r['message'][:120]}")
        ld = sum(x.remaining_fen for x in s.lots if x.facility_id == fid and x.settled)
        if fid == "FAC-L2" and ld and rng.random() < 0.1:
            amt = rng.randint(1, ld // 100) * 100
            r = try_op(OWNER, {"kind": "REPAY_FACILITY", "op_id": key("xrep"), "requested_by": "OWNER",
                               "facility_id": fid, "amount_fen": amt})
            print(f"  d{d} repay {fid} {amt}: {r['status']} {r['message'][:120]}")
    opens = [r for r in s.receivables if r.status == "OPEN" and r.outstanding_fen > 0 and r.due_day > d + 3]
    if opens and rng.random() < P_FIN:
        r0 = rng.choice(opens)
        cap = min(r0.outstanding_fen * 8 // 10, iff.limit_fen - iff.drawn_fen)
        if cap > 100:
            amt = rng.randint(1, cap // 100) * 100
            r = try_op(OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": key("fin"), "requested_by": "OWNER",
                               "facility_id": "FAC-IF", "receivable_id": r0.id, "advance_fen": amt})
            print(f"  d{d} finance {r0.id} {amt}: {r['status']} {r['message'][:140]}")
    landed = sum(x.remaining_fen for x in s.lots if x.facility_id == "FAC-LINE" and x.settled)
    if landed and rng.random() < 0.15:
        amt = rng.randint(1, landed // 100) * 100
        r = try_op(OWNER, {"kind": "REPAY_FACILITY", "op_id": key("rep"), "requested_by": "OWNER",
                           "facility_id": "FAC-LINE", "amount_fen": amt})
        print(f"  d{d} repay line {amt}: {r['status']} {r['message'][:120]}")
    owed = [r for r in s.receivables if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0]
    if owed and rng.random() < P_RX:
        r0 = rng.choice(owed)
        amt = r0.outstanding_fen if rng.random() < 0.4 else rng.randint(1, r0.outstanding_fen // 100) * 100
        r = try_op(BANK, {"kind": "RECEIVE_PAYMENT", "op_id": key("rx"), "requested_by": "SYSTEM",
                          "receivable_id": r0.id, "amount_fen": amt})
        print(f"  d{d} random receipt {r0.id} {amt}: {r['status']} {r['message'][:160]}")


checked = skipped = 0
while rt.day < DAYS:
    d = rt.day
    random_ops()
    invariants("after ops")
    try:
        t = projection(rt)
    except EngineError as e:
        problems.append(f"day {d}: projection fails: {e}")
        advance(c, d + 1)
        continue
    p = next(p for p in t.days if p.day == d)
    recourse = False
    s = rt.store.get_state()
    for e in p.events:
        lab = e.label or ""
        if e.kind.value == "REPAYMENT" and "assumed repaid" in (e.formula or "") and e.ref in ("FAC-LINE", "FAC-L2"):
            r = try_op(OWNER, {"kind": "REPAY_FACILITY", "op_id": key("arep"), "requested_by": "OWNER",
                               "facility_id": e.ref, "amount_fen": -e.amount_fen})
            print(f"  d{d} assumed line repayment {-e.amount_fen}: {r['status']} {r['message'][:140]}")
        elif e.kind.value == "REPAYMENT" and "fixed amount owed" in (e.formula or ""):
            r = try_op(OWNER, {"kind": "REPAY_FACILITY", "op_id": key("orp"), "requested_by": "OWNER",
                               "facility_id": "FAC-IF", "amount_fen": -e.amount_fen})
            print(f"  d{d} orphan repayment {-e.amount_fen}: {r['status']} {r['message'][:140]}")
        elif e.kind.value == "REPAYMENT" and lab.startswith("Repay advance on "):
            rid = lab.removeprefix("Repay advance on ")
            rr = next((x for x in s.receivables if x.id == rid), None)
            if rr is None or rr.due_day < d or rr.outstanding_fen <= 0:
                recourse = True
    for rid, amt in expected_receipts(t, d).items():
        if amt > 0:
            r = try_op(BANK, {"kind": "RECEIVE_PAYMENT", "op_id": key("prx"), "requested_by": "SYSTEM",
                              "receivable_id": rid, "amount_fen": amt})
            print(f"  d{d} projected receipt {rid} {amt}: {r['status']} {r['message'][:160]}")
    invariants("before close")
    advance(c, d + 1)
    actual = rt.store.get_state().cash_fen
    if recourse:
        skipped += 1
    else:
        checked += 1
        if actual != p.closing_fen:
            problems.append(f"day {d}: projected closing {p.closing_fen} but cash at start of day {d + 1} is {actual} "
                            f"(diff {actual - p.closing_fen}); events {[(e.kind.value, e.amount_fen, e.ref) for e in p.events]}")
    invariants("after close")

snap(rt, "end")
print(f"seed {seed}: {checked} days compared, {skipped} skipped (recourse), {len(problems)} problems")
for x in problems[:40]:
    print("PROBLEM", x)
