"""Small typed builders for the decision-record tests: stored records as the stores hold them, no engine and no HTTP."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.decisions import (
    DecisionInputs,
    EvaluatedFact,
    GapPlan,
    IfDecline,
    QuotedFact,
    QuotedLeg,
    SentFact,
    record_for,
)
from app.domain.fixtures import load_scenario
from app.domain.models import (
    CommitmentStatus,
    CompiledOffer,
    CompileStatus,
    FinancialState,
    FundingLot,
    OperationResult,
    OperationStatus,
    Outcome,
    Tier,
    Verdict,
)
from app.persistence.records import ApprovalRecord, ApprovalStatus, DecisionFactRecord
from tests.persistence.factories import commitment as make_commitment
from tests.persistence.factories import offer as make_offer
from tests.persistence.factories import verdict as make_verdict

OFFER_ID = "OFF-1"
DEAL = f"deal:{OFFER_ID}"
CURE = "alert:ALERT-RESERVE-34:v3"
PLAN = "alert:ALERT-RESERVE-34:v3:plan"


@dataclass(frozen=True)
class Run:
    """One operations-log entry (satisfies `LoggedRun`)."""

    seq: int
    kind: str
    idempotency_key: str
    payload: dict[str, Any]
    result: OperationResult
    day: int | None = None


def result(op_id: str, kind: str, status: OperationStatus, *, approval_id: str | None = None, day: int = 0) -> OperationResult:
    return OperationResult(op_id=op_id, kind=kind, status=status, tier=Tier.TIER_1, approval_id=approval_id, effective_day=day)


def run(seq: int, kind: str, key: str, status: OperationStatus, *, op_id: str | None = None, approval_id: str | None = None,
        day: int = 0, **payload: Any) -> Run:
    op = op_id or key.split("#", 1)[0]
    body = {"kind": kind, "op_id": op, "idempotency_key": key.split("#", 1)[0], **payload}
    return Run(seq, kind, key, body, result(op, kind, status, approval_id=approval_id, day=day), day)


def approval(aid: str, kind: str, key: str, status: ApprovalStatus, *, op_id: str | None = None, decided_day: int | None = None,
             **payload: Any) -> ApprovalRecord:
    op = op_id or key
    body = {"kind": kind, "op_id": op, "idempotency_key": key, **payload}
    return ApprovalRecord(id=aid, op_id=op, kind=kind, op_json=json.dumps(body), reason="test", status=status,
                          decided_by=None if status == ApprovalStatus.PENDING else "OWNER", decided_day=decided_day)


def accept_payload(c_nonce: str = "nonce-CMT-1", offer_id: str = OFFER_ID) -> dict[str, Any]:
    return {"offer_id": offer_id, "offer_version": 1, "terms_hash": "h", "nonce": c_nonce}


def accept_run(seq: int, status: OperationStatus, *, cid: str = "CMT-1", approval_id: str | None = None, day: int = 0,
               key: str | None = None) -> Run:
    return run(seq, "ACCEPT_OFFER", key or f"accept-{cid}", status, op_id=f"accept-{cid}", approval_id=approval_id, day=day,
               **accept_payload("nonce-" + cid))


def accept_approval(aid: str, status: ApprovalStatus, *, cid: str = "CMT-1", decided_day: int | None = None) -> ApprovalRecord:
    return approval(aid, "ACCEPT_OFFER", f"accept-{cid}", status, op_id=f"accept-{cid}", decided_day=decided_day,
                    **accept_payload("nonce-" + cid))


def lot(op_id: str, *, settled: bool, arrival: int = 40, facility: str = "FAC-LINE") -> FundingLot:
    return FundingLot(id=op_id, facility_id=facility, principal_fen=1_000_000, remaining_fen=1_000_000, request_day=34,
                      arrival_day=arrival, settled=settled)


def books(**changes: Any) -> FinancialState:
    state, _ = load_scenario()
    return state.model_copy(update=changes)


def deal_inputs(*, status: CommitmentStatus | None = None, offer: CompiledOffer | None = None, verdict: Verdict | None = None,
                has_verdict: bool = True, has_offer: bool = True, **more: Any) -> DecisionInputs:
    """A DEAL decision's inputs; `status` adds a commitment CMT-1 in that status."""
    commitments = (make_commitment("CMT-1", status),) if status is not None else ()
    return DecisionInputs(
        decision_id=DEAL, today=more.pop("today", 5),
        offers=((offer or make_offer(),) if has_offer else ()),
        verdicts=((verdict or make_verdict(),) if has_verdict else ()),
        commitments=more.pop("commitments", commitments), **more,
    )


def offer_with(status: CompileStatus) -> CompiledOffer:
    return make_offer().model_copy(update={"status": status})


def verdict_with(outcome: Outcome, vid: str = "V-1") -> Verdict:
    return make_verdict(vid).model_copy(update={"outcome": outcome})


def expired(*, lapsed: bool) -> Any:
    c = make_commitment("CMT-1", CommitmentStatus.EXPIRED)
    return c.model_copy(update={"lapsed_obligations": ["OB-1"]}) if lapsed else c


def sent_fact(*, outcome: str = "NO_DEAL", verdict_id: str = "V-1", commitment_id: str | None = None,
              funding: tuple[str, ...] = ()) -> SentFact:
    return SentFact(
        offer_id=OFFER_ID, verdict_id=verdict_id, state_version_shown=1, chosen_counter_id=None, counter_ids_sent=["C-A"],
        buyer_profile="hard_line", outcome="DEAL" if outcome == "DEAL" else "NO_DEAL",
        accepted_counter_id="C-A" if outcome == "DEAL" else None, transcript_hash="t" * 64, commitment_id=commitment_id,
        accept_op_id=f"accept-{commitment_id}" if commitment_id else None, funding_op_ids=list(funding),
        funding_blocked=None, counter_economics=None, gap_plan=GapPlan(need_fen=0, total_cost_fen=None, legs=[]),
    )


def evaluated_fact(verdict_id: str = "V-1") -> EvaluatedFact:
    return EvaluatedFact(offer_id=OFFER_ID, offer_version=1, verdict_id=verdict_id, outcome=Outcome.COUNTER,
                         counter_ids=["C-A"], recommended_counter_id="C-A", mandate_version=1)


def fact_row(decision_id: str, key: str, fact: Any, *, seq: int = 1, day: int = 3) -> DecisionFactRecord:
    from dataclasses import replace

    return replace(record_for(decision_id, key, fact, state_version=1, day=day), seq=seq, recorded_at="2026-10-10T00:00:00+00:00")


def quoted(*, legs: int = 2, alert_kind: str = "RESERVE_BREACH_AHEAD", restores: bool = False, alert_day: int | None = 35) -> QuotedFact:
    return QuotedFact(
        alert_id="ALERT-RESERVE-34", alert_kind=alert_kind, alert_day=alert_day, state_version_shown=3, source="cure",
        legs=[QuotedLeg(op_id=f"{CURE}:{n}", kind="DRAW_FACILITY", facility_id="FAC-LINE", receivable_id=None,
                        amount_fen=1_000_000, cost_fen=1_200, annual_rate=None, cost_days=30, cost_end_day=70,
                        lands_day=35, above_ceiling=False) for n in range(legs)],
        total_cost_fen=2_400, cost_note=None, needs_owner=False, max_apr_bp=1500, restores_reserve=restores,
        after_first_short_day=None, horizon_days=90,
        if_decline=IfDecline(kind="below_reserve", day=35, zero_day=None, shortfall_fen=500_000, max_shortfall_fen=500_000,
                             worst_day=35),
        residual_shortfall_fen=None,
    )


@dataclass(frozen=True)
class Alert:
    id: str = "ALERT-RESERVE-34"
    kind: str = "RESERVE_BREACH_AHEAD"
    day: int | None = 35
    amount_fen: int | None = 500_000
    committed_cure: bool | None = False


@dataclass(frozen=True)
class Promise:
    commitment_id: str
    status: str
    promised_day: int | None = 10
    receivable_id: str = "AR-1"


@dataclass
class Funding:
    """Mutable bag for assembling a FUNDING decision's inputs."""

    decision_id: str = CURE
    runs: list[Run] = field(default_factory=list)
    approvals: list[ApprovalRecord] = field(default_factory=list)
    facts: list[DecisionFactRecord] = field(default_factory=list)
    lots: list[FundingLot] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    newest: bool = False

    def inputs(self) -> DecisionInputs:
        return DecisionInputs(
            decision_id=self.decision_id, today=40, approvals=tuple(self.approvals), log=tuple(self.runs),
            facts=tuple(self.facts), state=books(lots=self.lots), alerts=tuple(self.alerts), newest_reserve=self.newest,
        )


def leg_run(seq: int, n: int, status: OperationStatus, *, base: str = CURE, approval_id: str | None = None,
            kind: str = "DRAW_FACILITY") -> Run:
    return run(seq, kind, f"{base}:{n}", status, approval_id=approval_id, day=34 + seq, facility_id="FAC-LINE", amount_fen=1_000_000)
