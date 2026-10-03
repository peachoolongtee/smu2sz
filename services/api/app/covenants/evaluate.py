"""Monthly ratio covenants (per facility definition + mandate limits) and clean-down.

Ratios are recomputed exactly from each MonthPoint's raw inputs (ebitda_fen, debt_service_fen,
total_debt_fen) with the single definition in `ratios.py`, so every violation's formula and inputs
reproduce its observed value. Each facility covenant is tested against its own threshold and shows
its own definition and formula text.
"""

from __future__ import annotations

from fractions import Fraction

from app.covenants.clean_down import check_clean_down
from app.covenants.ratios import fmt_exact, fmt_x, ratios_for
from app.domain.models import (
    Covenant,
    CovenantKind,
    Facility,
    Mandate,
    MonthPoint,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import bp, fmt_yuan

MANDATE_DSCR_DEFINITION = "owner mandate: monthly EBITDA / monthly debt service"
MANDATE_LEVERAGE_DEFINITION = "owner mandate: total debt / annualised EBITDA (12 x monthly EBITDA)"


def _month_inputs(m: MonthPoint) -> dict[str, str]:
    return {
        "month": str(m.month),
        "EBITDA_m": fmt_yuan(m.ebitda_fen),
        "DS_m": fmt_yuan(m.debt_service_fen),
        "Debt_m": fmt_yuan(m.total_debt_fen),
    }


def _dscr_check(
    m: MonthPoint, limit: Fraction, source: str, source_id: str, definition: str, formula_text: str
) -> Violation | None:
    dr, _ = ratios_for(m)
    d = dr.value if dr is not None else None
    if d is None or d >= limit:
        return None
    return Violation(
        code=ViolationCode.DSCR_BREACH,
        message=f"DSCR {fmt_x(d)} in month {m.month} is below the {source} minimum {fmt_x(limit)}",
        month=m.month,
        observed=fmt_x(d),
        limit=fmt_x(limit),
        formula=(
            f"{formula_text}: {fmt_yuan(m.ebitda_fen)} / {fmt_yuan(m.debt_service_fen)} "
            f"= {fmt_x(d)} < {fmt_x(limit)}"
        ),
        inputs={
            **_month_inputs(m),
            "source": source,
            "source_id": source_id,
            "definition": definition,
            "dscr_exact": fmt_exact(d),
            "limit_exact": fmt_exact(limit),
        },
    )


def _leverage_check(
    m: MonthPoint, limit: Fraction, source: str, source_id: str, definition: str, formula_text: str
) -> Violation | None:
    _, lr = ratios_for(m)
    lev = lr.value if lr is not None else None
    if lev is None:
        if m.total_debt_fen <= 0:
            return None
        observed, exact, detail = "undefined", "undefined", "EBITDA <= 0 with debt outstanding"
    elif lev <= limit:
        return None
    else:
        observed, exact, detail = fmt_x(lev), fmt_exact(lev), f"= {fmt_x(lev)} > {fmt_x(limit)}"
    return Violation(
        code=ViolationCode.LEVERAGE_BREACH,
        message=f"Leverage {observed} in month {m.month} is above the {source} maximum {fmt_x(limit)}",
        month=m.month,
        observed=observed,
        limit=fmt_x(limit),
        formula=(
            f"{formula_text}: {fmt_yuan(m.total_debt_fen)} / (12 x {fmt_yuan(m.ebitda_fen)}) {detail}"
        ),
        inputs={
            **_month_inputs(m),
            "source": source,
            "source_id": source_id,
            "definition": definition,
            "leverage_exact": exact,
            "limit_exact": fmt_exact(limit),
        },
    )


def _threshold(c: Covenant) -> Fraction:
    if c.threshold_bp is None:
        raise ValueError(f"covenant {c.id}: {c.kind} needs threshold_bp")
    return bp(c.threshold_bp)


def evaluate(trajectory: Trajectory, facilities: list[Facility], mandate: Mandate) -> list[Violation]:
    """Every MonthPoint against every covenant of every facility passed in (the caller chooses
    which facilities bind) and the mandate's DSCR/leverage limits; clean-down on each CREDIT_LINE.

    Order: per month, facility covenants in facility/covenant order, then the mandate; then
    clean-down violations. A month with zero debt service has no DSCR and cannot breach it."""
    out: list[Violation] = []
    months = sorted(trajectory.months, key=lambda m: m.month)
    for m in months:
        for f in facilities:
            for c in f.covenants:
                label = f"{f.name} covenant"
                if c.kind == CovenantKind.DSCR_MIN:
                    v = _dscr_check(m, _threshold(c), label, c.id, c.definition, c.formula)
                elif c.kind == CovenantKind.LEVERAGE_MAX:
                    v = _leverage_check(m, _threshold(c), label, c.id, c.definition, c.formula)
                else:
                    continue
                if v is not None:
                    out.append(v.model_copy(update={"inputs": {**v.inputs, "facility_id": f.id}}))
        mv = _dscr_check(
            m,
            bp(mandate.min_dscr_bp),
            "mandate",
            f"mandate v{mandate.version}",
            MANDATE_DSCR_DEFINITION,
            "EBITDA_m / DS_m >= min_dscr",
        )
        if mv is not None:
            out.append(mv)
        ml = _leverage_check(
            m,
            bp(mandate.max_leverage_bp),
            "mandate",
            f"mandate v{mandate.version}",
            MANDATE_LEVERAGE_DEFINITION,
            "Debt_m / (12 x EBITDA_m) <= max_leverage",
        )
        if ml is not None:
            out.append(ml)
    for f in facilities:
        for c in f.covenants:
            if c.kind == CovenantKind.CLEAN_DOWN:
                v = check_clean_down(trajectory, f, c)
                if v is not None:
                    out.append(v)
    return out
