"""Admission of a credit-line draw as a carried lot (commit 11acc56). Does the carried projection include the draw's
cash? Compare the admission's `after` trajectory with the projection of the books right after the draw executes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403
from app.books import current_books  # noqa: E402
from app.domain.models import Actor, DrawFacility  # noqa: E402
from app.funding.admission import _as_carried, admit  # noqa: E402

rt, c = fresh()
m = rt.store.get_mandate()
before = projection(rt)
print("before: min", before.min_cash_fen, "day", before.min_cash_day)
amt = int(sys.argv[1]) if len(sys.argv) > 1 else 15_000_000
d = DrawFacility(op_id="probe", idempotency_key="probe", mandate_version=m.version, requested_by=Actor.AGENT, day=0,
                 facility_id="FAC-LINE", amount_fen=amt)
books = current_books(rt.store.get_state(), rt.store.commitments())
carried = _as_carried(d, books.state)
print("carried state cash", carried.cash_fen, "vs real cash after a lead-0 draw", books.state.cash_fen + amt)
t_carried = project(carried, list(books.obligations), [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
print("admission 'after' closings d0..d13", [closing(t_carried, x) for x in range(14)])
a = admit(d, books, m)
print("admission:", [(v.code.value, v.message[:140]) for v in a.violations], a.approval_reason)
res = opj(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": "draw-1", "requested_by": "AGENT", "facility_id": "FAC-LINE",
                     "amount_fen": amt})
print("executor:", res[0], res[1]["status"], res[1]["message"][:300])
after = projection(rt)
print("books after the draw executed, closings d0..d13", [closing(after, x) for x in range(14)])
print("real after: min", after.min_cash_fen, "day", after.min_cash_day)
check("admission's carried projection omits the draw's own cash", carried.cash_fen != books.state.cash_fen + amt)
