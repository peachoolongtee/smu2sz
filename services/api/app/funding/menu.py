"""The funding menu, every source on the same basis (spec §7.2–7.3)."""

from __future__ import annotations

from app.covenants import line_can_carry_permanent_need
from app.domain.models import (
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    Mandate,
    ViolationCode,
)
from app.domain.money import Ratio, fmt_yuan
from app.funding.models import MenuRow
from app.funding.rates import all_in_rate, display_rate, is_debt, tier3_reasons
from app.mandate import check_apr


def _days_early(f: Facility, state: FinancialState) -> int | None:
    """Days early on the buyer's next open receivable (the one an offer would settle)."""
    best = None
    for r in state.receivables:
        if r.status != "OPEN" or r.counterparty_id != f.lender_id:
            continue
        days = r.issue_day + r.terms_days - (max(0, r.issue_day) + f.lead_time_days)
        if days > 0 and (best is None or r.issue_day + r.terms_days < best[0]):
            best = (r.issue_day + r.terms_days, days)
    return best[1] if best else None


def _covenant_notes(f: Facility) -> list[str]:
    notes = []
    for c in f.covenants:
        notes.append(f"{c.kind.value}: {c.definition} ({c.formula})")
    if any(c.kind == CovenantKind.CLEAN_DOWN for c in f.covenants):
        notes.append("short-term only: the clean-down rule means it cannot carry a permanent need")
    return notes


def menu_row(f: Facility, state: FinancialState, mandate: Mandate, need_fen: int | None = None,
             need_day: int | None = None) -> MenuRow:
    days = _days_early(f, state) if f.kind == FacilityKind.BUYER_EARLY_PAY else None
    rate, basis = all_in_rate(f, days_early=days)
    committed = f.status == FacilityStatus.COMMITTED
    limit_left = max(0, f.limit_fen - f.drawn_fen)
    available = limit_left if committed and f.owner_approved else 0
    reasons: list[ViolationCode] = []
    notes: list[str] = []
    if not committed or not f.owner_approved:
        reasons.append(ViolationCode.UNCOMMITTED_FACILITY)
        notes.append(f"{f.status.value}: counts as zero for hard constraints; shown in the expected plan only")
    if need_day is not None and f.lead_time_days > need_day:
        reasons.append(ViolationCode.LEAD_TIME_TOO_LONG)
        notes.append(f"cash on day {f.lead_time_days}, needed by day {need_day}")
    over_cap = f.kind != FacilityKind.EQUITY and check_apr(Ratio.of(rate), mandate, f.name) is not None
    if over_cap:  # shown, but not a bar: a plan that uses it needs the owner's approval
        reasons.append(ViolationCode.MAX_APR_EXCEEDED)
        notes.append("tariff above the mandate's max APR: the agent cannot use it alone, the owner must approve")
    reasons += tier3_reasons(f)
    short_term = f.kind == FacilityKind.CREDIT_LINE and not line_can_carry_permanent_need(f)
    if f.kind == FacilityKind.BUYER_EARLY_PAY:
        notes.append("only while the buyer offers it; reduces receivables and creates no debt")
    if limit_left == 0:
        notes.append("no capacity (limit fully used or zero)")
    elif need_fen is not None and available and available < need_fen:
        notes.append(f"covers at most {fmt_yuan(available)} of the {fmt_yuan(need_fen)} need")
    if f.source_note:
        notes.append(f.source_note)
    return MenuRow(
        facility_id=f.id,
        name=f.name,
        kind=f.kind,
        status=f.status,
        committed=committed,
        owner_approved=f.owner_approved,
        expected_only=f.owner_approved and f.status in (FacilityStatus.PENDING, FacilityStatus.NOT_APPLIED),
        all_in_rate=Ratio.of(rate),
        all_in_display=display_rate(f, rate),
        rate_basis=basis,
        time_to_cash_days=f.lead_time_days,
        limit_fen=f.limit_fen,
        available_fen=available,
        limit_display=fmt_yuan(f.limit_fen),
        available_display=fmt_yuan(available),
        counts_in_leverage=f.counts_in_leverage,
        counts_in_debt_service=f.counts_in_debt_service,
        is_debt=is_debt(f),
        short_term_only=short_term,
        covenant_notes=_covenant_notes(f),
        admissible_for_need=not [c for c in reasons if c != ViolationCode.MAX_APR_EXCEEDED] and available > 0,
        needs_owner_approval=over_cap,
        reasons=reasons,
        notes=notes,
    )


def menu_view(
    state: FinancialState, mandate: Mandate, need_fen: int | None = None, need_day: int | None = None
) -> list[MenuRow]:
    """One row per facility, in menu order. `admissible_for_need` is true only for a committed,
    owner-approved source with capacity, in time for `need_day`, within the mandate's max APR and
    with no Tier-3 condition."""
    return [menu_row(f, state, mandate, need_fen, need_day) for f in state.facilities]
