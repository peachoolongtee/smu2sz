"""Ratio path with an owner-added bullet term loan (12 months, 5%, 2% upfront fee, 5-day lead time).

Admission judges a term-loan draw as an engine ACTION: its upfront fee is one of the postings spread over the term on
the level basis (ADR-0008). Once executed, the lot is in the state and has not landed; the projection posts the fee
on the landing day OUTSIDE the level amount (`_land` runs before `_contractual` collects the term lot's postings), so
the landing month carries the whole fee. A draw sized at the edge of the DSCR minimum therefore passes admission and
the very next projection shows a DSCR breach, which then refuses every other funding operation until the cash lands."""
from _harness import *
from app.books import current_books
from app.covenants import evaluate as evaluate_covenants
from app.domain.models import Actor, DrawFacility, FacilityStatus
from app.funding.admission import admit

rt, c = fresh()
fac = {"id": "FAC-TL", "name": "Term loan", "kind": "GOV_GUARANTEED_LOAN", "lender_id": "BANK-2", "status": "COMMITTED",
       "owner_approved": True, "limit_fen": 60000000, "drawn_fen": 0, "rate_bp": 500, "upfront_fee_bp": 200,
       "lead_time_days": 5, "term_months": 12, "repayment": "BULLET"}
r = op(c, OWNER, {"kind": "ADD_FACILITY", "op_id": "add-tl", "requested_by": "OWNER", "facility": fac})
if r["status"] == "PENDING_APPROVAL":
    r = approve(c, r["approval_id"])
print("add facility:", r["status"], r["message"][:100])


def admitted(amount: int):
    m = rt.store.get_mandate()
    o = DrawFacility(op_id="probe", idempotency_key="probe", mandate_version=m.version, requested_by=Actor.AGENT,
                     day=rt.day, facility_id="FAC-TL", amount_fen=amount)
    return admit(o, current_books(rt.store.get_state(), rt.store.commitments()), m)


lo, hi = 100000, 60000000
while hi - lo > 100:
    mid = (lo + hi) // 2
    if admitted(mid).violations:
        hi = mid
    else:
        lo = mid
print("largest draw admission accepts:", lo, "fen; refused at", hi, [v.code.value for v in admitted(hi).violations][:3])


def ratio_breaches(label: str):
    t = projection(rt)
    m = rt.store.get_mandate()
    s = rt.store.get_state()
    binding = [f for f in s.facilities if f.status == FacilityStatus.COMMITTED]
    vs = [v for v in evaluate_covenants(t, binding, m) if v.code.value in ("DSCR_BREACH", "LEVERAGE_BREACH")]
    for mm in t.months[:3]:
        print(f"   [{label}] month {mm.month}: DS {mm.debt_service_fen} DSCR {mm.dscr.text if mm.dscr else None}")
    print(f"   [{label}] ratio breaches:", sorted({(v.code.value, v.month) for v in vs}))
    return vs


ratio_breaches("before")
res = op(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": "tl-draw", "requested_by": "AGENT", "facility_id": "FAC-TL",
                    "amount_fen": lo})
print("draw", lo, ":", res["status"], res["message"][:140])
after = ratio_breaches("after the draw executed")
small = opj(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": "line-small", "requested_by": "AGENT", "facility_id": "FAC-LINE",
                       "amount_fen": 1000000})
print("a ¥10,000 line draw now:", small[1]["status"], small[1]["message"][:200])
al = c.get("/alerts", headers=OWNER).json()
print("alerts:", [(a["kind"], a["title"]) for a in al["alerts"] if "COVENANT" in a["kind"]])
advance(c, 6)
ratio_breaches("day 6, the loan has landed")
check("a draw admission accepted shows a DSCR breach in the next projection of the same books",
      res["status"] == "EXECUTED" and bool(after))
