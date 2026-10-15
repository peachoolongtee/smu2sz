"""The decision's state and what it is waiting for, derived from stored reality only (ADR-0011 sections 5 and 6).

`derive(inputs) -> DecisionState` and `waiting_for(state, inputs) -> Waiting` are pure: they read the `DecisionInputs`
dataclass and nothing else (no store, no clock, no I/O, no recomputation of a price or a projection). The first matching rule
of each table wins. A fact that is missing is simply absent: the state still derives from the commitment, the approvals, the
log and the lots, and the quote or sent counter reads "not recorded" where the server words it.

Display sentences are not written here (INVARIANT 13: the server words them per request and language, in
`app.api.presentation`). This module returns codes, ids and numbers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol

from app.decisions.facts import (
    BuyerAcceptedFact,
    EvaluatedFact,
    OfferedFact,
    QuotedFact,
    RepliedFact,
    SentFact,
    parse_fact,
)
from app.decisions.identity import decision_id_for, family_of, offer_id_of
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CompileStatus,
    FinancialState,
    FundingLot,
    OperationResult,
    OperationStatus,
    Outcome,
    Receivable,
    Verdict,
)
from app.persistence.records import ApprovalRecord, ApprovalStatus, DecisionFactRecord

RESERVE_ALERT = "RESERVE_BREACH_AHEAD"
_DECIDE_ATTEMPT = "#decide:"  # a non-owner attempt to decide an approval is logged under this suffix


class DealState(StrEnum):
    RECEIVED = "RECEIVED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    RESPONSE_READY = "RESPONSE_READY"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"
    NO_DEAL = "NO_DEAL"
    AGREED = "AGREED"
    EXPIRED = "EXPIRED"
    MISSED = "MISSED"
    FULFILLED = "FULFILLED"
    REVOKED = "REVOKED"
    # The owner copied a verified counter and sent it outside FLOW (an OFFERED fact); nothing is agreed until they record the buyer's yes.
    AWAITING_BUYER = "AWAITING_BUYER"
    # The buyer answered the offered counter with terms of their own (a REPLIED fact): the reply is a request of its own, and this one is closed.
    REPLIED = "REPLIED"
    # An offer whose reply was ready but which can no longer be drawn on today's books (the invoice it was about has since changed): nothing to
    # do and nothing to wait for. `derive` never gives it: it is a fact about the books, set by the API read (`Context.states`).
    LAPSED = "LAPSED"


class FundingState(StrEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    SETTLED = "SETTLED"
    EXECUTED = "EXECUTED"


class WaitCode(StrEnum):
    OWNER_RESPONSE = "OWNER_RESPONSE"
    BUYER_CLARIFICATION = "BUYER_CLARIFICATION"
    BUYER_ANSWER = "BUYER_ANSWER"  # an offer the owner sent outside FLOW, open until its day
    OWNER_APPROVAL = "OWNER_APPROVAL"
    BANK_RECEIPT = "BANK_RECEIPT"
    INVOICE_ISSUE = "INVOICE_ISSUE"
    FUNDING_SETTLEMENT = "FUNDING_SETTLEMENT"
    OWNER_DECISION = "OWNER_DECISION"
    NOTHING = "NOTHING"


class Party(StrEnum):
    OWNER = "owner"
    BUYER = "buyer"
    BOOKS = "books"
    LENDER = "lender"
    NONE = "none"


# ---------------------------------------------------------------- what the routes hand in


class LoggedRun(Protocol):
    """One operations-log entry as `app.operations.log.LoggedEntry` provides it (it satisfies this protocol as it is)."""

    @property
    def seq(self) -> int: ...
    @property
    def kind(self) -> str: ...
    @property
    def idempotency_key(self) -> str: ...
    @property
    def payload(self) -> Mapping[str, Any]: ...
    @property
    def result(self) -> OperationResult: ...
    @property
    def day(self) -> int | None: ...


class PromiseLike(Protocol):
    """An early payment a commitment promised (`app.alerts.models.PromisedReceipt` satisfies it)."""

    @property
    def commitment_id(self) -> str: ...
    @property
    def receivable_id(self) -> str: ...
    @property
    def promised_day(self) -> int | None: ...
    @property
    def status(self) -> str: ...  # AWAITED | RECEIVED | LAPSED | SETTLED_OTHERWISE


class AlertLike(Protocol):
    """An open alert as read today (`app.alerts.models.Alert` satisfies it). Only the reserve alert is used."""

    @property
    def id(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def day(self) -> int | None: ...
    @property
    def amount_fen(self) -> int | None: ...
    @property
    def committed_cure(self) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class DecisionInputs:
    """Everything `derive` and `waiting_for` read: the stored records, passed in whole. Nothing is looked up.

    `offers`, `verdicts`, `commitments`, `approvals`, `log` and `facts` may hold records of other decisions: membership is
    decided here by `decision_id_for`, so the route reads each store once and passes the same inputs to every decision.
    `verdicts` and `log` are in stored order. `state` is the books today (lots, invoices, adjustments); `promised` is
    `reconcile().promised`; `alerts` are today's alerts; `newest_reserve` is set by `derive_all` for the one reserve record
    that may carry the residual."""

    decision_id: str
    today: int
    offers: tuple[CompiledOffer, ...] = ()
    verdicts: tuple[Verdict, ...] = ()
    commitments: tuple[Commitment, ...] = ()
    approvals: tuple[ApprovalRecord, ...] = ()
    log: tuple[LoggedRun, ...] = ()
    facts: tuple[DecisionFactRecord, ...] = ()
    state: FinancialState | None = None
    promised: tuple[PromiseLike, ...] = ()
    alerts: tuple[AlertLike, ...] = ()
    newest_reserve: bool = False
    # The records above grouped once by decision (`RecordIndex`), shared by every decision of a request. Never part of the identity of
    # the inputs; `derive` builds it from the records when it is not given, so a caller that derives one decision need not.
    index: RecordIndex | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class RecordIndex:
    """The request's shared records grouped once, so that deriving D decisions reads the log, the approvals, the facts, the verdicts, the
    commitments, the promises and the lots in time linear in their size and not D times over (every decision otherwise re-scanned them
    all). Built by `RecordIndex.of`; it answers exactly what the scans it replaces answered, in the same order.

    `runs` and `runs_by_op_id` hold (log position, entry) pairs in log order; `approvals` groups by the decision the approval's queued
    operation belongs to (an approval whose payload cannot be read belongs to `approval:{id}`); `approval_candidates` is the same
    decision ids by the stricter rule the list of decisions uses (an unreadable approval names none); `lots` maps a funding lot's
    operation id (the lot id, or the part before a `#`) to the positions in `state.lots`."""

    runs: Mapping[str, tuple[tuple[int, LoggedRun], ...]]
    runs_by_op_id: Mapping[str, tuple[tuple[int, LoggedRun], ...]]
    approvals: Mapping[str, tuple[ApprovalRecord, ...]]
    approval_payloads: Mapping[str, dict[str, Any]]
    approval_candidates: tuple[str, ...]
    facts: Mapping[str, tuple[DecisionFactRecord, ...]]
    verdicts: Mapping[str, tuple[Verdict, ...]]
    commitments: Mapping[str, tuple[Commitment, ...]]
    promised: Mapping[str, tuple[PromiseLike, ...]]
    lots_state: FinancialState | None
    lots: Mapping[str, tuple[int, ...]]

    @classmethod
    def of(
        cls, *, log: Sequence[LoggedRun], approvals: Sequence[ApprovalRecord], commitments: Sequence[Commitment],
        facts: Sequence[DecisionFactRecord], verdicts: Sequence[Verdict], promised: Sequence[PromiseLike],
        state: FinancialState | None = None,
    ) -> RecordIndex:
        runs: dict[str, list[tuple[int, LoggedRun]]] = {}
        by_op: dict[str, list[tuple[int, LoggedRun]]] = {}
        for pos, e in enumerate(log):
            did = decision_id_for(e.payload, e.idempotency_key, commitments, approval_id=e.result.approval_id)
            if did is not None:
                runs.setdefault(did, []).append((pos, e))
            op_id = e.payload.get("op_id")
            if isinstance(op_id, str):
                by_op.setdefault(op_id, []).append((pos, e))
        grouped: dict[str, list[ApprovalRecord]] = {}
        payloads: dict[str, dict[str, Any]] = {}
        candidates: dict[str, None] = {}
        for a in approvals:
            payload = _payload_of(a)
            payloads[a.id] = payload
            key = payload.get("idempotency_key")
            did = decision_id_for(payload, key if isinstance(key, str) else "", commitments, approval_id=a.id)
            if did is not None:
                grouped.setdefault(did, []).append(a)
            if _readable_payload(a) and did is not None:
                candidates[did] = None
        by_fact: dict[str, list[DecisionFactRecord]] = {}
        for r in sorted(facts, key=lambda r: r.seq):
            by_fact.setdefault(r.decision_id, []).append(r)
        by_offer_verdict: dict[str, list[Verdict]] = {}
        for v in verdicts:
            by_offer_verdict.setdefault(v.offer_id, []).append(v)
        by_offer_commitment: dict[str, list[Commitment]] = {}
        for c in commitments:
            by_offer_commitment.setdefault(c.offer_id, []).append(c)
        by_commitment: dict[str, list[PromiseLike]] = {}
        for p in promised:
            by_commitment.setdefault(p.commitment_id, []).append(p)
        lots: dict[str, list[int]] = {}
        if state is not None:
            for position, lot in enumerate(state.lots):
                for op_id in _lot_op_ids(lot.id):
                    lots.setdefault(op_id, []).append(position)
        return cls(
            runs={k: tuple(v) for k, v in runs.items()}, runs_by_op_id={k: tuple(v) for k, v in by_op.items()},
            approvals={k: tuple(v) for k, v in grouped.items()}, approval_payloads=payloads,
            approval_candidates=tuple(candidates), facts={k: tuple(v) for k, v in by_fact.items()},
            verdicts={k: tuple(v) for k, v in by_offer_verdict.items()},
            commitments={k: tuple(v) for k, v in by_offer_commitment.items()},
            promised={k: tuple(v) for k, v in by_commitment.items()}, lots_state=state,
            lots={k: tuple(v) for k, v in lots.items()},
        )

    @classmethod
    def for_inputs(cls, i: DecisionInputs) -> RecordIndex:
        return cls.of(log=i.log, approvals=i.approvals, commitments=i.commitments, facts=i.facts, verdicts=i.verdicts,
                      promised=i.promised, state=i.state)


def _lot_op_ids(lot_id: str) -> list[str]:
    """The operation ids a funding lot belongs to: its own id, and each prefix before a `#` (the lot of operation X is X or X#n)."""
    ids = [lot_id]
    cut = lot_id.find("#")
    while cut != -1:
        ids.append(lot_id[:cut])
        cut = lot_id.find("#", cut + 1)
    return ids


def _index_of(i: DecisionInputs) -> RecordIndex:
    return i.index if i.index is not None else RecordIndex.for_inputs(i)



# ---------------------------------------------------------------- what comes out


@dataclass(frozen=True, slots=True)
class OpState:
    """One operation of the decision and its last non-duplicate result."""

    op_id: str
    kind: str
    status: OperationStatus
    seq: int
    day: int | None
    approval_id: str | None
    facility_id: str | None
    receivable_id: str | None
    amount_fen: int | None


@dataclass(frozen=True, slots=True)
class Residual:
    """The reserve still at risk after a cure ran (read now, labelled as today's position)."""

    shortfall_fen: int | None
    starts_day: int | None
    committed_cure: bool | None
    alert_id: str
    quoted_to_restore: bool | None  # the quote's flag; None when the quote projected nothing


@dataclass(frozen=True, slots=True)
class DecisionState:
    decision_id: str
    family: str  # DEAL | FUNDING
    state: DealState | FundingState
    terminal: bool
    residual: Residual | None
    ops: tuple[OpState, ...]
    approvals: tuple[ApprovalRecord, ...]  # the decision's approvals, oldest first
    approval: ApprovalRecord | None  # DEAL: the one whose operation records the agreement
    offer: CompiledOffer | None
    verdict: Verdict | None
    commitment: Commitment | None
    evaluated: EvaluatedFact | None
    sent: SentFact | None
    quote: QuotedFact | None
    lots: tuple[FundingLot, ...]  # lots the decision's operations created
    opened_day: int | None
    updated_day: int | None
    updated_seq: int
    # DEAL: the agreement was recorded by the owner's own acceptance of the buyer's terms as asked (an AcceptOffer the owner requested), so
    # nothing was sent to the buyer and no simulated reply exists.
    accepted_as_asked: bool = False
    # DEAL: the latest offer the owner sent outside FLOW (OFFERED), and the request the buyer answered it with (REPLIED), when there are.
    offered: OfferedFact | None = None
    replied: RepliedFact | None = None
    # DEAL: the agreement is the buyer's yes to an offer sent outside FLOW, recorded by the owner (a BUYER_ACCEPTED fact names it)
    buyer_accepted: bool = False


@dataclass(frozen=True, slots=True)
class Waiting:
    code: WaitCode
    party: Party
    day: int | None
    ref: str | None = None  # the lender's facility id, or the buyer's counterparty id, for the server to name


# ---------------------------------------------------------------- reading the inputs


def _payload_of(approval: ApprovalRecord) -> dict[str, Any]:
    try:
        data = json.loads(approval.op_json)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _readable_payload(approval: ApprovalRecord) -> bool:
    """Whether the approval's queued operation is a JSON object (the list of decisions names no decision for one that is not)."""
    try:
        return isinstance(json.loads(approval.op_json), dict)
    except ValueError:
        return False


def _is_decide_attempt(run: LoggedRun) -> bool:
    return _DECIDE_ATTEMPT in run.idempotency_key


def _facts(i: DecisionInputs) -> list[tuple[DecisionFactRecord, Any]]:
    out = []
    for r in _index_of(i).facts.get(i.decision_id, ()):
        fact = parse_fact(r)
        if fact is not None:
            out.append((r, fact))
    return out


def _approval_members(i: DecisionInputs) -> list[ApprovalRecord]:
    return list(_index_of(i).approvals.get(i.decision_id, ()))


def _run_members(i: DecisionInputs, extra_op_ids: frozenset[str]) -> list[LoggedRun]:
    idx = _index_of(i)
    found = dict(idx.runs.get(i.decision_id, ()))
    for op_id in extra_op_ids:
        found.update(idx.runs_by_op_id.get(op_id, ()))
    return [found[pos] for pos in sorted(found)]


def _op_states(runs: Sequence[LoggedRun]) -> list[OpState]:
    """Each operation's last non-duplicate result, in the order the operations first appeared. A non-owner attempt to
    decide an approval is not a result of the operation."""
    last: dict[str, LoggedRun] = {}
    order: list[str] = []
    for e in runs:
        if _is_decide_attempt(e) or e.result.status == OperationStatus.DUPLICATE:
            continue
        op_id = str(e.payload.get("op_id") or e.result.op_id)
        if op_id not in last:
            order.append(op_id)
        last[op_id] = e
    out = []
    for op_id in order:
        e = last[op_id]
        p = e.payload
        out.append(OpState(
            op_id=op_id, kind=e.kind, status=e.result.status, seq=e.seq, day=e.day,
            approval_id=e.result.approval_id, facility_id=_str(p.get("facility_id")),
            receivable_id=_str(p.get("receivable_id")), amount_fen=_int(p.get("amount_fen", p.get("advance_fen"))),
        ))
    return out


def _str(v: object) -> str | None:
    return v if isinstance(v, str) else None


def _int(v: object) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _lots_of(state: FinancialState | None, op_ids: Sequence[str], idx: RecordIndex | None = None) -> tuple[FundingLot, ...]:
    """The lots the operations created, in the books' order. With the request's index (built on these same books) this is a lookup per
    operation id and not a scan of every lot."""
    if state is None:
        return ()
    if idx is not None and idx.lots_state is state:
        positions = sorted({pos for op_id in op_ids for pos in idx.lots.get(op_id, ())})
        return tuple(state.lots[pos] for pos in positions)
    return tuple(
        lot for lot in state.lots if any(lot.id == op_id or lot.id.startswith(op_id + "#") for op_id in op_ids)
    )


def _reserve_alert(i: DecisionInputs) -> AlertLike | None:
    return next((a for a in i.alerts if a.kind == RESERVE_ALERT), None)


# ---------------------------------------------------------------- DEAL


def owner_declined(runs: Sequence[LoggedRun]) -> bool:
    """Whether the owner declined the offer: a RejectOffer the owner requested ran (EXECUTED) among the decision's runs. A rejection the agent
    made (the chat's) is not the owner's decision and does not close the offer."""
    return any(e.kind == "REJECT_OFFER" and e.result.status == OperationStatus.EXECUTED and e.payload.get("requested_by") == "OWNER"
               and not _is_decide_attempt(e) for e in runs)


def _matches_accept(payload: Mapping[str, Any], c: Commitment) -> bool:
    kind = payload.get("kind")
    if kind == "RECORD_COMMITMENT":
        return payload.get("commitment_id") == c.id
    if kind == "ACCEPT_OFFER":
        return (payload.get("offer_id") == c.offer_id and payload.get("offer_version") == c.offer_version
                and payload.get("nonce") == c.nonce)
    return False


def _derive_deal(i: DecisionInputs) -> DecisionState:
    offer_id = offer_id_of(i.decision_id)
    offers = [o for o in i.offers if o.offer_id == offer_id]
    offer = max(offers, key=lambda o: o.version) if offers else None
    idx = _index_of(i)
    verdicts = list(idx.verdicts.get(offer_id or "", ()))
    verdict = verdicts[-1] if verdicts else None
    facts = _facts(i)
    sents = [f for _, f in facts if isinstance(f, SentFact)]
    latest_sent = sents[-1] if sents else None
    offers_sent = [f for _, f in facts if isinstance(f, OfferedFact)]
    # the offer stays open until the latest day any counter sent outside FLOW is open (two counters may be out at once): that one is the
    # deal's offer, so the state, what it waits for and the day it closes are read from one fact
    latest_offered = max(reversed(offers_sent), key=lambda f: f.valid_until_day) if offers_sent else None
    replied = next((f for _, f in reversed(facts) if isinstance(f, RepliedFact)), None)
    open_until = latest_offered.valid_until_day if latest_offered is not None else None
    accepted_ids = {f.commitment_id for _, f in facts if isinstance(f, BuyerAcceptedFact)}
    mine = list(idx.commitments.get(offer_id or "", ()))
    commitment = next((c for c in mine if latest_sent is not None and c.id == latest_sent.commitment_id), None)
    if commitment is None and mine:
        commitment = mine[-1]
    if commitment is not None:  # the agreement is the state: the verdict it was made from, not a later one (a re-read after the invoice changed)
        verdict = next((v for v in verdicts if v.id == commitment.verdict_id), verdict)
    evaluated = next((f for _, f in reversed(facts) if isinstance(f, EvaluatedFact) and (verdict is None or f.verdict_id == verdict.id)), None)
    extra = frozenset(
        op_id for f in sents for op_id in ([*f.funding_op_ids, *([f.accept_op_id] if f.accept_op_id else [])])
    )
    runs = _run_members(i, extra)
    ops = _op_states(runs)
    approvals = _approval_members(i)
    approval: ApprovalRecord | None = None
    accept_run: OpState | None = None
    if commitment is not None:
        approval = next((a for a in reversed(approvals) if _matches_accept(idx.approval_payloads.get(a.id) or _payload_of(a), commitment)), None)
        accept_ops = [o for o in ops if _matches_accept(_op_payload(runs, o.op_id), commitment)]
        accept_run = accept_ops[-1] if accept_ops else None
    sent_for_verdict = next((f for f in reversed(sents) if verdict is not None and f.verdict_id == verdict.id), None)
    promised = list(idx.promised.get(commitment.id, ())) if commitment is not None else []
    buyer_yes = commitment is not None and commitment.id in accepted_ids
    by_owner = commitment is not None and not buyer_yes and any(
        _matches_accept(e.payload, commitment) and e.payload.get("requested_by") == "OWNER" for e in runs)

    state = _deal_state(offer, verdict, commitment, approval, accept_run, sent_for_verdict, promised, owner_declined(runs),
                        offered_until=open_until, replied=replied is not None, today=i.today)
    terminal = state in _DEAL_TERMINAL and not (
        state == DealState.MISSED and commitment is not None and commitment.status != CommitmentStatus.EXPIRED
    )
    funding_ops = [o for o in ops if o.kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "REPAY_FACILITY")]
    updated_day, updated_seq, opened = _stamps(i, runs, approvals, [r for r, _ in facts], offer)
    return DecisionState(
        decision_id=i.decision_id, family="DEAL", state=state, terminal=terminal, residual=None, ops=tuple(ops),
        approvals=tuple(approvals), approval=approval, offer=offer, verdict=verdict, commitment=commitment,
        evaluated=evaluated, sent=latest_sent, quote=None, lots=_lots_of(i.state, [o.op_id for o in funding_ops], idx),
        opened_day=opened, updated_day=updated_day, updated_seq=updated_seq, accepted_as_asked=by_owner, offered=latest_offered,
        replied=replied, buyer_accepted=buyer_yes,
    )


_DEAL_TERMINAL = frozenset({
    DealState.REVOKED, DealState.FULFILLED, DealState.MISSED, DealState.EXPIRED, DealState.DECLINED, DealState.FAILED,
    DealState.NO_DEAL, DealState.REPLIED,
})


def _op_payload(runs: Sequence[LoggedRun], op_id: str) -> Mapping[str, Any]:
    return next((e.payload for e in runs if e.payload.get("op_id") == op_id), {})


def _deal_state(
    offer: CompiledOffer | None, verdict: Verdict | None, c: Commitment | None, a: ApprovalRecord | None,
    x: OpState | None, sent_for_verdict: SentFact | None, promised: Sequence[PromiseLike], declined: bool = False, *,
    offered_until: int | None = None, replied: bool = False, today: int | None = None,
) -> DealState:
    if c is not None:
        if c.status == CommitmentStatus.REVOKED:  # 1
            return DealState.REVOKED
        if c.status == CommitmentStatus.FULFILLED:  # 2
            return DealState.FULFILLED
        if c.status == CommitmentStatus.EXPIRED and c.lapsed_obligations:  # 3
            return DealState.MISSED
        live = c.status in (CommitmentStatus.ACTIVE, CommitmentStatus.ACCEPTED)  # ACCEPTED is ACTIVE's transient twin
        if live and any(p.status == "LAPSED" for p in promised):  # 4
            return DealState.MISSED
        if live:  # 5
            return DealState.AGREED
        if c.status == CommitmentStatus.EXPIRED:  # 6
            return DealState.EXPIRED
    if declined:  # 6a: the owner declined the offer outright (RejectOffer); nothing moved, and it is closed
        return DealState.DECLINED
    if a is not None and a.status == ApprovalStatus.PENDING:  # 7
        return DealState.AUTHORIZATION_REQUIRED
    if a is not None and a.status == ApprovalStatus.REJECTED:  # 8
        return DealState.DECLINED
    if x is not None and x.status == OperationStatus.REFUSED:  # 9
        return DealState.FAILED
    if replied:  # 9a: the buyer answered the offer sent outside FLOW with terms of their own, now a request of its own
        return DealState.REPLIED
    if offered_until is not None:  # 9b: an offer sent outside FLOW is open until its day; unanswered after it, there is no deal
        return DealState.AWAITING_BUYER if today is None or today <= offered_until else DealState.NO_DEAL
    if sent_for_verdict is not None and sent_for_verdict.outcome == "NO_DEAL":  # 10
        return DealState.NO_DEAL
    if (offer is not None and offer.status in (CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES)) or (
        verdict is not None and verdict.outcome == Outcome.NO_VERDICT
    ):  # 11
        return DealState.NEEDS_CLARIFICATION
    if verdict is not None:  # 12
        return DealState.RESPONSE_READY
    return DealState.RECEIVED  # 13


# ---------------------------------------------------------------- FUNDING


def _derive_funding(i: DecisionInputs) -> DecisionState:
    facts = _facts(i)
    quote = next((f for _, f in reversed(facts) if isinstance(f, QuotedFact)), None)
    runs = _run_members(i, frozenset())
    ops = _op_states(runs)
    approvals = _approval_members(i)
    lots = _lots_of(i.state, [o.op_id for o in ops], _index_of(i))
    state = _funding_state(ops, approvals, quote, lots)
    residual = _residual(i, state, quote)
    terminal = state in (FundingState.DECLINED, FundingState.FAILED, FundingState.SETTLED, FundingState.EXECUTED)
    if residual is not None:
        terminal = False
    updated_day, updated_seq, opened = _stamps(i, runs, approvals, [r for r, _ in facts], None)
    return DecisionState(
        decision_id=i.decision_id, family="FUNDING", state=state, terminal=terminal, residual=residual, ops=tuple(ops),
        approvals=tuple(approvals), approval=None, offer=None, verdict=None, commitment=None, evaluated=None, sent=None,
        quote=quote, lots=lots, opened_day=opened, updated_day=updated_day, updated_seq=updated_seq,
    )


def _funding_state(
    ops: Sequence[OpState], approvals: Sequence[ApprovalRecord], quote: QuotedFact | None, lots: Sequence[FundingLot]
) -> FundingState:
    executed = [o for o in ops if o.status == OperationStatus.EXECUTED]
    refused = [o for o in ops if o.status == OperationStatus.REFUSED]
    if any(a.status == ApprovalStatus.PENDING for a in approvals):  # 1
        return FundingState.AUTHORIZATION_REQUIRED
    if not executed and any(a.status == ApprovalStatus.REJECTED for a in approvals):  # 2
        return FundingState.DECLINED
    if not executed and (refused or not ops):  # 3 (a quote with no operation logged at all: nothing ran)
        return FundingState.FAILED
    fewer = quote is not None and len(ops) < len(quote.legs)
    if refused or fewer or len(executed) < len(ops):  # 4
        return FundingState.PARTIALLY_EXECUTED
    if any(not lot.settled for lot in lots):  # 5
        return FundingState.SETTLEMENT_PENDING
    return FundingState.SETTLED if lots else FundingState.EXECUTED  # 6, 7


def attaches(alert: AlertLike, quote: QuotedFact) -> bool:
    """Whether today's open reserve alert is this record's to carry. It is when it is the alert the record quoted (the same breach
    still open), or when the engine says nothing fixes it (`committed_cure` false: no committed funding restores the reserve), so
    that what is left is the owner's to decide. A later, unrelated breach that a committed cure covers belongs to the next step
    the home shows, not to an old record."""
    return alert.id == quote.alert_id or alert.committed_cure is False


def _residual(i: DecisionInputs, state: FundingState, quote: QuotedFact | None) -> Residual | None:
    """Set on the newest reserve-breach record in states 4 to 7 while a reserve alert that is its own (`attaches`) is open today.
    (ADR-0011 also lets `restores_reserve` false alone set it; with no open alert there is no current shortfall to show, so none
    is set.)"""
    if not i.newest_reserve or quote is None or quote.alert_kind != RESERVE_ALERT:
        return None
    if state not in (FundingState.PARTIALLY_EXECUTED, FundingState.SETTLEMENT_PENDING, FundingState.SETTLED,
                     FundingState.EXECUTED):
        return None
    alert = _reserve_alert(i)
    if alert is None or not attaches(alert, quote):
        return None
    return Residual(shortfall_fen=alert.amount_fen, starts_day=alert.day, committed_cure=alert.committed_cure,
                    alert_id=alert.id, quoted_to_restore=quote.restores_reserve)


def _stamps(
    i: DecisionInputs, runs: Sequence[LoggedRun], approvals: Sequence[ApprovalRecord],
    facts: Sequence[DecisionFactRecord], offer: CompiledOffer | None,
) -> tuple[int | None, int, int | None]:
    days: list[int] = [d for d in (e.day for e in runs) if d is not None]
    days += [a.decided_day for a in approvals if a.decided_day is not None]
    days += [f.day for f in facts]
    opened = list(days)
    if offer is not None:
        days.append(offer.received_day)
        opened.append(offer.received_day)
    seq = max((e.seq for e in runs), default=0)
    return (max(days) if days else None, seq, min(opened) if opened else None)


def derive(inputs: DecisionInputs) -> DecisionState:
    """The decision's state from the stored records alone. First matching rule of the family's table wins."""
    if inputs.index is None:
        inputs = replace(inputs, index=RecordIndex.for_inputs(inputs))
    if family_of(inputs.decision_id) == "DEAL":
        return _derive_deal(inputs)
    return _derive_funding(inputs)


def index_inputs(inputs: Sequence[DecisionInputs]) -> list[DecisionInputs]:
    """The inputs, each with the shared `RecordIndex` of the records it holds. Inputs that hold the very same record tuples (one request
    reads the stores once and hands every decision the same ones) share one index, built once."""
    built: dict[tuple[int, ...], RecordIndex] = {}
    out: list[DecisionInputs] = []
    for i in inputs:
        if i.index is None:
            key = (id(i.log), id(i.approvals), id(i.commitments), id(i.facts), id(i.verdicts), id(i.promised), id(i.state))
            if key not in built:
                built[key] = RecordIndex.for_inputs(i)
            i = replace(i, index=built[key])
        out.append(i)
    return out


def derive_all(inputs: Sequence[DecisionInputs]) -> list[DecisionState]:
    """Derive many decisions. The residual belongs to the newest reserve-breach funding record only, so a first pass finds
    which one that is (by last event day, then log seq) and the second derives it with the residual. The log, the approvals and the
    other records are indexed once for all of them (`index_inputs`)."""
    indexed = index_inputs(inputs)
    first = [derive(replace(i, newest_reserve=False)) for i in indexed]
    newest = newest_reserve_decision(first, _reserve_alert(indexed[0]) if indexed else None)
    return [derive(replace(i, newest_reserve=i.decision_id == newest)) for i in indexed]


def newest_reserve_decision(states: Sequence[DecisionState], alert: AlertLike | None = None) -> str | None:
    """The newest FUNDING record that quoted a reserve-breach cure, is in state 4 to 7 (partly executed to executed) and, when
    today's open reserve `alert` is given, is the record that alert is attached to (`attaches`)."""
    candidates = [
        s for s in states
        if s.family == "FUNDING" and s.quote is not None and s.quote.alert_kind == RESERVE_ALERT
        and s.state in (FundingState.PARTIALLY_EXECUTED, FundingState.SETTLEMENT_PENDING, FundingState.SETTLED,
                        FundingState.EXECUTED)
        and (alert is None or attaches(alert, s.quote))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.updated_day if s.updated_day is not None else -1, s.updated_seq)).decision_id


# ---------------------------------------------------------------- what the decision is waiting for


def _receivable(state: FinancialState | None, rid: str) -> Receivable | None:
    return next((r for r in state.receivables if r.id == rid), None) if state is not None else None


def _earliest(days: Sequence[int | None]) -> int | None:
    known = [d for d in days if d is not None]
    return min(known) if known else None


def _agreed_wait(s: DecisionState, i: DecisionInputs) -> Waiting | None:
    c = s.commitment
    assert c is not None
    awaited = [p for p in _index_of(i).promised.get(c.id, ()) if p.status == "AWAITED"]
    if awaited:
        return Waiting(WaitCode.BANK_RECEIPT, Party.BUYER, _earliest([p.promised_day for p in awaited]), c.counterparty_id)
    st = i.state
    if st is not None:
        mine = [a for a in st.invoice_adjustments if a.commitment_id == c.id]
        if mine:
            days = [r.next_issue_day for r in st.recurring_invoices if r.counterparty_id in {a.counterparty_id for a in mine}]
            return Waiting(WaitCode.INVOICE_ISSUE, Party.BOOKS, _earliest(days), c.counterparty_id)
        carrying = [r for r in st.receivables
                    if any(x.startswith(f"{c.id}:") for x in r.applied) and r.status in ("OPEN", "FINANCED")
                    and r.outstanding_fen > 0]
        if carrying:
            return Waiting(WaitCode.BANK_RECEIPT, Party.BUYER, _earliest([r.due_day for r in carrying]), c.counterparty_id)
    return None


def _missed_wait(s: DecisionState, i: DecisionInputs) -> Waiting:
    c = s.commitment
    assert c is not None
    rids = [p.receivable_id for p in _index_of(i).promised.get(c.id, ()) if p.status == "LAPSED"]
    if not rids:  # the clock ended the agreement: its lapsed obligations name the invoices
        rids = [o.base.receivable_id for o in c.obligations
                if o.id in c.lapsed_obligations and o.base.receivable_id is not None]
    days = [r.due_day for r in (_receivable(i.state, rid) for rid in rids) if r is not None]
    return Waiting(WaitCode.BANK_RECEIPT, Party.BUYER, _earliest(days), c.counterparty_id)


def _settlement_wait(s: DecisionState) -> Waiting | None:
    unsettled = [lot for lot in s.lots if not lot.settled]
    if not unsettled:
        return None
    last = max(unsettled, key=lambda lot: lot.arrival_day)
    return Waiting(WaitCode.FUNDING_SETTLEMENT, Party.LENDER, last.arrival_day, last.facility_id)


def waiting_for(state: DecisionState, inputs: DecisionInputs) -> Waiting:
    """What FLOW is waiting for, by the ADR's table; the first row that applies wins."""
    if inputs.index is None:
        inputs = replace(inputs, index=RecordIndex.for_inputs(inputs))
    st = state.state
    if st in (DealState.RECEIVED, DealState.RESPONSE_READY):
        return Waiting(WaitCode.OWNER_RESPONSE, Party.OWNER, None)
    if st == DealState.NEEDS_CLARIFICATION:
        return Waiting(WaitCode.BUYER_CLARIFICATION, Party.BUYER, None,
                       state.offer.counterparty_id if state.offer is not None else None)
    if st == DealState.AWAITING_BUYER:
        return Waiting(WaitCode.BUYER_ANSWER, Party.BUYER, state.offered.valid_until_day if state.offered is not None else None,
                       state.offer.counterparty_id if state.offer is not None else None)
    if st == FundingState.AUTHORIZATION_REQUIRED:  # the same value in both families
        if state.family == "DEAL":
            return Waiting(WaitCode.OWNER_APPROVAL, Party.OWNER,
                           state.commitment.expires_day if state.commitment is not None else None)
        return Waiting(WaitCode.OWNER_APPROVAL, Party.OWNER, state.quote.alert_day if state.quote is not None else None)
    if st == DealState.AGREED and state.commitment is not None:
        agreed = _agreed_wait(state, inputs)
        if agreed is not None:
            return agreed
    if st == DealState.MISSED and state.commitment is not None:
        return _missed_wait(state, inputs)
    if st == FundingState.SETTLEMENT_PENDING or (state.family == "DEAL" and st in (DealState.AGREED, DealState.NO_DEAL)):
        waiting = _settlement_wait(state)
        if waiting is not None:
            return waiting
    if st == FundingState.PARTIALLY_EXECUTED or state.residual is not None:
        return Waiting(WaitCode.OWNER_DECISION, Party.OWNER,
                       state.residual.starts_day if state.residual is not None else _alert_day(inputs))
    return Waiting(WaitCode.NOTHING, Party.NONE, None)


def _alert_day(i: DecisionInputs) -> int | None:
    alert = _reserve_alert(i)
    return alert.day if alert is not None else None


__all__ = [
    "RESERVE_ALERT",
    "AlertLike",
    "DealState",
    "DecisionInputs",
    "DecisionState",
    "FundingState",
    "LoggedRun",
    "OpState",
    "Party",
    "PromiseLike",
    "RecordIndex",
    "Residual",
    "WaitCode",
    "Waiting",
    "attaches",
    "derive",
    "derive_all",
    "index_inputs",
    "newest_reserve_decision",
    "owner_declined",
    "waiting_for",
]
