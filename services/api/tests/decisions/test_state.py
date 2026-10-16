"""`derive` and `waiting_for` on stored data only: one case per row of both state tables of ADR-0011 section 5, the
precedence cases, and one per row of the waiting table (section 6)."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Literal

import pytest

from app.decisions import (
    DealState,
    DecisionInputs,
    FundingState,
    WaitCode,
    derive,
    derive_all,
    waiting_for,
)
from app.domain.models import (
    CommitmentStatus,
    CompileStatus,
    InvoiceAdjustment,
    OperationStatus,
    Outcome,
    Receivable,
    RecurringInvoice,
)
from app.persistence.records import ApprovalStatus
from tests.persistence.factories import commitment as make_commitment
from tests.persistence.factories import verdict as make_verdict

from .builders import (
    CURE,
    DEAL,
    OFFER_ID,
    PLAN,
    Alert,
    Funding,
    Promise,
    accept_approval,
    accept_run,
    approval,
    books,
    deal_inputs,
    declined_fact,
    evaluated_fact,
    expired,
    fact_row,
    leg_run,
    lot,
    offer_with,
    offered_fact,
    quoted,
    replied_fact,
    run,
    sent_fact,
    verdict_with,
)

OK, REFUSED, PENDING, DUP = (OperationStatus.EXECUTED, OperationStatus.REFUSED, OperationStatus.PENDING_APPROVAL,
                             OperationStatus.DUPLICATE)
ACTIVE, PROPOSED = CommitmentStatus.ACTIVE, CommitmentStatus.PROPOSED


# ================================================================ DEAL: one case per row of the table

DEAL_ROWS = [
    ("1 REVOKED", lambda: deal_inputs(status=CommitmentStatus.REVOKED), DealState.REVOKED, True),
    ("2 FULFILLED", lambda: deal_inputs(status=CommitmentStatus.FULFILLED), DealState.FULFILLED, True),
    ("3 MISSED, expired with lapsed obligations", lambda: deal_inputs(commitments=(expired(lapsed=True),)),
     DealState.MISSED, True),
    ("4 MISSED, active with a lapsed promise",
     lambda: deal_inputs(status=ACTIVE, promised=(Promise("CMT-1", "LAPSED"),)), DealState.MISSED, False),
    ("5 AGREED, active", lambda: deal_inputs(status=ACTIVE), DealState.AGREED, False),
    ("5 AGREED, accepted (the transient live status)", lambda: deal_inputs(status=CommitmentStatus.ACCEPTED),
     DealState.AGREED, False),
    ("6 EXPIRED, lapsed before agreement", lambda: deal_inputs(commitments=(expired(lapsed=False),)), DealState.EXPIRED, True),
    ("7 AUTHORIZATION_REQUIRED",
     lambda: deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                         log=(accept_run(1, PENDING, approval_id="APR-1"),)), DealState.AUTHORIZATION_REQUIRED, False),
    ("8 DECLINED",
     lambda: deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.REJECTED, decided_day=6),),
                         log=(accept_run(1, PENDING, approval_id="APR-1"), accept_run(2, REFUSED, approval_id="APR-1"))),
     DealState.DECLINED, True),
    ("9 FAILED, refused at once", lambda: deal_inputs(status=PROPOSED, log=(accept_run(1, REFUSED),)), DealState.FAILED, True),
    ("9 FAILED, approved then refused on the re-run",
     lambda: deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.APPROVED, decided_day=6),),
                         log=(accept_run(1, PENDING, approval_id="APR-1"), accept_run(2, REFUSED, approval_id="APR-1"))),
     DealState.FAILED, True),
    ("9a REPLIED, the buyer answered an offer sent outside FLOW with terms of their own",
     lambda: deal_inputs(facts=(fact_row(DEAL, "V-1:C-A", offered_fact()), fact_row(DEAL, "OFF-reply", replied_fact(), seq=2))),
     DealState.REPLIED, True),
    ("9a NO_DEAL, the buyer declined an offer sent outside FLOW",
     lambda: deal_inputs(facts=(fact_row(DEAL, "V-1:C-A", offered_fact()), fact_row(DEAL, "declined:V-1:C-A", declined_fact(), seq=2))),
     DealState.NO_DEAL, True),
    ("9b AWAITING_BUYER, an offer sent outside FLOW still open", lambda: deal_inputs(facts=(fact_row(DEAL, "V-1:C-A", offered_fact()),)),
     DealState.AWAITING_BUYER, False),
    ("9b NO_DEAL, an offer sent outside FLOW unanswered after its day",
     lambda: deal_inputs(today=8, facts=(fact_row(DEAL, "V-1:C-A", offered_fact()),)), DealState.NO_DEAL, True),
    ("9b AGREED wins over an offer sent outside FLOW",
     lambda: deal_inputs(status=ACTIVE, facts=(fact_row(DEAL, "V-1:C-A", offered_fact()),)), DealState.AGREED, False),
    ("10 NO_DEAL", lambda: deal_inputs(facts=(fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact()),)), DealState.NO_DEAL, True),
    ("11 NEEDS_CLARIFICATION, abstained offer", lambda: deal_inputs(offer=offer_with(CompileStatus.ABSTAINED)),
     DealState.NEEDS_CLARIFICATION, False),
    ("11 NEEDS_CLARIFICATION, conflicting sources", lambda: deal_inputs(offer=offer_with(CompileStatus.CONFLICTING_SOURCES)),
     DealState.NEEDS_CLARIFICATION, False),
    ("11 NEEDS_CLARIFICATION, no verdict outcome", lambda: deal_inputs(verdict=verdict_with(Outcome.NO_VERDICT)),
     DealState.NEEDS_CLARIFICATION, False),
    ("12 RESPONSE_READY", lambda: deal_inputs(), DealState.RESPONSE_READY, False),
    ("12 RESPONSE_READY, accept outcome is not Agreed", lambda: deal_inputs(verdict=verdict_with(Outcome.ACCEPT)),
     DealState.RESPONSE_READY, False),
    ("13 RECEIVED", lambda: deal_inputs(has_verdict=False), DealState.RECEIVED, False),
    ("13 RECEIVED, nothing stored but the decision id", lambda: deal_inputs(has_verdict=False, has_offer=False),
     DealState.RECEIVED, False),
]


@pytest.mark.parametrize(("name", "build", "state", "terminal"), DEAL_ROWS, ids=[r[0] for r in DEAL_ROWS])
def test_every_row_of_the_deal_table(name: str, build, state: DealState, terminal: bool) -> None:
    s = derive(build())
    assert (s.family, s.state, s.terminal) == ("DEAL", state, terminal), name


# ---------------------------------------------------------------- DEAL: the owner declines a request (RejectOffer)


def reject_run(seq: int, status: OperationStatus, *, requested_by: str = "OWNER", offer_id: str = "OFF-1"):
    return run(seq, "REJECT_OFFER", f"decline-{offer_id}-V-1", status, op_id=f"decline-{offer_id}-V-1", offer_id=offer_id,
               reason_codes=[], requested_by=requested_by)


def test_an_owner_rejection_that_ran_declines_the_deal_and_closes_it() -> None:
    s = derive(deal_inputs(log=(reject_run(1, OperationStatus.EXECUTED),)))
    assert (s.state, s.terminal) == (DealState.DECLINED, True)
    assert [o.kind for o in s.ops] == ["REJECT_OFFER"]  # the refusal is one of the decision's operations


def test_a_rejection_the_agent_made_does_not_close_the_deal() -> None:
    assert derive(deal_inputs(log=(reject_run(1, OperationStatus.EXECUTED, requested_by="AGENT"),))).state == DealState.RESPONSE_READY


def test_a_refused_owner_rejection_declines_nothing() -> None:
    assert derive(deal_inputs(log=(reject_run(1, OperationStatus.REFUSED),))).state == DealState.RESPONSE_READY


def test_an_agreement_in_force_wins_over_a_rejection() -> None:
    assert derive(deal_inputs(status=ACTIVE, log=(reject_run(1, OperationStatus.EXECUTED),))).state == DealState.AGREED


def test_an_owner_accept_marks_the_agreement_as_accepted_as_asked() -> None:
    owner = accept_run(1, OperationStatus.EXECUTED)
    owner.payload["requested_by"] = "OWNER"
    assert derive(deal_inputs(status=ACTIVE, log=(owner,))).accepted_as_asked is True
    assert derive(deal_inputs(status=ACTIVE, log=(accept_run(1, OperationStatus.EXECUTED),))).accepted_as_asked is False


# ---------------------------------------------------------------- DEAL precedence


def test_expired_wins_over_a_pending_approval() -> None:
    i = deal_inputs(commitments=(expired(lapsed=False),), approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"),))
    assert derive(i).state == DealState.EXPIRED


def test_revoked_wins_over_everything_below_it() -> None:
    i = deal_inputs(status=CommitmentStatus.REVOKED, promised=(Promise("CMT-1", "LAPSED"),),
                    approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),))
    assert derive(i).state == DealState.REVOKED


def test_a_lapsed_promise_on_an_active_agreement_is_missed_not_agreed_and_stays_open() -> None:
    i = deal_inputs(status=ACTIVE, promised=(Promise("CMT-1", "AWAITED"), Promise("CMT-1", "LAPSED", receivable_id="AR-2")))
    s = derive(i)
    assert (s.state, s.terminal) == (DealState.MISSED, False)


def test_a_lapsed_promise_of_another_commitment_does_not_count() -> None:
    assert derive(deal_inputs(status=ACTIVE, promised=(Promise("CMT-9", "LAPSED"),))).state == DealState.AGREED


def test_agreed_wins_over_a_stale_pending_approval_and_a_refused_run() -> None:
    i = deal_inputs(status=ACTIVE, approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                    log=(accept_run(1, REFUSED),))
    assert derive(i).state == DealState.AGREED


def test_declined_wins_over_failed_when_the_owner_rejected_it() -> None:
    i = deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.REJECTED, decided_day=6),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"), accept_run(2, REFUSED, approval_id="APR-1")))
    assert derive(i).state == DealState.DECLINED


def test_failed_after_an_approval_is_not_declined() -> None:
    i = deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.APPROVED, decided_day=6),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"), accept_run(2, REFUSED, approval_id="APR-1")))
    assert derive(i).state == DealState.FAILED


def test_failed_wins_over_no_deal() -> None:
    i = deal_inputs(status=PROPOSED, log=(accept_run(1, REFUSED),), facts=(fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact()),))
    assert derive(i).state == DealState.FAILED


def test_a_pending_approval_wins_over_failed_and_no_deal() -> None:
    i = deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"),),
                    facts=(fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact()),))
    assert derive(i).state == DealState.AUTHORIZATION_REQUIRED


def test_a_non_owner_attempt_to_decide_is_not_a_result_of_the_operation() -> None:
    attempt = accept_run(2, REFUSED, approval_id="APR-1", key="accept-CMT-1#decide:APR-1:AGENT")
    i = deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"), attempt))
    assert derive(i).state == DealState.AUTHORIZATION_REQUIRED
    only = deal_inputs(status=PROPOSED, log=(attempt,))
    assert derive(only).state == DealState.RESPONSE_READY


def test_a_duplicate_result_does_not_replace_the_real_one() -> None:
    i = deal_inputs(status=PROPOSED, log=(accept_run(1, REFUSED), accept_run(2, DUP)))
    assert derive(i).state == DealState.FAILED


def test_the_last_non_duplicate_result_is_the_accepts_result() -> None:
    i = deal_inputs(status=PROPOSED, log=(accept_run(1, REFUSED), accept_run(2, OK)))
    assert derive(i).state == DealState.RESPONSE_READY  # executed: the commitment (in the store) is what says what it became


def test_no_deal_is_only_for_the_latest_verdict() -> None:
    old = fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact(verdict_id="V-1"))
    i = deal_inputs(verdict=make_verdict("V-2"), facts=(old,))
    assert derive(i).state == DealState.RESPONSE_READY
    i2 = deal_inputs(verdict=make_verdict("V-2"), facts=(old, fact_row(DEAL, "nodeal:V-2:hard_line", sent_fact(verdict_id="V-2"), seq=2)))
    assert derive(i2).state == DealState.NO_DEAL


def test_the_commitment_named_by_the_latest_sent_fact_wins_over_a_later_stored_one() -> None:
    first, later = make_commitment("CMT-1", ACTIVE), make_commitment("CMT-2", CommitmentStatus.REVOKED)
    sent = fact_row(DEAL, "accept-CMT-1", sent_fact(outcome="DEAL", commitment_id="CMT-1"))
    s = derive(deal_inputs(commitments=(first, later), facts=(sent,)))
    assert (s.commitment, s.state) == (first, DealState.AGREED)
    assert derive(deal_inputs(commitments=(first, later))).commitment == later  # without a fact: the last stored


def test_records_of_other_decisions_are_ignored() -> None:
    other = make_commitment("CMT-9", CommitmentStatus.REVOKED).model_copy(update={"offer_id": "OFF-2"})
    i = deal_inputs(commitments=(other,), log=(run(1, "ACCEPT_OFFER", "accept-CMT-9", REFUSED, offer_id="OFF-2"),),
                    facts=(fact_row("deal:OFF-2", "nodeal:V-9:x", sent_fact()),))
    assert derive(i).state == DealState.RESPONSE_READY


def test_a_fact_that_does_not_parse_is_skipped_never_a_crash() -> None:
    bad = replace(fact_row(DEAL, "V-1", evaluated_fact()), body_json='{"offer_id": 7}')
    s = derive(deal_inputs(facts=(bad,)))
    assert (s.state, s.evaluated) == (DealState.RESPONSE_READY, None)


def test_the_evaluated_fact_gives_the_verdict_its_day() -> None:
    s = derive(deal_inputs(facts=(fact_row(DEAL, "V-1", evaluated_fact(), day=7),)))
    assert s.evaluated is not None and s.updated_day == 7


def test_the_funding_legs_of_a_negotiation_belong_to_the_deal_with_or_without_the_sent_fact() -> None:
    legs = (run(3, "DRAW_FACILITY", f"fund-{OFFER_ID}-hard_line-0", OK, day=5, facility_id="FAC-LINE", amount_fen=9),)
    s = derive(deal_inputs(log=legs, state=books(lots=[lot(f"fund-{OFFER_ID}-hard_line-0", settled=False)])))
    assert [o.op_id for o in s.ops] == [f"fund-{OFFER_ID}-hard_line-0"] and len(s.lots) == 1
    # recorded in the SENT fact under another id: the fact names it
    odd = run(4, "DRAW_FACILITY", "legacy-key", OK, op_id="LEG-1", day=5, facility_id="FAC-LINE", amount_fen=9)
    fact = fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact(funding=("LEG-1",)))
    assert [o.op_id for o in derive(deal_inputs(log=(odd,), facts=(fact,))).ops] == ["LEG-1"]


# ================================================================ FUNDING: one case per row of the table


def funding(**kw) -> Funding:
    f = Funding()
    for k, v in kw.items():
        setattr(f, k, v)
    return f


def q(**kw):
    return [fact_row(CURE, CURE, quoted(**kw))]


FUNDING_ROWS = [
    ("1 AUTHORIZATION_REQUIRED, with an executed leg beside it",
     lambda: funding(runs=[leg_run(1, 0, OK), leg_run(2, 1, PENDING, approval_id="APR-2")],
                     approvals=[approval(
                         "APR-2", "DRAW_FACILITY", f"{CURE}:1", ApprovalStatus.PENDING)]),
     FundingState.AUTHORIZATION_REQUIRED, False),
    ("2 DECLINED", lambda: funding(
        runs=[leg_run(1, 0, PENDING, approval_id="APR-1"), leg_run(2, 0, REFUSED, approval_id="APR-1")],
        approvals=[approval(
            "APR-1", "DRAW_FACILITY", f"{CURE}:0", ApprovalStatus.REJECTED, decided_day=36)]),
     FundingState.DECLINED, True),
    ("3 FAILED, a leg refused", lambda: funding(runs=[leg_run(1, 0, REFUSED)], facts=q(legs=1)), FundingState.FAILED, True),
    ("3 FAILED, approved then refused on the re-run", lambda: funding(
        runs=[leg_run(1, 0, PENDING, approval_id="APR-1"), leg_run(2, 0, REFUSED, approval_id="APR-1")],
        approvals=[approval(
            "APR-1", "DRAW_FACILITY", f"{CURE}:0", ApprovalStatus.APPROVED, decided_day=36)]),
     FundingState.FAILED, True),
    ("3 FAILED, a quote and no operation logged", lambda: funding(facts=q()), FundingState.FAILED, True),
    ("4 PARTIALLY_EXECUTED, a leg refused", lambda: funding(runs=[leg_run(1, 0, OK), leg_run(2, 1, REFUSED)],
                                                             facts=q()), FundingState.PARTIALLY_EXECUTED, False),
    ("4 PARTIALLY_EXECUTED, fewer legs logged than quoted", lambda: funding(runs=[leg_run(1, 0, OK)], facts=q(legs=2)),
     FundingState.PARTIALLY_EXECUTED, False),
    ("5 SETTLEMENT_PENDING", lambda: funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1),
                                              lots=[lot(f"{CURE}:0", settled=False)]),
     FundingState.SETTLEMENT_PENDING, False),
    ("6 SETTLED", lambda: funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0", settled=True)]),
     FundingState.SETTLED, True),
    ("7 EXECUTED, no lot (a repayment)", lambda: funding(runs=[leg_run(1, 0, OK, kind="REPAY_FACILITY")], facts=q(legs=1)),
     FundingState.EXECUTED, True),
]


@pytest.mark.parametrize(("name", "build", "state", "terminal"), FUNDING_ROWS, ids=[r[0] for r in FUNDING_ROWS])
def test_every_row_of_the_funding_table(name: str, build, state: FundingState, terminal: bool) -> None:
    s = derive(build().inputs())
    assert (s.family, s.state, s.terminal) == ("FUNDING", state, terminal), name


def test_a_pending_approval_wins_over_everything() -> None:
    f = funding(runs=[leg_run(1, 0, REFUSED), leg_run(2, 1, PENDING, approval_id="APR-2")],
                approvals=[approval("APR-1", "DRAW_FACILITY", f"{CURE}:0", ApprovalStatus.REJECTED),
                           approval("APR-2", "DRAW_FACILITY", f"{CURE}:1", ApprovalStatus.PENDING)])
    assert derive(f.inputs()).state == FundingState.AUTHORIZATION_REQUIRED


def test_one_executed_leg_makes_a_rejected_second_leg_partial_not_declined() -> None:
    f = funding(runs=[leg_run(1, 0, OK), leg_run(2, 1, PENDING, approval_id="APR-2"),
                      leg_run(3, 1, REFUSED, approval_id="APR-2")],
                approvals=[approval("APR-2", "DRAW_FACILITY", f"{CURE}:1", ApprovalStatus.REJECTED)], facts=q())
    assert derive(f.inputs()).state == FundingState.PARTIALLY_EXECUTED


def test_a_lot_made_by_a_leg_is_found_by_its_op_id_or_the_hash_suffix() -> None:
    f = funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0#1", settled=False), lot("OTHER", settled=True)])
    s = derive(f.inputs())
    assert [x.id for x in s.lots] == [f"{CURE}:0#1"] and s.state == FundingState.SETTLEMENT_PENDING


def test_a_leg_with_a_longer_id_does_not_claim_the_lot_of_a_shorter_one() -> None:
    f = funding(runs=[leg_run(1, 1, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:10", settled=False)])
    assert derive(f.inputs()).lots == ()


def test_the_cure_and_the_plan_of_one_alert_are_two_decisions() -> None:
    cure = leg_run(1, 0, OK)
    plan = leg_run(2, 0, OK, base=PLAN)
    assert [o.op_id for o in derive(Funding(runs=[cure, plan]).inputs()).ops] == [f"{CURE}:0"]
    assert [o.op_id for o in derive(Funding(decision_id=PLAN, runs=[cure, plan]).inputs()).ops] == [f"{PLAN}:0"]


def test_a_later_state_version_of_the_same_alert_is_another_decision() -> None:
    other = leg_run(1, 0, OK, base="alert:ALERT-RESERVE-34:v4")
    assert derive(Funding(runs=[other]).inputs()).ops == ()


def test_a_standalone_approval_is_its_own_funding_record() -> None:
    a = approval("APR-9", "APPLY_FOR_FACILITY", "capex-apply-1", ApprovalStatus.PENDING, op_id="capex-apply-1")
    s = derive(DecisionInputs(decision_id="approval:APR-9", today=3, approvals=(a,)))
    assert (s.family, s.state) == ("FUNDING", FundingState.AUTHORIZATION_REQUIRED)


# ---------------------------------------------------------------- the residual (F17)


def test_the_newest_reserve_record_carries_the_residual_and_stays_open() -> None:
    f = funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0", settled=True)],
                alerts=[Alert(amount_fen=777, day=41, committed_cure=False)], newest=True)
    s = derive(f.inputs())
    assert s.state == FundingState.SETTLED and (s.terminal, s.residual is not None) == (False, True)
    assert s.residual is not None and (s.residual.shortfall_fen, s.residual.starts_day, s.residual.committed_cure) == (777, 41, False)
    assert waiting_for(s, f.inputs()).code == WaitCode.OWNER_DECISION


@pytest.mark.parametrize(
    ("why", "change"),
    [
        ("not the newest", {"newest": False}),
        ("no reserve alert open today", {"alerts": []}),
        ("another kind of alert", {"alerts": [Alert(kind="RESERVE_HEADROOM_LOW")]}),
        ("the quote was not for a reserve breach", {"facts": q(legs=1, alert_kind="RECEIVABLE_PAST_DUE")}),
        ("no quote recorded", {"facts": []}),
    ],
)
def test_no_residual_unless_all_conditions_hold(why: str, change: dict) -> None:
    f = funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0", settled=True)], alerts=[Alert()], newest=True)
    for k, v in change.items():
        setattr(f, k, v)
    s = derive(f.inputs())
    assert s.residual is None and s.terminal is True, why


def test_no_residual_on_a_declined_or_failed_record() -> None:
    f = funding(runs=[leg_run(1, 0, REFUSED)], facts=q(legs=1), alerts=[Alert()], newest=True)
    assert derive(f.inputs()).residual is None


def test_derive_all_gives_the_residual_to_the_newest_reserve_record_only() -> None:
    older = Funding(decision_id="alert:ALERT-RESERVE-20:v2", alerts=[Alert()])
    older.runs = [run(1, "DRAW_FACILITY", "alert:ALERT-RESERVE-20:v2:0", OK, day=20, facility_id="F", amount_fen=1)]
    older.facts = [fact_row(older.decision_id, older.decision_id, quoted(legs=1), day=20)]
    newer = Funding(alerts=[Alert()])
    newer.runs = [leg_run(2, 0, OK)]
    newer.facts = [fact_row(CURE, CURE, quoted(legs=1), day=34)]
    both = [replace(older.inputs(), alerts=(Alert(),)), replace(newer.inputs(), alerts=(Alert(),))]
    first, second = derive_all(both)
    assert first.residual is None and second.residual is not None
    assert derive_all(list(reversed(both)))[1].residual is None


# ================================================================ what FLOW is waiting for


def waits(i: DecisionInputs):
    w = waiting_for(derive(i), i)
    return w.code, w.party.value, w.day


def test_waiting_owner_response_for_received_and_response_ready() -> None:
    assert waits(deal_inputs(has_verdict=False)) == (WaitCode.OWNER_RESPONSE, "owner", None)
    assert waits(deal_inputs()) == (WaitCode.OWNER_RESPONSE, "owner", None)


def test_waiting_buyer_clarification() -> None:
    assert waits(deal_inputs(offer=offer_with(CompileStatus.ABSTAINED))) == (WaitCode.BUYER_CLARIFICATION, "buyer", None)


def test_waiting_owner_approval_dated_by_the_expiry_for_a_deal_and_by_the_alert_day_for_funding() -> None:
    i = deal_inputs(status=PROPOSED, approvals=(accept_approval("APR-1", ApprovalStatus.PENDING),),
                    log=(accept_run(1, PENDING, approval_id="APR-1"),))
    assert waits(i) == (WaitCode.OWNER_APPROVAL, "owner", 10)
    f = funding(runs=[leg_run(1, 0, PENDING, approval_id="APR-1")], facts=q(alert_day=35),
                approvals=[approval("APR-1", "DRAW_FACILITY", f"{CURE}:0", ApprovalStatus.PENDING)])
    assert waits(f.inputs()) == (WaitCode.OWNER_APPROVAL, "owner", 35)
    f.facts = []
    assert waits(f.inputs()) == (WaitCode.OWNER_APPROVAL, "owner", None)


def test_waiting_bank_receipt_for_an_awaited_promise_on_its_earliest_day() -> None:
    i = deal_inputs(status=ACTIVE, promised=(Promise("CMT-1", "AWAITED", 12), Promise("CMT-1", "AWAITED", 9),
                                             Promise("CMT-1", "RECEIVED", 3)))
    assert waits(i) == (WaitCode.BANK_RECEIPT, "buyer", 9)


def test_waiting_invoice_issue_for_an_adjustment_still_in_the_books() -> None:
    adj = InvoiceAdjustment(id="CMT-1:OB-2", commitment_id="CMT-1", obligation_id="OB-2", counterparty_id="BUYER-1", days_delta=30)
    recurring = [RecurringInvoice(counterparty_id="BUYER-1", face_fen=1, every_days=30, next_issue_day=48, terms_days=30),
                 RecurringInvoice(counterparty_id="BUYER-2", face_fen=1, every_days=30, next_issue_day=3, terms_days=30)]
    i = deal_inputs(status=ACTIVE, state=books(invoice_adjustments=[adj], recurring_invoices=recurring))
    assert waits(i) == (WaitCode.INVOICE_ISSUE, "books", 48)


def test_waiting_bank_receipt_for_invoices_carrying_the_agreement_that_are_still_outstanding() -> None:
    def inv(rid: str, status: Literal["OPEN", "SETTLED"], applied: list[str], terms: int, settled: int = 0) -> Receivable:
        return Receivable(id=rid, counterparty_id="BUYER-1", face_fen=100, issue_day=10, terms_days=terms, status=status,
                          applied=applied, settled_fen=settled)

    rs = [inv("AR-A", "OPEN", ["CMT-1:OB-2"], 60), inv("AR-B", "OPEN", ["CMT-1:OB-2"], 40), inv("AR-C", "SETTLED", ["CMT-1:OB-2"], 10, 100),
          inv("AR-D", "OPEN", ["CMT-2:OB-2"], 5), inv("AR-E", "OPEN", [], 5)]
    assert waits(deal_inputs(status=ACTIVE, state=books(receivables=rs))) == (WaitCode.BANK_RECEIPT, "buyer", 50)
    assert waits(deal_inputs(status=ACTIVE, state=books(receivables=rs[2:]))) == (WaitCode.NOTHING, "none", None)


def test_waiting_bank_receipt_for_a_missed_promise_on_the_invoices_own_due_day() -> None:
    inv = Receivable(id="AR-1", counterparty_id="BUYER-1", face_fen=100, issue_day=0, terms_days=45)
    live = deal_inputs(status=ACTIVE, promised=(Promise("CMT-1", "LAPSED"),), state=books(receivables=[inv]))
    assert waits(live) == (WaitCode.BANK_RECEIPT, "buyer", 45)
    ended = deal_inputs(commitments=(expired(lapsed=True),), state=books(receivables=[inv]))
    assert waits(ended) == (WaitCode.BANK_RECEIPT, "buyer", 45)  # the lapsed obligation names AR-1


def test_waiting_funding_settlement_on_the_latest_unsettled_arrival_naming_the_lender() -> None:
    f = funding(runs=[leg_run(1, 0, OK), leg_run(2, 1, OK)], facts=q(),
                lots=[lot(f"{CURE}:0", settled=False, arrival=38), lot(f"{CURE}:1", settled=False, arrival=44, facility="FAC-B"),
                      ])
    s = derive(f.inputs())
    w = waiting_for(s, f.inputs())
    assert (s.state, w.code, w.party.value, w.day, w.ref) == (FundingState.SETTLEMENT_PENDING, WaitCode.FUNDING_SETTLEMENT, "lender", 44, "FAC-B")


def test_waiting_funding_settlement_for_a_deal_whose_funding_is_in_transit() -> None:
    name = f"fund-{OFFER_ID}-hard_line-0"
    i = deal_inputs(log=(run(3, "DRAW_FACILITY", name, OK, facility_id="FAC-LINE", amount_fen=9),),
                    facts=(fact_row(DEAL, "nodeal:V-1:hard_line", sent_fact(funding=(name,))),),
                    state=books(lots=[lot(name, settled=False, arrival=41)]))
    assert derive(i).state == DealState.NO_DEAL
    assert waits(i) == (WaitCode.FUNDING_SETTLEMENT, "lender", 41)
    settled = replace(i, state=books(lots=[lot(name, settled=True)]))
    assert waits(settled) == (WaitCode.NOTHING, "none", None)


def test_waiting_owner_decision_for_a_partly_executed_record_dated_by_the_reserve_alert() -> None:
    f = funding(runs=[leg_run(1, 0, OK), leg_run(2, 1, REFUSED)], facts=q(), alerts=[Alert(day=52)])
    s = derive(f.inputs())
    assert s.state == FundingState.PARTIALLY_EXECUTED
    assert waits(f.inputs()) == (WaitCode.OWNER_DECISION, "owner", 52)
    f.alerts = []
    assert waits(f.inputs()) == (WaitCode.OWNER_DECISION, "owner", None)


@pytest.mark.parametrize(
    "status", [CommitmentStatus.FULFILLED, CommitmentStatus.REVOKED, CommitmentStatus.EXPIRED, CommitmentStatus.ACTIVE]
)
def test_waiting_nothing_for_the_rest(status: CommitmentStatus) -> None:
    assert waits(deal_inputs(status=status)) == (WaitCode.NOTHING, "none", None)


def test_waiting_nothing_for_declined_failed_executed_and_settled() -> None:
    declined = funding(runs=[leg_run(1, 0, PENDING, approval_id="A"), leg_run(2, 0, REFUSED, approval_id="A")],
                       approvals=[approval("A", "DRAW_FACILITY", f"{CURE}:0", ApprovalStatus.REJECTED)])
    failed = funding(runs=[leg_run(1, 0, REFUSED)], facts=q(legs=1))
    executed = funding(runs=[leg_run(1, 0, OK, kind="REPAY_FACILITY")], facts=q(legs=1))
    settled = funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0", settled=True)])
    for f in (declined, failed, executed, settled):
        assert waits(f.inputs()) == (WaitCode.NOTHING, "none", None)


def test_the_state_tables_cover_every_member_of_both_enums() -> None:
    """Every state in both machines is reachable from stored data only (the table-driven rows above)."""
    reached_deal = {r[2] for r in DEAL_ROWS}
    reached_funding = {r[2] for r in FUNDING_ROWS}
    # LAPSED is a fact about the books, not about the records: the API read sets it (`Context.lapse`, tests/api/test_lapsed_offers.py)
    assert reached_deal == set(DealState) - {DealState.LAPSED}
    assert reached_funding == set(FundingState)


def test_derive_reads_only_its_inputs() -> None:
    i = deal_inputs(status=ACTIVE, promised=(Promise("CMT-1", "AWAITED"),))
    assert derive(i) == derive(i) and waiting_for(derive(i), i) == waiting_for(derive(i), i)
    # the inputs are frozen: nothing can be written back into them
    with pytest.raises(AttributeError):
        i.today = 9  # type: ignore[misc]


# ---------------------------------------------------------------- the residual belongs to its own breach (review fix)


def _settled(alerts: list[Alert], newest: bool = True) -> Funding:
    return funding(runs=[leg_run(1, 0, OK)], facts=q(legs=1), lots=[lot(f"{CURE}:0", settled=True)], alerts=alerts, newest=newest)


def test_the_same_breach_still_open_keeps_the_residual_even_when_a_committed_cure_exists() -> None:
    f = _settled([Alert(id="ALERT-RESERVE-34", committed_cure=True)])
    s = derive(f.inputs())
    assert s.residual is not None and s.residual.committed_cure is True and s.terminal is False


def test_a_later_unrelated_breach_with_a_committed_cure_is_not_this_records_residual() -> None:
    f = _settled([Alert(id="ALERT-RESERVE-80", committed_cure=True)])
    s = derive(f.inputs())
    assert s.residual is None and s.terminal is True and s.state == FundingState.SETTLED
    assert waiting_for(s, f.inputs()).code == WaitCode.NOTHING


def test_a_later_breach_nothing_fixes_is_still_the_owners_to_decide() -> None:
    f = _settled([Alert(id="ALERT-RESERVE-80", committed_cure=False)])
    s = derive(f.inputs())
    assert s.residual is not None and s.residual.alert_id == "ALERT-RESERVE-80" and s.residual.committed_cure is False


def test_derive_all_gives_the_residual_to_the_newest_record_the_open_alert_belongs_to() -> None:
    older = Funding(decision_id="alert:ALERT-RESERVE-20:v2")
    older.runs = [run(1, "DRAW_FACILITY", "alert:ALERT-RESERVE-20:v2:0", OK, day=20, facility_id="F", amount_fen=1)]
    older.facts = [fact_row(older.decision_id, older.decision_id, quoted(legs=1).model_copy(update={"alert_id": "ALERT-RESERVE-20"}), day=20)]
    newer = _settled([])
    newer.facts = [fact_row(CURE, CURE, quoted(legs=1), day=34)]
    open_alert = Alert(id="ALERT-RESERVE-20", committed_cure=True)  # the old breach is the one still open, and a plan exists
    both = [replace(older.inputs(), alerts=(open_alert,)), replace(newer.inputs(), alerts=(open_alert,))]
    first, second = derive_all(both)
    assert first.residual is not None and second.residual is None and second.terminal is True


# ---------------------------------------------------------------- a quote that projected nothing says nothing about the reserve


def test_a_quote_stored_before_the_projected_field_reads_as_projected() -> None:
    from app.decisions import QuotedFact, body_json

    body = json.loads(body_json(quoted()))
    del body["projected"]
    assert QuotedFact.model_validate_json(json.dumps(body)).projected is True


def test_an_offer_sent_outside_reads_as_closed_when_the_deal_ended_another_way() -> None:
    """Verifier finding 4: a refused agreement (FAILED) or an owner's decline is not "still waiting for the buyer"."""
    from app.decisions.state import buyer_answer

    offered = fact_row(DEAL, "V-1:C-A", offered_fact())
    assert buyer_answer(derive(deal_inputs(status=PROPOSED, log=(accept_run(1, REFUSED),), facts=(offered,)))) == "closed"
    assert buyer_answer(derive(deal_inputs(facts=(offered,)))) is None
    assert buyer_answer(derive(deal_inputs(today=8, facts=(offered,)))) == "no_answer"
