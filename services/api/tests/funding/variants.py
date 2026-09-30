"""Small FinancialState variants built from the golden fixture (read-only; each returns a copy)."""

from __future__ import annotations

from app.domain.fixtures import load_scenario
from app.domain.models import (
    BaseKind,
    CashFlow,
    Contingency,
    Duration,
    DurationKind,
    FinancialState,
    FlowKind,
    Mandate,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)

SPAN = [SourceSpan(doc_id="TEST", start=0, end=4, text="test")]


def golden() -> tuple[FinancialState, Mandate]:
    return load_scenario("golden_sme")


def with_facility(state: FinancialState, fid: str, **update) -> FinancialState:
    facilities = [f.model_copy(update=update) if f.id == fid else f for f in state.facilities]
    return state.model_copy(update={"facilities": facilities})


def without_facilities(state: FinancialState, *fids: str) -> FinancialState:
    return state.model_copy(update={"facilities": [f for f in state.facilities if f.id not in fids]})


def with_flow_day(state: FinancialState, flow_id: str, day: int) -> FinancialState:
    flows = [f.model_copy(update={"day": day}) if f.id == flow_id else f for f in state.flows]
    return state.model_copy(update={"flows": flows})


def add_flow(state: FinancialState, fid: str, day: int, amount_fen: int) -> FinancialState:
    kind = FlowKind.OTHER if amount_fen > 0 else FlowKind.OPERATING
    flow = CashFlow(id=fid, day=day, amount_fen=amount_fen, kind=kind, label=fid)
    return state.model_copy(update={"flows": [*state.flows, flow]})


def with_receivable(state: FinancialState, rid: str, **update) -> FinancialState:
    rcvs = [r.model_copy(update=update) if r.id == rid else r for r in state.receivables]
    return state.model_copy(update={"receivables": rcvs})


def with_debt_principal(state: FinancialState, principal_fen: int) -> FinancialState:
    debts = [d.model_copy(update={"principal_fen": principal_fen}) for d in state.debts]
    return state.model_copy(update={"debts": debts})


def terms_extension(days: int = 15) -> Obligation:
    return Obligation(
        id="OB-EXT",
        type=ObligationType.TERMS_EXTENSION,
        counterparty_id="BUYER-1",
        days_delta=days,
        effective_day=0,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
        spans=SPAN,
        confidence=1.0,
    )
