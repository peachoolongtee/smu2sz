"""Property: over random menus, a COMMITTED plan only ever uses COMMITTED, owner-approved facilities,
and an admissible plan really holds the floor on the conservative trajectory (INVARIANT 4, 11)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.models import FacilityStatus, Mode
from app.financial import project
from app.funding import plan
from tests.funding.variants import golden, with_facility

STATUSES = st.sampled_from(list(FacilityStatus))
MENU = ["FAC-LINE", "FAC-IF", "FAC-EARLYPAY", "FAC-GGL", "FAC-BILL"]


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    statuses=st.fixed_dictionaries({fid: STATUSES for fid in MENU}),
    approved=st.fixed_dictionaries({fid: st.booleans() for fid in MENU}),
    ggl_lead=st.integers(min_value=0, max_value=30),
    bills=st.sampled_from([0, 10_000_000, 40_000_000]),
)
def test_committed_plan_uses_only_committed_facilities(statuses, approved, ggl_lead, bills):
    s, m = golden()
    for fid in MENU:
        s = with_facility(s, fid, status=statuses[fid], owner_approved=approved[fid])
    s = with_facility(s, "FAC-GGL", lead_time_days=ggl_lead, term_months=1)
    s = with_facility(s, "FAC-BILL", limit_fen=bills)
    facs = {f.id: f for f in s.facilities}
    p = plan(s, [], m)
    for a in p.actions:
        assert facs[a.facility_id].status == FacilityStatus.COMMITTED
        assert facs[a.facility_id].owner_approved
    if p.admissible:
        t = project(s, [], p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
        assert t.first_breach_day is None
        assert t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen == p.total_cost_fen
