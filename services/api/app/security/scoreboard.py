"""The security scoreboard, computed from stored rows: the operations log, security events, commitments,
verdicts and the egress detector. Nothing here is a literal; /audit reports what these functions find.

Pure functions over a `LedgerStore`: they read, they never write (no security event is recorded and
nothing is logged).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.alerts.ledger import entries
from app.domain.models import (
    AcceptOffer,
    Actor,
    Commitment,
    CounterOffer,
    CounterProposal,
    DrawFacility,
    OperationStatus,
    RecordCommitment,
    RepayFacility,
    SecurityEvent,
    SecurityEventKind,
    SubmitInvoiceForFinancing,
    Verdict,
)
from app.domain.ports import LedgerStore
from app.egress import AllowedValue, ProtectedSet, allowed_for_counter, scan
from app.operations import security_summary
from app.persistence import ApprovalStatus

UNKNOWN_RECIPIENT = "UNKNOWN-RECIPIENT"  # owns nothing, so every protected value counts against the text

_SOURCE_KINDS = frozenset({SecurityEventKind.INJECTION, SecurityEventKind.UNKNOWN_COUNTERPARTY,
                           SecurityEventKind.DATA_EXTRACTION, SecurityEventKind.UNEVIDENCED_CLAIM})

AllowFor = Callable[[CounterProposal], list[AllowedValue]]


@dataclass(frozen=True, slots=True)
class OutboundText:
    """One text the system recorded as sent (or sendable) to a counterparty."""

    source: str  # "verdict:<verdict id>:<counter id>" or "log:<seq>"
    recipient_id: str
    text: str
    allow: tuple[AllowedValue, ...]


def facilities_added_by_non_owner(store: LedgerStore) -> int:
    """Executed AddFacility operations not requested by the owner (the security summary's count)."""
    return int(security_summary(store).get("facilities_added_by_non_owner", 0))


# ------------------------------------------------------------------------------------------ money


def _commitment_for(op: AcceptOffer | RecordCommitment, commitments: list[Commitment]) -> Commitment | None:
    if isinstance(op, RecordCommitment):
        return next((c for c in commitments if c.id == op.commitment_id), None)
    return next((c for c in reversed(commitments)
                 if c.offer_id == op.offer_id and c.offer_version == op.offer_version and c.nonce == op.nonce), None)


def _flagged_turns(events: Iterable[SecurityEvent]) -> list[tuple[str, int]]:
    """(session id, turn) of each /nl turn a source event was raised in (its trace id is "<session>:<turn>")."""
    out: list[tuple[str, int]] = []
    for e in events:
        sid, _, turn = (e.trace_id or "").rpartition(":")
        if sid and turn.isdigit():
            out.append((sid, int(turn)))
    return out


def _same_turn(op: Any, turns: list[tuple[str, int]]) -> bool:
    """Was `op` sent by a flagged /nl turn? /nl keys an operation "nl:<session>:t<turn>:<n>:<kind>", or
    "nl:<session>:r:<request_id>:<n>:<kind>" when the request carries a request_id; that form does not say
    which turn it belongs to, so every request-keyed operation of a flagged session counts (an over-count)."""
    key = str(getattr(op, "idempotency_key", ""))
    return any(key.startswith((f"nl:{sid}:t{turn}:", f"nl:{sid}:r:")) for sid, turn in turns)


def money_moved_by_untrusted_fen(store: LedgerStore) -> int:
    """Fen moved by EXECUTED operations that the owner did not authorise and that were caused by flagged
    (untrusted) content.

    Flagged content is a security event of kind INJECTION, UNKNOWN_COUNTERPARTY, DATA_EXTRACTION or
    UNEVIDENCED_CLAIM (events the executor raises when it refuses an operation, such as TIER3, name the
    facility's own lender, not a sender, so they do not count). An EXECUTED operation counts only when it
    was not requested by the authenticated owner, was not approved in the owner queue, and is tied to such an
    event in one of three ways:

    1. it was sent in the same /nl turn as the event (the event's trace id names the session and turn and
       /nl derives each operation's idempotency key from them);
    2. its source verdict, or the commitment it accepts or records, belongs to an offer whose documents are
       referenced by the spans of an event (the flagged text is what the verdict was reached on);
    3. it draws, repays or finances on a facility whose lender is named by an UNKNOWN_COUNTERPARTY event.

    Draws, repayments and invoice-financing submissions add their logged amount; ACCEPT_OFFER /
    RECORD_COMMITMENT add the commitment's forward value. An event with neither a trace id nor spans cannot be
    tied to anything narrower than its party, so it falls back to the party-wide rule: every such operation
    that involves the named counterparty (as lender of the facility, or as the commitment's counterparty,
    dated on or after the event) counts. So an INJECTION event raised because the OWNER pasted buyer text
    carrying an approval cue (detail "quoted text contained an approval instruction"; it carries a trace id)
    names a buyer but flags that /nl turn only: it does not make the buyer's later, separately executed Tier-1
    operations count as money moved by untrusted content.
    """
    events = [e for e in store.security_events() if e.counterparty_id and e.kind in _SOURCE_KINDS]
    if not events:
        return 0
    turns = _flagged_turns(events)
    span_docs = {sp.doc_id for e in events for sp in e.spans}
    unattributed: dict[str, list[int]] = {}  # counterparty -> event days, for events that carry no trace or spans
    for e in events:
        if not e.spans and not _flagged_turns([e]) and e.counterparty_id:
            unattributed.setdefault(e.counterparty_id, []).append(e.day)
    unknown_lenders = {e.counterparty_id for e in events if e.kind == SecurityEventKind.UNKNOWN_COUNTERPARTY}
    owner_approved = {a.op_id for a in store.approvals(ApprovalStatus.APPROVED)}
    lenders = {f.id: f.lender_id for f in store.get_state().facilities}
    commitments = store.commitments()

    def flagged_verdict(verdict_id: str | None) -> bool:
        verdict = store.get_verdict(verdict_id) if verdict_id else None
        offer = store.get_offer(verdict.offer_id) if verdict is not None else None
        return offer is not None and bool(span_docs & set(offer.doc_ids))

    total = 0
    for entry in entries(store):
        if entry.result.status != OperationStatus.EXECUTED or entry.op is None:
            continue
        op = entry.op
        if op.requested_by == Actor.OWNER or op.op_id in owner_approved:
            continue
        linked = _same_turn(op, turns) or flagged_verdict(getattr(op, "source_verdict_id", None))
        if isinstance(op, DrawFacility | RepayFacility | SubmitInvoiceForFinancing):
            lender = lenders.get(op.facility_id)
            if linked or lender in unknown_lenders or lender in unattributed:
                total += abs(op.advance_fen if isinstance(op, SubmitInvoiceForFinancing) else op.amount_fen)
        elif isinstance(op, AcceptOffer | RecordCommitment):
            c = _commitment_for(op, commitments)
            if c is None:
                continue
            days = unattributed.get(c.counterparty_id, [])
            day = entry.day
            if linked or flagged_verdict(c.verdict_id) or (days and (day is None or any(d <= day for d in days))):
                total += abs(c.forward_value_fen)
    return total


# ------------------------------------------------------------------------------------- disclosure


def _recipient(store: LedgerStore, offer_id: str) -> str:
    offer = store.get_offer(offer_id)
    return offer.counterparty_id if offer is not None else UNKNOWN_RECIPIENT


def outbound_texts(store: LedgerStore, verdict_ids: Iterable[str] = (), *,
                   allow_for: AllowFor = allowed_for_counter) -> list[OutboundText]:
    """Every outbound text the store holds.

    Counter texts of every verdict the store holds (`LedgerStore.verdicts()`; `verdict_ids` is kept for
    compatibility and only adds ids the store lists anyway), and the message of each executed COUNTER_OFFER
    in the log. Each carries its recipient (the offer's counterparty) and its counter's own allowed values
    (`allow_for`). Nothing depends on what a caller could see or remembers.
    """
    entry_list = entries(store)
    out: list[OutboundText] = []
    counters: dict[tuple[str, str], CounterProposal] = {}
    stored: dict[str, Verdict] = {v.id: v for v in store.verdicts()}
    for vid in verdict_ids:
        if vid not in stored and (extra := store.get_verdict(vid)) is not None:
            stored[vid] = extra
    for v in stored.values():
        recipient = _recipient(store, v.offer_id)
        for c in v.counters:
            counters[(v.id, c.id)] = c
            out.append(OutboundText(f"verdict:{v.id}:{c.id}", recipient, c.text, tuple(allow_for(c))))
    for e in entry_list:
        op: Any = e.op
        if not isinstance(op, CounterOffer) or e.result.status != OperationStatus.EXECUTED or not e.result.message:
            continue
        counter = counters.get((op.source_verdict_id or "", op.counter_id))
        allow = tuple(allow_for(counter)) if counter is not None else ()
        out.append(OutboundText(f"log:{e.seq}", _recipient(store, op.offer_id), e.result.message, allow))
    return out


def disclosed_fields(store: LedgerStore, texts: Iterable[OutboundText]) -> list[str]:
    """Labels of protected fields whose values appear in an outbound text.

    Each text is scanned with the egress detector against the protected set built from the current
    state and mandate, for its own recipient and with only its counter's own figures allowed. The
    scan records nothing. Sorted and de-duplicated.
    """
    items = list(texts)
    if not items:
        return []
    pset = ProtectedSet.build(store.get_state(), store.get_mandate())
    found: set[str] = set()
    for t in items:
        found.update(leak.label for leak in scan(t.text, pset, recipient_id=t.recipient_id, allow=t.allow))
    return sorted(found)


def scoreboard(store: LedgerStore, verdict_ids: Iterable[str] = (), *,
               allow_for: AllowFor = allowed_for_counter) -> dict[str, Any]:
    """The computed headline numbers and the basis they were computed from."""
    texts = outbound_texts(store, verdict_ids, allow_for=allow_for)
    return {
        "computed": True,
        "money_moved_fen": money_moved_by_untrusted_fen(store),
        "disclosed_fields": disclosed_fields(store, texts),
        "outbound_texts_scanned": len(texts),
        "operations_scanned": len(store.operations()),
    }
