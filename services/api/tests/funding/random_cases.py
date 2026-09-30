"""Seeded random FinancialStates, menus, mandates and offers around the golden fixture, for the
router's differential test and the cash fast path's equivalence test. Deterministic per seed."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from random import Random

from app.domain.models import (
    BaseKind,
    Contingency,
    Duration,
    DurationKind,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    Mandate,
    Obligation,
    ObligationBase,
    ObligationType,
)
from tests.funding.variants import SPAN, add_flow, golden, terms_extension

LOAN_KINDS = frozenset({FacilityKind.GOV_GUARANTEED_LOAN, FacilityKind.EQUIPMENT_TERM_LOAN,
                        FacilityKind.EQUIPMENT_LEASE})
STATUS_WEIGHTS = [(FacilityStatus.COMMITTED, 6), (FacilityStatus.PENDING, 2), (FacilityStatus.NOT_APPLIED, 2),
                  (FacilityStatus.REFERENCE_ONLY, 1)]


@dataclass(frozen=True)
class Case:
    seed: int
    state: FinancialState
    obligations: list[Obligation]
    mandate: Mandate
    basis: str


@lru_cache
def _golden() -> tuple[FinancialState, Mandate]:
    return golden()


def _pick(rng: Random, weighted: list[tuple]) -> object:
    items, weights = zip(*weighted, strict=True)
    return rng.choices(items, weights=weights)[0]


def _facility_update(rng: Random, f) -> dict:
    if f.kind == FacilityKind.EQUITY:
        return {}
    upd: dict = {}
    if rng.random() < 0.35:
        upd["status"] = _pick(rng, STATUS_WEIGHTS)
    elif f.status != FacilityStatus.COMMITTED and rng.random() < 0.3:
        upd["status"] = FacilityStatus.COMMITTED
    upd["owner_approved"] = rng.random() < 0.92
    match f.kind:
        case FacilityKind.BUYER_EARLY_PAY:
            upd["rate_bp"] = rng.choice([f.rate_bp, rng.randint(20, 150), rng.randint(20, 300)])
        case FacilityKind.BANK_ACCEPTANCE_BILL:
            upd["rate_bp"] = rng.randint(30, 300)
            upd["limit_fen"] = rng.choice([0, 0, rng.randrange(1_000_000, 45_000_000, 500_000)])
            if rng.random() < 0.3:
                upd["term_months"] = rng.randint(1, 6)
        case FacilityKind.INVOICE_FINANCING:
            upd["rate_bp"] = rng.choice([f.rate_bp, rng.randint(300, 1600)])
            upd["advance_rate_bp"] = rng.choice([f.advance_rate_bp, None, rng.randrange(5000, 10_001, 500)])
            upd["fee_bp_per_advance"] = rng.choice([f.fee_bp_per_advance, 0, rng.randint(5, 60)])
            if rng.random() < 0.08:
                upd["drawn_fen"] = rng.randrange(1_000_000, 10_000_000, 500_000)
        case FacilityKind.CREDIT_LINE:
            upd["rate_bp"] = rng.choice([f.rate_bp, rng.randint(250, 1600)])
            if rng.random() < 0.1:
                upd["drawn_fen"] = rng.randrange(500_000, 5_000_000, 500_000)
        case _:
            upd["rate_bp"] = rng.choice([f.rate_bp, rng.randint(100, 1600)])
            if f.kind == FacilityKind.GOV_GUARANTEED_LOAN and rng.random() < 0.5:
                upd["term_months"] = rng.randint(1, 12)
            if f.kind in (FacilityKind.EQUIPMENT_TERM_LOAN, FacilityKind.EQUIPMENT_LEASE):
                # short terms keep the frozen reference search fast enough to run hundreds of cases
                # (a 48-month lease stretches every trajectory to ~1,450 days)
                upd["term_months"] = rng.choice([2, 3, 6])
    if f.kind != FacilityKind.BANK_ACCEPTANCE_BILL and rng.random() < 0.3:
        upd["limit_fen"] = rng.randrange(0, 45_000_000, 500_000)
    elif f.kind in LOAN_KINDS:
        upd["limit_fen"] = rng.randrange(5_000_000, 25_000_000, 500_000)  # the search grids a loan's cap
    if rng.random() < 0.4:
        upd["lead_time_days"] = rng.randint(0, 25)
    if rng.random() < 0.12:
        upd["upfront_fee_bp"] = rng.randint(10, 200)
    limit = upd.get("limit_fen", f.limit_fen)
    if upd.get("drawn_fen", 0) >= limit:
        upd.pop("drawn_fen", None)
    return upd


def _obligations(rng: Random, state: FinancialState) -> list[Obligation]:
    out: list[Obligation] = []
    if rng.random() < 0.3:
        out.append(terms_extension(rng.choice([5, 10, 15, 20, 30])))
    if rng.random() < 0.15:
        out.append(Obligation(
            id="OB-PRICE", type=ObligationType.PRICE_ADJUSTMENT, counterparty_id="BUYER-1",
            rate_bp=rng.choice([-80, -30, 45, 100]), effective_day=0,
            base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
            duration=Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=SPAN, confidence=1.0))
    rcv = next((r for r in state.receivables if r.id == "RCV-A"), None)
    if rcv is not None and rng.random() < 0.12:
        out.append(Obligation(
            id="OB-DISC", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1",
            rate_bp=rng.choice([60, 85, 120]), effective_day=rng.choice([None, 2, 5]),
            base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A",
                                amount_fen=rng.choice([None, rcv.face_fen // 2])),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN,
            confidence=1.0))
    if rng.random() < 0.1:
        out.append(Obligation(
            id="OB-REBATE", type=ObligationType.CONTINGENT_REBATE, counterparty_id="BUYER-1",
            amount_fen=rng.randrange(100_000, 3_000_000, 100_000), effective_day=rng.choice([None, 40, 90]),
            base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES), contingency=Contingency.CONTINGENT,
            duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN, confidence=1.0))
    return out


def random_case(seed: int) -> Case:
    rng = Random(seed)
    s, m = _golden()
    facilities = [f.model_copy(update=_facility_update(rng, f)) for f in s.facilities]
    flows = []
    for fl in s.flows:
        if fl.id == "F-BILL47" and rng.random() < 0.3:
            continue
        flows.append(fl.model_copy(update={
            "day": max(0, fl.day + rng.randint(-8, 12)),
            "amount_fen": fl.amount_fen * rng.randint(60, 130) // 100,
        }))
    receivables = [r.model_copy(update={"terms_days": rng.randint(25, 75), "confirmed": rng.random() < 0.9})
                   for r in s.receivables]
    recurring = [] if rng.random() < 0.2 else [
        ri.model_copy(update={"terms_days": rng.choice([30, 45, 60]), "face_fen": ri.face_fen * rng.randint(60, 140) // 100})
        for ri in s.recurring_invoices]
    debts = [d.model_copy(update={"principal_fen": rng.choice([0, 50_000_000, 150_000_000, 150_000_000,
                                                               200_000_000])})
             for d in s.debts]
    state = s.model_copy(update={
        "cash_fen": s.cash_fen + rng.randrange(-6_000_000, 15_000_000, 500_000),
        "facilities": facilities, "flows": flows, "receivables": receivables, "recurring_invoices": recurring,
        "debts": debts, "monthly_ebitda_fen": rng.choice([s.monthly_ebitda_fen, s.monthly_ebitda_fen, 7_000_000, 12_000_000]),
    })
    if rng.random() < 0.25:
        state = add_flow(state, "F-EXTRA", rng.randint(1, 60), -rng.randrange(2_000_000, 25_000_000, 500_000))
    mandate = m.model_copy(update={
        "min_cash_fen": rng.choice([m.min_cash_fen, m.min_cash_fen, 10_000_000, 20_000_000, 35_000_000]),
        "allow_new_borrowing": rng.random() < 0.9,
        "max_apr_bp": rng.choice([m.max_apr_bp, m.max_apr_bp, 1200, 2500]),
        "min_dscr_bp": rng.choice([m.min_dscr_bp, m.min_dscr_bp, 10_000, 14_000]),
        "max_leverage_bp": rng.choice([m.max_leverage_bp, m.max_leverage_bp, 22_000, 30_000]),
        "horizon_days": rng.choice([m.horizon_days, 90, 150]),
    })
    basis = "EXPECTED" if rng.random() < 0.2 else "COMMITTED"
    return Case(seed, state, _obligations(rng, state), mandate, basis)


def random_actions(rng: Random, state: FinancialState) -> list[FundingAction]:
    """Up to three funding actions of any kind on any facility (some deliberately malformed)."""
    rcv_ids = [r.id for r in state.receivables] + [f"RI:BUYER-1:{d}" for d in (2, 32, 62)]
    out = []
    for _ in range(rng.randint(0, 3)):
        f = rng.choice(state.facilities)
        kind = rng.choice([FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE, FundingActionKind.EARLY_PAY,
                           FundingActionKind.DISCOUNT_BILL, FundingActionKind.REPAY])
        match f.kind:
            case FacilityKind.INVOICE_FINANCING if rng.random() < 0.8:
                kind = FundingActionKind.FINANCE_INVOICE
            case FacilityKind.BUYER_EARLY_PAY if rng.random() < 0.8:
                kind = FundingActionKind.EARLY_PAY
            case FacilityKind.BANK_ACCEPTANCE_BILL if rng.random() < 0.8:
                kind = FundingActionKind.DISCOUNT_BILL
            case _ if rng.random() < 0.7:
                kind = FundingActionKind.DRAW
        out.append(FundingAction(
            kind=kind, facility_id=f.id, day=rng.choice([0, 0, 0, 3, 10]),
            amount_fen=rng.randrange(500_000, 40_000_000, 250_000),
            receivable_id=rng.choice(rcv_ids) if kind in (FundingActionKind.FINANCE_INVOICE,
                                                           FundingActionKind.EARLY_PAY) else None,
            repay_day=rng.choice([None, 20, 32, 47, 60, 180]) if kind != FundingActionKind.EARLY_PAY else None,
            rate_bp=rng.choice([None, 50, 120]) if kind in (FundingActionKind.EARLY_PAY,
                                                             FundingActionKind.DISCOUNT_BILL) else None,
        ))
    return out
