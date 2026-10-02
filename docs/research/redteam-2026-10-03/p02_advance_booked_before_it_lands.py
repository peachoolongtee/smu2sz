"""P02: an invoice-financing advance (FAC-IF, 3-day lead time) is booked as cash on the request day. The engine and
admission say it lands three days later. Requested on day 10, it lands on day 13, after the day-12 payroll; the
executor's books nevertheless show the payroll covered and the day-12 reserve alert disappears. Settlement then
bills interest and fees from the request day, not from the day the cash landed."""

from _harness import OWNER, advance, check, fresh, op, snap

from app.books import current_books
from app.domain.models import FundingAction, FundingActionKind, Mode
from app.financial import project

rt, c = fresh()
advance(c, 10)
s0 = snap(rt, "day 10 before")
m = rt.store.get_mandate()


def day_close(traj, d):
    return next(p.closing_fen for p in traj.days if p.day == d)


al0 = c.get("/alerts", headers=OWNER).json()["alerts"]
breach0 = [(a["kind"], a["day"]) for a in al0 if a["kind"] == "RESERVE_BREACH_AHEAD"]
print("  reserve alerts before:", breach0)

# what the engine (and admission) says this exact action does
st = rt.store.get_state()
books = current_books(st, rt.store.commitments())
act = FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF", receivable_id="RCV-A", day=10,
                    amount_fen=33_600_000)
eng = project(books.state, books.with_([]), [act], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
base = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
print("  engine with the advance: day 12 close", day_close(eng, 12), "day 13 close", day_close(eng, 13))

r = op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "requested_by": "OWNER",
                  "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33_600_000})
print("  finance:", r["status"], r["message"])
s1 = snap(rt, "day 10 after")
t1 = c.get("/trajectory", headers=OWNER).json()
d12 = next(p for p in t1["days"] if p["day"] == 12)
print("  /trajectory day 12 closing after execution:", d12.get("closing_fen", d12))
al1 = c.get("/alerts", headers=OWNER).json()["alerts"]
breach1 = [(a["kind"], a["day"]) for a in al1 if a["kind"] == "RESERVE_BREACH_AHEAD"]
print("  reserve alerts after:", breach1)

# settlement: the buyer pays RCV-A in full on its due day 32
advance(c, 32)
s2 = snap(rt, "day 32 before receipt")
rr = op(c, {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"},
        {"kind": "RECEIVE_PAYMENT", "op_id": "rcpt-A", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
         "amount_fen": 42_000_000})
print("  receipt:", rr["status"], rr["message"])
s3 = snap(rt, "day 32 after receipt")
charged = s2["cash"] + 42_000_000 - 33_600_000 - s3["cash"]
eng_cost = (eng.interest_posted_fen + eng.fees_posted_fen) - (base.interest_posted_fen + base.fees_posted_fen)
print(f"  executor charged interest+fees {charged} fen; engine projected {eng_cost} fen")

print("\nRESULT")
broken = [
    check("advance booked on the request day although the engine lands it 3 days later",
          s1["cash"] - s0["cash"] == 33_600_000 and day_close(eng, 12) < m.min_cash_fen),
    check("the day-12 reserve alert disappeared although the cash lands on day 13",
          any(d == 12 for _, d in breach0) and not any(d == 12 for _, d in breach1)),
    check("settlement bills more than the engine/admission priced", eng_cost is not None and charged > eng_cost),
]
print("BROKEN" if any(broken) else "HELD")
