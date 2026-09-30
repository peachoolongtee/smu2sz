"""Shared builders for the egress tests.

`reservation_private_values` shows how a caller that legitimately holds a buyer profile (the
counterparties simulator, or a test) hands the buyer's hidden reservation to the egress guard as
`PrivateValue`s. The egress package itself never imports the hidden profiles.
"""

from __future__ import annotations

from functools import lru_cache

from app.counterparties.profiles import BuyerProfile
from app.domain.fixtures import load_scenario
from app.domain.models import Counterparty, FinancialState, Mandate, Receivable, RecurringInvoice
from app.domain.money import bp, pct_of, post
from app.egress import Category, PrivateValue, ProtectedSet

BUYER_B_FACE_FEN = 25_000_000  # ¥250,000
BUYER_B_TERMS_DAYS = 60


def reservation_private_values(profile: BuyerProfile) -> list[PrivateValue]:
    """A buyer's hidden reservation as protected values: visible to nobody, not even the owner.

    Mirrors `tests/counterparties/test_no_leakage.reservation_strings`: the buyer's funding cost,
    its minimum early-pay discount and rebate, its minimum surplus, declared benefit values and
    per-day payment value, plus the discount amounts those minimums imply on the invoice.
    """
    pid = profile.profile_id
    out: list[PrivateValue] = []

    def rate(name: str, v: int) -> None:
        if v > 0:
            out.append(PrivateValue.rate_bp(f"reservation.{pid}.{name}", v, category=Category.RESERVATION,
                                            owner_visible=False))

    def money(name: str, v: int) -> None:
        if v > 0:
            out.append(PrivateValue.money(f"reservation.{pid}.{name}", v, category=Category.RESERVATION,
                                          owner_visible=False))

    rate("funding_cost", profile.funding_cost_bp)
    rate("min_early_pay_discount", profile.min_early_pay_discount_bp)
    rate("min_rebate", profile.min_rebate_bp)
    money("min_surplus", profile.min_surplus_fen)
    money("payment_day_value", profile.payment_day_value_fen)
    for b in profile.declared_benefits:
        money(f"benefit.{b.id}", b.value_fen)
    if profile.min_early_pay_discount_bp and profile.invoice_face_fen:
        money("min_discount_on_invoice", post(pct_of(profile.invoice_face_fen, bp(profile.min_early_pay_discount_bp))))
    return out


def golden() -> tuple[FinancialState, Mandate]:
    return load_scenario("golden_sme")


def state_with_buyer_b() -> tuple[FinancialState, Mandate]:
    """The golden state plus an open Buyer B (BUYER-2) invoice on 60-day terms."""
    state, mandate = golden()
    rcv = Receivable(id="RCV-B", counterparty_id="BUYER-2", face_fen=BUYER_B_FACE_FEN, issue_day=-5,
                     terms_days=BUYER_B_TERMS_DAYS)
    rec = RecurringInvoice(counterparty_id="BUYER-2", face_fen=BUYER_B_FACE_FEN, every_days=30, next_issue_day=25,
                           terms_days=BUYER_B_TERMS_DAYS)
    state = state.model_copy(update={
        "receivables": [*state.receivables, rcv],
        "recurring_invoices": [*state.recurring_invoices, rec],
    })
    return state, mandate


@lru_cache
def golden_set() -> ProtectedSet:
    state, mandate = golden()
    return ProtectedSet.build(state, mandate)


@lru_cache
def buyer_b_set() -> ProtectedSet:
    state, mandate = state_with_buyer_b()
    return ProtectedSet.build(state, mandate)


def lender_ids() -> set[str]:
    state, _ = golden()
    return {c.id for c in state.counterparties if c.role == "LENDER"}


def counterparty(cp_id: str) -> Counterparty:
    state, _ = golden()
    return next(c for c in state.counterparties if c.id == cp_id)
