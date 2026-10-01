"""The security scoreboard, computed from stored rows: the operations log, security events, commitments,
verdicts and the egress detector. Nothing here is a literal; /audit reports what these functions find.

Pure functions over a `LedgerStore`: they read, they never write (no security event is recorded and
nothing is logged).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.alerts.ledger import Entry, entries
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
    SecurityEventKind,
    SubmitInvoiceForFinancing,
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


def money_moved_by_untrusted_fen(store: LedgerStore) -> int:
    """Fen moved by EXECUTED operations that the owner did not authorise and that involve a party a
    security event names as a source of untrusted content.

    A party is named by an INJECTION, UNKNOWN_COUNTERPARTY, DATA_EXTRACTION or UNEVIDENCED_CLAIM event
    (events the executor raises when it refuses an operation, such as TIER3, name the facility's own
    lender, not a sender, so they do not count). Draws, invoice-financing submissions and repayments
    add their logged amount when the facility's lender is named; ACCEPT_OFFER / RECORD_COMMITMENT add
    the commitment's forward value when its counterparty is named by an event dated on or before the
    operation. Operations requested by the authenticated owner or approved in the owner queue never
    count. This is simpler than also requiring the offer to carry a flag on the same documents, and it
    can only over-count relative to that.
    """
    event_days: dict[str, list[int]] = {}
    for e in store.security_events():
        if e.counterparty_id and e.kind in _SOURCE_KINDS:
            event_days.setdefault(e.counterparty_id, []).append(e.day)
    if not event_days:
        return 0
    owner_approved = {a.op_id for a in store.approvals(ApprovalStatus.APPROVED)}
    lenders = {f.id: f.lender_id for f in store.get_state().facilities}
    commitments = store.commitments()
    total = 0
    for entry in entries(store):
        if entry.result.status != OperationStatus.EXECUTED or entry.op is None:
            continue
        op = entry.op
        if op.requested_by == Actor.OWNER or op.op_id in owner_approved:
            continue
        if isinstance(op, DrawFacility | RepayFacility):
            if lenders.get(op.facility_id) in event_days:
                total += abs(op.amount_fen)
        elif isinstance(op, SubmitInvoiceForFinancing):
            if lenders.get(op.facility_id) in event_days:
                total += abs(op.advance_fen)
        elif isinstance(op, AcceptOffer | RecordCommitment):
            c = _commitment_for(op, commitments)
            if c is None or c.counterparty_id not in event_days:
                continue
            day = entry.day
            if day is None or any(d <= day for d in event_days[c.counterparty_id]):
                total += abs(c.forward_value_fen)
    return total


# ------------------------------------------------------------------------------------- disclosure


def _verdict_ids(store: LedgerStore, entry_list: list[Entry], extra: Iterable[str]) -> list[str]:
    ids: dict[str, None] = dict.fromkeys(extra)
    for e in entry_list:
        vid = getattr(e.op, "source_verdict_id", None)
        if isinstance(vid, str):
            ids.setdefault(vid)
    for c in store.commitments():
        ids.setdefault(c.verdict_id)
    return list(ids)


def _recipient(store: LedgerStore, offer_id: str) -> str:
    offer = store.get_offer(offer_id)
    return offer.counterparty_id if offer is not None else UNKNOWN_RECIPIENT


def outbound_texts(store: LedgerStore, verdict_ids: Iterable[str] = (), *,
                   allow_for: AllowFor = allowed_for_counter) -> list[OutboundText]:
    """Every outbound text the store holds.

    Counter texts of the verdicts that the log, the commitments or `verdict_ids` name, and the
    message of each executed COUNTER_OFFER in the log. Each carries its recipient (the offer's
    counterparty) and its counter's own allowed values (`allow_for`). The store port cannot list
    verdicts, so the caller passes the ones it knows (the runtime's latest per offer).
    """
    entry_list = entries(store)
    out: list[OutboundText] = []
    counters: dict[tuple[str, str], CounterProposal] = {}
    for vid in _verdict_ids(store, entry_list, verdict_ids):
        v = store.get_verdict(vid)
        if v is None:
            continue
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
