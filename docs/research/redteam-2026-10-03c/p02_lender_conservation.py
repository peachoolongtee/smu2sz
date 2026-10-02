"""Lender conservation on a financed invoice under many receipt patterns: the lender must receive exactly principal
+ charges (billed once, original principal, whole periods from landing to clearing), the owner keeps the rest, lots sum
to drawn, an orphan is repayable exactly once."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403
from app.financial.charges import finance_invoice_charges  # noqa: E402

FAC = "FAC-IF"


def lender_paid(rt, before_cash, after_cash, amount):
    return amount - (after_cash - before_cash)


def scenario(name, adv, pattern):
    """pattern: list of (day, amount or 'rest' or ('repay', amt))"""
    rt, c = fresh()
    res = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": f"fin-{name}", "requested_by": "AGENT",
                        "facility_id": FAC, "receivable_id": "RCV-A", "advance_fen": adv})
    assert res["status"] == "EXECUTED", res
    f = next(x for x in rt.store.get_state().facilities if x.id == FAC)
    to_lender, landed_cash, notes, cleared_day = 0, 0, [], None
    for day, what in pattern:
        if rt.day < day:
            cash0 = rt.store.get_state().cash_fen
            advance(c, day)
            landed_cash += rt.store.get_state().cash_fen - cash0 if day > 3 and landed_cash == 0 else 0
        s = rt.store.get_state()
        r = next(x for x in s.receivables if x.id == "RCV-A")
        if isinstance(what, tuple):
            amt = what[1]
            cash0 = s.cash_fen
            out = op(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": f"rp-{name}-{day}-{amt}", "requested_by": "OWNER",
                                "facility_id": FAC, "amount_fen": amt})
            paid = cash0 - rt.store.get_state().cash_fen if out["status"] == "EXECUTED" else 0
            to_lender += paid
            notes.append(f"d{day} repay {amt}: {out['status']} {out['message'][:150]}")
            continue
        amt = r.outstanding_fen if what == "rest" else what
        cash0 = s.cash_fen
        out = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": f"rx-{name}-{day}-{amt}", "requested_by": "SYSTEM",
                           "receivable_id": "RCV-A", "amount_fen": amt})
        if out["status"] == "EXECUTED":
            to_lender += amt - (rt.store.get_state().cash_fen - cash0)
        notes.append(f"d{day} rx {amt}: {out['status']} {out['message'][:220]}")
    s = rt.store.get_state()
    r = next(x for x in s.receivables if x.id == "RCV-A")
    lot = [x for x in s.lots if x.facility_id == FAC]
    print(f"== {name}: advance {adv}")
    for n in notes:
        print("   ", n)
    print("    final rcv", r.status, r.face_fen, r.settled_fen, r.advance_fen, "lots", [(x.id, x.principal_fen, x.remaining_fen) for x in lot],
          "drawn", next(x for x in s.facilities if x.id == FAC).drawn_fen)
    print("    lender received", to_lender, "conservation", conservation(rt), "chain", rt.store.verify_chain())
    return rt, to_lender


# 1. one full receipt on the due day
rt, got = scenario("full", 33_600_000, [(32, "rest")])
i, fee, p = finance_invoice_charges(next(x for x in rt.store.get_state().facilities if x.id == FAC), 33_600_000, 32 - 3)
check("full: lender gets principal + charges", got != 33_600_000 + i + fee)

# 2. partial non-final smaller than principal, then rest
rt, got = scenario("partial", 33_600_000, [(10, 10_000_000), (32, "rest")])
i, fee, p = finance_invoice_charges(next(x for x in rt.store.get_state().facilities if x.id == FAC), 33_600_000, 32 - 3)
check("partial: lender gets principal + charges", got != 33_600_000 + i + fee)

# 3. non-final receipt above principal but below claim -> fixed remainder, then rest
rt, got = scenario("fixedrem", 33_600_000, [(40, 33_700_000), (50, "rest")])
i, fee, p = finance_invoice_charges(next(x for x in rt.store.get_state().facilities if x.id == FAC), 33_600_000, 40 - 3)
check("fixedrem: lender gets principal + charges billed at 40", got != 33_600_000 + i + fee)

# 4. final short receipt -> orphan, owner repays, then repays again
rt, got0 = scenario("orphan", 33_600_000, [(10, 30_000_000), (32, 12_000_000), (33, ("repay", 10**9))])
s = rt.store.get_state()
owed = sum(x.remaining_fen for x in s.lots if x.facility_id == FAC)
print("    orphan owed", owed)
# 5. receipt one fen at a time before landing (lot not landed), exactly at advance-rate limit
rt, got = scenario("onefen", 33_600_000, [(1, 1)])
s = rt.store.get_state()
print("    after 1 fen on day 1: lots", lots(rt), "cash", s.cash_fen)
