import typing

import pytest

from app.domain import models as m
from app.domain.fixtures import load_scenario
from app.domain.models import Actor, Tier
from app.mandate import MandatePolicyImpl, tier_for

STATE, MANDATE = load_scenario()
LINE = next(f for f in STATE.facilities if f.id == "FAC-LINE")
LIMIT = MANDATE.tier2_single_commitment_fen  # ¥100,000.00


def op(cls, actor=Actor.AGENT, **kw):
    return cls(op_id="op", idempotency_key="k", mandate_version=1, requested_by=actor, day=0, **kw)


def tier(o, **kw):
    return tier_for(o, MANDATE, STATE, **kw)


CASES = [
    # (operation, expected tier)
    (op(m.AcceptOffer, offer_id="o", offer_version=1, terms_hash="h", nonce="n"), Tier.TIER_1),
    (op(m.CounterOffer, offer_id="o", counter_id="c"), Tier.TIER_1),
    (op(m.RejectOffer, offer_id="o", reason_codes=[]), Tier.TIER_1),
    (op(m.RecordCommitment, commitment_id="c", nonce="n"), Tier.TIER_1),
    (op(m.DrawFacility, facility_id="FAC-LINE", amount_fen=LIMIT), Tier.TIER_1),
    (op(m.RepayFacility, facility_id="FAC-LINE", amount_fen=15_000_000), Tier.TIER_1),
    (
        op(m.SubmitInvoiceForFinancing, facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=LIMIT),
        Tier.TIER_1,
    ),
    (op(m.ReceivePayment, receivable_id="RCV-A", amount_fen=42_000_000), Tier.TIER_1),
    (op(m.RequestOwnerApproval, subject="s", payload_op_id="p"), Tier.TIER_1),
    (op(m.GenerateBorrowerFile, facility_id="FAC-GGL", amount_fen=1), Tier.TIER_2),
    (op(m.ApplyForFacility, facility_id="FAC-GGL", amount_fen=1), Tier.TIER_2),
    (op(m.SignPersonalGuarantee, actor=Actor.OWNER, facility_id="FAC-LINE"), Tier.TIER_3),
    (op(m.PledgeCollateral, actor=Actor.OWNER, facility_id="FAC-LINE"), Tier.TIER_3),
    (op(m.IssueEquity, actor=Actor.OWNER, amount_fen=1), Tier.TIER_3),
    (op(m.ChangeMandate, actor=Actor.OWNER, new_version=2), Tier.TIER_3),
    (op(m.AddFacility, actor=Actor.OWNER, facility=LINE), Tier.TIER_2),
    (op(m.AddFacility, actor=Actor.AGENT, facility=LINE), Tier.TIER_3),
    (op(m.AddFacility, actor=Actor.COUNTERPARTY, facility=LINE), Tier.TIER_3),
    (op(m.AddFacility, actor=Actor.SYSTEM, facility=LINE), Tier.TIER_3),
]


@pytest.mark.parametrize("o, expected", CASES, ids=[f"{c[0].kind}-{c[0].requested_by}" for c in CASES])
def test_tier_for_every_operation(o, expected):
    assert tier(o) == expected


def test_every_operation_kind_is_covered():
    kinds = {cls.model_fields["kind"].default for cls in typing.get_args(typing.get_args(m.Operation)[0])}
    assert kinds == {o.kind for o, _ in CASES}


def test_committed_line_draw_is_tier1_at_any_size_within_limit():
    # spec v2 §5.3: operating an existing committed facility is Tier 1; the ¥100k threshold is for new commitments
    assert tier(op(m.DrawFacility, facility_id="FAC-LINE", amount_fen=15_000_000)) == Tier.TIER_1


def test_committed_invoice_advance_is_tier1_at_any_size():
    o = op(m.SubmitInvoiceForFinancing, facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=LIMIT + 1)
    assert tier(o) == Tier.TIER_1


def test_apply_for_facility_is_tier2_at_any_size():
    assert tier(op(m.ApplyForFacility, facility_id="FAC-GGL", amount_fen=1)) == Tier.TIER_2


@pytest.mark.parametrize("fid", ["FAC-GGL", "FAC-ETL", "FAC-EQUITY", "NOT-ON-MENU"])
def test_draw_on_non_committed_facility_is_tier2(fid):
    assert tier(op(m.DrawFacility, facility_id=fid, amount_fen=1)) == Tier.TIER_2
    o = op(m.SubmitInvoiceForFinancing, facility_id=fid, receivable_id="RCV-A", advance_fen=1)
    assert tier(o) == Tier.TIER_2


def test_accept_offer_with_terms_change_is_tier2():
    o = op(m.AcceptOffer, offer_id="o", offer_version=1, terms_hash="h", nonce="n")
    assert tier(o) == Tier.TIER_1
    assert tier(o, accepts_terms_change=True) == Tier.TIER_2
    assert tier(o, commitment_value_fen=LIMIT) == Tier.TIER_1
    assert tier(o, commitment_value_fen=LIMIT + 1) == Tier.TIER_2


def test_record_commitment_with_terms_change_is_tier2():
    o = op(m.RecordCommitment, commitment_id="c", nonce="n")
    assert tier(o) == Tier.TIER_1
    assert tier(o, accepts_terms_change=True) == Tier.TIER_2
    assert tier(o, commitment_value_fen=LIMIT + 1) == Tier.TIER_2


def test_terms_change_flag_does_not_affect_other_operations():
    assert tier(op(m.RejectOffer, offer_id="o", reason_codes=[]), accepts_terms_change=True) == Tier.TIER_1


def test_owner_cannot_lower_tier3():
    o = op(m.ChangeMandate, actor=Actor.OWNER, new_version=2)
    assert tier(o, accepts_terms_change=False, commitment_value_fen=0) == Tier.TIER_3


def test_unknown_operation_fails_closed():
    assert tier(object()) == Tier.TIER_3


def test_policy_class_delegates():
    o = op(m.AcceptOffer, offer_id="o", offer_version=1, terms_hash="h", nonce="n")
    assert MandatePolicyImpl().tier_for(o, MANDATE, STATE, accepts_terms_change=True) == Tier.TIER_2
