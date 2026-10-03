"""Randomised: each day a few random operations (partial and full bank receipts, early receipts, line draws and
repayments, invoice advances, owner receipts), then two invariants:

1. conservation: lots sum to drawn per facility; settled <= face; a FINANCED invoice still owes something.
2. the projection made after today's operations, for a day on which it books nothing that needs an operation
   (no buyer receipt, no assumed or recourse repayment), equals the cash the clock leaves after closing the day.

usage: p11_random_daily_invariant.py [seeds] [days]"""
import random
import sys

from _harness import *
from app.domain.models import LedgerEventKind as K

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 120
bad = []


def needs_op(p) -> bool:
    for e in p.events:
        if e.kind in (K.RECEIPT, K.EARLY_RECEIPT, K.DISCOUNT):
            return True
        if e.kind in (K.REPAYMENT, K.INTEREST, K.FEE) and (e.ref in ("FAC-LINE", "FAC-IF")):
            return True
    return False


for seed in range(SEEDS):
    R = random.Random(seed)
    rt, c = fresh()
    n = 0
    while rt.day < DAYS:
        d = rt.day
        s = rt.store.get_state()
        for _ in range(R.randint(0, 3)):
            n += 1
            s = rt.store.get_state()
            choice = R.random()
            open_rcv = [r for r in s.receivables if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0]
            if choice < 0.35 and open_rcv:
                r = R.choice(open_rcv)
                full = R.random() < 0.6
                amt = r.outstanding_fen if full else R.randint(1, r.outstanding_fen)
                if r.due_day != d and full and R.random() < 0.7:
                    continue
                who = BANK if R.random() < 0.8 else OWNER
                body = {"kind": "RECEIVE_PAYMENT", "op_id": f"s{seed}-rx-{n}", "requested_by": "SYSTEM" if who is BANK else "OWNER",
                        "receivable_id": r.id, "amount_fen": amt}
                code, res = opj(c, who, body)
                tag = res["status"] if code == 200 else code
            elif choice < 0.55:
                amt = R.choice([1, 100, 1000000, 5000000, 15000000, R.randint(1, 15000000)])
                code, res = opj(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": f"s{seed}-draw-{n}", "requested_by": "AGENT",
                                           "facility_id": "FAC-LINE", "amount_fen": amt})
            elif choice < 0.7:
                line = next(f for f in s.facilities if f.id == "FAC-LINE")
                if line.drawn_fen:
                    amt = R.choice([line.drawn_fen, R.randint(1, line.drawn_fen)])
                    code, res = opj(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": f"s{seed}-repay-{n}",
                                               "requested_by": "OWNER", "facility_id": "FAC-LINE", "amount_fen": amt})
            elif choice < 0.9:
                cand = [r for r in s.receivables if r.status == "OPEN" and r.outstanding_fen > 0]
                if cand:
                    r = R.choice(cand)
                    cap = r.outstanding_fen * 8000 // 10000
                    if cap > 0:
                        amt = R.choice([cap, R.randint(1, cap), 1])
                        code, res = opj(c, AGENT if R.random() < 0.5 else OWNER,
                                        {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": f"s{seed}-fin-{n}",
                                         "requested_by": "AGENT", "facility_id": "FAC-IF", "receivable_id": r.id,
                                         "advance_fen": amt})
            br = conservation(rt)
            if br:
                bad.append((seed, d, "conservation", br))
                print("CONSERVATION", seed, d, br)
        t = projection(rt, 5)
        p = next(p for p in t.days if p.day == d)
        before = rt.store.get_state().cash_fen
        advance(c, d + 1)
        after = rt.store.get_state().cash_fen
        if not needs_op(p) and after != p.closing_fen:
            bad.append((seed, d, "projection", p.closing_fen, after))
            print(f"PROJ seed {seed} day {d}: projected {p.closing_fen} actual {after} (opening {before})")
            for e in p.events:
                print("    ", e.kind.value, e.amount_fen, e.ref, e.label[:90])
    ok = rt.store.verify_chain()
    if not ok:
        bad.append((seed, "chain"))
    print(f"seed {seed}: day {rt.day} cash {rt.store.get_state().cash_fen} ops {n} chain {ok}")
check("an invariant broke in a random run", bool(bad))
