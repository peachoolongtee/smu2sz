"""Covenants: DSCR, leverage and clean-down, per facility definition. Pure, exact (ADR-0002).

Public interface: `evaluate()`, `ratios()`, `ratios_for()`, `pro_forma()`, `worst_dscr()`, `worst_leverage()`,
`line_can_carry_permanent_need()`,
and `CovenantEvaluatorImpl`, which satisfies `app.domain.ports.CovenantEvaluator`.
"""

from __future__ import annotations

from app.covenants.clean_down import line_balances, line_can_carry_permanent_need, longest_zero_run
from app.covenants.evaluate import evaluate
from app.covenants.ratios import (
    Basis,
    book_basis,
    fmt_x,
    leverage_debt_fen,
    pro_forma,
    ratios,
    ratios_for,
    ratios_or_undefined,
    with_extra,
    worst_dscr,
    worst_leverage,
)
from app.domain.models import Facility, Mandate, Trajectory, Violation


class CovenantEvaluatorImpl:
    """Satisfies `app.domain.ports.CovenantEvaluator`."""

    def evaluate(self, trajectory: Trajectory, facilities: list[Facility], mandate: Mandate) -> list[Violation]:
        return evaluate(trajectory, facilities, mandate)

    ratios = staticmethod(ratios)
    pro_forma = staticmethod(pro_forma)
    line_can_carry_permanent_need = staticmethod(line_can_carry_permanent_need)


__all__ = [
    "Basis",
    "CovenantEvaluatorImpl",
    "book_basis",
    "evaluate",
    "fmt_x",
    "leverage_debt_fen",
    "line_balances",
    "line_can_carry_permanent_need",
    "longest_zero_run",
    "pro_forma",
    "ratios",
    "ratios_for",
    "ratios_or_undefined",
    "with_extra",
    "worst_dscr",
    "worst_leverage",
]
