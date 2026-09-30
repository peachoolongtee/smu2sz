"""`Engine`: the TrajectoryEngine port (app.domain.ports) over the module's pure functions."""

from __future__ import annotations

from app.domain.models import ConcessionValue, FinancialState, FundingAction, Mode, Obligation, Trajectory
from app.domain.money import Ratio
from app.financial.concessions import value_concessions
from app.financial.trajectory import project


class Engine:
    """Stateless. Every call is a pure function of its arguments."""

    def project(
        self,
        state: FinancialState,
        obligations: list[Obligation],
        actions: list[FundingAction],
        mode: Mode,
        horizon_days: int,
        min_cash_fen: int | None = None,
    ) -> Trajectory:
        return project(state, obligations, actions, mode, horizon_days, min_cash_fen)

    def value_concessions(
        self,
        obligations: list[Obligation],
        state: FinancialState,
        funding_rate: Ratio,
        basis_label: str,
        horizon_days: int,
    ) -> list[ConcessionValue]:
        return value_concessions(obligations, state, funding_rate, basis_label, horizon_days)
